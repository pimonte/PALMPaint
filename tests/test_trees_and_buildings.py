"""Tests for trees next to buildings.

PALM counts LAD in a building column from the roof, so leaves written from the
ground there would float above the roof by the building height. Like palm_csd
(overhanging_trees: False), PALMPaint allows no leaves in or above a building.
Bridge columns (buildings_3d only) are not building columns.
"""

import numpy as np

from test_roundtrip import TREE_CELL, make_model, save_and_load


def column_has_leaves(model, row, col):
    return bool(np.any(model.resolved_vegetation["lad"][:, row, col] > 0))


def test_no_tree_leaves_in_building_columns():
    model = make_model()
    row, col = TREE_CELL
    model.set_pixel(row, col + 1, building_id=1, building_height=4.0, building_type=2)

    model.add_tree(row, col, tree_height=10.0, crown_diameter=6.0)

    assert column_has_leaves(model, row, col)
    assert not column_has_leaves(model, row, col + 1)


def test_building_painted_under_a_crown_deletes_its_leaves(tmp_path):
    # Leaves loaded from a file, so the next tree rebuild cannot hide a miss
    model = make_model()
    model.add_tree(*TREE_CELL, tree_height=10.0, crown_diameter=6.0)
    loaded = save_and_load(model, tmp_path / "driver.nc")
    loaded.tree_instances = []
    row, col = TREE_CELL
    assert column_has_leaves(loaded, row, col + 1)

    loaded.set_pixel(row, col + 1, building_id=1, building_height=4.0, building_type=2)

    assert not column_has_leaves(loaded, row, col + 1)
    assert column_has_leaves(loaded, row, col)


def test_leaves_in_building_columns_are_removed_on_load(tmp_path):
    model = make_model()
    model.add_tree(*TREE_CELL, tree_height=10.0, crown_diameter=6.0)
    # A building written straight into the arrays, as another tool could leave it
    row, col = TREE_CELL
    model.building_height[row, col] = 4.0
    model.building_id[row, col] = 1
    model.building_type[row, col] = 2

    loaded = save_and_load(model, tmp_path / "driver.nc")

    assert loaded.resolved_vegetation["lad_removed_in_buildings"] == 1
    assert not column_has_leaves(loaded, row, col)
    assert column_has_leaves(loaded, row, col + 1)
