"""
Module to save grid data to a NetCDF file.
This file is meant to be used with the PALMPaint application.
    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""
import math
import netCDF4 as nc
from netCDF4 import Dataset
import numpy as np

from base.geo_reference import (
    add_grid_mapping,
    coordinate_attribute_names,
    ensure_georeference,
    write_georeference,
)
from base.gridmodel import GridModel


def _arrays_equal(left, right):
    if left is None or right is None:
        return False
    left_arr = np.asarray(left)
    right_arr = np.asarray(right)
    return left_arr.shape == right_arr.shape and np.array_equal(left_arr, right_arr)


def _row_blocks(ny, block_rows=128):
    block_rows = max(1, int(block_rows))
    for start in range(0, ny, block_rows):
        end = min(ny, start + block_rows)
        yield start, end


def _write_2d_variable(var, data, *, transform=None, block_rows=128):
    """Write a 2-D array in row blocks to avoid large temporary copies."""
    ny = data.shape[0]
    for start, end in _row_blocks(ny, block_rows=block_rows):
        block = data[start:end]
        if transform is not None:
            block = transform(block)
        var[start:end, :] = block


def _write_3d_variable(var, data, *, transform=None, block_rows=32):
    """Write a 3-D array in z/y blocks to avoid large temporary copies."""
    nz = data.shape[0]
    for iz in range(nz):
        layer = data[iz]
        for start, end in _row_blocks(layer.shape[0], block_rows=block_rows):
            block = layer[start:end]
            if transform is not None:
                block = transform(block)
            var[iz, start:end, :] = block


def _building_3d_iter(building_id_data, building_height_data, z_data, *, block_rows=64):
    """Yield buildings_3d slices without materializing the full 3-D volume."""
    footprint_mask = (building_id_data > 0) & (building_height_data > GridModel.FLOAT_FILL)
    clamped_heights = np.maximum(building_height_data, 0.0)
    for iz, z_val in enumerate(z_data):
        for start, end in _row_blocks(building_id_data.shape[0], block_rows=block_rows):
            block = (
                footprint_mask[start:end, :]
                & (z_val <= clamped_heights[start:end, :])
            ).astype(np.int8, copy=False)
            yield iz, start, end, block


def SaveModel(
    model,
    res,
    dz,
    ori,
    surface_config,
    filename="quicksave",
    tree_instances=None,
    resolved_vegetation=None,
    georef=None,
    export_buildings_3d=False,
):
        nx = int(model.nx)
        ny = int(model.ny)
        print("NX", nx)
        print("NY", ny)

        dx = dy = res
        vertical_dz = float(dz) if float(dz) > 0.0 else float(res)

        vegetation_data = model.vegetation_type
        soil_data = model.soil_type
        pavement_data = model.pavement_type
        water_data = model.water_type
        building_id_data = model.building_id
        building_height_data = model.building_height
        building_type_data = model.building_type
        height_data = model.zt
        water_pars_data = model.water_pars

        source_buildings_3d = None if resolved_vegetation is None else resolved_vegetation.get("source_buildings_3d")
        source_buildings_3d_z = None if resolved_vegetation is None else resolved_vegetation.get("source_buildings_3d_z")
        source_buildings_2d = None if resolved_vegetation is None else resolved_vegetation.get("source_buildings_2d")
        source_building_id = None if resolved_vegetation is None else resolved_vegetation.get("source_building_id")
        source_building_type = None if resolved_vegetation is None else resolved_vegetation.get("source_building_type")

        deleted_building_ids = []
        replaced_building_pixel_count = 0
        z_data = None
        reuse_source_buildings_3d = False

        print("SAVE NETCDF")
        print(f"Saving to {filename}...")

        georef = ensure_georeference(origin=ori, georef=georef)
        coordinates_attr = coordinate_attribute_names(georef)

        if export_buildings_3d and np.any(building_id_data > 0):
            if (
                source_buildings_3d is not None
                and source_buildings_3d_z is not None
                and _arrays_equal(building_height_data, source_buildings_2d)
                and _arrays_equal(building_id_data, source_building_id)
                and _arrays_equal(building_type_data, source_building_type)
            ):
                reuse_source_buildings_3d = True
                z_data = np.asarray(source_buildings_3d_z, dtype=np.float32)
            else:
                footprint_mask = (building_id_data > 0) & (building_height_data > GridModel.FLOAT_FILL)
                if np.any(footprint_mask):
                    z_max = float(np.max(np.maximum(building_height_data[footprint_mask], 0.0)))
                    z_levels = np.arange(0, math.ceil(z_max / vertical_dz) + 1, dtype=np.float32) * vertical_dz
                    if z_levels.size == 0:
                        z_levels = np.array([0.0], dtype=np.float32)
                    if z_levels.size > 1:
                        z_levels[1:] = z_levels[1:] - 0.5 * vertical_dz
                    z_data = z_levels.astype(np.float32, copy=False)

        with Dataset(filename, 'w', format='NETCDF4') as nc_file:
            nc_file.createDimension('x', nx)
            nc_file.createDimension('y', ny)
            if z_data is not None:
                nc_file.createDimension("z", len(z_data))
            if resolved_vegetation is not None and resolved_vegetation.get("zlad") is not None:
                zlad_data = resolved_vegetation["zlad"]
                nc_file.createDimension("zlad", len(zlad_data))
            else:
                zlad_data = None

            default_water_temps = None
            water_param_mask = water_data > GridModel.INT_FILL
            if np.any(water_param_mask):
                default_water_temps = np.full((ny, nx), np.nan, dtype=np.float32)
                for water_type_value, cfg in surface_config["water"]["types"].items():
                    default_water_temps[water_data == int(water_type_value)] = float(cfg["water_temperature"])
                current_water_temp = np.asarray(water_pars_data[0], dtype=np.float32)
                custom_water_mask = (
                    water_param_mask
                    & (current_water_temp > GridModel.FLOAT_FILL)
                    & np.isfinite(default_water_temps)
                    & (np.abs(current_water_temp - default_water_temps) > 1e-6)
                )
            else:
                custom_water_mask = np.zeros((ny, nx), dtype=bool)

            if np.any(custom_water_mask):
                nc_file.createDimension('nwater_pars', 7)

            x = nc_file.createVariable('x', 'f4', ('x',))
            x.long_name = 'distance to origin in x-direction'
            x.units = 'm'
            x.axis = 'X'
            x[:] = np.arange(0, nx * dx, dx) + 0.5 * dx

            y = nc_file.createVariable('y', 'f4', ('y',))
            y.long_name = 'distance to origin in y-direction'
            y.units = 'm'
            y.axis = 'Y'
            y[:] = np.arange(0, ny * dy, dy) + 0.5 * dy

            write_georeference(nc_file, nx, ny, dx, georef)

            if z_data is not None:
                z = nc_file.createVariable("z", "f4", ("z",))
                z.long_name = "z coordinate"
                z.units = "m"
                z.axis = "Z"
                z[:] = z_data

            nc_zt = nc_file.createVariable('zt', 'f4', ('y', 'x'), fill_value=-9999.0)
            nc_zt.long_name = 'terrain height'
            nc_zt.units = 'm'
            add_grid_mapping(nc_zt, coordinates_attr)
            _write_2d_variable(nc_zt, height_data)

            if np.any(soil_data > GridModel.INT_FILL):
                nc_soil_type = nc_file.createVariable('soil_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_soil_type.long_name = "soil type classification"
                nc_soil_type.units = "1"
                nc_soil_type.lod = np.int32(1)
                add_grid_mapping(nc_soil_type, coordinates_attr)
                _write_2d_variable(nc_soil_type, soil_data)

            if np.any(vegetation_data > GridModel.INT_FILL):
                nc_vegetation_type = nc_file.createVariable('vegetation_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_vegetation_type.long_name = "vegetation type classification"
                nc_vegetation_type.units = "1"
                add_grid_mapping(nc_vegetation_type, coordinates_attr)
                _write_2d_variable(nc_vegetation_type, vegetation_data)

            if np.any(pavement_data > GridModel.INT_FILL):
                nc_pavement_type = nc_file.createVariable('pavement_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_pavement_type.long_name = "pavement type classification"
                nc_pavement_type.units = "1"
                add_grid_mapping(nc_pavement_type, coordinates_attr)
                _write_2d_variable(nc_pavement_type, pavement_data)

            if np.any(water_data > GridModel.INT_FILL):
                nc_water_type = nc_file.createVariable('water_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_water_type.long_name = "water type classification"
                nc_water_type.units = "1"
                add_grid_mapping(nc_water_type, coordinates_attr)
                _write_2d_variable(nc_water_type, water_data)

            if np.any(building_height_data > GridModel.FLOAT_FILL) or np.any(building_id_data > 0):
                print("BUILDINGS detected (switch on USM Namelist in PALM)")

                nc_buildings_2d = nc_file.createVariable('buildings_2d', 'f4', ('y', 'x'), fill_value=-9999.0)
                nc_buildings_2d.long_name = "building height"
                nc_buildings_2d.units = "m"
                nc_buildings_2d.lod = np.int32(1)
                add_grid_mapping(nc_buildings_2d, coordinates_attr)
                _write_2d_variable(nc_buildings_2d, building_height_data)

                if np.any(building_id_data > 0):
                    nc_building_id = nc_file.createVariable('building_id', 'i4', ('y', 'x'), fill_value=GridModel.BUILDING_ID_FILL)
                    nc_building_id.long_name = "building ID"
                    nc_building_id.units = ""
                    add_grid_mapping(nc_building_id, coordinates_attr)
                    _write_2d_variable(
                        nc_building_id,
                        building_id_data,
                        transform=lambda block: np.where(block > 0, block, GridModel.BUILDING_ID_FILL),
                    )

                if np.any(building_type_data > GridModel.INT_FILL):
                    nc_building_type = nc_file.createVariable('building_type', 'i1', ('y', 'x'), fill_value=-127)
                    nc_building_type.long_name = "building type classification"
                    nc_building_type.units = "1"
                    add_grid_mapping(nc_building_type, coordinates_attr)
                    _write_2d_variable(nc_building_type, building_type_data)

                if z_data is not None:
                    nc_buildings_3d = nc_file.createVariable("buildings_3d", "i1", ("z", "y", "x"), fill_value=-127)
                    nc_buildings_3d.long_name = "building flag"
                    nc_buildings_3d.units = "1"
                    nc_buildings_3d.lod = np.int32(2)
                    add_grid_mapping(nc_buildings_3d, coordinates_attr)
                    if reuse_source_buildings_3d:
                        _write_3d_variable(nc_buildings_3d, source_buildings_3d)
                    else:
                        for iz, start, end, block in _building_3d_iter(building_id_data, building_height_data, z_data):
                            nc_buildings_3d[iz, start:end, :] = block

            if zlad_data is not None:
                nc_zlad = nc_file.createVariable("zlad", "f4", ("zlad",))
                nc_zlad.long_name = "z coordinate for resolved vegetation"
                nc_zlad.units = "m"
                nc_zlad[:] = zlad_data

            if resolved_vegetation is not None:
                lad_data = resolved_vegetation.get("lad")
                bad_data = resolved_vegetation.get("bad")
                tree_id_data = resolved_vegetation.get("tree_id")

                if lad_data is not None:
                    nc_lad = nc_file.createVariable("lad", "f4", ("zlad", "y", "x"), fill_value=-9999.0)
                    nc_lad.long_name = "leaf area density"
                    nc_lad.units = "m2 m-3"
                    add_grid_mapping(nc_lad, coordinates_attr)
                    _write_3d_variable(nc_lad, lad_data)

                if bad_data is not None:
                    nc_bad = nc_file.createVariable("bad", "f4", ("zlad", "y", "x"), fill_value=-9999.0)
                    nc_bad.long_name = "basal area density"
                    nc_bad.units = "m2 m-3"
                    add_grid_mapping(nc_bad, coordinates_attr)
                    _write_3d_variable(nc_bad, bad_data)

                if tree_id_data is not None:
                    nc_tree_id = nc_file.createVariable("tree_id", "i4", ("zlad", "y", "x"), fill_value=-9999)
                    nc_tree_id.long_name = "tree id"
                    nc_tree_id.units = ""
                    add_grid_mapping(nc_tree_id, coordinates_attr)
                    _write_3d_variable(nc_tree_id, tree_id_data)

            if np.any(custom_water_mask):
                nc_water_pars = nc_file.createVariable('water_pars', 'f4', ('nwater_pars', 'y', 'x'), fill_value=-9999.0)
                nc_water_pars.long_name = "grid point specific water parameters"
                nc_water_pars.units = "see nwater_pars index definition"
                add_grid_mapping(nc_water_pars, coordinates_attr)
                nc_water_pars[:, :, :] = nc_water_pars._FillValue
                for start, end in _row_blocks(ny, block_rows=128):
                    block_mask = custom_water_mask[start:end, :]
                    if not np.any(block_mask):
                        continue
                    block = np.full((7, end - start, nx), -9999.0, dtype=np.float32)
                    block[0, :, :][block_mask] = np.asarray(water_pars_data[0, start:end, :], dtype=np.float32)[block_mask]
                    nc_water_pars[:, start:end, :] = block

            nc_file.title = 'Idealized Scenario'
            nc_file.author = 'PALM User'
            nc_file.palmpaint_dz = vertical_dz

        print(f"NetCDF file saved: {filename}")
        return {
            "export_buildings_3d": bool(export_buildings_3d),
            "deleted_building_ids": deleted_building_ids,
            "deleted_building_count": len(deleted_building_ids),
            "replaced_building_pixel_count": replaced_building_pixel_count,
        }


def Save(
    data,
    res,
    dz,
    ori,
    surface_config,
    filename="quicksave",
    tree_instances=None,
    resolved_vegetation=None,
    georef=None,
    export_buildings_3d=False,
):
        rows = [key[0] for key in data.keys()]
        cols = [key[1] for key in data.keys()]
        ny = max(rows) + 1
        nx = max(cols) + 1
        model = GridModel.from_legacy_dict(data, nx, ny, res, dz, surface_config, quantize=False)
        return SaveModel(
            model,
            res,
            dz,
            ori,
            surface_config,
            filename,
            tree_instances=tree_instances,
            resolved_vegetation=resolved_vegetation,
            georef=georef,
            export_buildings_3d=export_buildings_3d,
        )
