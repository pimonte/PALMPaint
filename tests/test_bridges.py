"""Tests for bridges: buildings that exist only in buildings_3d.

palm_csd and palmgeo write a bridge as building_id (and building_type) without
buildings_2d, and its voxels only in buildings_3d, above free space. PALMPaint
cannot paint such a building, so it must keep the file's buildings_3d column
as long as the 2D building data of that column is unchanged. A building_id
without any building voxel stops PALM with error DRV0034.
"""

import netCDF4
import numpy as np
import pytest

import base.surface_config as surface_config
from base.create_sd import SaveModel
from base.geo_reference import default_georeference
from base.load_sd import LoadModel

Z_LEVELS = [0.0, 0.5, 1.5, 2.5, 3.5]
HOUSE_CELL = (1, 1)  # a normal building, 3 m high
BRIDGE_ROW = 3
BRIDGE_COLS = [2, 3, 4, 5]
BRIDGE_COLUMN = [0, 0, 0, 1, 1]  # voxels at 2.5 m and 3.5 m, free space below


def make_driver_with_bridge(path):
    with netCDF4.Dataset(path, "w") as nc_file:
        nc_file.createDimension("x", 8)
        nc_file.createDimension("y", 6)
        nc_file.createDimension("z", len(Z_LEVELS))
        nc_file.createVariable("x", "f4", ("x",))[:] = np.arange(8) + 0.5
        nc_file.createVariable("y", "f4", ("y",))[:] = np.arange(6) + 0.5
        nc_file.createVariable("z", "f4", ("z",))[:] = Z_LEVELS
        nc_file.createVariable("zt", "f4", ("y", "x"))[:] = 0.0

        height = np.full((6, 8), -9999.0, dtype=np.float32)
        building_id = np.full((6, 8), -9999, dtype=np.int32)
        building_type = np.full((6, 8), -127, dtype=np.int8)
        buildings_3d = np.zeros((len(Z_LEVELS), 6, 8), dtype=np.int8)

        height[HOUSE_CELL] = 3.0
        building_id[HOUSE_CELL] = 1
        building_type[HOUSE_CELL] = 2
        buildings_3d[:4, HOUSE_CELL[0], HOUSE_CELL[1]] = 1  # 0 to 2.5 m

        for col in BRIDGE_COLS:  # no buildings_2d for the bridge
            building_id[BRIDGE_ROW, col] = 2
            building_type[BRIDGE_ROW, col] = 2
            buildings_3d[:, BRIDGE_ROW, col] = BRIDGE_COLUMN

        nc_file.createVariable("buildings_2d", "f4", ("y", "x"), fill_value=-9999.0)[:] = height
        nc_file.createVariable("building_id", "i4", ("y", "x"), fill_value=-9999)[:] = building_id
        nc_file.createVariable("building_type", "i1", ("y", "x"), fill_value=-127)[:] = building_type
        nc_file.createVariable("buildings_3d", "i1", ("z", "y", "x"), fill_value=-127)[:] = buildings_3d


def save_with_buildings_3d(model, path, export_buildings_3d=True):
    georef = default_georeference()
    return SaveModel(
        model, model.res, model.dz, georef.as_origin_tuple(), model.surface_config,
        str(path),
        resolved_vegetation=model.resolved_vegetation,
        georef=georef,
        export_buildings_3d=export_buildings_3d,
    )


@pytest.fixture
def loaded(tmp_path):
    path = tmp_path / "bridge.nc"
    make_driver_with_bridge(path)
    model, *_ = LoadModel(str(path), surface_config=surface_config.SURFACE_CONFIG)
    return model


# (row shift, column shift) of the bridge after each operation
OPERATIONS = {
    "edit elsewhere": (lambda m: m.building_height.__setitem__(HOUSE_CELL, 2.0) or m, (0, 0)),
    "add border": (lambda m: m.padded(n_north=1, n_south=2, n_west=3, n_east=0), (2, 3)),
    "crop": (lambda m: m.cropped(col_start=1, row_start=1, new_nx=7, new_ny=5), (-1, -1)),
    "filter sweep": (lambda m: m.apply_filter_sweep() and m, (0, 0)),
}


@pytest.mark.parametrize("operation", OPERATIONS)
def test_bridge_survives(loaded, tmp_path, operation):
    change, (dr, dc) = OPERATIONS[operation]
    model = change(loaded)
    saved = tmp_path / "saved.nc"
    save_with_buildings_3d(model, saved)

    with netCDF4.Dataset(saved) as nc_file:
        building_id = nc_file["building_id"][:].filled(-9999)
        buildings_3d = nc_file["buildings_3d"][:].filled(0)
    for col in BRIDGE_COLS:
        r, c = BRIDGE_ROW + dr, col + dc
        assert building_id[r, c] == 2, "bridge ID lost"
        assert list(buildings_3d[: len(BRIDGE_COLUMN), r, c]) == BRIDGE_COLUMN, "bridge voxels lost"


def test_edited_building_is_rebuilt_from_2d(loaded, tmp_path):
    loaded.building_height[HOUSE_CELL] = 1.0  # lower the house: 0 m and 0.5 m only
    saved = tmp_path / "saved.nc"
    save_with_buildings_3d(loaded, saved)

    with netCDF4.Dataset(saved) as nc_file:
        house = nc_file["buildings_3d"][:, HOUSE_CELL[0], HOUSE_CELL[1]].filled(0)
    assert list(house[:4]) == [1, 1, 0, 0]


def test_bridge_is_left_out_without_buildings_3d(loaded, tmp_path):
    # Without buildings_3d a bridge has no voxel at all. Its building_id must not
    # be written, otherwise PALM stops with DRV0034. The model keeps it.
    saved = tmp_path / "saved.nc"
    summary = save_with_buildings_3d(loaded, saved, export_buildings_3d=False)

    assert summary["left_out_3d_only_cells"] == len(BRIDGE_COLS)
    assert summary["building_id_without_building"] == 0
    with netCDF4.Dataset(saved) as nc_file:
        building_id = nc_file["building_id"][:].filled(-9999)
    assert all(building_id[BRIDGE_ROW, col] == -9999 for col in BRIDGE_COLS)
    assert all(loaded.building_id[BRIDGE_ROW, col] == 2 for col in BRIDGE_COLS)
