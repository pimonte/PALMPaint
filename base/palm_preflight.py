"""
PALM-compatible topography preflight helpers for PALMPaint.

The routines in this module intentionally mirror PALMPaint's current
constant-dz assumptions instead of trying to cover the full PALM vertical-grid
feature set.
"""

from __future__ import annotations

from collections import deque

import numpy as np
from base.building_config import default_building_type


CAVITY_THRESHOLD = 9


def _default_building_type(surface_config):
    return default_building_type()


def _building_footprint(building_id, building_height, float_fill):
    height = np.asarray(building_height, dtype=np.float32)
    return (np.asarray(building_id) > 0) & np.isfinite(height) & (height > 0.0)


def _infer_column_building_labels(building_id, building_type, footprint, int_fill=-127):
    id_arr  = np.asarray(building_id)
    type_arr = np.asarray(building_type)
    col_id   = np.where(footprint, id_arr,   int_fill).astype(id_arr.dtype,   copy=True)
    col_type = np.where(footprint, type_arr, int_fill).astype(type_arr.dtype, copy=True)
    return col_id, col_type


def _build_topography_classification(zt, building_height, building_id, building_type, dz, float_fill):
    zt              = np.asarray(zt,              dtype=np.float32)
    building_height = np.asarray(building_height, dtype=np.float32)
    building_id     = np.asarray(building_id)
    ny, nx = zt.shape
    step = float(dz) if float(dz) > 0.0 else 1.0

    footprint  = _building_footprint(building_id, building_height, float_fill)
    top_height = np.where(footprint, zt + np.maximum(building_height, 0.0), zt)
    max_top    = float(top_height.max()) if top_height.size else 0.0
    nz         = max(1, int(np.ceil(max_top / step)))

    z_centers = (np.arange(nz, dtype=np.float32) + 0.5) * step   # shape (nz,)
    z         = z_centers[:, np.newaxis, np.newaxis]              # broadcast axis

    classes = np.zeros((nz, ny, nx), dtype=np.int8)
    classes[z <= zt[np.newaxis]]                                                                   = 1
    classes[footprint[np.newaxis] & (z > zt[np.newaxis]) & (z <= (zt + np.maximum(building_height, 0.0))[np.newaxis])] = 2

    col_id, col_type = _infer_column_building_labels(building_id, building_type, footprint)
    return classes, col_id, col_type, step


# ---------------------------------------------------------------------------
# Hole filling  (vectorised)
# ---------------------------------------------------------------------------

def _count_solid_neighbors(solid):
    """Return per-cell count of solid 6-neighbors (no diagonal, no wrap)."""
    nz, ny, nx = solid.shape
    count = np.zeros((nz, ny, nx), dtype=np.int8)
    count[1:,  :,  :] += solid[:-1,  :,  :]   # k-1 (below)
    count[:-1, :,  :] += solid[1:,   :,  :]   # k+1 (above)
    count[:,  1:,  :] += solid[:,  :-1, :]    # j-1
    count[:, :-1,  :] += solid[:,  1:,  :]    # j+1
    count[:,  :,  1:] += solid[:,   :, :-1]   # i-1
    count[:,  :, :-1] += solid[:,   :,  1:]   # i+1
    return count


def _fill_holes(classes, col_id, col_type):
    """Iterative 1-gridpoint hole filling, fully vectorised.

    A fluid cell surrounded by ≥ 4 solid neighbours is filled.
    Returns (total_fills, sweep_count, fill_mask_3d).
    """
    nz, ny, nx = classes.shape

    # 2-D map: does this (row, col) column contain a building?
    has_building = col_id > 0   # shape (ny, nx)

    # For hole-filled cells that have no column building yet we propagate
    # from a neighbour.  Pre-build shifted views for the 2-D label arrays.
    fill_mask   = np.zeros((nz, ny, nx), dtype=bool)
    total_fills = 0
    sweeps      = 0

    while True:
        solid   = classes != 0
        count   = _count_solid_neighbors(solid)
        to_fill = (~solid) & (count >= 4)   # candidate fluid cells

        if not np.any(to_fill):
            break

        sweeps      += 1
        total_fills += int(np.count_nonzero(to_fill))
        fill_mask   |= to_fill

        # Determine fill class per (row, col) column
        # Propagate building label from a horizontal neighbour where needed
        fill_cols_yx = np.any(to_fill, axis=0)   # (ny, nx) mask of affected columns
        new_has_bld  = has_building.copy()

        # horizontal neighbour propagation for columns that lack a building label
        needs_label = fill_cols_yx & ~has_building
        if np.any(needs_label):
            # shift the existing has_building mask in all 4 directions and OR together
            inherited = np.zeros((ny, nx), dtype=bool)
            if ny > 1:
                inherited[1:,  :] |= has_building[:-1, :]
                inherited[:-1, :] |= has_building[1:,  :]
            if nx > 1:
                inherited[:,  1:] |= has_building[:, :-1]
                inherited[:, :-1] |= has_building[:,  1:]
            new_has_bld |= (needs_label & inherited)

        fill_class = np.where(new_has_bld, np.int8(2), np.int8(1))   # (ny, nx)
        classes[to_fill] = np.broadcast_to(fill_class[np.newaxis], classes.shape)[to_fill]
        has_building = new_has_bld   # keep updated for next sweep

    return total_fills, sweeps, fill_mask


