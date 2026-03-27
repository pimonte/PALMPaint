"""
Module to save grid data to a NetCDF file.
This file is meant to be used with the PALMPaint application.
    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""
import math
from importlib import metadata
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
        #print("DATA", data)
        rows = [key[0] for key in data.keys()]  # Extract all row indices
        cols = [key[1] for key in data.keys()]  # Extract all column indices

        ny = max(rows) + 1  # Maximum row index + 1 gives number of rows
        nx = max(cols) + 1
        print("NX", nx)
        print("NY", ny)
        
        dx = dy = res
        vertical_dz = float(dz) if float(dz) > 0.0 else float(res)
        
        vegetation_data = np.full((ny, nx), -1) 
        soil_data = np.full((ny, nx), -1) 
        pavement_data = np.full((ny, nx), -1)
        water_data = np.full((ny, nx), -1)
        building_id_data = np.full((ny, nx), GridModel.BUILDING_ID_FILL, dtype=np.int32)
        building_height_data = np.full((ny, nx), GridModel.FLOAT_FILL, dtype=np.float32)
        raw_building_height_data = np.full((ny, nx), GridModel.FLOAT_FILL, dtype=np.float32)
        building_type_data = np.full((ny, nx), -1)
        height_data = np.full((ny, nx), -9999.0, dtype=np.float32)
        buildings_3d_data = None
        z_data = None
        deleted_building_ids = []
        replaced_building_pixel_count = 0
        
        water_pars_data = np.full((7, ny, nx), -9999.0, dtype=np.float32)
        

        
        for (row, col), metadata in data.items():
            #print(metadata)
            if "zt" in metadata and metadata["zt"] is not None:
                height_data[row, col] = GridModel.quantize_terrain_height(metadata["zt"], vertical_dz)
            if "vegetation_type" in metadata and metadata["vegetation_type"] is not None:
                vegetation_data[row, col] = metadata["vegetation_type"]
            if "soil_type" in metadata and metadata["soil_type"] is not None:
                soil_data[row, col] = metadata["soil_type"]
            if "pavement_type" in metadata and metadata["pavement_type"] is not None:
                pavement_data[row, col] = metadata["pavement_type"]
            if "water_type" in metadata and metadata["water_type"] is not None:
                water_data[row, col] = metadata["water_type"]
            building_height = metadata.get("building_height")
            if building_height is not None:
                try:
                    raw_building_height = float(building_height)
                except (TypeError, ValueError):
                    raw_building_height = GridModel.FLOAT_FILL
                if np.isfinite(raw_building_height):
                    raw_building_height_data[row, col] = raw_building_height
                quantized_building_height = GridModel.quantize_building_height(building_height, vertical_dz)
                building_height_data[row, col] = quantized_building_height
                if quantized_building_height > GridModel.FLOAT_FILL:
                    if "building_id" in metadata and metadata["building_id"] is not None:
                        building_id_data[row, col] = metadata["building_id"]
                    if "building_type" in metadata and metadata["building_type"] is not None:
                        building_type_data[row, col] = metadata["building_type"]
                
            # write water_pars only if temperature differs from the default of water_type
            if metadata.get("water_type", -127) > -127:
                water_type_value = int(metadata["water_type"])
                water_temp = float(metadata.get("water_temperature", -9999.0))

                default_temp = float(
                    surface_config["water"]["types"][water_type_value]["water_temperature"]
                )

                if water_temp > -9999.0 and abs(water_temp - default_temp) > 1e-6:
                    water_pars_data[0, row, col] = water_temp
                
        # flip the data
        # vegetation_data = np.flipud(vegetation_data)
        # soil_data = np.flipud(soil_data)
        # pavement_data = np.flipud(pavement_data)
        # water_data = np.flipud(water_data)
        # building_id_data = np.flipud(building_id_data)
        # building_height_data = np.flipud(building_height_data)
        # building_type_data = np.flipud(building_type_data)
        # height_data = np.flipud(height_data)
        
                
        #print("VEGETATION", vegetation_data)
                
        print("SAVE NETCDF")
        
        print(f"Saving to {filename}...")
        


        georef = ensure_georeference(origin=ori, georef=georef)

        coordinates_attr = coordinate_attribute_names(georef)

        if export_buildings_3d and np.any(building_id_data > 0):
            original_building_ids = np.unique(building_id_data[building_id_data > 0]).astype(np.int32)
            eligible_3d_mask = (building_id_data > 0) & (
                raw_building_height_data > (0.5 * vertical_dz + 1e-9)
            )
            replaced_pixel_mask = (building_id_data > 0) & ~eligible_3d_mask

            if np.any(eligible_3d_mask):
                layer_counts = np.floor(
                    (raw_building_height_data[eligible_3d_mask] + 0.5 * vertical_dz - 1e-9)
                    / vertical_dz
                ).astype(np.int32)
                max_layers = int(np.max(np.maximum(layer_counts, 1)))
                buildings_3d_data = np.zeros((max_layers, ny, nx), dtype=np.int8)
                z_data = np.zeros((max_layers,), dtype=np.float32)
                if max_layers > 1:
                    z_data[1:] = vertical_dz * (np.arange(1, max_layers, dtype=np.float32) - 0.5)

                rows_idx, cols_idx = np.where(eligible_3d_mask)
                for row, col in zip(rows_idx, cols_idx):
                    raw_height = float(raw_building_height_data[row, col])
                    layer_count = int(
                        math.floor((raw_height + 0.5 * vertical_dz - 1e-9) / vertical_dz)
                    )
                    layer_count = max(layer_count, 1)
                    buildings_3d_data[:layer_count, row, col] = 1

            if np.any(replaced_pixel_mask):
                surviving_building_ids = {
                    int(value) for value in np.unique(building_id_data[eligible_3d_mask]) if int(value) > 0
                }
                deleted_building_ids = [
                    int(value) for value in original_building_ids if int(value) not in surviving_building_ids
                ]
                replaced_building_pixel_count = int(np.count_nonzero(replaced_pixel_mask))

                asphalt_type = 1
                asphalt_soil_type = int(
                    surface_config["pavement"]["types"].get(
                        asphalt_type,
                        {"soil_type": surface_config["soil"]["default_type"]},
                    )["soil_type"]
                )

                vegetation_data[replaced_pixel_mask] = -1
                water_data[replaced_pixel_mask] = -1
                pavement_data[replaced_pixel_mask] = asphalt_type
                soil_data[replaced_pixel_mask] = asphalt_soil_type
                water_pars_data[:, replaced_pixel_mask] = GridModel.FLOAT_FILL
                building_height_data[replaced_pixel_mask] = GridModel.FLOAT_FILL
                building_id_data[replaced_pixel_mask] = GridModel.BUILDING_ID_FILL
                building_type_data[replaced_pixel_mask] = -1

        with (Dataset(filename, 'w', format='NETCDF4') as nc_file):

            # Define dimensions
            nc_file.createDimension('x', nx)
            nc_file.createDimension('y', ny)
            if z_data is not None:
                nc_file.createDimension("z", len(z_data))
            if resolved_vegetation is not None and resolved_vegetation.get("zlad") is not None:
                zlad_data = resolved_vegetation["zlad"]
                nc_file.createDimension("zlad", len(zlad_data))
            else:
                zlad_data = None
            if np.any(water_pars_data > -9999.0):
                nc_file.createDimension('nwater_pars', 7)

            # Coordinates
            # -----------
            
            x = nc_file.createVariable('x', 'f4', ('x',))
            x.long_name = 'distance to origin in x-direction'
            x.units = 'm'
            x.axis = 'X'
            x[:] = np.arange(0, (nx)*dx, dx) + 0.5 * dx

            
            y = nc_file.createVariable('y', 'f4', ('y',))
            y.long_name = 'distance to origin in y-direction'
            y.units = 'm'
            y.axis = 'Y'
            y[:] = np.arange(0, (ny)*dy, dy) + 0.5 * dy

            write_georeference(nc_file, nx, ny, dx, georef)

            if z_data is not None:
                z = nc_file.createVariable("z", "f4", ("z",))
                z.long_name = "z coordinate"
                z.units = "m"
                z.axis = "Z"
                z[:] = z_data

            # Land surface
            nc_zt = nc_file.createVariable(
            'zt', 'f4', ('y', 'x'), fill_value=-9999.0)
            nc_zt.long_name = 'terrain height'
            nc_zt.units = 'm'
            add_grid_mapping(nc_zt, coordinates_attr)
            nc_zt[:, :] = nc_zt._FillValue

            nc_soil_type = nc_file.createVariable(
                'soil_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_soil_type.long_name = "soil type classification"
            nc_soil_type.units = "1"
            nc_soil_type.lod = np.int32(1)
            add_grid_mapping(nc_soil_type, coordinates_attr)
            nc_soil_type[:, :] = nc_soil_type._FillValue

            nc_vegetation_type = nc_file.createVariable(
                'vegetation_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_vegetation_type.long_name = "vegetation type classification"
            nc_vegetation_type.units = "1"
            add_grid_mapping(nc_vegetation_type, coordinates_attr)
            nc_vegetation_type[:, :] = nc_vegetation_type._FillValue

            nc_pavement_type = nc_file.createVariable(
                'pavement_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_pavement_type.long_name = "pavement type classification"
            nc_pavement_type.units = "1"
            add_grid_mapping(nc_pavement_type, coordinates_attr)
            nc_pavement_type[:, :] = nc_pavement_type._FillValue

            nc_water_type = nc_file.createVariable(
                'water_type', 'i1', ('y', 'x'), fill_value=-127)
            nc_water_type.long_name = "water type classification"
            nc_water_type.units = "1"
            add_grid_mapping(nc_water_type, coordinates_attr)
            nc_water_type[:, :] = nc_water_type._FillValue
            
            
            
            # Where data is > fill_value, set the data in the NetCDF file
            nc_zt[:, :] = np.where(
                height_data[:, :] > -9999.0,
                height_data[:, :],
                nc_zt._FillValue,
            )
            
            nc_vegetation_type[:, :] = nc_vegetation_type._FillValue
            nc_vegetation_type[:, :] = np.where(
            vegetation_data[:, :] > -1,
            vegetation_data[:, :],
            nc_vegetation_type._FillValue)
            
            nc_soil_type[:, :] = nc_soil_type._FillValue
            nc_soil_type[:, :] = np.where(
            soil_data[:, :] > -1,
            soil_data[:, :],
            nc_soil_type._FillValue)
            
            nc_pavement_type[:, :] = nc_pavement_type._FillValue
            nc_pavement_type[:, :] = np.where(
            pavement_data[:, :] > -1,
            pavement_data[:, :],
            nc_pavement_type._FillValue)
            
            nc_water_type[:, :] = nc_water_type._FillValue
            nc_water_type[:, :] = np.where(
            water_data[:, :] > -1,
            water_data[:, :],
            nc_water_type._FillValue)
            
            # Buildings
            if np.any(building_height_data > GridModel.FLOAT_FILL) or np.any(building_id_data > 0):
                print("BUILDINGS detected (switch on USM Namelist in PALM)")
                
                nc_buildings_2d = nc_file.createVariable(
                'buildings_2d', 'f4', ('y', 'x'), fill_value=-9999.0)
                nc_buildings_2d.long_name = "building height"
                nc_buildings_2d.units = "m"
                nc_buildings_2d.lod = np.int32(1)
                add_grid_mapping(nc_buildings_2d, coordinates_attr)
                nc_buildings_2d[:, :] = nc_buildings_2d._FillValue
                
                nc_buildings_2d[:, :] = nc_buildings_2d._FillValue
                nc_buildings_2d[:, :] = np.where(
                building_height_data[:, :] > GridModel.FLOAT_FILL,
                building_height_data[:, :],
                nc_buildings_2d._FillValue)

                if np.any(building_id_data > 0):
                    nc_building_id = nc_file.createVariable(
                    'building_id', 'i4', ('y', 'x'), fill_value=GridModel.BUILDING_ID_FILL)
                    nc_building_id.long_name = "building ID"
                    nc_building_id.units = ""
                    add_grid_mapping(nc_building_id, coordinates_attr)
                    nc_building_id[:, :] = nc_building_id._FillValue
                    nc_building_id[:, :] = np.where(
                    building_id_data[:, :] > 0,
                    building_id_data[:, :],
                    nc_building_id._FillValue)

                if np.any(building_type_data > -1):
                    nc_building_type = nc_file.createVariable(
                    'building_type', 'i1', ('y', 'x'), fill_value=-127)
                    nc_building_type.long_name = "building type classification"
                    nc_building_type.units = "1"
                    add_grid_mapping(nc_building_type, coordinates_attr)
                    nc_building_type[:, :] = nc_building_type._FillValue
                    nc_building_type[:, :] = np.where(
                    building_type_data[:, :] > -1,
                    building_type_data[:, :],
                    nc_building_type._FillValue)

                if buildings_3d_data is not None:
                    nc_buildings_3d = nc_file.createVariable(
                        "buildings_3d", "i1", ("z", "y", "x"), fill_value=-127
                    )
                    nc_buildings_3d.long_name = "building flag"
                    nc_buildings_3d.units = "1"
                    nc_buildings_3d.lod = np.int32(2)
                    add_grid_mapping(nc_buildings_3d, coordinates_attr)
                    nc_buildings_3d[:, :, :] = buildings_3d_data
            
            # Trees
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
                    nc_lad = nc_file.createVariable(
                        "lad", "f4", ("zlad", "y", "x"), fill_value=-9999.0
                    )
                    nc_lad.long_name = "leaf area density"
                    nc_lad.units = "m2 m-3"
                    add_grid_mapping(nc_lad, coordinates_attr)
                    nc_lad[:, :, :] = lad_data

                if bad_data is not None:
                    nc_bad = nc_file.createVariable(
                        "bad", "f4", ("zlad", "y", "x"), fill_value=-9999.0
                    )
                    nc_bad.long_name = "basal area density"
                    nc_bad.units = "m2 m-3"
                    add_grid_mapping(nc_bad, coordinates_attr)
                    nc_bad[:, :, :] = bad_data

                if tree_id_data is not None:
                    nc_tree_id = nc_file.createVariable(
                        "tree_id", "i4", ("zlad", "y", "x"), fill_value=-9999
                    )
                    nc_tree_id.long_name = "tree id"
                    nc_tree_id.units = ""
                    add_grid_mapping(nc_tree_id, coordinates_attr)
                    nc_tree_id[:, :, :] = tree_id_data

            # Parameters
            if np.any(water_pars_data > -9999.0):
                nc_water_pars = nc_file.createVariable(
                    'water_pars', 'f4', ('nwater_pars', 'y', 'x'), fill_value=-9999.0
                )
                nc_water_pars.long_name = "grid point specific water parameters"
                nc_water_pars.units = "see nwater_pars index definition"
                add_grid_mapping(nc_water_pars, coordinates_attr)
                nc_water_pars[:, :, :] = water_pars_data

    
            # Add metadata
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
