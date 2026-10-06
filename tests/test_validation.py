"""Tests for the validation: errors only where PALM itself stops.

The rules follow PALM's checks in netcdf_data_input_mod.f90 (DRV00xx). Drivers
from palm_csd and palmgeo that PALM accepts must not be reported as invalid,
and Clean Static Driver must not delete data that PALM accepts.
"""

import pytest

import base.surface_config as surface_config
from base.load_sd import LoadModel
from test_bridges import make_driver_with_bridge
from test_roundtrip import BUILDING_CELL, PAVEMENT_CELL, WATER_CELL, make_model


def allow_negative_terrain(model):
    model.zt[0, 0] = -3.0  # PALM subtracts the lowest terrain point


def allow_surface_on_building(model):
    # e.g. the ground under a bridge. Vegetation needs a soil_type everywhere (DRV0023)
    model.vegetation_type[BUILDING_CELL] = 3
    model.soil_type[BUILDING_CELL] = 2


def stray_soil(model):
    # PALM ignores soil under water and buildings: a note, not an error
    model.soil_type[BUILDING_CELL] = 2
    model.soil_type[WATER_CELL] = 2


@pytest.mark.parametrize(
    "change", [allow_negative_terrain, allow_surface_on_building, stray_soil]
)
def test_what_palm_accepts_is_valid(change):
    model = make_model()
    change(model)
    result = model.validate()
    assert result["valid"], result["violations"]


def building_without_type(model):
    model.building_type[BUILDING_CELL] = model.INT_FILL  # DRV0033


def building_without_id(model):
    model.building_id[BUILDING_CELL] = model.BUILDING_ID_FILL  # DRV0034


def terrain_with_fill_value(model):
    model.zt[PAVEMENT_CELL] = model.FLOAT_FILL  # zt must not contain fill values


@pytest.mark.parametrize(
    "change", [building_without_type, building_without_id, terrain_with_fill_value]
)
def test_what_palm_rejects_is_an_error(change):
    model = make_model()
    change(model)
    assert not model.validate()["valid"]


def test_bridge_needs_buildings_3d(tmp_path):
    path = tmp_path / "bridge.nc"
    make_driver_with_bridge(path)
    model, *_ = LoadModel(str(path), surface_config=surface_config.SURFACE_CONFIG)

    assert model.validate(export_buildings_3d=True)["valid"]
    # Without buildings_3d the bridge cannot be saved, its building_id would stop PALM
    assert not model.validate(export_buildings_3d=False)["valid"]


def test_stray_soil_is_a_note():
    model = make_model()
    stray_soil(model)
    assert len(model.validate()["notes"]) == 1


def test_clean_keeps_what_palm_accepts():
    model = make_model()
    allow_negative_terrain(model)
    allow_surface_on_building(model)  # ground under a bridge: vegetation and soil
    model.clean_static_driver()

    assert model.zt[0, 0] == -3.0
    assert model.vegetation_type[BUILDING_CELL] == 3
    assert model.soil_type[BUILDING_CELL] == 2


def test_clean_removes_soil_without_vegetation_or_pavement():
    model = make_model()
    stray_soil(model)
    model.clean_static_driver()

    assert model.soil_type[BUILDING_CELL] == model.INT_FILL
    assert model.soil_type[WATER_CELL] == model.INT_FILL
    assert model.soil_type[PAVEMENT_CELL] == 1  # real soil stays


def test_forest_roughness_too_large_for_the_grid_is_noted():
    # PALM stops with LSM0048 where z0 >= dz/4 (forest: z0 = 2 m)
    from base.gridmodel import GridModel
    import base.surface_config as surface_config

    def notes_for(dz, vegetation_type, own_z0=None):
        model = GridModel(6, 6, 2.0, dz, surface_config.SURFACE_CONFIG)
        model.vegetation_type[:, :] = vegetation_type
        model.soil_type[:, :] = 3
        if own_z0 is not None:
            model.vegetation_pars[4, :, :] = own_z0
        return [n for n in model.validate()["notes"] if "LSM0048" in n]

    assert notes_for(2.0, 4)                 # forest on a 2 m grid
    assert not notes_for(10.0, 4)            # 2 m < 10 m / 4
    assert not notes_for(2.0, 3)             # short grass, z0 = 0.03 m
    assert notes_for(2.0, 3, own_z0=0.8)     # own roughness length in vegetation_pars
