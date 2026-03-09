"""
Module to load grid data from a NetCDF file.
This file is meant to be used with the PALMPaint application.
    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

from netCDF4 import Dataset
import numpy as np

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

        veg        = get_data("vegetation_type")
        soil       = get_data("soil_type")
        pav        = get_data("pavement_type")
        water      = get_data("water_type")
        bldg_id    = get_data("building_id")
        bldg_height = get_data("buildings_2d")
        bldg_type  = get_data("building_type")

        grid = {}
        for row in range(ny):
            for col in range(nx):
                grid[(row, col)] = {
                    "vegetation_type": int(veg[row, col]),
                    "soil_type":       int(soil[row, col]),
                    "pavement_type":   int(pav[row, col]),
                    "water_type":      int(water[row, col]),
                    "building_id":     int(bldg_id[row, col]),
                    "building_height": float(bldg_height[row, col]),
                    "building_type":   int(bldg_type[row, col]),
                }

    return grid, nx, ny, res, ori