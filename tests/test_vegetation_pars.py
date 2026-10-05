"""Tests for vegetation_pars: per-cell overrides of the vegetation_type defaults.

palm_csd and palmgeo write the leaf area index (index 1) of every grass and
shrub cell there, palmpy the roughness length (index 4). The round trips in
test_roundtrip.py check that they survive save, undo, border and crop.
"""

import numpy as np
import pytest

from test_roundtrip import INT_FILL, VEGETATION_CELL, make_model


def lai(model):
    return float(model.vegetation_pars[1][VEGETATION_CELL])


def test_parameters_stay_with_the_vegetation_and_go_with_it():
    model = make_model()
    r, c = VEGETATION_CELL
    same_type = int(model.vegetation_type[r, c])

    model.set_pixel(r, c, zt=6.0)                          # terrain only
    model.set_pixel(r, c, vegetation_type=same_type)       # the same grass again
    assert lai(model) == pytest.approx(2.4)   # float32, as in the file

    model.set_pixel(r, c, vegetation_type=INT_FILL, pavement_type=1, soil_type=1)
    assert np.all(model.vegetation_pars[:, r, c] == model.FLOAT_FILL)


def test_another_vegetation_type_clears_the_parameters():
    model = make_model()
    r, c = VEGETATION_CELL
    other_type = int(model.vegetation_type[r, c]) % 18 + 1

    model.set_pixel(r, c, vegetation_type=other_type)

    assert lai(model) == model.FLOAT_FILL


def test_copy_and_paste_keeps_the_parameters():
    model = make_model()
    pixel = model.get_pixel(*VEGETATION_CELL)

    model.set_pixel(0, 0, **pixel)

    np.testing.assert_array_equal(model.vegetation_pars[:, 0, 0], model.vegetation_pars[(slice(None),) + VEGETATION_CELL])


def test_validation_follows_palm():
    model = make_model()
    # parameters left on a pavement cell: PALM ignores them (LSM0041)
    model.vegetation_pars[1, 1, 1] = 3.0
    # vegetation_type 0 is "user defined" and needs all 12 parameters (DRV0029)
    model.vegetation_type[0, 0] = 0
    model.vegetation_pars[:5, 0, 0] = 1.0

    result = model.validate()

    assert any("vegetation_pars but no vegetation" in note for note in result["notes"])
    assert any("DRV0029" in error for error in result["violations"])
    assert model.clean_static_driver()["vegetation_pars_cleared_outside_vegetation"] == 1
    assert model.vegetation_pars[1, 1, 1] == model.FLOAT_FILL
