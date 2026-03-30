"""
PALM-compatible topography preflight helpers for PALMPaint.

The routines in this module intentionally mirror PALMPaint's current
constant-dz assumptions instead of trying to cover the full PALM vertical-grid
feature set.
"""

from __future__ import annotations

from collections import deque

import numpy as np


DEFAULT_BUILDING_TYPE = 1
CAVITY_THRESHOLD = 9


def _four_neighbors(row, col, ny, nx):
    if row > 0:
        yield row - 1, col
    if row + 1 < ny:
        yield row + 1, col
    if col > 0:
        yield row, col - 1
    if col + 1 < nx:
        yield row, col + 1


def _normalize_zt_array(zt, float_fill):
    arr = np.asarray(zt, dtype=np.float32).copy()
    invalid_mask = ~np.isfinite(arr) | np.isclose(arr, float(float_fill)) | (arr < 0.0)
    arr[invalid_mask] = 0.0
    return arr, invalid_mask


def _normalize_building_heights(building_height, float_fill):
    arr = np.asarray(building_height, dtype=np.float32).copy()
    invalid_mask = ~np.isfinite(arr) | np.isclose(arr, float(float_fill)) | (arr < 0.0)
    arr[invalid_mask] = float(float_fill)
    return arr


def _building_footprint(building_id, building_height, float_fill):
    height = np.asarray(building_height, dtype=np.float32)
    return (np.asarray(building_id) > 0) & np.isfinite(height) & (height > 0.0)


def find_building_components(building_id, building_height, float_fill):
    """Return connected 4-neighbour components for each positive building ID."""
    building_id = np.asarray(building_id)
    footprint = _building_footprint(building_id, building_height, float_fill)
    ny, nx = building_id.shape
    visited = np.zeros((ny, nx), dtype=bool)
    components = {}

    rows, cols = np.where(footprint)
    for row, col in zip(rows.tolist(), cols.tolist()):
        if visited[row, col]:
            continue
        bid = int(building_id[row, col])
        queue = deque([(row, col)])
        visited[row, col] = True
        cells = []
        while queue:
            cr, cc = queue.popleft()
            cells.append((cr, cc))
            for nr, nc in _four_neighbors(cr, cc, ny, nx):
                if visited[nr, nc]:
                    continue
                if footprint[nr, nc] and int(building_id[nr, nc]) == bid:
                    visited[nr, nc] = True
                    queue.append((nr, nc))
        components.setdefault(bid, []).append(cells)

    return components


def analyze_building_groups(zt, building_id, building_height, building_type, float_fill):
    """Inspect building groups for disconnected IDs and PALM oro_max effects."""
    zt = np.asarray(zt, dtype=np.float32)
    building_id = np.asarray(building_id)
    building_height = np.asarray(building_height, dtype=np.float32)
    building_type = np.asarray(building_type)
    components_by_id = find_building_components(building_id, building_height, float_fill)

    ny, nx = building_id.shape
    disconnected_mask = np.zeros((ny, nx), dtype=bool)
    altered_mask = np.zeros((ny, nx), dtype=bool)
    disconnected_ids = []
    altered_group_ids = []

    for bid, components in components_by_id.items():
        if len(components) > 1:
            disconnected_ids.append(bid)
            for cells in components:
                for row, col in cells:
                    disconnected_mask[row, col] = True

        component_requires_change = False
        for cells in components:
            cell_rows = np.array([row for row, _ in cells], dtype=int)
            cell_cols = np.array([col for _, col in cells], dtype=int)
            local_types = building_type[cell_rows, cell_cols]
            if np.all(local_types == 7):
                continue
            local_zt = zt[cell_rows, cell_cols]
            if local_zt.size > 0 and np.any(np.abs(local_zt - np.max(local_zt)) > 1e-6):
                component_requires_change = True
                altered_mask[cell_rows, cell_cols] = True

        if component_requires_change:
            altered_group_ids.append(bid)

    return {
        "components_by_id": components_by_id,
        "disconnected_mask": disconnected_mask,
        "altered_mask": altered_mask,
        "disconnected_ids": disconnected_ids,
        "altered_group_ids": altered_group_ids,
        "disconnected_group_count": len(disconnected_ids),
        "disconnected_cell_count": int(np.count_nonzero(disconnected_mask)),
        "terrain_adjust_group_count": len(altered_group_ids),
        "terrain_adjust_cell_count": int(np.count_nonzero(altered_mask)),
    }


