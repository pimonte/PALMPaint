"""
Module to load grid data from a NetCDF file.
This file is meant to be used with the PALMPaint application.
    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

from netCDF4 import Dataset
import numpy as np

from base.geo_reference import load_georeference
from base.gridmodel import GridModel

def get_2d_data(nc_file, var_name, ny, nx, fill_value=-127, dtype=None):
    """Load a 2D variable (y, x) or return a filled fallback array."""
    if var_name in nc_file.variables:
        data = nc_file.variables[var_name][:]
        if hasattr(data, "filled"):
            fv = getattr(nc_file.variables[var_name], "_FillValue", fill_value)
            data = data.filled(fv)
        if dtype is not None:
            data = data.astype(dtype)
        return data

    return np.full(
        (ny, nx),
        fill_value,
        dtype=dtype if dtype is not None else np.float32
    )
    
def get_3d_data(nc_file, var_name, ny, nx, dtype=None):
    """Load a 3D variable (__, y, x) or return None."""
    if var_name not in nc_file.variables:
        return None

    data = nc_file.variables[var_name][:]
    if hasattr(data, "filled"):
        fv = getattr(nc_file.variables[var_name], "_FillValue", -9999.0)
        data = data.filled(fv)

    if dtype is not None:
        data = data.astype(dtype)

    if data.ndim != 3:
        return None

    if data.shape[1] != ny or data.shape[2] != nx:
        return None

    return data


def get_pars_data(nc_file, var_name, npars, ny, nx, fill_value=-9999.0, dtype=np.float32):
    """Load a 3D parameter variable (npars, y, x) or return a filled fallback array."""
    if var_name in nc_file.variables:
        data = nc_file.variables[var_name][:]
        if hasattr(data, "filled"):
            fv = getattr(nc_file.variables[var_name], "_FillValue", fill_value)
            data = data.filled(fv)
        return data.astype(dtype)

    return np.full((npars, ny, nx), fill_value, dtype=dtype)

def Load(filename="output.nc"):
    """
    Load grid data from a NetCDF file and convert it into a dictionary
    for the paint application.

    Returns:
      (grid, nx, ny, res, dz, origin_tuple, resolved_vegetation, georef)

    The grid is a dictionary where keys are (row, col) and values are
    dictionaries with pixel properties:
      - vegetation_type
      - soil_type
      - pavement_type
      - water_type
      - building_id
      - building_height (from 'buildings_2d')
      - building_type
      - color (default set to 'brown')
      - outline (default set to 'gray')

    The function also reads coordinate variables to determine the resolution.
    """
    with Dataset(filename, 'r') as nc_file:
        # Get dimensions
        nx = len(nc_file.dimensions["x"])
        ny = len(nc_file.dimensions["y"])
        georef = load_georeference(nc_file)
        ori = georef.as_origin_tuple()

        # Determine horizontal resolution from the x coordinate variable.
        # The x values are defined as: np.arange(0, nx*dx, dx) + 0.5*dx in create_sd.py
        x = nc_file.variables["x"][:]
        res = float(x[1] - x[0]) if nx > 1 else 1.0

        z_coords = None
        if "buildings_3d" in nc_file.variables and "z" in nc_file.variables:
            z_coords = nc_file.variables["z"][:]
            if hasattr(z_coords, "filled"):
                fv = getattr(nc_file.variables["z"], "_FillValue", -9999.0)
                z_coords = z_coords.filled(fv)
            z_coords = np.asarray(z_coords, dtype=np.float32)

        def get_data(var_name):
            if var_name in nc_file.variables:
                var = nc_file.variables[var_name][:]
                if hasattr(var, "filled"):
                    fv = getattr(nc_file.variables[var_name], "_FillValue", -127)
                    return var.filled(fv)
                return var
            return np.full((ny, nx), -127)

        # --- 2D fields ---
        veg = get_2d_data(nc_file, "vegetation_type", ny, nx, fill_value=-127, dtype=np.int8)
        soil = get_2d_data(nc_file, "soil_type", ny, nx, fill_value=-127, dtype=np.int8)
        pav = get_2d_data(nc_file, "pavement_type", ny, nx, fill_value=-127, dtype=np.int8)
        water = get_2d_data(nc_file, "water_type", ny, nx, fill_value=-127, dtype=np.int8)
        bldg_id = get_2d_data(
            nc_file, "building_id", ny, nx, fill_value=GridModel.BUILDING_ID_FILL, dtype=np.int32
        )
        bldg_height = get_2d_data(nc_file, "buildings_2d", ny, nx, fill_value=-9999.0, dtype=np.float32)
        bldg_type = get_2d_data(nc_file, "building_type", ny, nx, fill_value=-127, dtype=np.int8)
        zt = get_2d_data(nc_file, "zt", ny, nx, fill_value=0.0, dtype=np.float32)

        # --- parameter stacks / pars ---
        water_pars = get_pars_data(nc_file, "water_pars", 7, ny, nx, fill_value=-9999.0, dtype=np.float32)
        zlad = None
        if "zlad" in nc_file.variables:
            zlad = nc_file.variables["zlad"][:]
            if hasattr(zlad, "filled"):
                fv = getattr(nc_file.variables["zlad"], "_FillValue", -9999.0)
                zlad = zlad.filled(fv)
            zlad = zlad.astype(np.float32)

        stored_dz = getattr(nc_file, "palmpaint_dz", None)

        if z_coords is not None:
            dz = GridModel.infer_vertical_step(z_coords, res)
        elif zlad is not None:
            dz = GridModel.infer_dz_from_zlad(zlad, res)
        elif stored_dz is not None:
            dz = float(stored_dz)
        else:
            dz = float(res)

        lad = get_3d_data(nc_file, "lad", ny, nx, dtype=np.float32)
        bad = get_3d_data(nc_file, "bad", ny, nx, dtype=np.float32)
        tree_id = get_3d_data(nc_file, "tree_id", ny, nx, dtype=np.int32)

        resolved_vegetation = {
            "zlad": zlad,
            "lad": lad,
            "bad": bad,
            "tree_id": tree_id,
            "source_has_buildings_3d": "buildings_3d" in nc_file.variables,
        }

        grid = {}
        for row in range(ny):
            for col in range(nx):
                building_height = float(bldg_height[row, col])
                building_id = int(bldg_id[row, col])
                building_type = int(bldg_type[row, col])
                if building_height <= GridModel.FLOAT_FILL:
                    building_id = GridModel.INT_FILL
                    building_type = GridModel.INT_FILL

                grid[(row, col)] = {
                    "zt":              float(zt[row, col]),
                    "vegetation_type": int(veg[row, col]),
                    "soil_type":       int(soil[row, col]),
                    "pavement_type":   int(pav[row, col]),
                    "water_type":      int(water[row, col]),
                    "building_id":     building_id,
                    "building_height": building_height,
                    "building_type":   building_type,
                    
                    "water_temperature": float(water_pars[0, row, col]),
                }

    return grid, nx, ny, res, dz, ori, resolved_vegetation, georef
