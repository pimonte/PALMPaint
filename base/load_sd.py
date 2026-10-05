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
            data = data.filled(fill_value)
        if dtype is not None:
            data = data.astype(dtype)
        return data

    return np.full(
        (ny, nx),
        fill_value,
        dtype=dtype if dtype is not None else np.float32
    )
    
def get_3d_data(nc_file, var_name, ny, nx, fill_value, dtype=None, storage_factory=None):
    """Load a 3D variable (__, y, x) or return None.

    When ``storage_factory`` is provided, the data is streamed slice-by-slice
    into that target to avoid materializing the full 3D array in RAM.
    Cells that hold the file's _FillValue get ``fill_value``, the model's fill
    value, because other tools use other fill values (e.g. -9999.9).
    """
    if var_name not in nc_file.variables:
        return None

    var = nc_file.variables[var_name]
    if len(var.shape) != 3:
        return None

    if var.shape[1] != ny or var.shape[2] != nx:
        return None

    target_dtype = np.dtype(dtype if dtype is not None else var.dtype)

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
            data = data.filled(fill_value)
        return data.astype(dtype)

    return np.full((npars, ny, nx), fill_value, dtype=dtype)


def get_4d_data(nc_file, var_name, shape, fill_value=-9999.0, dtype=np.float32, storage_factory=None):
    """Load a 4D variable or return a filled fallback array."""
    if var_name not in nc_file.variables:
        if storage_factory is None:
            return np.full(shape, fill_value, dtype=dtype)
        data = storage_factory(shape, dtype, fill_value, var_name)
        data[...] = fill_value
        return data

    var = nc_file.variables[var_name]
    if len(var.shape) != 4 or tuple(int(v) for v in var.shape) != tuple(int(v) for v in shape):
        if storage_factory is None:
            return np.full(shape, fill_value, dtype=dtype)
        data = storage_factory(shape, dtype, fill_value, var_name)
        data[...] = fill_value
        return data

    target_dtype = np.dtype(dtype)
    if storage_factory is None:
        data = var[:]
        if hasattr(data, "filled"):
            data = data.filled(fill_value)
        return data.astype(target_dtype, copy=False)

    data = storage_factory(shape, target_dtype, fill_value, var_name)
    for idx0 in range(shape[0]):
        for idx1 in range(shape[1]):
            layer = var[idx0, idx1, :, :]
            if hasattr(layer, "filled"):
                layer = layer.filled(fill_value)
            data[idx0, idx1, :, :] = np.asarray(layer, dtype=target_dtype)
    return data

