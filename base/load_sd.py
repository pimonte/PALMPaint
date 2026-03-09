"""
Module to load grid data from a NetCDF file.
This file is meant to be used with the PALMPaint application.
    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

from netCDF4 import Dataset
import numpy as np

def get_2d_data(nc_file, var_name, ny, nx, fill_value=-127, dtype=None):
    """Load a 2D variable (y, x) or return a filled fallback array."""
    if var_name in nc_file.variables:
        data = nc_file.variables[var_name][:]
        if hasattr(data, "filled"):
            data = data.filled(nc_file.variables[var_name]._FillValue)
        if dtype is not None:
            data = data.astype(dtype)
        return data

    return np.full(
        (ny, nx),
        fill_value,
        dtype=dtype if dtype is not None else np.float32
    )


def get_pars_data(nc_file, var_name, npars, ny, nx, fill_value=-9999.0, dtype=np.float32):
    """Load a 3D parameter variable (npars, y, x) or return a filled fallback array."""
    if var_name in nc_file.variables:
        data = nc_file.variables[var_name][:]
        if hasattr(data, "filled"):
            data = data.filled(nc_file.variables[var_name]._FillValue)
        return data.astype(dtype)

    return np.full((npars, ny, nx), fill_value, dtype=dtype)

def Load(filename="output.nc"):
    """
    Load grid data from a NetCDF file and convert it into a dictionary
    for the paint application. Returns a tuple: (grid, nx, ny, res).

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
        ori = [nc_file.origin_lat, nc_file.origin_lon,
               nc_file.origin_x, nc_file.origin_y]

        # Determine resolution from the x coordinate variable.
        # The x values are defined as: np.arange(0, nx*dx, dx) + 0.5*dx in create_sd.py
        x = nc_file.variables["x"][:]
        res = float(x[1] - x[0]) if nx > 1 else 1.0

        def get_data(var_name):
            if var_name in nc_file.variables:
                var = nc_file.variables[var_name][:]
                if hasattr(var, "filled"):
                    return var.filled(nc_file.variables[var_name]._FillValue)
                return var
            return np.full((ny, nx), -127)

        # --- 2D fields ---
        veg = get_2d_data(nc_file, "vegetation_type", ny, nx, fill_value=-127, dtype=np.int8)
        soil = get_2d_data(nc_file, "soil_type", ny, nx, fill_value=-127, dtype=np.int8)
        pav = get_2d_data(nc_file, "pavement_type", ny, nx, fill_value=-127, dtype=np.int8)
        water = get_2d_data(nc_file, "water_type", ny, nx, fill_value=-127, dtype=np.int8)
        bldg_id = get_2d_data(nc_file, "building_id", ny, nx, fill_value=-127, dtype=np.int16)
        bldg_height = get_2d_data(nc_file, "buildings_2d", ny, nx, fill_value=-9999.0, dtype=np.float32)
        bldg_type = get_2d_data(nc_file, "building_type", ny, nx, fill_value=-127, dtype=np.int8)
        zt = get_2d_data(nc_file, "zt", ny, nx, fill_value=0.0, dtype=np.float32)

        # --- parameter stacks / pars ---
        water_pars = get_pars_data(nc_file, "water_pars", 7, ny, nx, fill_value=-9999.0, dtype=np.float32)

        grid = {}
        for row in range(ny):
            for col in range(nx):
                grid[(row, col)] = {
                    "zt":              float(zt[row, col]),
                    "vegetation_type": int(veg[row, col]),
                    "soil_type":       int(soil[row, col]),
                    "pavement_type":   int(pav[row, col]),
                    "water_type":      int(water[row, col]),
                    "building_id":     int(bldg_id[row, col]),
                    "building_height": float(bldg_height[row, col]),
                    "building_type":   int(bldg_type[row, col]),
                    
                    "water_temperature": float(water_pars[0, row, col]),
                }

    return grid, nx, ny, res, ori

