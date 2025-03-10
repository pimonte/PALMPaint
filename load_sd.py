"""
Module to load grid data from a NetCDF file.
This file is meant to be used with the PALMPaint application.
"""

from netCDF4 import Dataset
import numpy as np

def get_pixel_color(veg, soil, pav, water, bldg_id):
    """
    Determines the color of a pixel based on its attributes.
    Priority:
    1. Water -> Blue
    2. Buildings -> Black
    3. Pavement -> Gray
    4. Vegetation -> Green
    5. Soil -> Brown
    6. Fallback -> White
    """
    if water > -1:
        return "blue"  # Water pixels
    elif bldg_id > -1:
        return "black"  # Buildings
    elif pav > -1:
        return "gray"  # Pavement
    elif veg > -1:
        return "green"  # Vegetation
    elif soil == 1:
        return "brown"  # Soil (default)
    return "white"  # Fallback color (if no data)

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
    # Open the NetCDF file in read mode
    nc_file = Dataset(filename, 'r')

    # Get dimensions
    nx = len(nc_file.dimensions["x"])
    ny = len(nc_file.dimensions["y"])

    # Determine resolution from the x coordinate variable.
    # The x values are defined as: np.arange(0, nx*dx, dx) + 0.5*dx in create_sd.py
    x = nc_file.variables["x"][:]
    res = (x[1] - x[0]) if nx > 1 else 1
    
    def get_data(var_name):
        # Check if the variable exists in the NetCDF file
        if var_name in nc_file.variables:
            var = nc_file.variables[var_name][:]
        # If var is a masked array, fill the masked elements with the _FillValue.
            if hasattr(var, "filled"):
                return var.filled(nc_file.variables[var_name]._FillValue)
            return var
        else:
        # If the variable does not exist, return an array of fill values
            return np.zeros((ny, nx)) -127

    # Read the saved variables
    veg = get_data("vegetation_type")
    soil = get_data("soil_type")
    pav = get_data("pavement_type")
    water = get_data("water_type")
    bldg_id = get_data("building_id")
    bldg_height = get_data("buildings_2d")  # Building height is saved here
    bldg_type = get_data("building_type")

    veg = np.flipud(veg)
    soil = np.flipud(soil)
    pav = np.flipud(pav)
    water = np.flipud(water)
    bldg_id = np.flipud(bldg_id)
    bldg_height = np.flipud(bldg_height)
    bldg_type = np.flipud(bldg_type)

    # Build the grid dictionary
    grid = {}
    for row in range(ny):
        for col in range(nx):
            color = get_pixel_color(veg[row, col], soil[row, col], 
                                    pav[row, col], water[row, col], bldg_id[row, col])
            pixel = {
                "vegetation_type": int(veg[row, col]),
                "soil_type": int(soil[row, col]),
                "pavement_type": int(pav[row, col]),
                "water_type": int(water[row, col]),
                "building_id": int(bldg_id[row, col]),
                "building_height": float(bldg_height[row, col]),
                "building_type": int(bldg_type[row, col]),
                "color": color,   # Default; you may update this based on the type later
                "outline": "gray"
            }
            grid[(row, col)] = pixel
            

    nc_file.close()
    return grid, nx, ny, res