# ---------------------------------------------------------------------------
# Cavity filling  (BFS per layer, with clean early-abort)
# ---------------------------------------------------------------------------

def _four_neighbors(row, col, ny, nx):
    if row > 0:        yield row - 1, col
    if row + 1 < ny:   yield row + 1, col
    if col > 0:        yield row, col - 1
    if col + 1 < nx:   yield row, col + 1


def _fill_cavities(classes, col_id):
    """Fill enclosed fluid cavities of < CAVITY_THRESHOLD cells in the xy-plane.

    Mirrors the PALM cavity filter:
    - only courtyard-type cavities (xy-plane) are treated
    - a cavity is only filled if the layer directly below is fully solid
    - filling is done layer by layer from k=1 upward
    Returns (cavity_count, fill_mask_3d).
    """
    nz, ny, nx = classes.shape
    fill_mask   = np.zeros((nz, ny, nx), dtype=bool)
    cavity_count = 0

    has_building = col_id > 0   # (ny, nx)

    for k in range(1, nz):
        layer_fluid = classes[k] == 0          # (ny, nx)
        layer_below = classes[k - 1] != 0      # (ny, nx)
        visited     = np.zeros((ny, nx), dtype=bool)

        fluid_rows, fluid_cols = np.nonzero(layer_fluid)

        for idx in range(fluid_rows.size):
            row, col = int(fluid_rows[idx]), int(fluid_cols[idx])
            if visited[row, col]:
                continue

            # BFS — abort as soon as we exceed the threshold
            region         = []
            large_region   = False
            touches_border = False
            queue          = deque()
            queue.append((row, col))
            visited[row, col] = True

            while queue:
                cr, cc = queue.popleft()
                region.append((cr, cc))

                if cr == 0 or cc == 0 or cr == ny - 1 or cc == nx - 1:
                    touches_border = True

                if len(region) >= CAVITY_THRESHOLD:
                    # Drain remaining queue to mark cells visited, no filling
                    large_region = True
                    while queue:
                        dr, dc = queue.popleft()
                        for nr, nc in _four_neighbors(dr, dc, ny, nx):
                            if not visited[nr, nc] and not layer_fluid[nr, nc]:
                                continue
                            if visited[nr, nc] or classes[k, nr, nc] != 0:
                                continue
                            visited[nr, nc] = True
                            queue.append((nr, nc))
                    break

                for nr, nc in _four_neighbors(cr, cc, ny, nx):
                    if visited[nr, nc] or classes[k, nr, nc] != 0:
                        continue
                    visited[nr, nc] = True
                    queue.append((nr, nc))

            if large_region or touches_border:
                continue

            # Only fill if the entire region sits on solid ground
            if not all(layer_below[rr, cc] for rr, cc in region):
                continue

            cavity_count += 1
            for rr, cc in region:
                fill_class = np.int8(2) if has_building[rr, cc] else np.int8(1)
                classes[k, rr, cc]   = fill_class
                fill_mask[k, rr, cc] = True

    return cavity_count, fill_mask


# ---------------------------------------------------------------------------
# Reconstruct 2-D arrays from the filtered 3-D classification
# ---------------------------------------------------------------------------

