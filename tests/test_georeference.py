"""Tests for reading the georeference (origin and CRS) of a static driver.

PALM takes the four origin attributes as they are: origin_lat / origin_lon set
the Coriolis force and the sun position, origin_x / origin_y the output
coordinates. PALMPaint must not recalculate any of them on load or save.
"""

import netCDF4
import pytest

import base.surface_config as surface_config
from base.geo_reference import (
    georeference_as_given,
    projected_to_latlon,
    shifted_georeference,
    unknown_crs_georeference,
)
from base.load_sd import LoadModel
from test_roundtrip import save_and_load

ORIGIN_KEYS = ("origin_lat", "origin_lon", "origin_x", "origin_y")

# Origins of real drivers in example_sds/, none of them has a crs variable.
# x / y match lat / lon in UTM zone 32 (promet_test_01)
CONSISTENT_UTM = (52.23612440809281, 9.467193840872879, 531904.0, 5787404.0)
# x / y look like UTM zone 33, but lie 23 km away from lat / lon (rans_tkee)
INCONSISTENT_UTM = (52.50965, 13.313899, 370961.0, 5800926.0)
# x / y are Swiss LV03 coordinates (palmpy yv-bre-1)
SWISS_LV03 = (46.727, 6.563, 533068.0, 175458.0)
# x / y match lat / lon in WGS 84 / UTM zone 33N (cut_cell_topography)
WGS84_UTM33 = (50.104210191678945, 14.385449690858314, 456052.4, 5550398.2)

# crs variables as other tools write them, PALMPaint must not change them
CRS_WGS84_UTM33 = {
    "long_name": "coordinate reference system",
    "grid_mapping_name": "transverse_mercator",
    "semi_major_axis": 6378137.0,
    "inverse_flattening": 298.257223563,
    "longitude_of_prime_meridian": 0.0,
    "longitude_of_central_meridian": 15.0,
    "latitude_of_projection_origin": 0.0,
    "scale_factor_at_central_meridian": 0.9996,
    "false_easting": 500000.0,
    "false_northing": 0.0,
    "units": "m",
    "epsg_code": "EPSG:32633",
}
# LV03 is not UTM: PALMPaint cannot convert it, only keep it
CRS_SWISS_LV03 = {
    "long_name": "coordinate reference system",
    "grid_mapping_name": "oblique_mercator",
    "epsg_code": "EPSG:21781",
    "units": "m",
}


def make_driver(path, origin, crs=None):
    """A tiny driver with the four origin attributes and an optional crs variable."""
    with netCDF4.Dataset(path, "w") as nc_file:
        nc_file.createDimension("x", 4)
        nc_file.createDimension("y", 3)
        nc_file.createVariable("x", "f4", ("x",))[:] = [5.0, 15.0, 25.0, 35.0]
        nc_file.createVariable("y", "f4", ("y",))[:] = [5.0, 15.0, 25.0]
        nc_file.createVariable("zt", "f4", ("y", "x"))[:] = 0.0
        for key, value in zip(ORIGIN_KEYS, origin):
            setattr(nc_file, key, value)
        if crs is not None:
            crs_var = nc_file.createVariable("crs", "i4")
            for name, value in crs.items():
                setattr(crs_var, name, value)


def read_origin(path):
    with netCDF4.Dataset(path) as nc_file:
        return tuple(float(getattr(nc_file, key)) for key in ORIGIN_KEYS)


@pytest.mark.parametrize(
    "origin, expected_epsg",
    [
        (CONSISTENT_UTM, 25832),  # CRS can be inferred from lat / lon
        (INCONSISTENT_UTM, None),  # CRS stays unknown
        (SWISS_LV03, None),
    ],
)
def test_origin_is_kept_on_load(tmp_path, origin, expected_epsg):
    path = tmp_path / "driver.nc"
    make_driver(path, origin)
    *_, georef = LoadModel(str(path), surface_config=surface_config.SURFACE_CONFIG)

    assert georef.as_origin_tuple() == pytest.approx(origin, abs=1e-9)
    assert georef.epsg_code == expected_epsg


def test_unknown_crs_is_not_invented_on_save(tmp_path):
    source = tmp_path / "driver.nc"
    make_driver(source, SWISS_LV03)
    model, *_, georef = LoadModel(str(source), surface_config=surface_config.SURFACE_CONFIG)

    saved = tmp_path / "saved.nc"
    save_and_load(model, saved, georef=georef)

    assert read_origin(saved) == pytest.approx(SWISS_LV03, abs=1e-9)
    with netCDF4.Dataset(saved) as nc_file:
        assert "crs" not in nc_file.variables
        assert "lat" not in nc_file.variables
        assert not hasattr(nc_file.variables["zt"], "grid_mapping")


@pytest.mark.parametrize(
    "origin, crs",
    [(WGS84_UTM33, CRS_WGS84_UTM33), (SWISS_LV03, CRS_SWISS_LV03)],
)
def test_crs_variable_is_kept_on_save(tmp_path, origin, crs):
    source = tmp_path / "driver.nc"
    make_driver(source, origin, crs)
    model, *_, georef = LoadModel(str(source), surface_config=surface_config.SURFACE_CONFIG)

    saved = tmp_path / "saved.nc"
    save_and_load(model, saved, georef=georef)

    assert read_origin(saved) == pytest.approx(origin, abs=1e-9)
    with netCDF4.Dataset(saved) as nc_file:
        crs_var = nc_file.variables["crs"]
        assert {name: crs_var.getncattr(name) for name in crs_var.ncattrs()} == crs


def test_border_and_crop_move_the_origin():
    # Add Border with 3 cells west and 2 south at 10 m: the corner moves 30 m / 20 m
    georef = georeference_as_given(*CONSISTENT_UTM, epsg_code=25832)
    moved, warning = shifted_georeference(georef, dx=-30.0, dy=-20.0)

    assert warning is None
    assert (moved.origin_x, moved.origin_y) == (531874.0, 5787384.0)
    lon, lat = projected_to_latlon(moved.origin_x, moved.origin_y, 25832)
    # 1e-6 deg is about 0.1 m, lat / lon are shifted, not recalculated
    assert (moved.origin_lat, moved.origin_lon) == pytest.approx((lat, lon), abs=1e-6)


def test_origin_move_without_utm_keeps_lat_lon_and_warns():
    georef = unknown_crs_georeference(*SWISS_LV03)
    moved, warning = shifted_georeference(georef, dx=64.0, dy=32.0)

    assert (moved.origin_x, moved.origin_y) == (533132.0, 175490.0)
    assert (moved.origin_lat, moved.origin_lon) == (SWISS_LV03[0], SWISS_LV03[1])
    assert warning is not None