def _next_unused_building_id(building_id):
    used = set(int(value) for value in np.asarray(building_id)[np.asarray(building_id) > 0].tolist())
    next_id = 1
    while next_id in used:
        next_id += 1
    return next_id, used


def split_disconnected_building_ids(building_id, building_height, building_type, float_fill):
    """Split duplicated building IDs by 4-connected footprint components."""
    building_id = np.asarray(building_id)
    building_height = np.asarray(building_height, dtype=np.float32)
    building_type = np.asarray(building_type)
    result = np.array(building_id, copy=True)
    components_by_id = find_building_components(building_id, building_height, float_fill)
    split_mask = np.zeros(building_id.shape, dtype=bool)

    next_id, used = _next_unused_building_id(result)
    split_groups = 0
    split_components = 0
    split_cells = 0

    for bid, components in components_by_id.items():
        if len(components) <= 1:
            continue
        split_groups += 1
        for cells in components[1:]:
            while next_id in used:
                next_id += 1
            used.add(next_id)
            split_components += 1
            split_cells += len(cells)
            for row, col in cells:
                result[row, col] = next_id
                split_mask[row, col] = True
            next_id += 1

    return result, {
        "split_mask": split_mask,
        "split_group_count": split_groups,
        "split_component_count": split_components,
        "split_cell_count": split_cells,
    }


def normalize_building_terrain(zt, building_id, building_height, building_type, float_fill):
    """Raise terrain under each connected building group to PALM's oro_max."""
    zt = np.asarray(zt, dtype=np.float32).copy()
    building_type = np.asarray(building_type)
    components_by_id = find_building_components(building_id, building_height, float_fill)
    changed_mask = np.zeros(zt.shape, dtype=bool)

    for _bid, components in components_by_id.items():
        for cells in components:
            cell_rows = np.array([row for row, _ in cells], dtype=int)
            cell_cols = np.array([col for _, col in cells], dtype=int)
            local_types = building_type[cell_rows, cell_cols]
            if np.all(local_types == 7):
                continue
            target = float(np.max(zt[cell_rows, cell_cols]))
            diff_mask = np.abs(zt[cell_rows, cell_cols] - target) > 1e-6
            if np.any(diff_mask):
                zt[cell_rows, cell_cols] = target
                changed_mask[cell_rows[diff_mask], cell_cols[diff_mask]] = True

    return zt, {
        "changed_mask": changed_mask,
        "changed_group_count": len(np.unique(np.asarray(building_id)[changed_mask])) if np.any(changed_mask) else 0,
        "changed_cell_count": int(np.count_nonzero(changed_mask)),
    }


def _infer_column_building_labels(building_id, building_type, footprint, int_fill=-127):
    id_arr = np.asarray(building_id)
    type_arr = np.asarray(building_type)
    col_id = np.where(footprint, id_arr, int_fill).astype(id_arr.dtype, copy=False)
    col_type = np.where(footprint, type_arr, int_fill).astype(type_arr.dtype, copy=False)
    return np.array(col_id, copy=True), np.array(col_type, copy=True)


