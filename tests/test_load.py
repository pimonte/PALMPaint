"""Tests for the warning about variables PALMPaint does not support."""

import netCDF4

from base.load_sd import find_unsupported_variables
from test_roundtrip import make_model, save_and_load


def test_only_foreign_variables_are_reported(tmp_path):
    path = tmp_path / "driver.nc"
    save_and_load(make_model(), path)
    with netCDF4.Dataset(path, "a") as nc_file:
        nc_file.createVariable("surface_fraction", "f4", ("y", "x"))
    assert find_unsupported_variables(str(path)) == ["surface_fraction"]
