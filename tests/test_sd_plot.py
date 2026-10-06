"""Tests for the cross-section in the analysis plots.

A mirrored or misplaced section still draws without any error, so these
bugs are silent. Model row 0 is the south edge, column 0 the west edge.
"""

import numpy as np

from base.gridmodel import GridModel
from base.sd_plot import cross_section_slices, lad_on_terrain


def make_section_model():
    """10 x 20 grid with one building at the south-west corner."""
    model = GridModel(10, 20, 2.0, 2.0)
    model.zt[:, :] = 0.0
    model.building_height[0, 0] = 10.0
    return model


def test_ns_section_starts_in_the_south():
    zt, bh, lad, col = cross_section_slices(make_section_model(), "N-S", 0)
    assert col == 0
    assert bh[0] == 10.0, "the south building must be the first value (left in the plot)"
    assert bh[-1] == GridModel.FLOAT_FILL


def test_we_section_slice_counts_from_the_south():
    zt, bh, lad, row = cross_section_slices(make_section_model(), "W-E", 0)
    assert row == 0
    assert bh[0] == 10.0, "slice 0 must be the southern row"


def test_lad_is_lifted_by_the_terrain():
    # One column on flat ground, one on a 5 m hill. Same tree in both.
    dz = 1.0
    zlad = np.array([0.0, 0.5, 1.5, 2.5])            # PALM levels, above ground
    lad = np.array([[0.0, 0.0], [0.2, 0.2], [0.4, 0.4], [0.0, 0.0]])
    zt = np.array([0.0, 5.0])

    lad_abs, dz_lad = lad_on_terrain(lad, zlad, zt, dz)

    assert dz_lad == 1.0
    assert lad_abs[0, 0] == 0.2 and lad_abs[1, 0] == 0.4   # flat: 0 to 2 m
    assert lad_abs[:5, 1].max() == 0.0, "no leaves inside the hill"
    assert lad_abs[5, 1] == 0.2 and lad_abs[6, 1] == 0.4   # hill: 5 to 7 m
