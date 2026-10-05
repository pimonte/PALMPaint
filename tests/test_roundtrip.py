"""
Round-trip tests for GridModel.

A round trip sends the model through an operation and back, then checks that
nothing was lost:

    save -> load               (SaveModel / LoadModel)
    undo snapshot -> restore   (export_state / from_state)
    add border -> crop         (padded / cropped)

Run all tests:      python -m pytest
Run one file:       python -m pytest tests/test_roundtrip.py
Run one test:       python -m pytest tests/test_roundtrip.py::test_save_load_keeps_all_layers
Show print output:  python -m pytest -s
"""

import numpy as np
import pytest

import base.surface_config as surface_config
from base.create_sd import SaveModel
from base.geo_reference import default_georeference
from base.gridmodel import GridModel
from base.load_sd import LoadModel

INT_FILL = GridModel.INT_FILL

# Layers that must always exist. Only used to check that layers_2d() works.
# The round trips compare every layer layers_2d() finds, including new ones.
KNOWN_LAYERS_2D = {
    "zt",
    "vegetation_type",
    "soil_type",
    "pavement_type",
    "street_type",
    "water_type",
    "building_id",
    "building_height",
    "building_type",
    "irrigation_flag",
    "shf",
    "ssws",
}

# Layers deliberately not tested: parked features, not part of 1.0.
# They stay empty in make_model() and are skipped in the comparison, because
# comparing two empty layers would always pass without testing anything.
NOT_TESTED = {"irrigation_flag", "shf", "ssws"}

# Cell positions (row, col) used by the example model and the tree tests.
PAVEMENT_CELL = (1, 1)
WATER_CELL = (2, 2)
BUILDING_CELL = (5, 5)
TREE_CELL = (7, 2)
NEW_TREE_CELL = (2, 9)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
# builds test data
def make_model(nx=12, ny=10, res=2.0):
    """A small model where every layer holds at least one non-fill value."""
    model = GridModel(nx, ny, res, res, surface_config.SURFACE_CONFIG)
    model.zt[:] = 4.0

    r, c = PAVEMENT_CELL
    model.set_pixel(r, c, vegetation_type=INT_FILL, pavement_type=1, soil_type=1, street_type=3)

    r, c = WATER_CELL
    model.set_pixel(r, c, vegetation_type=INT_FILL, soil_type=INT_FILL, water_type=2)
    model.water_pars[0, r, c] = 290.0

    r, c = BUILDING_CELL
    model.set_pixel(r, c, vegetation_type=INT_FILL, soil_type=INT_FILL,
                    building_id=7, building_height=10.0, building_type=2)
    model.building_pars["building_albedo_type"][..., r, c] = 36.0  # PALM: building wall standard
    return model

# examine and check results
def layers_2d(model):
    """Names of all 2D layers: every attribute that is an array of shape (ny, nx).

    Found automatically, so a newly added layer is compared without
    anyone having to update a list.
    """
    return sorted(
        name for name, value in vars(model).items()
        if isinstance(value, np.ndarray) and value.shape == (model.ny, model.nx)
    )


def assert_same_layers(expected, actual):
    """Fail with a readable message naming every layer that differs."""
    differing = [
        name for name in layers_2d(expected)
        if name not in NOT_TESTED
        and not np.array_equal(getattr(expected, name), getattr(actual, name))
    ]
    if not np.array_equal(expected.water_pars, actual.water_pars):
        differing.append("water_pars")
    for name in expected.building_pars:
        if not np.array_equal(expected.building_pars[name], actual.building_pars[name]):
            differing.append(name)
    assert differing == [], f"layers changed by the round trip: {differing}"


def lad_cells(model):
    """Set of (row, col) columns that contain leaf area density > 0."""
    lad = model.resolved_vegetation.get("lad")
    if lad is None:
        return set()
    _, rows, cols = np.nonzero(np.asarray(lad) > 0)
    return set(zip(rows.tolist(), cols.tolist()))

# shortcut for saving and loading a model
def save_and_load(model, path, georef=None):
    """Save like the app does, then load and return the loaded model."""
    if georef is None:
        georef = default_georeference()
    SaveModel(
        model, model.res, model.dz, georef.as_origin_tuple(), model.surface_config,
        str(path),
        tree_instances=model.tree_instances,
        resolved_vegetation=model.resolved_vegetation,
        georef=georef,
    )
    loaded, *_ = LoadModel(str(path), surface_config=model.surface_config)
    return loaded


# ---------------------------------------------------------------------------
# Fixtures: pytest calls these and passes the result to every test that names
# them as a parameter. Each test gets a fresh model.
# ---------------------------------------------------------------------------

@pytest.fixture
def model():
    return make_model()