def _build_topography_classification(zt, building_height, building_id, building_type, dz, float_fill):
    zt = np.asarray(zt, dtype=np.float32)
    building_height = np.asarray(building_height, dtype=np.float32)
    building_id = np.asarray(building_id)
    ny, nx = zt.shape
    step = float(dz) if float(dz) > 0.0 else 1.0

    footprint = _building_footprint(building_id, building_height, float_fill)
    top_height = np.array(zt, copy=True)
    top_height[footprint] = zt[footprint] + np.maximum(building_height[footprint], 0.0)
    max_top = float(np.max(top_height)) if top_height.size else 0.0
    nz = max(1, int(np.ceil(max_top / step)))

    z_centers = (np.arange(nz, dtype=np.float32) + 0.5) * step
    classes = np.zeros((nz, ny, nx), dtype=np.int8)

    terrain_mask = z_centers[:, np.newaxis, np.newaxis] <= zt[np.newaxis, :, :]
    classes[terrain_mask] = 1

    building_mask = (
        footprint[np.newaxis, :, :]
        & (z_centers[:, np.newaxis, np.newaxis] > zt[np.newaxis, :, :])
        & (z_centers[:, np.newaxis, np.newaxis] <= (zt + np.maximum(building_height, 0.0))[np.newaxis, :, :])
    )
    classes[building_mask] = 2

    column_building_id, column_building_type = _infer_column_building_labels(
        building_id, building_type, footprint
    )
    return classes, column_building_id, column_building_type, step


def _inherit_building_label(row, col, building_id, building_type):
    ny, nx = building_id.shape
    for nr, nc in _four_neighbors(row, col, ny, nx):
        if int(building_id[nr, nc]) > 0:
            return int(building_id[nr, nc]), int(building_type[nr, nc]) if int(building_type[nr, nc]) > -127 else DEFAULT_BUILDING_TYPE
    return None, None


