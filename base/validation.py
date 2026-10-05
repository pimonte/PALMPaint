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


def _id_without_building(model, export_buildings_3d):
    """Cells whose building_id would have no building in the saved file (DRV0034).

    Buildings that exist only in buildings_3d (bridges) are written only with
    Export buildings_3d, and only where the file's voxels are still valid.
    """
    only_in_3d = (model.building_id > 0) & ~(model.building_height > model.FLOAT_FILL)
    if not np.any(only_in_3d) or not export_buildings_3d:
        return only_in_3d
    source = model._file_buildings()
    kept = model.unchanged_building_columns(
        model.building_height, model.building_id, model.building_type, source
    )
    if kept is None:
        return only_in_3d
    has_voxels = np.any(np.asarray(source["source_buildings_3d"]) > 0, axis=0)
    return only_in_3d & ~(kept & has_voxels)


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


def clean_model(model):
    """Clean common static-driver inconsistencies in-place and return a summary.

    Only changes what PALM rejects or what can never be used, plus LAD in
    building columns: like palm_csd (overhanging_trees: False), a driver has no
    leaves in or above a building. Surface types on building cells (the ground
    under bridges) and negative zt are valid for PALM and stay.
    """
    summary = {
        "zt_repaired": 0,
        "soil_cleared_without_vegetation_or_pavement": 0,
        "water_pars_cleared_outside_water": 0,
        "soil_filled_from_surface_config": 0,
        "building_ids_auto_assigned": 0,
        "building_parameters_cleared_outside_buildings": 0,
        "lad_removed_in_buildings": 0,
    }

    invalid_zt_mask = (
        ~np.isfinite(model.zt)
        | np.isclose(model.zt, float(model.FLOAT_FILL))
    )
    summary["zt_repaired"] = int(np.count_nonzero(invalid_zt_mask))
    if summary["zt_repaired"]:
        model.zt[invalid_zt_mask] = 0.0

    has_building = _has_building(model)

    # Soil only under vegetation or pavement, not under water or buildings
    stray_soil_mask = (model.soil_type > model.INT_FILL) & ~(
        (model.vegetation_type > model.INT_FILL) | (model.pavement_type > model.INT_FILL)
    )
    summary["soil_cleared_without_vegetation_or_pavement"] = int(np.count_nonzero(stray_soil_mask))
    model.soil_type[stray_soil_mask] = model.INT_FILL

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

    summary["lad_removed_in_buildings"] = model.remove_lad_in_building_columns()

    return summary