@pytest.fixture
def model_with_tree():
    model = make_model()
    model.add_tree(*TREE_CELL, tree_height=10.0, crown_diameter=6.0)
    assert TREE_CELL in lad_cells(model)  # sanity check: the tree was placed
    return model


# ---------------------------------------------------------------------------
# Round trips
# ---------------------------------------------------------------------------

def test_layer_discovery_finds_known_layers(model):
    # Guards the guard: if layers_2d() found nothing, every round trip
    # below would pass without comparing anything.
    assert KNOWN_LAYERS_2D <= set(layers_2d(model))


def test_undo_snapshot_keeps_all_layers(model):
    restored = GridModel.from_state(model.export_state())
    assert_same_layers(model, restored)


def test_save_load_keeps_all_layers(model, tmp_path):
    # tmp_path is a built-in pytest fixture: a fresh temporary folder per test
    loaded = save_and_load(model, tmp_path / "driver.nc")
    assert_same_layers(model, loaded)


def test_save_without_surface_config_keeps_all_layers(model, tmp_path):
    # Scripts may call SaveModel without a surface_config. It crashed on the
    # water cell, and without defaults the water temperature would be lost.
    model.surface_config = None
    loaded = save_and_load(model, tmp_path / "driver.nc")
    assert_same_layers(model, loaded)


def test_pad_then_crop_keeps_all_layers(model):
    padded = model.padded(n_north=2, n_south=1, n_west=3, n_east=0)
    cropped = padded.cropped(col_start=3, row_start=1, new_nx=model.nx, new_ny=model.ny)
    assert_same_layers(model, cropped)


def test_border_sides_match_the_compass(model):
    # Row 0 is the southern edge (PALM's y index 0), column 0 the western edge.
    # North and east borders are appended, so the building keeps its index.
    padded = model.padded(n_north=2, n_south=0, n_west=0, n_east=3)
    assert padded.building_id[BUILDING_CELL] == 7
    # South and west borders come first, so the building moves by them
    padded = model.padded(n_north=0, n_south=2, n_west=3, n_east=0)
    r, c = BUILDING_CELL
    assert padded.building_id[r + 2, c + 3] == 7


# ---------------------------------------------------------------------------
# Trees
# ---------------------------------------------------------------------------

# parametrize runs the same test once per entry, each reported separately
@pytest.mark.parametrize("operation", ["pad", "crop"])
def test_border_and_crop_work_with_placed_trees(model_with_tree, operation):
    # Different offsets for rows and columns, so a row/column mix-up is caught
    if operation == "pad":
        # n_north differs from n_south, so a north / south mix-up is caught
        result = model_with_tree.padded(n_north=3, n_south=2, n_west=1, n_east=0)
        expected_cell = (TREE_CELL[0] + 2, TREE_CELL[1] + 1)
    else:
        result = model_with_tree.cropped(col_start=1, row_start=1, new_nx=10, new_ny=8)
        expected_cell = (TREE_CELL[0] - 1, TREE_CELL[1] - 1)
    # A tree is stored twice: as an editable record and as LAD voxels.
    # Both must move, because trees are rebuilt from the records later.
    assert len(result.tree_instances) == 1
    tree = result.tree_instances[0]
    assert (tree["row"], tree["col"]) == expected_cell, "tree record not moved"
    assert expected_cell in lad_cells(result)


@pytest.mark.parametrize("operation", ["pad", "crop"])
def test_loaded_trees_survive_border_or_crop_and_new_tree(model_with_tree, tmp_path, operation):
    loaded = save_and_load(model_with_tree, tmp_path / "driver.nc")
    # Pad adds one cell on every side, crop cuts one off the top and left.
    # Both trees stay inside the grid in either case.
    if operation == "pad":
        result = loaded.padded(n_north=1, n_south=1, n_west=1, n_east=1)
        shift = 1
    else:
        result = loaded.cropped(col_start=1, row_start=1, new_nx=10, new_ny=8)
        shift = -1
    old_tree = (TREE_CELL[0] + shift, TREE_CELL[1] + shift)
    new_tree = (NEW_TREE_CELL[0] + shift, NEW_TREE_CELL[1] + shift)

    result.add_tree(*new_tree, tree_height=10.0, crown_diameter=6.0)

    cells = lad_cells(result)
    assert new_tree in cells
    assert old_tree in cells, "the tree loaded from the file was wiped"


def test_new_tree_after_load_gets_unused_id(model_with_tree, tmp_path):
    loaded = save_and_load(model_with_tree, tmp_path / "driver.nc")
    loaded_ids = set(np.unique(loaded.resolved_vegetation["tree_id"])) - {0, -9999}

    result = loaded.add_tree(*NEW_TREE_CELL, tree_height=10.0, crown_diameter=6.0)

    assert result["tree_id"] not in loaded_ids
