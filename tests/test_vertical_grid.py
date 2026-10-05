"""Tests for the vertical levels of resolved vegetation (zlad).

PALM requires zlad to equal its grid levels zu: 0 at the surface, then dz/2,
3 dz/2, ... (init_grid.f90), otherwise it stops with error PCM0010. Level
k >= 1 covers (k - 1) dz to k dz above the ground, level 0 is never read.
"""

import netCDF4
import numpy as np
import pytest

import base.surface_config as surface_config
from base.load_sd import LoadModel
from test_load import make_driver_with_palm_fill_values
from test_roundtrip import TREE_CELL, make_model, save_and_load


def palm_levels(nz, dz):
    """PALM's zu, written out here so the test does not reuse the code it checks."""
    return np.array([0.0] + [(k - 0.5) * dz for k in range(1, nz)])


def top_of_leaves(model, row, col):
    """Upper edge (m above ground) of the highest level with leaves in a column."""
    rv = model.resolved_vegetation
    top = np.nonzero(rv["lad"][:, row, col] > 0)[0].max()
    return rv["zlad"][top] + model.dz / 2


def test_new_tree_is_saved_on_palm_levels(tmp_path):
    model = make_model()
    model.add_tree(*TREE_CELL, tree_height=10.0, crown_diameter=6.0)
    loaded = save_and_load(model, tmp_path / "driver.nc")
    rv = loaded.resolved_vegetation

    np.testing.assert_allclose(rv["zlad"], palm_levels(len(rv["zlad"]), loaded.dz))
    assert not np.any(rv["lad"][0] > 0), "PALM never reads level 0"
    assert top_of_leaves(loaded, *TREE_CELL) == pytest.approx(10.0)


def test_tree_on_palm_driver_ends_at_tree_height(tmp_path):
    # A driver with PALM's own zlad, as palm_csd writes it
    path = tmp_path / "palm_style.nc"
    make_driver_with_palm_fill_values(path)
    model, *_ = LoadModel(str(path), surface_config=surface_config.SURFACE_CONFIG)
    assert not model.resolved_vegetation["zlad_repaired"]

    model.add_tree(0, 0, tree_height=6.0, crown_diameter=1.0)

    zlad = model.resolved_vegetation["zlad"]
    np.testing.assert_allclose(zlad, palm_levels(len(zlad), model.dz))
    assert top_of_leaves(model, 0, 0) == pytest.approx(6.0)


def make_driver_with_old_palmpaint_zlad(path):
    """A tiny driver as PALMPaint before 0.5.6 saved it: zlad = dz/2, 3 dz/2, ... (dz = 2)."""
    with netCDF4.Dataset(path, "w") as nc_file:
        nc_file.createDimension("x", 4)
        nc_file.createDimension("y", 3)
        nc_file.createDimension("zlad", 3)
        nc_file.createVariable("x", "f4", ("x",))[:] = [1.0, 3.0, 5.0, 7.0]
        nc_file.createVariable("y", "f4", ("y",))[:] = [1.0, 3.0, 5.0]
        nc_file.createVariable("zlad", "f4", ("zlad",))[:] = [1.0, 3.0, 5.0]
        nc_file.createVariable("zt", "f4", ("y", "x"))[:] = 0.0
        lad = nc_file.createVariable("lad", "f4", ("zlad", "y", "x"), fill_value=-9999.0)
        lad[:, 2, 3] = [0.1, 0.2, 0.3]   # leaves from 0 to 6 m


def test_old_palmpaint_zlad_is_repaired_on_load(tmp_path):
    path = tmp_path / "old_palmpaint.nc"
    make_driver_with_old_palmpaint_zlad(path)

    model, *_ = LoadModel(str(path), surface_config=surface_config.SURFACE_CONFIG)
    rv = model.resolved_vegetation

    assert rv["zlad_repaired"]
    np.testing.assert_allclose(rv["zlad"], [0.0, 1.0, 3.0, 5.0])
    # same leaves, each layer on the PALM level that covers its height
    np.testing.assert_allclose(rv["lad"][:, 2, 3], [0.0, 0.1, 0.2, 0.3])