def _reconstruct_2d(classes, building_id, building_height, building_type, col_id, col_type, step, float_fill, int_fill, default_building_type):
    """Derive zt / building_height / building_id / building_type from the
    filtered voxel classes array using vectorised NumPy operations."""
    nz, ny, nx = classes.shape

    terrain_mask  = classes == 1    # (nz, ny, nx)
    building_mask = classes == 2

    # --- terrain top ---
    has_terrain   = np.any(terrain_mask, axis=0)
    # highest k index with class == 1, then convert to height
    top_k_terrain = nz - 1 - np.argmax(terrain_mask[::-1], axis=0)   # (ny, nx)
    new_zt = np.where(has_terrain, (top_k_terrain + 1) * step, 0.0).astype(np.float32)

    # --- building top ---
    has_building  = np.any(building_mask, axis=0)
    top_k_bld     = nz - 1 - np.argmax(building_mask[::-1], axis=0)
    bld_top_h     = ((top_k_bld + 1) * step).astype(np.float32)
    new_building_height = np.where(
        has_building,
        np.maximum(0.0, bld_top_h - new_zt),
        float(float_fill),
    ).astype(np.float32)

    # --- building id / type ---
    new_building_id   = np.array(building_id,   copy=True)
    new_building_type = np.array(building_type, copy=True)

    # Cells that gained a building after filtering but had no column id:
    # inherit from a horizontal neighbour (same simple 4-neighbor propagation)
    needs_id = has_building & (new_building_id <= 0)
    if np.any(needs_id):
        padded_id   = np.where(new_building_id > 0,   new_building_id,   0)
        padded_type = np.where(new_building_id > 0,   new_building_type, default_building_type)
        for shift_axis, shift_dir in ((0, 1), (0, -1), (1, 1), (1, -1)):
            still_needs = needs_id & (new_building_id <= 0)
            if not np.any(still_needs):
                break
            neighbour_id   = np.roll(padded_id,   shift_dir, axis=shift_axis)
            neighbour_type = np.roll(padded_type, shift_dir, axis=shift_axis)
            # block wrap-around
            if shift_axis == 0:
                if shift_dir == 1:  neighbour_id[0,  :] = 0
                else:               neighbour_id[-1, :] = 0
            else:
                if shift_dir == 1:  neighbour_id[:,  0] = 0
                else:               neighbour_id[:, -1] = 0
            update = still_needs & (neighbour_id > 0)
            new_building_id[update]   = neighbour_id[update]
            new_building_type[update] = neighbour_type[update]

        # Fallback for isolated new cells with no nearby label
        still_needs = needs_id & (new_building_id <= 0)
        new_building_id[still_needs]   = 1
        new_building_type[still_needs] = default_building_type

    # Fix missing building_type on cells that already have a valid id
    bad_type = has_building & (new_building_id > 0) & (new_building_type <= int_fill)
    new_building_type[bad_type] = default_building_type

    # Clear building fields for cells that lost their building after filtering
    surface_only = (np.asarray(building_id) > 0) & np.isfinite(np.asarray(building_height, dtype=np.float32)) \
                   & np.isclose(np.asarray(building_height, dtype=np.float32), 0.0)
    no_building = ~has_building

    # Sub-voxel buildings (building_height < dz and no voxel centre inside the
    # building) produce zero class-2 voxels and would be incorrectly cleared.
    # Preserve their original data so they don't become bare non-building cells.
    original_footprint = (
        (np.asarray(building_id) > 0)
        & np.isfinite(np.asarray(building_height, dtype=np.float32))
        & (np.asarray(building_height, dtype=np.float32) > 0.0)
    )
    lost_buildings = no_building & original_footprint & ~surface_only

    clear_mask = no_building & ~surface_only & ~lost_buildings
    new_building_height[clear_mask] = float(float_fill)
    new_building_id[clear_mask]     = int_fill
    new_building_type[clear_mask]   = int_fill
    new_building_height[no_building & surface_only] = 0.0
    # For sub-voxel buildings: restore original height; id/type already copied.
    new_building_height[lost_buildings] = np.asarray(building_height, dtype=np.float32)[lost_buildings]

    return new_zt, new_building_height, new_building_id, new_building_type


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def apply_topography_filters(zt, building_height, building_id, building_type, dz, float_fill, int_fill, default_building_type=1):
    """Apply PALM-style hole and cavity filtering to a discrete constant-dz mask."""
    classes, col_id, col_type, step = _build_topography_classification(
        zt, building_height, building_id, building_type, dz, float_fill
    )

    hole_fills, hole_sweeps, hole_fill_mask = _fill_holes(classes, col_id, col_type)

    cavity_count, cavity_fill_mask = _fill_cavities(classes, col_id)

    new_zt, new_bh, new_bid, new_btype = _reconstruct_2d(
        classes, building_id, building_height, building_type, col_id, col_type, step, float_fill, int_fill, default_building_type
    )

    return {
        "zt":                  new_zt,
        "building_height":     new_bh,
        "building_id":         new_bid,
        "building_type":       new_btype,
        "hole_fill_count":     hole_fills,
        "hole_sweeps":         hole_sweeps,
        "hole_fill_columns":   np.any(hole_fill_mask, axis=0),
        "cavity_fill_count":   cavity_count,
        "cavity_fill_voxels":  int(np.count_nonzero(cavity_fill_mask)),
        "cavity_fill_columns": np.any(cavity_fill_mask, axis=0),
    }
    
 
def preview_filter_sweep(model):
    """Preview PALM-style hole and cavity filtering without ID/terrain preprocessing."""
    filter_result = apply_topography_filters(
        model.zt,
        model.building_height,
        model.building_id,
        model.building_type,
        model.dz,
        model.FLOAT_FILL,
        model.INT_FILL,
        _default_building_type(getattr(model, "surface_config", None)),
    )
    preview_mask = filter_result["hole_fill_columns"] | filter_result["cavity_fill_columns"]
    return {
        "summary": {
            #"zt_repaired": 0,
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
    lost_building_mask = original_building_mask & ~_building_footprint(
        model.building_id,
        model.building_height,
        model.FLOAT_FILL,
    )
    if np.any(lost_building_mask):
        model.clear_building_parameters_where(lost_building_mask)
    if np.any(new_building_mask):
        model.soil_type[new_building_mask] = model.INT_FILL
        model.vegetation_type[new_building_mask] = model.INT_FILL
        model.pavement_type[new_building_mask] = model.INT_FILL
        model.water_type[new_building_mask] = model.INT_FILL

    result["summary"]["new_building_cells"] = int(np.count_nonzero(new_building_mask))
    return result