def apply_topography_filters(zt, building_height, building_id, building_type, dz, float_fill, int_fill):
    """Apply PALM-style hole and cavity filtering to a discrete constant-dz mask."""
    classes, col_building_id, col_building_type, step = _build_topography_classification(
        zt, building_height, building_id, building_type, dz, float_fill
    )
    nz, ny, nx = classes.shape
    hole_fills = 0
    hole_sweeps = 0
    hole_fill_mask = np.zeros((nz, ny, nx), dtype=bool)

    changed = True
    while changed:
        changed = False
        sweep_fills = []
        for k in range(nz):
            for row in range(ny):
                for col in range(nx):
                    if classes[k, row, col] != 0:
                        continue
                    walls = 0
                    if row > 0 and classes[k, row - 1, col] != 0:
                        walls += 1
                    if row + 1 < ny and classes[k, row + 1, col] != 0:
                        walls += 1
                    if col > 0 and classes[k, row, col - 1] != 0:
                        walls += 1
                    if col + 1 < nx and classes[k, row, col + 1] != 0:
                        walls += 1
                    if k > 0 and classes[k - 1, row, col] != 0:
                        walls += 1
                    if k + 1 < nz and classes[k + 1, row, col] != 0:
                        walls += 1
                    if walls >= 4:
                        bid = int(col_building_id[row, col])
                        btype = int(col_building_type[row, col])
                        if bid <= 0:
                            inherited_id, inherited_type = _inherit_building_label(
                                row, col, col_building_id, col_building_type
                            )
                            if inherited_id is not None:
                                bid = inherited_id
                                btype = inherited_type
                                col_building_id[row, col] = bid
                                col_building_type[row, col] = btype
                        fill_class = 2 if bid > 0 else 1
                        sweep_fills.append((k, row, col, fill_class))
        if sweep_fills:
            hole_sweeps += 1
            hole_fills += len(sweep_fills)
            for k, row, col, fill_class in sweep_fills:
                classes[k, row, col] = fill_class
                hole_fill_mask[k, row, col] = True
            changed = True

    cavity_fill_mask = np.zeros((nz, ny, nx), dtype=bool)
    cavity_count = 0

    for k in range(1, nz):
        visited = np.zeros((ny, nx), dtype=bool)
        for row in range(ny):
            for col in range(nx):
                if visited[row, col] or classes[k, row, col] != 0:
                    continue
                region = []
                queue = deque([(row, col)])
                visited[row, col] = True
                touches_boundary = False
                while queue and len(region) < CAVITY_THRESHOLD:
                    cr, cc = queue.popleft()
                    region.append((cr, cc))
                    if cr == 0 or cc == 0 or cr == ny - 1 or cc == nx - 1:
                        touches_boundary = True
                    for nr, nc in _four_neighbors(cr, cc, ny, nx):
                        if visited[nr, nc] or classes[k, nr, nc] != 0:
                            continue
                        visited[nr, nc] = True
                        queue.append((nr, nc))
                if queue:
                    touches_boundary = True
                    while queue:
                        cr, cc = queue.popleft()
                        region.append((cr, cc))
                        for nr, nc in _four_neighbors(cr, cc, ny, nx):
                            if visited[nr, nc] or classes[k, nr, nc] != 0:
                                continue
                            visited[nr, nc] = True
                            queue.append((nr, nc))
                if touches_boundary or len(region) >= CAVITY_THRESHOLD:
                    continue
                below_solid = all(classes[k - 1, rr, cc] != 0 for rr, cc in region)
                if not below_solid:
                    continue
                cavity_count += 1
                for rr, cc in region:
                    fill_class = 2 if int(col_building_id[rr, cc]) > 0 else 1
                    classes[k, rr, cc] = fill_class
                    cavity_fill_mask[k, rr, cc] = True

    new_zt = np.zeros((ny, nx), dtype=np.float32)
    new_building_height = np.full((ny, nx), float(float_fill), dtype=np.float32)
    new_building_id = np.array(building_id, copy=True)
    new_building_type = np.array(building_type, copy=True)
    surface_only_mask = (np.asarray(building_id) > 0) & np.isfinite(building_height) & np.isclose(
        np.asarray(building_height, dtype=np.float32), 0.0
    )

    for row in range(ny):
        for col in range(nx):
            terrain_levels = np.where(classes[:, row, col] == 1)[0]
            building_levels = np.where(classes[:, row, col] == 2)[0]

            if terrain_levels.size:
                new_zt[row, col] = float((terrain_levels.max() + 1) * step)

            if building_levels.size:
                top = float((building_levels.max() + 1) * step)
                new_building_height[row, col] = max(0.0, top - new_zt[row, col])
                if int(new_building_id[row, col]) <= 0:
                    inferred_id, inferred_type = _inherit_building_label(
                        row, col, new_building_id, new_building_type
                    )
                    new_building_id[row, col] = inferred_id if inferred_id is not None else 1
                    new_building_type[row, col] = (
                        inferred_type if inferred_type is not None else DEFAULT_BUILDING_TYPE
                    )
                elif int(new_building_type[row, col]) <= int(int_fill):
                    new_building_type[row, col] = DEFAULT_BUILDING_TYPE
            else:
                if surface_only_mask[row, col]:
                    new_building_height[row, col] = 0.0
                else:
                    new_building_height[row, col] = float(float_fill)
                    new_building_id[row, col] = int_fill
                    new_building_type[row, col] = int_fill

    return {
        "zt": new_zt,
        "building_height": new_building_height,
        "building_id": new_building_id,
        "building_type": new_building_type,
        "hole_fill_count": hole_fills,
        "hole_sweeps": hole_sweeps,
        "hole_fill_columns": np.any(hole_fill_mask, axis=0),
        "cavity_fill_count": cavity_count,
        "cavity_fill_voxels": int(np.count_nonzero(cavity_fill_mask)),
        "cavity_fill_columns": np.any(cavity_fill_mask, axis=0),
    }


def preview_split_building_ids(model):
    """Preview splitting duplicated building IDs across disconnected footprints."""
    cleaned_bh = np.vectorize(
        lambda value: model.quantize_building_height(value, model.dz), otypes=[np.float32]
    )(_normalize_building_heights(model.building_height, model.FLOAT_FILL))
    split_ids, split_summary = split_disconnected_building_ids(
        model.building_id, cleaned_bh, model.building_type, model.FLOAT_FILL
    )
    return {
        "summary": {
            "building_ids_split_groups": int(split_summary["split_group_count"]),
            "building_ids_split_components": int(split_summary["split_component_count"]),
            "building_ids_split_cells": int(split_summary["split_cell_count"]),
        },
        "preview": {"building_id": split_ids},
    }


def apply_split_building_ids(model):
    """Apply ID splitting across disconnected building footprints."""
    result = preview_split_building_ids(model)
    model.building_id[:, :] = result["preview"]["building_id"]
    return result