def LoadModel(filename="output.nc", surface_config=None):
    """
    Load grid data from a NetCDF file directly into a GridModel.

    Returns:
      (model, nx, ny, res, dz, origin_tuple, resolved_vegetation, georef)
    """
    with Dataset(filename, 'r') as nc_file:
        # A PALM static driver always has x and y dimensions
        for dim in ("x", "y"):
            if dim not in nc_file.dimensions:
                raise ValueError(f"The file has no {dim} dimension. Is it a PALM static driver?")

        # Get dimensions
        nx = len(nc_file.dimensions["x"])
        ny = len(nc_file.dimensions["y"])

        # Determine horizontal resolution from the x coordinate variable.
        # The x values are defined as: np.arange(0, nx*dx, dx) + 0.5*dx in create_sd.py
        # so x[0] = 0.5*dx → dx = 2*x[0] for single-cell grids.
        x = nc_file.variables["x"][:]
        res = float(x[1] - x[0]) if nx > 1 else float(2 * x[0])

        # origin_x / origin_y and origin_lat / origin_lon count as the same point
        # when they are less than one grid cell apart
        georef = load_georeference(nc_file, tolerance=max(res, 1.0))
        ori = georef.as_origin_tuple()

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
        street_type = get_2d_data(nc_file, "street_type", ny, nx, fill_value=-127, dtype=np.int8)
        water = get_2d_data(nc_file, "water_type", ny, nx, fill_value=-127, dtype=np.int8)
        irr = get_2d_data(nc_file, "irrigation_flag", ny, nx, fill_value=-127, dtype=np.int8)
        shf  = get_2d_data(nc_file, "shf",  ny, nx, fill_value=-9999.0, dtype=np.float32)
        ssws = get_2d_data(nc_file, "ssws", ny, nx, fill_value=-9999.0, dtype=np.float32)
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
        model.street_type[:, :] = street_type
        model.water_type[:, :] = water
        model.building_id[:, :] = bldg_id
        model.building_height[:, :] = bldg_height
        model.building_type[:, :] = bldg_type
        model.zt[:, :] = zt
        model.water_pars[:, :, :] = water_pars
        model.irrigation_flag[:, :] = irr
        model.shf[:, :]  = shf
        model.ssws[:, :] = ssws

        def _storage_factory(shape, dtype, _fill_value, name_prefix):
            return model.allocate_storage(shape, dtype, fill_value=0, name_prefix=name_prefix)

        source_buildings_3d = get_3d_data(
            nc_file,
            "buildings_3d",
            ny,
            nx,
            GridModel.INT_FILL,
            dtype=np.int8,
            storage_factory=_storage_factory,
        )
        lad = get_3d_data(
            nc_file,
            "lad",
            ny,
            nx,
            GridModel.FLOAT_FILL,
            dtype=np.float32,
            storage_factory=_storage_factory,
        )
        bad = get_3d_data(
            nc_file,
            "bad",
            ny,
            nx,
            GridModel.FLOAT_FILL,
            dtype=np.float32,
            storage_factory=_storage_factory,
        )
        tree_id = get_3d_data(
            nc_file,
            "tree_id",
            ny,
            nx,
            -9999,
            dtype=np.int32,
            storage_factory=_storage_factory,
        )
        # palmpy writes tree_id in 2D, one ID per column. PALM's spec and palm_csd
        # use 3D, so every voxel with leaves in a column gets the column's ID.
        tree_id_from_2d = None
        if tree_id is None and lad is not None:
            tree_id, tree_id_from_2d = _tree_id_from_2d(nc_file, lad, bad, _storage_factory)
        # 3D variables PALMPaint saves but could not read here (unexpected shape)
        read_3d = {"buildings_3d": source_buildings_3d, "lad": lad, "bad": bad, "tree_id": tree_id}
        # An index variable like tree_id(tree_id) only labels a dimension, it is no data
        unreadable_3d = [
            f"{name} {nc_file.variables[name].dimensions}"
            for name, data in read_3d.items()
            if name in nc_file.variables and data is None
            and nc_file.variables[name].dimensions != (name,)
        ]

        for name, dim_names in GridModel.BUILDING_PARAMETER_SPECS:
            target = model.building_pars[name]
            if len(dim_names) == 1:
                target[...] = get_pars_data(
                    nc_file,
                    name,
                    target.shape[0],
                    ny,
                    nx,
                    fill_value=GridModel.FLOAT_FILL,
                    dtype=np.float32,
                )
            else:
                target[...] = get_4d_data(
                    nc_file,
                    name,
                    target.shape,
                    fill_value=GridModel.FLOAT_FILL,
                    dtype=np.float32,
                    storage_factory=None,
                )

        # PALMPaint before 0.5.6 wrote zlad = dz/2, 3 dz/2, ... for new projects,
        # without PALM's surface level 0, so PALM stops with PCM0010. Each layer
        # holds the vegetation of its height, so put an empty level 0 in front
        # and every layer lands on the PALM level that covers it.
        zlad_repaired = False
        if zlad is not None and lad is not None and is_old_palmpaint_zlad(zlad, dz):
            zlad = GridModel.palm_zlad(len(zlad) + 1, dz)
            lad = _with_empty_level_0(lad, _storage_factory, "lad")
            bad = _with_empty_level_0(bad, _storage_factory, "bad")
            tree_id = _with_empty_level_0(tree_id, _storage_factory, "tree_id")
            zlad_repaired = True

        resolved_vegetation = {
            "zlad": zlad,
            "zlad_repaired": zlad_repaired,
            "tree_id_from_2d": tree_id_from_2d,
            "unreadable_3d_variables": unreadable_3d,
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
        # No leaves in or above buildings, like palm_csd (overhanging_trees: False)
        resolved_vegetation["lad_removed_in_buildings"] = model.remove_lad_in_building_columns()

        if tree_id is not None:
            max_id = int(tree_id.max())
            if max_id > 0:
                model.next_tree_id = max_id + 1

    return model, nx, ny, res, dz, ori, resolved_vegetation, georef


def Load(filename="output.nc", surface_config=None):
    """Backward-compatible wrapper returning the legacy per-cell dictionary."""
    model, nx, ny, res, dz, ori, resolved_vegetation, georef = LoadModel(
        filename,
        surface_config=surface_config,
    )
    return model.to_legacy_dict(), nx, ny, res, dz, ori, resolved_vegetation, georef

# Variables that survive load and save. Coordinates and georeference
# variables are not read, but SaveModel writes them again.
_SUPPORTED_VARIABLES = {
    "x", "y", "z", "zlad", "crs", "lat", "lon", "E_UTM", "N_UTM",
    "zt", "vegetation_type", "soil_type", "pavement_type", "street_type",
    "water_type", "water_pars", "irrigation_flag", "shf", "ssws",
    "building_id", "building_type", "buildings_2d", "buildings_3d",
    "lad", "bad", "tree_id",
}
_SUPPORTED_VARIABLES.update(name for name, _dims in GridModel.BUILDING_PARAMETER_SPECS)


def _tree_id_from_2d(nc_file, lad, bad, storage_factory):
    """Spread a 2D tree_id (one ID per column) over the voxels with leaves.

    Returns the 3D tree_id and a dict with the number of columns whose ID was
    kept and of columns whose ID had no leaves to sit on, or (None, None) when
    the file has no 2D tree_id of the grid's size.
    """
    var = nc_file.variables.get("tree_id")
    if var is None or tuple(var.shape) != tuple(lad.shape[1:]):
        return None, None
    ids = var[:]
    if hasattr(ids, "filled"):
        ids = ids.filled(0)
    ids = np.where(ids > 0, ids, 0).astype(np.int32)

    tree_id = storage_factory(lad.shape, np.int32, 0, "tree_id")
    has_leaves = np.zeros(ids.shape, dtype=bool)
    for k in range(lad.shape[0]):      # layer by layer, lad may be a file on disk
        leaves = np.asarray(lad[k]) > 0
        if bad is not None:
            leaves |= np.asarray(bad[k]) > 0
        tree_id[k] = np.where(leaves, ids, 0)
        has_leaves |= leaves
    with_id = ids > 0
    return tree_id, {
        "columns": int(np.count_nonzero(with_id & has_leaves)),
        "without_leaves": int(np.count_nonzero(with_id & ~has_leaves)),
    }


def is_old_palmpaint_zlad(zlad, dz):
    """True for the zlad of PALMPaint before 0.5.6: (k + 0.5) dz, without PALM's level 0."""
    zlad = np.asarray(zlad, dtype=np.float64)
    if zlad.size == 0 or dz <= 0:
        return False
    return bool(np.allclose(zlad, (np.arange(zlad.size) + 0.5) * dz, atol=1e-3 * dz))


def _with_empty_level_0(data, storage_factory, name_prefix):
    """Return a copy of a (nz, ny, nx) array with an empty level put in front."""
    if data is None:
        return None
    out = storage_factory((data.shape[0] + 1,) + data.shape[1:], data.dtype, 0, name_prefix)
    out[1:] = data
    return out


def find_unsupported_variables(filename):
    """Return the sorted names of variables in a file that PALMPaint does not save."""
    with Dataset(filename, "r") as nc_file:
        # Index variables like nwater_pars only label a dimension. PALM reads the
        # dimension length, not the variable, so dropping them loses nothing.
        return sorted(
            name for name, var in nc_file.variables.items()
            if name not in _SUPPORTED_VARIABLES and var.dimensions != (name,)
        )
