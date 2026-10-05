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

from base.building_config import BUILDING_CONFIG
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


def _write_4d_variable(var, data, *, transform=None, block_rows=16):
    """Write a 4-D array in leading-dimension/z/y blocks."""
    for i0 in range(data.shape[0]):
        for i1 in range(data.shape[1]):
            layer = data[i0, i1]
            for start, end in _row_blocks(layer.shape[0], block_rows=block_rows):
                block = layer[start:end]
                if transform is not None:
                    block = transform(block)
                var[i0, i1, start:end, :] = block


def _has_non_fill_values(data, fill_value):
    arr = np.asarray(data)
    return bool(np.any(np.isfinite(arr) & (arr > float(fill_value))))


def _building_3d_iter(building_id_data, building_height_data, z_data, *, block_rows=64,
                      kept_columns=None, source_buildings_3d=None):
    """Yield buildings_3d slices without materializing the full 3-D volume.

    Columns in ``kept_columns`` are copied from ``source_buildings_3d`` (the
    file's buildings_3d, which also holds bridges), all others are built from
    buildings_2d.
    """
    footprint_mask = (building_id_data > 0) & (building_height_data > GridModel.FLOAT_FILL)
    clamped_heights = np.maximum(building_height_data, 0.0)
    for iz, z_val in enumerate(z_data):
        for start, end in _row_blocks(building_id_data.shape[0], block_rows=block_rows):
            block = (
                footprint_mask[start:end, :]
                & (z_val <= clamped_heights[start:end, :])
            ).astype(np.int8, copy=False)
            if kept_columns is not None:
                if iz < source_buildings_3d.shape[0]:
                    source_block = (np.asarray(source_buildings_3d[iz, start:end, :]) > 0).astype(np.int8)
                else:
                    source_block = np.zeros_like(block)
                block = np.where(kept_columns[start:end, :], source_block, block).astype(np.int8)
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
        # Without buildings_3d, buildings that exist only in 3D (bridges) cannot be
        # written. Their building_id / building_type are left out of the file,
        # otherwise PALM stops with DRV0034. The model keeps them.
        left_out_3d_only_cells = 0
        if not export_buildings_3d:
            only_in_3d = model.buildings_only_in_3d()
            left_out_3d_only_cells = int(np.count_nonzero(only_in_3d))
            if left_out_3d_only_cells:
                building_id_data = np.where(only_in_3d, GridModel.BUILDING_ID_FILL, building_id_data)
                building_type_data = np.where(only_in_3d, GridModel.INT_FILL, building_type_data)
        height_data = model.zt
        water_pars_data = model.water_pars
        vegetation_pars_data = model.vegetation_pars
        street_type_data = model.street_type
        irrigation_flag_data = model.irrigation_flag
        shf_data  = model.shf
        ssws_data = model.ssws
        building_parameter_data = model.building_pars

        source_buildings_3d = None if resolved_vegetation is None else resolved_vegetation.get("source_buildings_3d")
        source_buildings_3d_z = None if resolved_vegetation is None else resolved_vegetation.get("source_buildings_3d_z")
        source_buildings_2d = None if resolved_vegetation is None else resolved_vegetation.get("source_buildings_2d")
        source_building_id = None if resolved_vegetation is None else resolved_vegetation.get("source_building_id")
        source_building_type = None if resolved_vegetation is None else resolved_vegetation.get("source_building_type")

        deleted_building_ids = []
        replaced_building_pixel_count = 0
        z_data = None
        reuse_source_buildings_3d = False
        kept_columns = None
        # Cells with a building_id but no building voxel, PALM stops there with DRV0034
        building_id_without_building = 0

        print("SAVE NETCDF")
        print(f"Saving to {filename}...")

        georef = ensure_georeference(origin=ori, georef=georef)
        coordinates_attr = coordinate_attribute_names(georef)

        if export_buildings_3d and np.any(building_id_data > 0):
            kept_columns = GridModel.unchanged_building_columns(
                building_height_data, building_id_data, building_type_data, resolved_vegetation
            )
            if kept_columns is not None and kept_columns.all():
                reuse_source_buildings_3d = True
                z_data = np.asarray(source_buildings_3d_z, dtype=np.float32)
            else:
                # Edited columns are built from buildings_2d, unchanged ones keep the file's voxels
                rebuilt = (building_id_data > 0) & (building_height_data > GridModel.FLOAT_FILL)
                if kept_columns is not None:
                    rebuilt &= ~kept_columns
                z_max = float(np.max(np.maximum(building_height_data[rebuilt], 0.0))) if np.any(rebuilt) else 0.0
                z_levels = np.arange(0, math.ceil(z_max / vertical_dz) + 1, dtype=np.float32) * vertical_dz
                if z_levels.size == 0:
                    z_levels = np.array([0.0], dtype=np.float32)
                if z_levels.size > 1:
                    z_levels[1:] = z_levels[1:] - 0.5 * vertical_dz
                z_data = z_levels.astype(np.float32, copy=False)
                if kept_columns is not None:
                    # The file's z levels, extended if an edited building is taller
                    source_z = np.asarray(source_buildings_3d_z, dtype=np.float32)
                    if z_data[-1] > source_z[-1]:
                        extra = z_data[z_data > source_z[-1]]
                        z_data = np.concatenate([source_z, extra]).astype(np.float32)
                    else:
                        z_data = source_z

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
                water_types = (surface_config or {}).get("water", {}).get("types", {})
                for water_type_value, cfg in water_types.items():
                    default_water_temps[water_data == int(water_type_value)] = float(cfg["water_temperature"])
                current_water_temp = np.asarray(water_pars_data[0], dtype=np.float32)
                # Written where the temperature differs from its type's default, or
                # where no default is known (no surface_config, unknown water type)
                custom_water_mask = (
                    water_param_mask
                    & (current_water_temp > GridModel.FLOAT_FILL)
                    & (
                        ~np.isfinite(default_water_temps)
                        | (np.abs(current_water_temp - default_water_temps) > 1e-6)
                    )
                )
            else:
                custom_water_mask = np.zeros((ny, nx), dtype=bool)

            # The other six water parameters are written wherever they are set on water
            other_water_pars_mask = water_param_mask & np.any(
                np.asarray(water_pars_data[1:]) > GridModel.FLOAT_FILL, axis=0
            )
            water_pars_out_mask = custom_water_mask | other_water_pars_mask
            if np.any(water_pars_out_mask):
                nc_file.createDimension('nwater_pars', 7)

            has_vegetation_pars = bool(np.any(np.asarray(vegetation_pars_data) > GridModel.FLOAT_FILL))
            if has_vegetation_pars:
                nc_file.createDimension('nvegetation_pars', vegetation_pars_data.shape[0])

            active_building_param_specs = [
                (name, dim_names)
                for name, dim_names in GridModel.BUILDING_PARAMETER_SPECS
                if _has_non_fill_values(building_parameter_data[name], GridModel.FLOAT_FILL)
            ]
            needed_building_dims = {
                dim_name
                for _name, dim_names in active_building_param_specs
                for dim_name in dim_names
            }
            for dim_name in sorted(needed_building_dims):
                nc_file.createDimension(dim_name, BUILDING_CONFIG["parameter_dimensions"][dim_name])

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

            write_surface_types = np.any(
                (vegetation_data > GridModel.INT_FILL)
                | (pavement_data > GridModel.INT_FILL)
                | (water_data > GridModel.INT_FILL)
            )

            if write_surface_types:
                nc_vegetation_type = nc_file.createVariable('vegetation_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_vegetation_type.long_name = "vegetation type classification"
                nc_vegetation_type.units = "1"
                add_grid_mapping(nc_vegetation_type, coordinates_attr)
                _write_2d_variable(nc_vegetation_type, vegetation_data)

            if write_surface_types:
                nc_pavement_type = nc_file.createVariable('pavement_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_pavement_type.long_name = "pavement type classification"
                nc_pavement_type.units = "1"
                add_grid_mapping(nc_pavement_type, coordinates_attr)
                _write_2d_variable(nc_pavement_type, pavement_data)

            if write_surface_types and np.any(street_type_data > GridModel.INT_FILL):
                nc_street_type = nc_file.createVariable('street_type', 'i1', ('y', 'x'), fill_value=-127)
                nc_street_type.long_name = "street type classification"
                nc_street_type.units = "1"
                add_grid_mapping(nc_street_type, coordinates_attr)
                _write_2d_variable(nc_street_type, street_type_data)

            if write_surface_types:
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
                    occupied = np.zeros((ny, nx), dtype=bool)
                    if reuse_source_buildings_3d:
                        _write_3d_variable(nc_buildings_3d, source_buildings_3d)
                        occupied = np.any(np.asarray(source_buildings_3d) > 0, axis=0)
                    else:
                        for iz, start, end, block in _building_3d_iter(
                            building_id_data, building_height_data, z_data,
                            kept_columns=kept_columns, source_buildings_3d=source_buildings_3d,
                        ):
                            nc_buildings_3d[iz, start:end, :] = block
                            occupied[start:end, :] |= block > 0
                    building_id_without_building = int(np.count_nonzero((building_id_data > 0) & ~occupied))
                else:
                    building_id_without_building = int(np.count_nonzero(
                        (building_id_data > 0) & ~(building_height_data > GridModel.FLOAT_FILL)
                    ))

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

            if np.any(irrigation_flag_data > GridModel.INT_FILL):
                nc_irr = nc_file.createVariable('irrigation_flag', 'i1', ('y', 'x'), fill_value=-127)
                nc_irr.long_name = "irrigation flag"
                nc_irr.units = "1"
                add_grid_mapping(nc_irr, coordinates_attr)
                nc_irr[:, :] = irrigation_flag_data

            if _has_non_fill_values(shf_data, GridModel.FLOAT_FILL):
                nc_shf = nc_file.createVariable('shf', 'f4', ('y', 'x'), fill_value=-9999.0)
                nc_shf.long_name = "surface sensible heat flux"
                nc_shf.units = "K m s-1"
                add_grid_mapping(nc_shf, coordinates_attr)
                _write_2d_variable(nc_shf, shf_data)

            if _has_non_fill_values(ssws_data, GridModel.FLOAT_FILL):
                nc_ssws = nc_file.createVariable('ssws', 'f4', ('y', 'x'), fill_value=-9999.0)
                nc_ssws.long_name = "surface passive scalar flux"
                nc_ssws.units = "kg m-2 s-1"
                add_grid_mapping(nc_ssws, coordinates_attr)
                _write_2d_variable(nc_ssws, ssws_data)

            if np.any(water_pars_out_mask):
                nc_water_pars = nc_file.createVariable('water_pars', 'f4', ('nwater_pars', 'y', 'x'), fill_value=-9999.0)
                nc_water_pars.long_name = "grid point specific water parameters"
                nc_water_pars.units = "see nwater_pars index definition"
                add_grid_mapping(nc_water_pars, coordinates_attr)
                nc_water_pars[:, :, :] = nc_water_pars._FillValue
                for start, end in _row_blocks(ny, block_rows=128):
                    if not np.any(water_pars_out_mask[start:end, :]):
                        continue
                    source = np.asarray(water_pars_data[:, start:end, :], dtype=np.float32)
                    block = np.full(source.shape, -9999.0, dtype=np.float32)
                    # temperature only where it differs from its type's default
                    temperature_mask = custom_water_mask[start:end, :]
                    block[0][temperature_mask] = source[0][temperature_mask]
                    others = (source[1:] > GridModel.FLOAT_FILL) & water_param_mask[start:end, :]
                    block[1:][others] = source[1:][others]
                    nc_water_pars[:, start:end, :] = block

            if has_vegetation_pars:
                nc_vegetation_pars = nc_file.createVariable(
                    'vegetation_pars', 'f4', ('nvegetation_pars', 'y', 'x'), fill_value=-9999.0
                )
                nc_vegetation_pars.long_name = "grid point specific vegetation parameters"
                nc_vegetation_pars.units = "see nvegetation_pars index definition"
                add_grid_mapping(nc_vegetation_pars, coordinates_attr)
                for start, end in _row_blocks(ny, block_rows=128):
                    nc_vegetation_pars[:, start:end, :] = np.asarray(
                        vegetation_pars_data[:, start:end, :], dtype=np.float32
                    )

            for name, dim_names in active_building_param_specs:
                dims = tuple(dim_names) + ("y", "x")
                variable = nc_file.createVariable(name, "f4", dims, fill_value=-9999.0)
                meta = BUILDING_CONFIG["parameter_metadata"].get(name, {})
                variable.long_name = meta.get("long_name", name.replace("_", " "))
                variable.units = meta.get("units", "")
                add_grid_mapping(variable, coordinates_attr)
                if len(dim_names) == 1:
                    _write_3d_variable(variable, building_parameter_data[name])
                else:
                    _write_4d_variable(variable, building_parameter_data[name])

            nc_file.title = 'Idealized Scenario'
            nc_file.author = 'PALM User'
            nc_file.palmpaint_dz = vertical_dz

        print(f"NetCDF file saved: {filename}")
        return {
            "export_buildings_3d": bool(export_buildings_3d),
            "deleted_building_ids": deleted_building_ids,
            "deleted_building_count": len(deleted_building_ids),
            "replaced_building_pixel_count": replaced_building_pixel_count,
            "building_id_without_building": building_id_without_building,
            "left_out_3d_only_cells": left_out_3d_only_cells,
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