def preview_align_building_terrain(model):
    """Preview terrain alignment to per-building oro_max groups."""
    cleaned_zt, invalid_zt_mask = _normalize_zt_array(model.zt, model.FLOAT_FILL)
    cleaned_zt = np.vectorize(
        lambda value: model.quantize_terrain_height(value, model.dz), otypes=[np.float32]
    )(cleaned_zt)
    cleaned_bh = np.vectorize(
        lambda value: model.quantize_building_height(value, model.dz), otypes=[np.float32]
    )(_normalize_building_heights(model.building_height, model.FLOAT_FILL))
    normalized_zt, terrain_summary = normalize_building_terrain(
        cleaned_zt, model.building_id, cleaned_bh, model.building_type, model.FLOAT_FILL
    )
    return {
        "summary": {
            "zt_repaired": int(np.count_nonzero(invalid_zt_mask)),
            "terrain_adjusted_groups": int(terrain_summary["changed_group_count"]),
            "terrain_adjusted_cells": int(terrain_summary["changed_cell_count"]),
        },
        "preview": {"zt": normalized_zt},
    }


def apply_align_building_terrain(model):
    """Apply terrain alignment to per-building oro_max groups."""
    result = preview_align_building_terrain(model)
    model.zt[:, :] = result["preview"]["zt"]
    return result


def preview_filter_sweep(model):
    """Preview PALM-style hole and cavity filtering without ID/terrain preprocessing."""
    cleaned_zt, invalid_zt_mask = _normalize_zt_array(model.zt, model.FLOAT_FILL)
    cleaned_zt = np.vectorize(
        lambda value: model.quantize_terrain_height(value, model.dz), otypes=[np.float32]
    )(cleaned_zt)
    cleaned_bh = np.vectorize(
        lambda value: model.quantize_building_height(value, model.dz), otypes=[np.float32]
    )(_normalize_building_heights(model.building_height, model.FLOAT_FILL))
    filter_result = apply_topography_filters(
        cleaned_zt,
        cleaned_bh,
        model.building_id,
        model.building_type,
        model.dz,
        model.FLOAT_FILL,
        model.INT_FILL,
    )
    preview_mask = filter_result["hole_fill_columns"] | filter_result["cavity_fill_columns"]
    return {
        "summary": {
            "zt_repaired": int(np.count_nonzero(invalid_zt_mask)),
            "hole_fills": int(filter_result["hole_fill_count"]),
            "hole_fill_sweeps": int(filter_result["hole_sweeps"]),
            "narrow_cavities_filled": int(filter_result["cavity_fill_count"]),
            "narrow_cavity_voxels_filled": int(filter_result["cavity_fill_voxels"]),
            "preview_changed_cells": int(np.count_nonzero(preview_mask)),
        },
        "preview": {
            "zt": filter_result["zt"],
            "building_height": filter_result["building_height"],
            "building_id": filter_result["building_id"],
            "building_type": filter_result["building_type"],
        },
        "preview_mask": preview_mask,
    }


def apply_filter_sweep(model):
    """Apply PALM-style hole and cavity filtering without ID/terrain preprocessing."""
    result = preview_filter_sweep(model)
    original_building_mask = _building_footprint(model.building_id, model.building_height, model.FLOAT_FILL)
    new_building_mask = _building_footprint(
        result["preview"]["building_id"],
        result["preview"]["building_height"],
        model.FLOAT_FILL,
    ) & ~original_building_mask

    model.zt[:, :] = result["preview"]["zt"]
    model.building_height[:, :] = result["preview"]["building_height"]
    model.building_id[:, :] = result["preview"]["building_id"]
    model.building_type[:, :] = result["preview"]["building_type"]
    if np.any(new_building_mask):
        model.soil_type[new_building_mask] = model.INT_FILL
        model.vegetation_type[new_building_mask] = model.INT_FILL
        model.pavement_type[new_building_mask] = model.INT_FILL
        model.water_type[new_building_mask] = model.INT_FILL

    result["summary"]["new_building_cells"] = int(np.count_nonzero(new_building_mask))
    return result