def validate(model, georef=None, export_buildings_3d=True):
    """Check *model* against the rules PALM applies when it reads a static driver.

    Parameters
    ----------
    model : GridModel
        The grid model to validate.
    georef : GeoReference or None, optional
        If supplied, coordinate-range checks (e.g. DRV0001) are also run.
    export_buildings_3d : bool, optional
        Whether buildings_3d is saved. Without it, buildings that exist only in
        3D (bridges) cannot be saved, their building_id is reported (DRV0034).

    Returns
    -------
    dict with keys:
      'valid'        - True if no violations were found
      'violations'   - list of errors: PALM stops or the data is wrong
      'notes'        - list of hints: PALM runs, but the user should know
      'invalid_mask' - boolean numpy array of shape (ny, nx), True for every
                       cell involved in at least one per-cell violation.
                       Global checks (e.g. DRV0001) and notes do not affect it.
      'note_mask'    - boolean numpy array of shape (ny, nx), the cells of the notes

    Errors
    ------
    1. vegetation_type / pavement_type / water_type are mutually exclusive (DRV0024).
    3. If any surface type is used anywhere, every non-building cell
       must have exactly one of the three types (DRV0021 / DRV0022).
    4. water_pars may only be set on water cells.
    5. Vegetation and pavement cells require a soil_type (DRV0023).
    6. On non-building columns with LAD/BAD, a surface type is required.
    7. building_type requires building_id.
    8. building_id values must be positive and <= INT32_MAX.
    9. A building needs a building_type and a building_id, and a building_id
       needs a building (DRV0033 / DRV0034).
    zt must not contain fill values or NaN. Negative zt is fine, PALM
    subtracts the lowest terrain point.
    DRV0001: origin_lon must be in [-180, 180] and origin_lat in [-90, 90].

    Notes
    -----
    LAD/BAD in a building column: PALM counts zlad from the roof there, so
    this vegetation ends up higher than its zlad says. Like palm_csd, PALMPaint
    allows no leaves in or above a building, clean_model() removes them.
    soil_type without vegetation or pavement (water, buildings): PALM ignores
    it, but a clean driver has soil only where there is soil. clean_model()
    removes it.
    Bridge cells whose deck reaches down to the ground: the flow cannot pass
    under them (seen in palmgeo drivers, where the deck height is too low).

    Not checked on purpose, because PALM needs or allows it: surface types on
    building cells. The ground under a bridge needs one (LSM0039), and palm_csd
    writes them for buildings lower than dz.
    """
    violations = []
    notes = []

    INT_FILL   = model.INT_FILL
    FLOAT_FILL = model.FLOAT_FILL

    ny, nx = model.vegetation_type.shape
    invalid_mask = np.zeros((ny, nx), dtype=bool)
    note_mask = np.zeros((ny, nx), dtype=bool)

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

    # zt: no fill values or NaN. Negative values are fine, PALM subtracts the
    # lowest terrain point (topography_mod.f90)
    invalid_zt_mask = (
        ~np.isfinite(model.zt)
        | np.isclose(model.zt, float(FLOAT_FILL))
    )
    n_invalid_zt = int(np.count_nonzero(invalid_zt_mask))
    if n_invalid_zt:
        violations.append(
            f"{n_invalid_zt} cell(s) have invalid zt values "
            "(fill values and NaN/Inf are not allowed)."
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

    # soil_type only where there is soil: under vegetation or pavement
    stray_soil_mask = (model.soil_type > INT_FILL) & ~(has_veg | has_pav)
    n_stray_soil = int(np.count_nonzero(stray_soil_mask))
    if n_stray_soil:
        notes.append(f"{n_stray_soil} cells have soil without vegetation or pavement.")
        note_mask |= stray_soil_mask

    # 6. LAD/BAD in building columns: PALM allows it, PALMPaint does not (like palm_csd).
    rv = model.resolved_vegetation
    lad = None if rv is None else rv.get("lad")
    bad = None if rv is None else rv.get("bad")
    if lad is not None or bad is not None:
        active_2d = np.zeros((ny, nx), dtype=bool)
        if lad is not None:
            active_2d |= np.any(lad > 0, axis=0)
        if bad is not None:
            active_2d |= np.any(bad > 0, axis=0)

        roof_trees_mask = active_2d & (model.building_height > FLOAT_FILL)
        n_roof_trees = int(np.count_nonzero(roof_trees_mask))
        if n_roof_trees:
            notes.append(f"{n_roof_trees} building cells have LAD, Clean Static Driver removes it.")
            note_mask |= roof_trees_mask

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

    # 9. Building, building_type and building_id belong together (PALM DRV0033 / DRV0034)
    has_height = model.building_height > FLOAT_FILL
    height_no_id_mask = has_height & ~has_bld_id
    n_height_no_id = int(np.count_nonzero(height_no_id_mask))
    if n_height_no_id:
        violations.append(
            f"{n_height_no_id} building cell(s) have no building_id "
            "(PALM stops with DRV0034)."
        )
        invalid_mask |= height_no_id_mask

    building_no_type_mask = (has_height | has_bld_id) & ~has_bld_type
    n_building_no_type = int(np.count_nonzero(building_no_type_mask))
    if n_building_no_type:
        violations.append(
            f"{n_building_no_type} building cell(s) have no building_type "
            "(PALM stops with DRV0033)."
        )
        invalid_mask |= building_no_type_mask

    id_no_building_mask = _id_without_building(model, export_buildings_3d)
    n_id_no_building = int(np.count_nonzero(id_no_building_mask))
    if n_id_no_building:
        if export_buildings_3d:
            reason = "and no building voxel from the loaded file"
        else:
            reason = (
                "and exist only in buildings_3d (for example bridges). Export "
                "buildings_3d is switched off, so they are left out of the saved file. "
                "Switch it on in the Extras menu to keep them"
            )
        violations.append(
            f"{n_id_no_building} cell(s) have a building_id but no building height {reason} "
            "(PALM would stop with DRV0034)."
        )
        invalid_mask |= id_no_building_mask

    # Bridges whose deck reaches the ground block the flow below them
    bridge_bottom, _bridge_top = model.bridge_extent()
    blocked_bridge_mask = (bridge_bottom > FLOAT_FILL) & (bridge_bottom <= 0.0)
    n_blocked_bridge = int(np.count_nonzero(blocked_bridge_mask))
    if n_blocked_bridge:
        notes.append(f"{n_blocked_bridge} bridge cells have no free space below the deck.")
        note_mask |= blocked_bridge_mask

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
        "notes": notes,
        "violations": violations,
        "invalid_mask": invalid_mask,
        "note_mask": note_mask,
    }
