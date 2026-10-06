"""Tests for loading drivers: unsupported variables, foreign fill values, 2D tree_id."""

import netCDF4
import numpy as np

import base.surface_config as surface_config
from base.load_sd import LoadModel, find_unsupported_variables
from test_roundtrip import make_model, save_and_load


def test_only_foreign_variables_are_reported(tmp_path):
    path = tmp_path / "driver.nc"
    save_and_load(make_model(), path)
    with netCDF4.Dataset(path, "a") as nc_file:
        nc_file.createVariable("surface_fraction", "f4", ("y", "x"))
    assert find_unsupported_variables(str(path)) == ["surface_fraction"]


def make_driver_with_palm_fill_values(path):
    """A tiny driver written like PALM's own test cases: float fill value -9999.9.

    PALMPaint uses -9999.0. Cells holding the file's fill value are empty and
    must stay empty after load and save.
    """
    with netCDF4.Dataset(path, "w") as nc_file:
        nc_file.createDimension("x", 4)
        nc_file.createDimension("y", 3)
        nc_file.createDimension("zlad", 2)
        nc_file.createVariable("x", "f4", ("x",))[:] = [0.5, 1.5, 2.5, 3.5]
        nc_file.createVariable("y", "f4", ("y",))[:] = [0.5, 1.5, 2.5]
        nc_file.createVariable("zlad", "f4", ("zlad",))[:] = [0.0, 0.5]
        nc_file.createVariable("zt", "f4", ("y", "x"))[:] = 0.0

        # one building in cell (1, 1), all other cells empty
        height = nc_file.createVariable("buildings_2d", "f4", ("y", "x"), fill_value=-9999.9)
        height[1, 1] = 10.0
        bid = nc_file.createVariable("building_id", "i4", ("y", "x"), fill_value=-9999)
        bid[1, 1] = 1
        btype = nc_file.createVariable("building_type", "i1", ("y", "x"), fill_value=-127)
        btype[1, 1] = 2

        # leaves in one column (2, 3), all other voxels empty
        lad = nc_file.createVariable("lad", "f4", ("zlad", "y", "x"), fill_value=-9999.9)
        lad[:, 2, 3] = 0.8


def count_empty(path, var_name):
    """Number of cells netCDF4 masks as fill value in a saved file."""
    with netCDF4.Dataset(path) as nc_file:
        return int(np.ma.count_masked(nc_file.variables[var_name][:]))


def test_foreign_fill_values_stay_empty_after_save(tmp_path):
    source = tmp_path / "palm_style.nc"
    make_driver_with_palm_fill_values(source)
    model, *_ = LoadModel(str(source), surface_config=surface_config.SURFACE_CONFIG)

    saved = tmp_path / "saved.nc"
    save_and_load(model, saved)

    assert count_empty(saved, "buildings_2d") == count_empty(source, "buildings_2d")
    assert count_empty(saved, "lad") == count_empty(source, "lad")


def make_driver_with_2d_tree_id(path, lad_dims=("zlad", "y", "x")):
    """A tiny driver like palmpy writes it: tree_id in 2D, one ID per column.

    Column (2, 3) has leaves and ID 7. Column (0, 0) has ID 9 but no leaves.
    """
    with netCDF4.Dataset(path, "w") as nc_file:
        nc_file.createDimension("x", 4)
        nc_file.createDimension("y", 3)
        nc_file.createDimension("zlad", 3)
        nc_file.createVariable("x", "f4", ("x",))[:] = [0.5, 1.5, 2.5, 3.5]
        nc_file.createVariable("y", "f4", ("y",))[:] = [0.5, 1.5, 2.5]
        nc_file.createVariable("zlad", "f4", ("zlad",))[:] = [0.0, 0.5, 1.5]
        nc_file.createVariable("zt", "f4", ("y", "x"))[:] = np.zeros((3, 4), np.float32)

        lad = np.full((3, 3, 4), -9999.0, np.float32)
        lad[1:, 2, 3] = 0.8
        if len(lad_dims) == 2:
            lad = lad[1]
        nc_file.createVariable("lad", "f4", lad_dims, fill_value=-9999.0)[:] = lad

        tree_id = np.full((3, 4), -9999, np.int32)
        tree_id[2, 3] = 7
        tree_id[0, 0] = 9
        nc_file.createVariable("tree_id", "i4", ("y", "x"), fill_value=-9999)[:] = tree_id


def test_2d_tree_id_is_kept_on_the_voxels_with_leaves(tmp_path):
    source = tmp_path / "palmpy_style.nc"
    make_driver_with_2d_tree_id(source)

    model, *_ = LoadModel(str(source), surface_config=surface_config.SURFACE_CONFIG)

    rv = model.resolved_vegetation
    assert rv["tree_id_from_2d"] == {"columns": 1, "without_leaves": 1}
    np.testing.assert_array_equal(rv["tree_id"][:, 2, 3], [0, 7, 7])
    assert not np.any(rv["tree_id"][:, 0, 0] > 0)

    saved = tmp_path / "saved.nc"
    save_and_load(model, saved)
    with netCDF4.Dataset(saved) as nc_file:
        assert nc_file.variables["tree_id"].dimensions == ("zlad", "y", "x")


def test_3d_variables_with_an_unexpected_shape_are_reported(tmp_path):
    source = tmp_path / "flat_lad.nc"
    make_driver_with_2d_tree_id(source, lad_dims=("y", "x"))

    model, *_ = LoadModel(str(source), surface_config=surface_config.SURFACE_CONFIG)

    # without lad, the 2D tree_id has no voxels to sit on and is reported too
    assert model.resolved_vegetation["unreadable_3d_variables"] == ["lad ('y', 'x')", "tree_id ('y', 'x')"]


def test_global_attributes_survive_save_border_crop_and_undo(tmp_path):
    # palmgeo and London drivers carry the attribution their data licenses
    # require in the global attribute "source"
    source = tmp_path / "with_attributes.nc"
    save_and_load(make_model(), source)
    with netCDF4.Dataset(source, "a") as nc_file:
        nc_file.source = "OpenStreetMap contributors (ODbL), Copernicus Sentinel-2"
        nc_file.title = "Hannover test"
        nc_file.licence = "ODbL"
        nc_file.origin_x = 1.0              # stale, the georeference wins on save
    model, *_ = LoadModel(str(source), surface_config=surface_config.SURFACE_CONFIG)

    from base.gridmodel import GridModel
    for name, changed in (
        ("save", model),
        ("border and crop", model.padded(1, 2, 3, 4).cropped(3, 2, model.nx, model.ny)),
        ("undo", GridModel.from_state(model.export_state())),
    ):
        saved = tmp_path / "saved.nc"
        save_and_load(changed, saved)
        with netCDF4.Dataset(saved) as nc_file:
            assert nc_file.source == "OpenStreetMap contributors (ODbL), Copernicus Sentinel-2", name
            assert nc_file.title == "Hannover test", name
            assert nc_file.licence == "ODbL", name
            assert nc_file.origin_x != 1.0, name
