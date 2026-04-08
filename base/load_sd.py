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
    
def get_3d_data(nc_file, var_name, ny, nx, dtype=None, storage_factory=None):
    """Load a 3D variable (__, y, x) or return None.

    When ``storage_factory`` is provided, the data is streamed slice-by-slice
    into that target to avoid materializing the full 3D array in RAM.
    """
    if var_name not in nc_file.variables:
        return None

    var = nc_file.variables[var_name]
    if len(var.shape) != 3:
        return None

    if var.shape[1] != ny or var.shape[2] != nx:
        return None

    target_dtype = np.dtype(dtype if dtype is not None else var.dtype)
    fill_value = getattr(var, "_FillValue", -9999.0)

    if storage_factory is None:
        data = var[:]
        if hasattr(data, "filled"):
            data = data.filled(fill_value)
        if dtype is not None:
            data = data.astype(target_dtype)
        return data

    data = storage_factory(var.shape, target_dtype, fill_value, var_name)
    for idx in range(var.shape[0]):
        layer = var[idx, :, :]
        if hasattr(layer, "filled"):
            layer = layer.filled(fill_value)
        if dtype is not None:
            layer = layer.astype(target_dtype, copy=False)
        data[idx, :, :] = layer
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

def LoadModel(filename="output.nc", surface_config=None):
    """
    Load grid data from a NetCDF file directly into a GridModel.

    Returns:
      (model, nx, ny, res, dz, origin_tuple, resolved_vegetation, georef)
    """
    with Dataset(filename, 'r') as nc_file:
        # Get dimensions
        nx = len(nc_file.dimensions["x"])
        ny = len(nc_file.dimensions["y"])
        georef = load_georeference(nc_file)
        ori = georef.as_origin_tuple()

        # Determine horizontal resolution from the x coordinate variable.
        # The x values are defined as: np.arange(0, nx*dx, dx) + 0.5*dx in create_sd.py
        # so x[0] = 0.5*dx → dx = 2*x[0] for single-cell grids.
        x = nc_file.variables["x"][:]
        res = float(x[1] - x[0]) if nx > 1 else float(2 * x[0])

        z_coords = None
        if "buildings_3d" in nc_file.variables and "z" in nc_file.variables:
            z_coords = nc_file.variables["z"][:]
            if hasattr(z_coords, "filled"):
                fv = getattr(nc_file.variables["z"], "_FillValue", -9999.0)
                z_coords = z_coords.filled(fv)
            z_coords = np.asarray(z_coords, dtype=np.float32)

        # def get_data(var_name):
        #     if var_name in nc_file.variables:
        #         var = nc_file.variables[var_name][:]
        #         if hasattr(var, "filled"):
        #             fv = getattr(nc_file.variables[var_name], "_FillValue", -127)
        #             return var.filled(fv)
        #         return var
        #     return np.full((ny, nx), -127)

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

        model = GridModel(nx, ny, res, dz, surface_config=surface_config)
        model.vegetation_type[:, :] = veg
        model.soil_type[:, :] = soil
        model.pavement_type[:, :] = pav
        model.water_type[:, :] = water
        model.building_id[:, :] = bldg_id
        model.building_height[:, :] = bldg_height
        model.building_type[:, :] = bldg_type
        model.zt[:, :] = zt
        model.water_pars[:, :, :] = water_pars

        def _storage_factory(shape, dtype, _fill_value, name_prefix):
            return model.allocate_storage(shape, dtype, fill_value=0, name_prefix=name_prefix)

        source_buildings_3d = get_3d_data(
            nc_file,
            "buildings_3d",
            ny,
            nx,
            dtype=np.int8,
            storage_factory=_storage_factory,
        )
        lad = get_3d_data(
            nc_file,
            "lad",
            ny,
            nx,
            dtype=np.float32,
            storage_factory=_storage_factory,
        )
        bad = get_3d_data(
            nc_file,
            "bad",
            ny,
            nx,
            dtype=np.float32,
            storage_factory=_storage_factory,
        )
        tree_id = get_3d_data(
            nc_file,
            "tree_id",
            ny,
            nx,
            dtype=np.int32,
            storage_factory=_storage_factory,
        )

        resolved_vegetation = {
            "zlad": zlad,
            "lad": lad,
            "bad": bad,
            "tree_id": tree_id,
            "source_has_buildings_3d": "buildings_3d" in nc_file.variables,
            "source_buildings_3d": source_buildings_3d,
            "source_buildings_3d_z": None if z_coords is None else np.array(z_coords, copy=True),
            "source_buildings_2d": np.array(bldg_height, copy=True),
            "source_building_id": np.array(bldg_id, copy=True),
            "source_building_type": np.array(bldg_type, copy=True),
        }
        model._loaded_rv = resolved_vegetation
        model.resolved_vegetation = resolved_vegetation

    return model, nx, ny, res, dz, ori, resolved_vegetation, georef


def Load(filename="output.nc", surface_config=None):
    """Backward-compatible wrapper returning the legacy per-cell dictionary."""
    model, nx, ny, res, dz, ori, resolved_vegetation, georef = LoadModel(
        filename,
        surface_config=surface_config,
    )
    return model.to_legacy_dict(), nx, ny, res, dz, ori, resolved_vegetation, georef
