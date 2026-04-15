"""
Surface-layer consistency checks for PALMPaint GridModel instances.

All checks are implemented as standalone functions that accept a GridModel
(duck-typed) so this module can grow independently without touching gridmodel.py.

    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

import numpy as np


AUTO_BUILDING_ID_START = np.iinfo(np.int32).max - 1


def _known_building_id_fill_values(model):
    return {
        int(model.INT_FILL),
        int(getattr(model, "BUILDING_ID_FILL", model.INT_FILL)),
    }


def _has_building_id(model):
    return model.building_id > 0


def _has_building(model):
    return _has_building_id(model) | (model.building_height > model.FLOAT_FILL)


def _default_soil_for_surface(model, *, vegetation_type=None, pavement_type=None):
    surface_config = getattr(model, "surface_config", None) or {}
    soil_default = int(surface_config.get("soil", {}).get("default_type", 1))

    if vegetation_type is not None and int(vegetation_type) > model.INT_FILL:
        veg_def = surface_config.get("vegetation", {}).get("types", {}).get(int(vegetation_type), {})
        return int(veg_def.get("soil_type", soil_default))

    if pavement_type is not None and int(pavement_type) > model.INT_FILL:
        pav_def = surface_config.get("pavement", {}).get("types", {}).get(int(pavement_type), {})
        return int(pav_def.get("soil_type", soil_default))

    return soil_default


def _vertical_overlap_with_buildings(model):
    """Return a per-cell mask where LAD/BAD overlaps the building volume."""
    rv = model.resolved_vegetation
    if rv is None:
        return np.zeros(model.vegetation_type.shape, dtype=bool)

    zlad = rv.get("zlad")
    if zlad is None:
        return np.zeros(model.vegetation_type.shape, dtype=bool)

    lad = rv.get("lad")
    bad = rv.get("bad")
    if lad is None and bad is None:
        return np.zeros(model.vegetation_type.shape, dtype=bool)

    active_volume = None
    if lad is not None:
        active_volume = lad > 0
    if bad is not None:
        bad_active = bad > 0
        active_volume = bad_active if active_volume is None else (active_volume | bad_active)

    if active_volume is None or not np.any(active_volume):
        return np.zeros(model.vegetation_type.shape, dtype=bool)

    zlad = np.asarray(zlad, dtype=np.float32)
    overlap_mask = np.zeros(active_volume.shape[1:], dtype=bool)

    source_buildings_3d = rv.get("source_buildings_3d")
    source_buildings_3d_z = rv.get("source_buildings_3d_z")
    if source_buildings_3d is not None and source_buildings_3d_z is not None:
        occupied = np.asarray(source_buildings_3d) > 0
        z3d = np.asarray(source_buildings_3d_z, dtype=np.float32)
        occupied_columns = np.any(occupied, axis=0)
        if np.any(occupied_columns):
            top_indices = np.argmax(occupied[::-1], axis=0)
            top_indices = occupied.shape[0] - 1 - top_indices
            top_z = z3d[top_indices]
            active_below_top = active_volume & (zlad[:, np.newaxis, np.newaxis] <= top_z[np.newaxis, :, :])
            overlap_mask = occupied_columns & np.any(active_below_top, axis=0)
        return overlap_mask

    active_below_height = active_volume & (
        zlad[:, np.newaxis, np.newaxis] <= model.building_height[np.newaxis, :, :]
    )
    has_building_height = model.building_height > model.FLOAT_FILL
    return has_building_height & np.any(active_below_height, axis=0)


def _vegetation_overlap_voxels(model):
    """Return a 3-D mask where LAD/BAD intersects the building volume."""
    rv = model.resolved_vegetation
    if rv is None:
        return None

    zlad = rv.get("zlad")
    if zlad is None:
        return None

    lad = rv.get("lad")
    bad = rv.get("bad")
    if lad is None and bad is None:
        return None

    active_volume = None
    if lad is not None:
        active_volume = lad > 0
    if bad is not None:
        bad_active = bad > 0
        active_volume = bad_active if active_volume is None else (active_volume | bad_active)

    if active_volume is None:
        return None

    zlad = np.asarray(zlad, dtype=np.float32)
    source_buildings_3d = rv.get("source_buildings_3d")
    source_buildings_3d_z = rv.get("source_buildings_3d_z")
    if source_buildings_3d is not None and source_buildings_3d_z is not None:
        occupied = np.asarray(source_buildings_3d) > 0
        z3d = np.asarray(source_buildings_3d_z, dtype=np.float32)
        occupied_columns = np.any(occupied, axis=0)
        if not np.any(occupied_columns):
            return np.zeros_like(active_volume, dtype=bool)
        top_indices = np.argmax(occupied[::-1], axis=0)
        top_indices = occupied.shape[0] - 1 - top_indices
        top_z = z3d[top_indices]
        return active_volume & occupied_columns[np.newaxis, :, :] & (
            zlad[:, np.newaxis, np.newaxis] <= top_z[np.newaxis, :, :]
        )

    has_building_height = model.building_height > model.FLOAT_FILL
    return active_volume & has_building_height[np.newaxis, :, :] & (
        zlad[:, np.newaxis, np.newaxis] <= model.building_height[np.newaxis, :, :]
    )


def clean_model(model):
    """Clean common static-driver inconsistencies in-place and return a summary."""
    summary = {
        "zt_repaired": 0,
        "vegetation_voxels_cleared_in_buildings": 0,
        "vegetation_columns_cleared_in_buildings": 0,
        "tree_ids_cleared_in_buildings": 0,
        "soil_cleared_under_water_or_buildings": 0,
        "surface_types_cleared_on_buildings": 0,
        "water_pars_cleared_outside_water": 0,
        "soil_filled_from_surface_config": 0,
        "building_ids_auto_assigned": 0,
        "building_parameters_cleared_outside_buildings": 0,
    }

    invalid_zt_mask = (
        ~np.isfinite(model.zt)
        | np.isclose(model.zt, float(model.FLOAT_FILL))
        | (np.asarray(model.zt, dtype=np.float32) < 0.0)
    )
    summary["zt_repaired"] = int(np.count_nonzero(invalid_zt_mask))
    if summary["zt_repaired"]:
        model.zt[invalid_zt_mask] = 0.0

    has_building = _has_building(model)
    has_veg = model.vegetation_type > model.INT_FILL
    has_pav = model.pavement_type > model.INT_FILL
    has_wat = model.water_type > model.INT_FILL

    overlap_voxels = _vegetation_overlap_voxels(model)
    if overlap_voxels is not None and np.any(overlap_voxels):
        rv_candidates = [model.resolved_vegetation]
        loaded_rv = getattr(model, "_loaded_rv", None)
        if loaded_rv is not None and loaded_rv is not model.resolved_vegetation:
            rv_candidates.append(loaded_rv)

        affected_columns = np.any(overlap_voxels, axis=0)
        summary["vegetation_columns_cleared_in_buildings"] = int(np.count_nonzero(affected_columns))

        for rv in rv_candidates:
            lad = rv.get("lad")
            bad = rv.get("bad")
            tree_id = rv.get("tree_id")

            if lad is not None:
                lad_clear = overlap_voxels & (lad > 0)
                summary["vegetation_voxels_cleared_in_buildings"] += int(np.count_nonzero(lad_clear))
                lad[lad_clear] = 0.0

            if bad is not None:
                bad_clear = overlap_voxels & (bad > 0)
                summary["vegetation_voxels_cleared_in_buildings"] += int(np.count_nonzero(bad_clear))
                bad[bad_clear] = 0.0

            if tree_id is not None:
                tree_clear = overlap_voxels & (tree_id > 0)
                summary["tree_ids_cleared_in_buildings"] += int(np.count_nonzero(tree_clear))
                tree_id[tree_clear] = 0

        if len(rv_candidates) > 1:
            summary["vegetation_voxels_cleared_in_buildings"] //= len(rv_candidates)
            summary["tree_ids_cleared_in_buildings"] //= len(rv_candidates)

    wrong_soil_mask = (has_building | has_wat) & (model.soil_type > model.INT_FILL)
    summary["soil_cleared_under_water_or_buildings"] = int(np.count_nonzero(wrong_soil_mask))
    model.soil_type[wrong_soil_mask] = model.INT_FILL

    surface_clear_mask = has_building & (has_veg | has_pav | has_wat)
    summary["surface_types_cleared_on_buildings"] = int(np.count_nonzero(surface_clear_mask))
    model.vegetation_type[surface_clear_mask] = model.INT_FILL
    model.pavement_type[surface_clear_mask] = model.INT_FILL
    model.water_type[surface_clear_mask] = model.INT_FILL

    water_pars_set = np.any(model.water_pars > model.FLOAT_FILL, axis=0)
    orphan_wp_mask = water_pars_set & ~(model.water_type > model.INT_FILL)
    summary["water_pars_cleared_outside_water"] = int(np.count_nonzero(orphan_wp_mask))
    model.water_pars[:, orphan_wp_mask] = model.FLOAT_FILL

    building_param_masks = []
    for name, _dim_names in getattr(model, "BUILDING_PARAMETER_SPECS", ()):
        arr = model.building_pars[name]
        active = np.any(arr > model.FLOAT_FILL, axis=tuple(range(arr.ndim - 2)))
        building_param_masks.append(active)
    if building_param_masks:
        building_params_set = np.logical_or.reduce(building_param_masks)
        orphan_building_param_mask = building_params_set & ~has_building
        summary["building_parameters_cleared_outside_buildings"] = int(np.count_nonzero(orphan_building_param_mask))
        model.clear_building_parameters_where(orphan_building_param_mask)

    has_veg = model.vegetation_type > model.INT_FILL
    has_pav = model.pavement_type > model.INT_FILL
    no_soil_mask = (has_veg | has_pav) & (model.soil_type <= model.INT_FILL)
    if np.any(no_soil_mask):
        rows, cols = np.where(no_soil_mask)
        for row, col in zip(rows, cols):
            vegetation_type = int(model.vegetation_type[row, col])
            pavement_type = int(model.pavement_type[row, col])
            model.soil_type[row, col] = _default_soil_for_surface(
                model,
                vegetation_type=vegetation_type if vegetation_type > model.INT_FILL else None,
                pavement_type=pavement_type if pavement_type > model.INT_FILL else None,
            )
        summary["soil_filled_from_surface_config"] = len(rows)

    has_bld_type = model.building_type > model.INT_FILL
    has_bld_id = _has_building_id(model)
    type_no_id_mask = has_bld_type & ~has_bld_id
    n_auto = int(np.count_nonzero(type_no_id_mask))
    if n_auto:
        used_ids = set(int(v) for v in model.building_id[model.building_id > 0].tolist())
        auto_id = AUTO_BUILDING_ID_START
        while auto_id in used_ids and auto_id > 0:
            auto_id -= 1
        rows, cols = np.where(type_no_id_mask)
        for row, col in zip(rows, cols):
            model.building_id[row, col] = auto_id
        summary["building_ids_auto_assigned"] = n_auto

    return summary


def validate(model, georef=None):
    """Check surface-layer consistency rules for *model*.

    Parameters
    ----------
    model : GridModel
        The grid model to validate.
    georef : GeoReference or None, optional
        If supplied, coordinate-range checks (e.g. DRV0001) are also run.

    Returns
    -------
    dict with keys:
      'valid'        – True if no violations were found
      'violations'   – list of human-readable violation strings
      'invalid_mask' – boolean numpy array of shape (ny, nx); True for every
                       cell that is involved in at least one per-cell rule
                       violation.  Global checks (e.g. DRV0001) have no
                       associated cells and do not affect this mask.

    Rules enforced
    --------------
    1. vegetation_type / pavement_type / water_type are mutually exclusive.
    2. Building cells must not also carry a surface type.
    3. If any surface type is used anywhere, every non-building cell
       must have exactly one of the three types (no bare fill allowed).
    4. water_pars may only be set on water cells.
    5. Vegetation and pavement cells require a soil_type.
       Building and water cells must have soil_type = fill.
    6. LAD/BAD data may be above buildings, but must not intersect the
       building volume. On non-building columns, a surface type is required.
    7. building_type requires building_id.
    8. building_id values must be positive and ≤ INT32_MAX.
    DRV0001: origin_lon must be in [-180, 180] and origin_lat in [-90, 90].
    """
    violations = []

    INT_FILL   = model.INT_FILL
    FLOAT_FILL = model.FLOAT_FILL

    ny, nx = model.vegetation_type.shape
    invalid_mask = np.zeros((ny, nx), dtype=bool)

    # Building IDs are valid only when they are strictly positive. In practice we
    # also see multiple legacy fill conventions for "unset" cells, most commonly
    # -127 and -9999.
    known_building_id_fill_values = _known_building_id_fill_values(model)
    has_bld_id = _has_building_id(model)
    invalid_bld_id_mask = (model.building_id <= 0)
    explicit_invalid_bld_id_mask = invalid_bld_id_mask & ~np.isin(
        model.building_id,
        tuple(known_building_id_fill_values),
    )

    has_building = _has_building(model)
    has_veg = model.vegetation_type > INT_FILL
    has_pav = model.pavement_type   > INT_FILL
    has_wat = model.water_type      > INT_FILL

    # 1. Mutual exclusivity
    invalid_zt_mask = (
        ~np.isfinite(model.zt)
        | np.isclose(model.zt, float(FLOAT_FILL))
        | (np.asarray(model.zt, dtype=np.float32) < 0.0)
    )
    n_invalid_zt = int(np.count_nonzero(invalid_zt_mask))
    if n_invalid_zt:
        violations.append(
            f"{n_invalid_zt} cell(s) have invalid zt values "
            "(fill values, NaN/Inf, or negative terrain heights are not allowed)."
        )
        invalid_mask |= invalid_zt_mask

    # 1. Mutual exclusivity
    overlap_mask = (has_veg & has_pav) | (has_veg & has_wat) | (has_pav & has_wat)
    n_overlap = int(np.count_nonzero(overlap_mask))
    if n_overlap:
        violations.append(
            f"{n_overlap} cell(s) have more than one surface type set "
            "(vegetation / pavement / water are mutually exclusive)."
        )
        invalid_mask |= overlap_mask

    # 2. Building cells must not carry a surface type
    bld_surface_mask = has_building & (has_veg | has_pav | has_wat)
    n_bld_surface = int(np.count_nonzero(bld_surface_mask))
    if n_bld_surface:
        violations.append(
            f"{n_bld_surface} building cell(s) also have a surface type set "
            "(surface type must be fill on building cells)."
        )
        invalid_mask |= bld_surface_mask

    # 3. Completeness: once any surface type is used, no non-building cell
    #    may remain without one
    if np.any(has_veg | has_pav | has_wat):
        missing_mask = ~has_building & ~has_veg & ~has_pav & ~has_wat
        n_missing = int(np.count_nonzero(missing_mask))
        if n_missing:
            violations.append(
                f"{n_missing} non-building cell(s) have no surface type "
                "(all non-building cells must have vegetation, pavement, or "
                "water when at least one surface type is in use)."
            )
            invalid_mask |= missing_mask

    # 4. water_pars only on water cells
    water_pars_set = np.any(model.water_pars > FLOAT_FILL, axis=0)
    orphan_wp_mask = water_pars_set & ~has_wat
    n_orphan_wp = int(np.count_nonzero(orphan_wp_mask))
    if n_orphan_wp:
        violations.append(
            f"{n_orphan_wp} cell(s) have water_pars set but no water_type."
        )
        invalid_mask |= orphan_wp_mask

    # 5a. Vegetation / pavement cells need soil_type
    no_soil_mask = (has_veg | has_pav) & (model.soil_type <= INT_FILL)
    n_no_soil = int(np.count_nonzero(no_soil_mask))
    if n_no_soil:
        violations.append(
            f"{n_no_soil} vegetation/pavement cell(s) are missing a soil_type."
        )
        invalid_mask |= no_soil_mask

    # 5b. Building / water cells must have soil_type = fill
    wrong_soil_mask = (has_building | has_wat) & (model.soil_type > INT_FILL)
    n_wrong_soil = int(np.count_nonzero(wrong_soil_mask))
    if n_wrong_soil:
        violations.append(
            f"{n_wrong_soil} building/water cell(s) have a soil_type set "
            "(soil_type must be fill on building and water cells)."
        )
        invalid_mask |= wrong_soil_mask

    # 6. LAD/BAD data may be above buildings, but must not overlap them.
    rv = model.resolved_vegetation
    lad = None if rv is None else rv.get("lad")
    bad = None if rv is None else rv.get("bad")
    if lad is not None or bad is not None:
        active_2d = np.zeros((ny, nx), dtype=bool)
        if lad is not None:
            active_2d |= np.any(lad > 0, axis=0)
        if bad is not None:
            active_2d |= np.any(bad > 0, axis=0)

        overlap_trees_mask = _vertical_overlap_with_buildings(model)
        n_overlap_trees = int(np.count_nonzero(overlap_trees_mask))
        if n_overlap_trees:
            violations.append(
                f"{n_overlap_trees} cell(s) have LAD/BAD inside the building volume "
                "(resolved vegetation may be above buildings, but not inside them)."
            )
            invalid_mask |= overlap_trees_mask

        orphan_trees_mask = active_2d & ~(has_veg | has_pav | has_wat) & ~has_building
        n_orphan_trees = int(np.count_nonzero(orphan_trees_mask))
        if n_orphan_trees:
            violations.append(
                f"{n_orphan_trees} cell(s) have LAD/BAD set but no surface type "
                "and no building column beneath them."
            )
            invalid_mask |= orphan_trees_mask

    # 7. building_type requires building_id
    has_bld_type = model.building_type > INT_FILL
    type_no_id_mask = has_bld_type & ~has_bld_id
    n_type_no_id = int(np.count_nonzero(type_no_id_mask))
    if n_type_no_id:
        violations.append(
            f"{n_type_no_id} cell(s) have a building_type set but no building_id "
            "(building_id is required whenever building_type is provided)."
        )
        invalid_mask |= type_no_id_mask

    # 8. building_id values must fit in a signed 32-bit integer (1 … 2 147 483 647)
    INT32_MAX = np.iinfo(np.int32).max   # 2 147 483 647
    n_nonpositive = int(np.count_nonzero(explicit_invalid_bld_id_mask))
    if n_nonpositive:
        violations.append(
            f"{n_nonpositive} cell(s) have a building_id ≤ 0. "
            "Building IDs must be positive integers."
        )
        invalid_mask |= explicit_invalid_bld_id_mask

    overflow_mask = has_bld_id & (model.building_id > INT32_MAX)
    n_overflow = int(np.count_nonzero(overflow_mask))
    if n_overflow:
        violations.append(
            f"{n_overflow} cell(s) have a building_id > {INT32_MAX} "
            "(maximum value representable as a signed 32-bit integer). "
            "This can cause errors in PALM's building processing."
        )
        invalid_mask |= overflow_mask

    # DRV0001 — coordinate range check (global, no per-cell coordinates)
    if georef is not None:
        lon = getattr(georef, "origin_lon", None)
        lat = getattr(georef, "origin_lat", None)
        if lon is not None and not (-180.0 <= float(lon) <= 180.0):
            violations.append(
                f"DRV0001 [ERROR]: origin_lon = {lon:.6f} is outside the allowed "
                "range [-180.0, 180.0]."
            )
        if lat is not None and not (-90.0 <= float(lat) <= 90.0):
            violations.append(
                f"DRV0001 [ERROR]: origin_lat = {lat:.6f} is outside the allowed "
                "range [-90.0, 90.0]."
            )

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "invalid_mask": invalid_mask,
    }
