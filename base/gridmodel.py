"""
Data model for the PALMPaint grid.

Holds all surface layer data as numpy arrays with shape (ny, nx).
Contains no Tkinter or display logic — can be used by any view backend
or a future 3D viewer.

    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

import math
import os
import tempfile
import copy

import numpy as np

# ---------------------------------------------------------------------------
# CSS3 / X11 named colour → (R, G, B) lookup table.
# Covers every named colour used in the default surface_config plus the full
# CSS3 set and a handful of Tk-specific X11 numbered variants (e.g. "green4").
# Used by get_color_array_rgb() so that gridmodel stays display-framework-free.
# ---------------------------------------------------------------------------
_CSS_COLORS: dict = {
    "aliceblue":           (240, 248, 255),
    "antiquewhite":        (250, 235, 215),
    "aqua":                (  0, 255, 255),
    "aquamarine":          (127, 255, 212),
    "azure":               (240, 255, 255),
    "beige":               (245, 245, 220),
    "bisque":              (255, 228, 196),
    "black":               (  0,   0,   0),
    "blanchedalmond":      (255, 235, 205),
    "blue":                (  0,   0, 255),
    "blueviolet":          (138,  43, 226),
    "brown":               (165,  42,  42),
    "burlywood":           (222, 184, 135),
    "cadetblue":           ( 95, 158, 160),
    "chartreuse":          (127, 255,   0),
    "chocolate":           (210, 105,  30),
    "coral":               (255, 127,  80),
    "cornflowerblue":      (100, 149, 237),
    "cornsilk":            (255, 248, 220),
    "crimson":             (220,  20,  60),
    "cyan":                (  0, 255, 255),
    "darkblue":            (  0,   0, 139),
    "darkcyan":            (  0, 139, 139),
    "darkgoldenrod":       (184, 134,  11),
    "darkgray":            (169, 169, 169),
    "darkgreen":           (  0, 100,   0),
    "darkgrey":            (169, 169, 169),
    "darkkhaki":           (189, 183, 107),
    "darkmagenta":         (139,   0, 139),
    "darkolivegreen":      ( 85, 107,  47),
    "darkorange":          (255, 140,   0),
    "darkorchid":          (153,  50, 204),
    "darkred":             (139,   0,   0),
    "darksalmon":          (233, 150, 122),
    "darkseagreen":        (143, 188, 143),
    "darkslateblue":       ( 72,  61, 139),
    "darkslategray":       ( 47,  79,  79),
    "darkslategrey":       ( 47,  79,  79),
    "darkturquoise":       (  0, 206, 209),
    "darkviolet":          (148,   0, 211),
    "deeppink":            (255,  20, 147),
    "deepskyblue":         (  0, 191, 255),
    "dimgray":             (105, 105, 105),
    "dimgrey":             (105, 105, 105),
    "dodgerblue":          ( 30, 144, 255),
    "firebrick":           (178,  34,  34),
    "floralwhite":         (255, 250, 240),
    "forestgreen":         ( 34, 139,  34),
    "fuchsia":             (255,   0, 255),
    "gainsboro":           (220, 220, 220),
    "ghostwhite":          (248, 248, 255),
    "gold":                (255, 215,   0),
    "goldenrod":           (218, 165,  32),
    "gray":                (128, 128, 128),
    "green":               (  0, 128,   0),
    "greenyellow":         (173, 255,  47),
    "grey":                (128, 128, 128),
    # Tk / X11 numbered variants not in CSS3
    "green1":              (  0, 255,   0),
    "green2":              (  0, 238,   0),
    "green3":              (  0, 205,   0),
    "green4":              (  0, 139,   0),
    "honeydew":            (240, 255, 240),
    "hotpink":             (255, 105, 180),
    "indianred":           (205,  92,  92),
    "indigo":              ( 75,   0, 130),
    "ivory":               (255, 255, 240),
    "khaki":               (240, 230, 140),
    "lavender":            (230, 230, 250),
    "lavenderblush":       (255, 240, 245),
    "lawngreen":           (124, 252,   0),
    "lemonchiffon":        (255, 250, 205),
    "lightblue":           (173, 216, 230),
    "lightcoral":          (240, 128, 128),
    "lightcyan":           (224, 255, 255),
    "lightgoldenrodyellow":(250, 250, 210),
    "lightgray":           (211, 211, 211),
    "lightgreen":          (144, 238, 144),
    "lightgrey":           (211, 211, 211),
    "lightpink":           (255, 182, 193),
    "lightsalmon":         (255, 160, 122),
    "lightseagreen":       ( 32, 178, 170),
    "lightskyblue":        (135, 206, 250),
    "lightslategray":      (119, 136, 153),
    "lightslategrey":      (119, 136, 153),
    "lightsteelblue":      (176, 196, 222),
    "lightyellow":         (255, 255, 224),
    "lime":                (  0, 255,   0),
    "limegreen":           ( 50, 205,  50),
    "linen":               (250, 240, 230),
    "magenta":             (255,   0, 255),
    "maroon":              (128,   0,   0),
    "mediumaquamarine":    (102, 205, 170),
    "mediumblue":          (  0,   0, 205),
    "mediumorchid":        (186,  85, 211),
    "mediumpurple":        (147, 112, 219),
    "mediumseagreen":      ( 60, 179, 113),
    "mediumslateblue":     (123, 104, 238),
    "mediumspringgreen":   (  0, 250, 154),
    "mediumturquoise":     ( 72, 209, 204),
    "mediumvioletred":     (199,  21, 133),
    "midnightblue":        ( 25,  25, 112),
    "mintcream":           (245, 255, 250),
    "mistyrose":           (255, 228, 225),
    "moccasin":            (255, 228, 181),
    "navajowhite":         (255, 222, 173),
    "navy":                (  0,   0, 128),
    "oldlace":             (253, 245, 230),
    "olive":               (128, 128,   0),
    "olivedrab":           (107, 142,  35),
    "orange":              (255, 165,   0),
    "orangered":           (255,  69,   0),
    "orchid":              (218, 112, 214),
    "palegoldenrod":       (238, 232, 170),
    "palegreen":           (152, 251, 152),
    "paleturquoise":       (175, 238, 238),
    "palevioletred":       (219, 112, 147),
    "papayawhip":          (255, 239, 213),
    "peachpuff":           (255, 218, 185),
    "peru":                (205, 133,  63),
    "pink":                (255, 192, 203),
    "plum":                (221, 160, 221),
    "powderblue":          (176, 224, 230),
    "purple":              (128,   0, 128),
    "red":                 (255,   0,   0),
    "rosybrown":           (188, 143, 143),
    "royalblue":           ( 65, 105, 225),
    "saddlebrown":         (139,  69,  19),
    "salmon":              (250, 128, 114),
    "sandybrown":          (244, 164,  96),
    "seagreen":            ( 46, 139,  87),
    "seashell":            (255, 245, 238),
    "sienna":              (160,  82,  45),
    "silver":              (192, 192, 192),
    "skyblue":             (135, 206, 235),
    "slateblue":           (106,  90, 205),
    "slategray":           (112, 128, 144),
    "slategrey":           (112, 128, 144),
    "snow":                (255, 250, 250),
    "springgreen":         (  0, 255, 127),
    "steelblue":           ( 70, 130, 180),
    "tan":                 (210, 180, 140),
    "teal":                (  0, 128, 128),
    "thistle":             (216, 191, 216),
    "tomato":              (255,  99,  71),
    "turquoise":           ( 64, 224, 208),
    "violet":              (238, 130, 238),
    "wheat":               (245, 222, 179),
    "white":               (255, 255, 255),
    "whitesmoke":          (245, 245, 245),
    "yellow":              (255, 255,   0),
    "yellowgreen":         (154, 205,  50),
}


class GridModel:
    """
    Data store for one PALM Static Driver domain.

    Each surface layer is a numpy array of shape (ny, nx).
    Fill values follow PIDS conventions:
      - INT_FILL  = -127   for integer layers
      - FLOAT_FILL = -9999.0 for float layers

    """

    INT_FILL   = -127
    FLOAT_FILL = -9999.0
    BUILDING_ID_FILL = -9999
    TEMP_BACKED_ARRAY_THRESHOLD_BYTES = 64 * 1024 * 1024

    @staticmethod
    def infer_vertical_step(coords, fallback):
        """Infer a representative vertical spacing from a 1-D vertical coordinate array.

        Some external files contain a leading zero followed by regularly spaced
        layer coordinates (for example ``0, 2, 6, 10, ...``). Using only the
        first difference would underestimate dz in that case. We therefore
        ignore the leading half-step when present.
        """
        if coords is None:
            return float(fallback)
        coords = np.asarray(coords, dtype=np.float32)
        if coords.size < 2:
            return float(fallback)
        diffs = np.diff(coords)
        diffs = diffs[np.isfinite(diffs) & (diffs > 0.0)]
        if diffs.size == 0:
            return float(fallback)
        if coords[0] == 0.0:
            if diffs.size == 1:
                return float(2.0 * diffs[0])
            trailing_diffs = diffs[1:]
            if trailing_diffs.size > 0:
                trailing_median = float(np.median(trailing_diffs))
                if diffs[0] < 0.75 * trailing_median:
                    return trailing_median
        return float(np.median(diffs))

    @staticmethod
    def infer_dz_from_zlad(zlad, fallback):
        """Backward-compatible wrapper for zlad-based dz inference."""
        return GridModel.infer_vertical_step(zlad, fallback)

    @staticmethod
    def quantize_building_height(value, dz):
        """Snap building heights to the vertical grid.

        Buildings use the same half-cell threshold as PALM's 3-D voxelisation:
        values below ``dz/2`` stay as a zero-height footprint (which still
        becomes a voxel at ``z=0`` in ``buildings_3d``), while larger values
        snap to the nearest dz-based top height.
        """
        if value is None:
            return float(GridModel.FLOAT_FILL)

        value = float(value)
        if not np.isfinite(value) or value < 0.0:
            return float(GridModel.FLOAT_FILL)
        if value == 0.0:
            return 0.0

        step = float(dz) if float(dz) > 0.0 else 1.0
        snapped = math.floor((value + 0.5 * step + 1e-9) / step) * step
        return max(0.0, float(snapped))

    @staticmethod
    def quantize_terrain_height(value, dz):
        """Discretize terrain height using PALM's all-or-nothing zt logic.

        For constant vertical spacing, PALM marks a terrain cell as occupied
        once the continuous terrain reaches the scalar height of that cell.
        The effective terrain top therefore lies on the corresponding zw level,
        which is equivalent to a half-cell threshold before snapping upward.
        """
        if value is None:
            return 0.0

        value = float(value)
        if not np.isfinite(value) or value <= 0.0:
            return 0.0

        step = float(dz) if float(dz) > 0.0 else 1.0
        snapped = math.floor((value + 0.5 * step + 1e-9) / step) * step
        return max(0.0, float(snapped))

    def __init__(self, nx, ny, res, dz=None, surface_config=None):
        """
        Parameters
        ----------
        nx, ny : int
            Number of grid cells in x and y direction.
        res : float
            Physical grid width in metres (dx = dy = res).
        dz : float, optional
            Vertical grid spacing in metres. Defaults to ``res``.
        surface_config : dict, optional
            Configuration for vegetation types and categories.
        """
        self.nx  = nx
        self.ny  = ny
        self.res = res  # physical resolution in metres
        self.dz = float(dz) if dz is not None else float(res)
        self.show_grid_lines = True
        self.surface_config = surface_config
        self._temp_store = None
        self._temp_array_counter = 0
        self._building_top_cache = None

        # Default: bare soil everywhere — derive types from surface_config when available
        _sc = surface_config or {}
        _veg_default  = _sc.get("vegetation", {}).get("default_type", 1)
        _soil_default = (_sc.get("vegetation", {})
                           .get("types", {})
                           .get(_veg_default, {})
                           .get("soil_type", _sc.get("soil", {}).get("default_type", 1)))

        self.zt = np.full((ny, nx), 0.0, dtype=np.float32)
        self.vegetation_type = np.full((ny, nx), _veg_default,  dtype=np.int8)
        self.soil_type       = np.full((ny, nx), _soil_default, dtype=np.int8)
        self.pavement_type   = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)
        self.water_type      = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)
        self.building_id     = np.full((ny, nx), self.INT_FILL,  dtype=np.int32)
        self.building_height = np.full((ny, nx), self.FLOAT_FILL, dtype=np.float32)
        self.building_type   = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)

        self.water_pars = np.full((7, ny, nx), self.FLOAT_FILL, dtype=np.float32)
        # Future USM per-surface properties — populated by 3D editor?
        #self.building_surface_pars = {}
        
        # --------------------------------------------------------------
        # Single-tree / resolved vegetation support
        # --------------------------------------------------------------

        # Editable tree objects managed by PALMPaint
        self.tree_instances = []
        self.next_tree_id = 1

        # 3D-Volume information
        self.resolved_vegetation = {
            "zlad": None,          # shape: (nzlad,)
            "lad": None,           # shape: (nzlad, ny, nx)
            "bad": None,           # shape: (nzlad, ny, nx) or None
            "tree_id": None,       # shape: (nzlad, ny, nx) or None
        }
        # _loaded_rv stores the resolved-vegetation arrays exactly as loaded from
        # the NetCDF file (lad, bad, tree_id, zlad).  It acts as an immutable
        # base layer that is preserved across add_tree()/remove_tree calls.
        #
        # Why we need it: _rebuild_resolved_vegetation() builds fresh lad/tree_id
        # arrays from tree_instances, which is empty right after loading a file.
        # Without this backup, every add_tree() call on a loaded project would
        # wipe all vegetation that existed in the file.  By keeping _loaded_rv
        # we can copy the original data back into the new arrays before overlaying
        # the freshly-placed trees on top.
        #
        # Limitation: trees that were saved without per-cell tree_id (e.g. from an
        # external PALM simulation) are stored here as raw lad data and cannot be
        # individually selected via tree_instances.  They can only be erased
        # cell-by-cell via remove_loaded_lad_at().
        self._loaded_rv = None

    def _ensure_temp_store(self):
        if self._temp_store is None:
            self._temp_store = tempfile.TemporaryDirectory(prefix="palmpaint_arrays_")
        return self._temp_store.name

    def _should_use_temp_backing(self, shape, dtype, prefer_temp=None):
        if prefer_temp is not None:
            return bool(prefer_temp)
        size_bytes = int(np.prod(shape, dtype=np.int64)) * np.dtype(dtype).itemsize
        return size_bytes >= self.TEMP_BACKED_ARRAY_THRESHOLD_BYTES

    def allocate_storage(self, shape, dtype, *, fill_value=0, prefer_temp=None, name_prefix="array"):
        """Allocate an ndarray, using a temporary memmap for large volumes."""
        dtype = np.dtype(dtype)
        shape = tuple(int(dim) for dim in shape)
        if self._should_use_temp_backing(shape, dtype, prefer_temp=prefer_temp):
            store_dir = self._ensure_temp_store()
            self._temp_array_counter += 1
            path = os.path.join(store_dir, f"{name_prefix}_{self._temp_array_counter}.dat")
            arr = np.memmap(path, dtype=dtype, mode="w+", shape=shape)
            if fill_value == 0:
                arr[:] = 0
            else:
                arr.fill(fill_value)
            return arr

        if fill_value == 0:
            return np.zeros(shape, dtype=dtype)
        return np.full(shape, fill_value, dtype=dtype)

    def materialize_storage(self, source, *, dtype=None, prefer_temp=None, name_prefix="array"):
        """Copy source data into regular or temp-backed storage."""
        arr = np.asarray(source)
        target_dtype = arr.dtype if dtype is None else np.dtype(dtype)
        out = self.allocate_storage(
            arr.shape,
            target_dtype,
            prefer_temp=prefer_temp,
            name_prefix=name_prefix,
        )
        out[...] = arr.astype(target_dtype, copy=False)
        return out

    def _invalidate_building_cache(self):
        self._building_top_cache = None

    def _copy_state_array(self, array, *, name_prefix):
        if array is None:
            return None
        return self.materialize_storage(array, name_prefix=name_prefix)

    def _snapshot_loaded_rv(self):
        """Return a snapshot of the mutable loaded vegetation base layer."""
        if self._loaded_rv is None:
            return None
        rv = self._loaded_rv
        return {
            "zlad": None if rv.get("zlad") is None else np.array(rv["zlad"], copy=True),
            "lad": self._copy_state_array(rv.get("lad"), name_prefix="undo_lad"),
            "bad": self._copy_state_array(rv.get("bad"), name_prefix="undo_bad"),
            "tree_id": self._copy_state_array(rv.get("tree_id"), name_prefix="undo_tree_id"),
            "source_has_buildings_3d": rv.get("source_has_buildings_3d"),
            # Source metadata is treated as immutable baseline data and can be shared.
            "source_buildings_3d": rv.get("source_buildings_3d"),
            "source_buildings_3d_z": rv.get("source_buildings_3d_z"),
            "source_buildings_2d": rv.get("source_buildings_2d"),
            "source_building_id": rv.get("source_building_id"),
            "source_building_type": rv.get("source_building_type"),
        }

    def export_state(self):
        """Return an undo-friendly snapshot of the model state."""
        return {
            "nx": self.nx,
            "ny": self.ny,
            "res": self.res,
            "dz": self.dz,
            "surface_config": self.surface_config,
            "zt": np.array(self.zt, copy=True),
            "vegetation_type": np.array(self.vegetation_type, copy=True),
            "soil_type": np.array(self.soil_type, copy=True),
            "pavement_type": np.array(self.pavement_type, copy=True),
            "water_type": np.array(self.water_type, copy=True),
            "building_id": np.array(self.building_id, copy=True),
            "building_height": np.array(self.building_height, copy=True),
            "building_type": np.array(self.building_type, copy=True),
            "water_pars": np.array(self.water_pars, copy=True),
            "tree_instances": copy.deepcopy(self.tree_instances),
            "next_tree_id": self.next_tree_id,
            "loaded_rv": self._snapshot_loaded_rv(),
        }

    @classmethod
    def from_state(cls, state):
        """Recreate a GridModel from :meth:`export_state` output."""
        model = cls(
            state["nx"],
            state["ny"],
            state["res"],
            state["dz"],
            state.get("surface_config"),
        )
        model.zt[:, :] = state["zt"]
        model.vegetation_type[:, :] = state["vegetation_type"]
        model.soil_type[:, :] = state["soil_type"]
        model.pavement_type[:, :] = state["pavement_type"]
        model.water_type[:, :] = state["water_type"]
        model.building_id[:, :] = state["building_id"]
        model.building_height[:, :] = state["building_height"]
        model.building_type[:, :] = state["building_type"]
        model.water_pars[:, :, :] = state["water_pars"]
        model.tree_instances = copy.deepcopy(state.get("tree_instances", []))
        model.next_tree_id = int(state.get("next_tree_id", 1))
        loaded_rv = state.get("loaded_rv")
        if loaded_rv is not None:
            model._loaded_rv = {
                "zlad": None if loaded_rv.get("zlad") is None else np.array(loaded_rv["zlad"], copy=True),
                "lad": model._copy_state_array(loaded_rv.get("lad"), name_prefix="restore_lad"),
                "bad": model._copy_state_array(loaded_rv.get("bad"), name_prefix="restore_bad"),
                "tree_id": model._copy_state_array(loaded_rv.get("tree_id"), name_prefix="restore_tree_id"),
                "source_has_buildings_3d": loaded_rv.get("source_has_buildings_3d"),
                "source_buildings_3d": loaded_rv.get("source_buildings_3d"),
                "source_buildings_3d_z": loaded_rv.get("source_buildings_3d_z"),
                "source_buildings_2d": loaded_rv.get("source_buildings_2d"),
                "source_building_id": loaded_rv.get("source_building_id"),
                "source_building_type": loaded_rv.get("source_building_type"),
            }
        else:
            model._loaded_rv = None

        if model.tree_instances:
            model._rebuild_resolved_vegetation()
        elif model._loaded_rv is not None:
            model.resolved_vegetation = model._loaded_rv
        else:
            model.resolved_vegetation = {"zlad": None, "lad": None, "bad": None, "tree_id": None}
        model._invalidate_building_cache()
        return model

    def clear_water_parameters(self, row, col):
        """Reset all water parameters for one pixel."""
        self.water_pars[:, row, col] = self.FLOAT_FILL

    # ------------------------------------------------------------------
    # Single-tree management
    # ------------------------------------------------------------------

    def add_tree(self, row, col, tree_height=10.0, crown_diameter=7.0,
                 trunk_diameter=0.3, crown_height=None, lai=3.0, tree_type_id=0,
                 generator_params=None):
        """Place a single resolved tree at (row, col).

        If a tree already exists at (row, col) it is replaced.
        Afterwards the 3-D resolved-vegetation arrays are rebuilt.

        Parameters
        ----------
        generator_params : dict or None
            If supplied, must be a dict of kwargs for TreeParams (from the
            Tree Generator dialog).  The tree will be built by
            ``generate_tree()`` at the physical grid resolution instead of the
            simple ellipsoid fallback.  The dict must have exactly one of
            ``lai`` or ``lad_max`` set (and the other None).
        """
        if crown_height is None:
            crown_height = 0.6 * float(tree_height)
        # Replace any previous tree on the same cell
        self.tree_instances = [t for t in self.tree_instances
                               if not (t["row"] == row and t["col"] == col)]
        self.tree_instances.append({
            "id": self.next_tree_id,
            "row": int(row),
            "col": int(col),
            "tree_height": float(tree_height),
            "crown_diameter": float(crown_diameter),
            "trunk_diameter": float(trunk_diameter),
            "crown_height": float(crown_height),
            "lai": float(lai),
            "tree_type_id": int(tree_type_id),
            "generator_params": generator_params,
        })
        tree_id = self.next_tree_id
        self.next_tree_id += 1
        clip_summary = self._rebuild_resolved_vegetation(track_tree_id=tree_id)
        if clip_summary is not None and clip_summary["placed_voxels"] == 0:
            self.tree_instances = [t for t in self.tree_instances if t["id"] != tree_id]
            self._rebuild_resolved_vegetation()
        return {
            "tree_id": tree_id,
            **(clip_summary or {"clipped_voxels": 0, "placed_voxels": 0}),
        }

    def remove_tree_at(self, row, col):
        """Remove the tree whose trunk is at (row, col) and rebuild."""
        self.tree_instances = [t for t in self.tree_instances
                               if not (t["row"] == row and t["col"] == col)]
        self._rebuild_resolved_vegetation()

    def remove_tree_by_id(self, tree_id):
        """Remove the tree with the given id from tree_instances and rebuild."""
        self.tree_instances = [t for t in self.tree_instances
                               if t["id"] != tree_id]
        self._rebuild_resolved_vegetation()

    def get_tree_id_at(self, row, col):
        """Return the tree_id of the resolved-vegetation cell at (row, col).

        Searches all z-levels in resolved_vegetation["tree_id"] and returns
        the first non-zero value found, or 0 if none.
        """
        tid_vol = self.resolved_vegetation.get("tree_id") if self.resolved_vegetation else None
        if tid_vol is None:
            return 0
        col_ids = tid_vol[:, row, col]
        nonzero = col_ids[col_ids > 0]
        return int(nonzero[0]) if nonzero.size > 0 else 0

    def has_lad_at(self, row, col):
        """Return True if any z-level at (row, col) has lad > 0."""
        lad_vol = self.resolved_vegetation.get("lad") if self.resolved_vegetation else None
        if lad_vol is None:
            return False
        return bool(np.any(lad_vol[:, row, col] > 0))

    def _resolved_vegetation_source_metadata(self):
        """Return preserved source metadata for resolved vegetation volumes."""
        source = self._loaded_rv if self._loaded_rv is not None else self.resolved_vegetation
        if source is None:
            return {}
        keys = (
            "source_has_buildings_3d",
            "source_buildings_3d",
            "source_buildings_3d_z",
            "source_buildings_2d",
            "source_building_id",
            "source_building_type",
        )
        metadata = {}
        for key in keys:
            metadata[key] = source.get(key)
        return metadata

    def _building_top_z(self):
        """Return the top occupied z value per building column, or FLOAT_FILL."""
        if self._building_top_cache is not None:
            return self._building_top_cache

        top_z = np.full((self.ny, self.nx), self.FLOAT_FILL, dtype=np.float32)
        source = self.resolved_vegetation if self.resolved_vegetation is not None else self._loaded_rv
        source_buildings_3d = None if source is None else source.get("source_buildings_3d")
        source_buildings_3d_z = None if source is None else source.get("source_buildings_3d_z")
        if source_buildings_3d is not None and source_buildings_3d_z is not None:
            z3d = np.asarray(source_buildings_3d_z, dtype=np.float32)
            for iz, z_val in enumerate(z3d):
                occupied_layer = np.asarray(source_buildings_3d[iz]) > 0
                if np.any(occupied_layer):
                    top_z[occupied_layer] = z_val
            self._building_top_cache = top_z
            return self._building_top_cache

        valid_heights = self.building_height > self.FLOAT_FILL
        top_z[valid_heights] = self.building_height[valid_heights]
        self._building_top_cache = top_z
        return self._building_top_cache

    def _build_tree_generator_params(self, tree):
        """Return generator params for a tree instance or placement request."""
        gp = tree.get("generator_params")
        if gp is not None:
            return gp

        h_tree = float(tree["tree_height"])
        cd = float(tree["crown_diameter"])
        ch_tree = float(tree.get("crown_height") or 0.6 * h_tree)
        cr_ratio = ch_tree / cd if cd > 0.0 else 1.0
        return {
            "max_tree_height":   h_tree,
            "crown_diameter":    cd,
            "trunk_diameter":    float(tree.get("trunk_diameter") or 0.3),
            "crown_shape":       1,
            "crown_ratio":       cr_ratio,
            "alpha":             5.0,
            "beta":              3.0,
            "lai":               float(tree["lai"]),
            "lad_model":         "palm_extinction",
            "palm_extinction_k": 0.6,
            "bad_lad_ratio":     0.025,
        }

    def _iter_tree_voxels(self, tree, dz, nz):
        """Yield generated global LAD/BAD voxels for one tree."""
        tr = tree["row"]
        tc = tree["col"]
        gp = self._build_tree_generator_params(tree)

        from base.tree_generator_core import generate_tree, TreeParams, Grid

        _grid = Grid(dx=self.res, dy=self.res, dz=dz, pad_xy=0.0, pad_z=0.0)
        try:
            result = generate_tree(TreeParams(**gp), _grid)
        except Exception:
            yield (0, tr, tc, float(tree["lai"]) / dz if dz > 0 else float(tree["lai"]), 0.0)
            return

        lad_tree = result["lad"]
        bad_tree = result["bad"]
        z_tree = result["coords"]["z"]
        nz_t, ny_t, nx_t = lad_tree.shape
        cx_t = nx_t // 2
        cy_t = ny_t // 2
        for iz_t in range(nz_t):
            z_val = z_tree[iz_t]
            iz_g = int(z_val / dz)
            if not (0 <= iz_g < nz):
                continue
            for iy_t in range(ny_t):
                rr = tr - cy_t + iy_t
                if not (0 <= rr < self.ny):
                    continue
                for ix_t in range(nx_t):
                    cc = tc - cx_t + ix_t
                    if not (0 <= cc < self.nx):
                        continue
                    v = lad_tree[iz_t, iy_t, ix_t]
                    b = bad_tree[iz_t, iy_t, ix_t]
                    if v > 0.0 or b > 0.0:
                        yield (iz_g, rr, cc, float(v), float(b))

    def get_tree_info_at(self, row, col):
        """Return a dict with tree diagnostics for (row, col), or None if no lad.

        Keys:
          max_height    – z-coordinate (m) of the highest lad > 0 level, or None
          lad_max       – maximum LAD in the column (m²/m³)
          lad_integral  – vertical integral sum(LAD * dz) for the column (m²/m²)
          bad_max       – maximum BAD in the column (m²/m³), or None if absent
          bad_integral  – vertical integral sum(BAD * dz) (m²/m²), or None if absent
          tree_id       – integer tree ID (0 = no ID / loaded-only cell)
        """
        rv = self.resolved_vegetation
        lad_vol = rv.get("lad") if rv else None
        if lad_vol is None or not np.any(lad_vol[:, row, col] > 0):
            return None

        col_lad = lad_vol[:, row, col]
        zlad = rv.get("zlad")
        nz_idx = np.where(col_lad > 0)[0]
        max_height = float(zlad[nz_idx[-1]]) if (zlad is not None and nz_idx.size > 0) else None
        dz = self.infer_dz_from_zlad(zlad, self.dz)
        positive_lad = col_lad[col_lad > 0]

        bad_vol = rv.get("bad")
        if bad_vol is not None:
            col_bad = bad_vol[:, row, col]
            positive_bad = col_bad[col_bad > 0]
            bad_max = float(positive_bad.max()) if positive_bad.size > 0 else 0.0
            bad_integral = float(positive_bad.sum() * dz)
        else:
            bad_max = None
            bad_integral = None

        return {
            "max_height":   max_height,
            "lad_max":      float(positive_lad.max()) if positive_lad.size > 0 else 0.0,
            "lad_integral": float(positive_lad.sum() * dz),
            "bad_max":      bad_max,
            "bad_integral": bad_integral,
            "tree_id":      self.get_tree_id_at(row, col),
        }

    def remove_loaded_lad_at(self, row, col):
        """Erase lad (and tree_id) data at (row, col) in the loaded base layer.

        Used for right-click deletion of cells that have lad > 0 but no
        corresponding tree_instance (i.e. vegetation loaded from an external
        PALM file without per-tree IDs).
        """
        if self._loaded_rv is None:
            return
        lad = self._loaded_rv.get("lad")
        if lad is not None:
            lad[:, row, col] = 0.0
        tid = self._loaded_rv.get("tree_id")
        if tid is not None:
            tid[:, row, col] = 0
        self._rebuild_resolved_vegetation()

    def _rebuild_resolved_vegetation(self, track_tree_id=None):
        """Recompute lad/tree_id from tree_instances using an ellipsoid crown model."""
        has_loaded = (self._loaded_rv is not None
                      and self._loaded_rv.get("lad") is not None)

        if not self.tree_instances:
            if has_loaded:
                self.resolved_vegetation = self._loaded_rv
            else:
                self.resolved_vegetation = {"zlad": None, "lad": None,
                                            "bad": None, "tree_id": None}
            return

        dz = float(self.dz)
        max_height = max(t["tree_height"] for t in self.tree_instances)
        nz = int(np.ceil(max_height / dz)) + 1
        if has_loaded:
            nz = max(nz, self._loaded_rv["lad"].shape[0])
        loaded_zlad = self._loaded_rv.get("zlad") if has_loaded else None
        if loaded_zlad is not None:
            loaded_zlad = np.asarray(loaded_zlad, dtype=np.float32)
        if loaded_zlad is not None and loaded_zlad.size > 0:
            if loaded_zlad.size >= nz:
                zlad = loaded_zlad[:nz].copy()
            else:
                extra = loaded_zlad[-1] + dz * np.arange(1, nz - loaded_zlad.size + 1, dtype=np.float32)
                zlad = np.concatenate([loaded_zlad, extra]).astype(np.float32, copy=False)
        else:
            zlad = ((np.arange(nz, dtype=np.float32) + 0.5) * dz).astype(np.float32, copy=False)

        building_top_z = self._building_top_z()
        lad = self.allocate_storage((nz, self.ny, self.nx), np.float32, fill_value=0, name_prefix="lad")
        bad = self.allocate_storage((nz, self.ny, self.nx), np.float32, fill_value=0, name_prefix="bad")
        tree_id_arr = self.allocate_storage((nz, self.ny, self.nx), np.int32, fill_value=0, name_prefix="tree_id")
        tracked_clipped = set()
        tracked_placed = set()

        # Merge externally-loaded base data into the arrays
        if has_loaded:
            nz_src = min(self._loaded_rv["lad"].shape[0], nz)
            lad_src = self._loaded_rv["lad"][:nz_src]
            valid = lad_src > 0
            lad[:nz_src][valid] = lad_src[valid]
            loaded_tid = self._loaded_rv.get("tree_id")
            if loaded_tid is not None:
                nz_id = min(loaded_tid.shape[0], nz)
                mask = loaded_tid[:nz_id] != 0
                tree_id_arr[:nz_id][mask] = loaded_tid[:nz_id][mask]
            loaded_bad = self._loaded_rv.get("bad")
            if loaded_bad is not None:
                nz_b = min(loaded_bad.shape[0], nz)
                bad_src = loaded_bad[:nz_b]
                valid_b = bad_src > 0
                bad[:nz_b][valid_b] = bad_src[valid_b]

        for tree in self.tree_instances:
            tid = tree["id"]
            for iz_g, rr, cc, v, b in self._iter_tree_voxels(tree, dz, nz):
                if zlad[iz_g] <= building_top_z[rr, cc]:
                    if tid == track_tree_id:
                        tracked_clipped.add((iz_g, rr, cc))
                    continue
                if v > 0.0:
                    lad[iz_g, rr, cc] += v
                    tree_id_arr[iz_g, rr, cc] = tid
                if b > 0.0:
                    bad[iz_g, rr, cc] += b
                if tid == track_tree_id:
                    tracked_placed.add((iz_g, rr, cc))

        self.resolved_vegetation = {
            "zlad": zlad,
            "lad": lad,
            "bad": bad,
            "tree_id": tree_id_arr,
            **self._resolved_vegetation_source_metadata(),
        }
        if track_tree_id is not None:
            return {
                "clipped_voxels": len(tracked_clipped),
                "placed_voxels": len(tracked_placed),
            }
        return None

    # Helper methods for surface config access
    def set_water_parameter(self, par_index, row, col, value):
        """Set one water parameter for a single pixel."""
        self.water_pars[par_index, row, col] = value

    def get_water_parameter(self, par_index, row, col):
        """Get one water parameter for a single pixel."""
        return float(self.water_pars[par_index, row, col])
    

    # ------------------------------------------------------------------
    # Pixel-level access
    # ------------------------------------------------------------------

    def set_pixel(self, row, col, quantize=True, **kwargs):
        """Write data layer values for a single pixel.

        Unknown keys (e.g. 'color', 'outline', 'id') are silently ignored,
        so the method is safe to call with legacy pixel dicts.
        """
        layer_map = {
            "zt":              self.zt,
            "vegetation_type": self.vegetation_type,
            "soil_type":       self.soil_type,
            "pavement_type":   self.pavement_type,
            "water_type":      self.water_type,
            "building_id":     self.building_id,
            "building_height": self.building_height,
            "building_type":   self.building_type,
        }
        building_keys = {"building_id", "building_height", "building_type"}
        if any(key in kwargs for key in building_keys):
            self._invalidate_building_cache()
            building_id = kwargs.get("building_id", self.building_id[row, col])
            building_height = kwargs.get("building_height", self.building_height[row, col])
            building_type = kwargs.get("building_type", self.building_type[row, col])

            if quantize:
                stored_height = self.quantize_building_height(building_height, self.dz)
            else:
                try:
                    stored_height = float(building_height)
                except (TypeError, ValueError):
                    stored_height = self.FLOAT_FILL

            if stored_height <= self.FLOAT_FILL or not np.isfinite(stored_height):
                self.building_id[row, col] = self.INT_FILL
                self.building_height[row, col] = self.FLOAT_FILL
                self.building_type[row, col] = self.INT_FILL
            else:
                self.building_id[row, col] = int(building_id)
                self.building_height[row, col] = stored_height
                self.building_type[row, col] = int(building_type)

        for key, value in kwargs.items():
            if key in building_keys:
                continue
            if key in layer_map:
                if key == "zt":
                    if quantize:
                        layer_map[key][row, col] = self.quantize_terrain_height(value, self.dz)
                    else:
                        try:
                            layer_map[key][row, col] = float(value)
                        except (TypeError, ValueError):
                            layer_map[key][row, col] = 0.0
                else:
                    layer_map[key][row, col] = value
            elif key == "water_temperature":
                self.water_pars[0, row, col] = value

    def discretize_all_heights(self):
        """Apply PALMPaint's dz-based discretization rules to the whole model."""
        old_zt = self.zt.copy()
        old_building_height = self.building_height.copy()
        old_building_id = self.building_id.copy()
        old_building_type = self.building_type.copy()

        terrain_quantizer = np.vectorize(lambda value: self.quantize_terrain_height(value, self.dz), otypes=[np.float32])
        building_quantizer = np.vectorize(lambda value: self.quantize_building_height(value, self.dz), otypes=[np.float32])

        self.zt[:, :] = terrain_quantizer(self.zt)
        self.building_height[:, :] = building_quantizer(self.building_height)

        removed_mask = self.building_height <= self.FLOAT_FILL
        self.building_id[removed_mask] = self.INT_FILL
        self.building_type[removed_mask] = self.INT_FILL

        terrain_changed = int(np.count_nonzero(np.abs(self.zt - old_zt) > 1e-6))
        building_changed = int(
            np.count_nonzero(np.abs(self.building_height - old_building_height) > 1e-6)
        )
        cleared_buildings = int(
            np.count_nonzero(
                (old_building_height > self.FLOAT_FILL) & (self.building_height <= self.FLOAT_FILL)
            )
        )
        id_changed = int(np.count_nonzero(self.building_id != old_building_id))
        type_changed = int(np.count_nonzero(self.building_type != old_building_type))

        return {
            "terrain_changed": terrain_changed,
            "building_height_changed": building_changed,
            "cleared_buildings": cleared_buildings,
            "building_id_changed": id_changed,
            "building_type_changed": type_changed,
        }

    def validate(self, georef=None):
        """Check surface-layer consistency rules.

        Delegates to :func:`base.validation.validate` — see that module for
        the full rule documentation.

        Parameters
        ----------
        georef : GeoReference or None, optional
            If supplied, coordinate-range checks (DRV0001) are also run.

        Returns
        -------
        dict with keys 'valid' (bool) and 'violations' (list of str).
        """
        from base.validation import validate as _validate
        return _validate(self, georef=georef)

    def clean_static_driver(self):
        """Clean common static-driver inconsistencies in-place."""
        from base.validation import clean_model as _clean_model
        return _clean_model(self)

    def preview_filter_sweep(self):
        """Preview PALM-style hole and cavity filtering."""
        from base.palm_preflight import preview_filter_sweep as _preview_filter_sweep
        return _preview_filter_sweep(self)

    def apply_filter_sweep(self):
        """Apply PALM-style hole and cavity filtering."""
        from base.palm_preflight import apply_filter_sweep as _apply_filter_sweep
        return _apply_filter_sweep(self)

    def preview_split_building_ids(self):
        """Preview splitting disconnected building footprints to unique IDs."""
        from base.palm_preflight import preview_split_building_ids as _preview_split_building_ids
        return _preview_split_building_ids(self)

    def apply_split_building_ids(self):
        """Apply splitting disconnected building footprints to unique IDs."""
        from base.palm_preflight import apply_split_building_ids as _apply_split_building_ids
        return _apply_split_building_ids(self)

    def preview_align_building_terrain(self):
        """Preview terrain alignment to PALM's per-building oro_max logic."""
        from base.palm_preflight import preview_align_building_terrain as _preview_align_building_terrain
        return _preview_align_building_terrain(self)

    def apply_align_building_terrain(self):
        """Apply terrain alignment to PALM's per-building oro_max logic."""
        from base.palm_preflight import apply_align_building_terrain as _apply_align_building_terrain
        return _apply_align_building_terrain(self)

    def get_pixel(self, row, col):
        """Return all data layer values for one pixel as a plain dict."""
        return {
            "zt":              float(self.zt[row, col]),
            "vegetation_type": int(self.vegetation_type[row, col]),
            "soil_type":       int(self.soil_type[row, col]),
            "pavement_type":   int(self.pavement_type[row, col]),
            "water_type":      int(self.water_type[row, col]),
            "building_id":     int(self.building_id[row, col]),
            "building_height": float(self.building_height[row, col]),
            "building_type":   int(self.building_type[row, col]),
            
            "water_temperature": float(self.water_pars[0, row, col]),
        }

    def get_height_range(self):
        """Return min/max terrain height for grayscale normalization."""
        valid = self.zt[self.zt >= 0.0]
        if valid.size == 0:
            return 0.0, 1.0
        z_min = float(valid.min())
        z_max = float(valid.max())
        if z_max <= z_min:
            z_max = z_min + 1.0
        return z_min, z_max

    @staticmethod
    def _terrain_palette(levels):
        """Create a terrain-like palette (green to brown), excluding blue."""
        # Anchor colors inspired by matplotlib terrain, restricted to land tones.
        anchors = [
            (0x2E, 0x8B, 0x57),  # sea green
            (0x7F, 0xB0, 0x69),  # grass/sage
            (0xC8, 0xC6, 0x7A),  # dry grass
            (0xB8, 0x92, 0x5A),  # ochre
            (0x8B, 0x5A, 0x2B),  # brown
        ]

        levels = max(1, int(levels))
        if levels == 1:
            r, g, b = anchors[-1]
            return [f"#{r:02x}{g:02x}{b:02x}"]

        palette = []
        segments = len(anchors) - 1
        for idx in range(levels):
            pos = idx / (levels - 1)
            seg_pos = pos * segments
            seg_idx = min(segments - 1, int(seg_pos))
            frac = seg_pos - seg_idx
            c0 = anchors[seg_idx]
            c1 = anchors[seg_idx + 1]
            r = int(round(c0[0] + (c1[0] - c0[0]) * frac))
            g = int(round(c0[1] + (c1[1] - c0[1]) * frac))
            b = int(round(c0[2] + (c1[2] - c0[2]) * frac))
            palette.append(f"#{r:02x}{g:02x}{b:02x}")
        return palette

    def get_height_color(self, row, col, z_min=0.0, z_step=1.0, levels=10):
        """Map terrain height to discrete terrain-like color levels."""
        z_step = max(1e-6, float(z_step))
        levels = max(1, int(levels))
        z_val = max(0.0, float(self.zt[row, col]))

        level_index = int((z_val - float(z_min)) // z_step)
        level_index = min(max(level_index, 0), levels - 1)
        return self._terrain_palette(levels)[level_index]

    def get_soil_color(self, row, col):
        """Map soil type to a dedicated soil-view color."""
        soil_type = int(self.soil_type[row, col])
        soil_section = self.surface_config.get("soil", {})
        soil_types = soil_section.get("types", {})
        soil_def = soil_types.get(soil_type, {})
        display = soil_def.get("display", {})
        color = display.get("color")
        if color:
            return color

        # Fallback palette for soils if no display color is configured.
        fallback = {
            1: "#c2b280",  # coarse
            2: "#b49a6a",  # medium
            3: "#9f8458",  # medium-fine
            4: "#8b6f47",  # fine
            5: "#6e5438",  # very fine
            6: "#4f3c2c",  # organic
        }
        return fallback.get(soil_type, "#8f7a5a")

    def get_water_color(self, row, col):
        """Resolve water color from surface configuration."""
        water_type = int(self.water_type[row, col])
        water_section = self.surface_config.get("water", {})
        water_types = water_section.get("types", {})
        water_def = water_types.get(water_type, {})
        display = water_def.get("display", {})
        return display.get("color", "blue")

    def get_height_grayscale_color(self, row, col, z_min=0.0, z_max=10.0):
        """Map terrain height to grayscale for landcover background display."""
        z_min = float(z_min)
        z_max = float(z_max)
        if not np.isfinite(z_min):
            z_min = 0.0
        if not np.isfinite(z_max) or z_max <= z_min:
            z_max = z_min + max(float(self.dz), 1.0)
        z_val = float(max(0.0, self.zt[row, col]))
        frac = (z_val - z_min) / (z_max - z_min)
        frac = min(max(frac, 0.0), 1.0)
        gray = int(round(255.0 * frac))
        return f"#{gray:02x}{gray:02x}{gray:02x}"

    def get_color(
        self,
        row,
        col,
        view_mode="landcover",
        visible_layers=None,
        show_height_background=False,
        show_soil_background=False,
        height_bg_min=0.0,
        height_bg_max=10.0,
        z_min=0.0,
        z_max=None,
        z_step=1.0,
        levels=10,
    ):
        """Derive display colour from layer data.

        Priority order:
          water > building > pavement > vegetation > bare soil
        """
        if view_mode == "heightmap":
            return self.get_height_color(row, col, z_min=z_min, z_step=z_step, levels=levels)

        if view_mode == "soil":
            if self.water_type[row, col] > self.INT_FILL:
                return self.get_water_color(row, col)
            if self.building_id[row, col] > self.INT_FILL or self.building_height[row, col] > 0.0:
                return "black"
            return self.get_soil_color(row, col)

        visible_layers = set(visible_layers) if visible_layers is not None else {
            "vegetation", "pavement", "water", "building"
        }

        if "water" in visible_layers and self.water_type[row, col] > self.INT_FILL:
            return self.get_water_color(row, col)
        # Robust building detection for legacy files with wrapped building_id values.
        if (
            "building" in visible_layers
            and (
                self.building_id[row, col] > self.INT_FILL
                or self.building_height[row, col] > 0.0
            )
        ):
            return "black"
        if "pavement" in visible_layers and self.pavement_type[row, col] > self.INT_FILL:
            pav_type = int(self.pavement_type[row, col])
            
            pavement_section = self.surface_config.get("pavement", {})
            pavement_types = pavement_section.get("types", {})
            pavement_def = pavement_types.get(pav_type, {})
            display = pavement_def.get("display", {})
            color = display.get("color")
            if color:
                return color
        if "vegetation" in visible_layers and self.vegetation_type[row, col] > self.INT_FILL:
            veg_type = int(self.vegetation_type[row, col])
            
            vegetation_section = self.surface_config.get("vegetation", {})
            vegetation_types = vegetation_section.get("types", {})
            vegetation_def = vegetation_types.get(veg_type, {})
            display = vegetation_def.get("display", {})
            color = display.get("color")
            if color:
                return color

        if show_height_background:
            return self.get_height_grayscale_color(
                row,
                col,
                z_min=height_bg_min,
                z_max=height_bg_max,
            )
        if show_soil_background:
            return self.get_soil_color(row, col)
        return "white"  # all layers are fill — bare / erased cell

    # ------------------------------------------------------------------
    # Vectorised colour helpers (backend-independent)
    # ------------------------------------------------------------------

    @staticmethod
    def _hex_to_rgb(color_str):
        """Convert a Tk/CSS colour string to an (R, G, B) uint8 tuple.

        Handles:
        * ``#RRGGBB`` and ``#RGB`` hex notation
        * Named CSS3 / X11 colours listed in the module-level ``_CSS_COLORS``
          table, including Tk-specific variants such as ``"green4"``.

        Unknown names return a neutral mid-grey ``(200, 200, 200)``.
        """
        s = color_str.strip()
        if s.startswith("#"):
            c = s[1:]
            if len(c) == 6:
                return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
            if len(c) == 3:
                return (int(c[0] * 2, 16), int(c[1] * 2, 16), int(c[2] * 2, 16))
        return _CSS_COLORS.get(s.lower(), (200, 200, 200))

    def _apply_water_to_array(self, arr):
        """Overwrite *arr* in-place for all water cells (any view mode)."""
        _hx = self._hex_to_rgb
        # Default water blue for types not present in surface_config
        arr[self.water_type > self.INT_FILL] = (0, 0, 255)
        # Per-type override from config
        for type_id, defn in (
            self.surface_config.get("water", {}).get("types", {}).items()
        ):
            c = defn.get("display", {}).get("color", "blue")
            arr[self.water_type == int(type_id)] = _hx(c)

    def _color_array_heightmap(self, arr, z_min=0.0, z_step=1.0, levels=10):
        """Fill *arr* in-place with terrain-palette colours for heightmap view."""
        z_step = max(1e-6, float(z_step))
        levels = max(1, int(levels))
        palette_hex = self._terrain_palette(levels)
        palette_rgb = [self._hex_to_rgb(c) for c in palette_hex]
        z_vals = np.maximum(0.0, self.zt.astype(float))
        level_indices = np.clip(
            ((z_vals - float(z_min)) / z_step).astype(int), 0, levels - 1
        )
        for i, rgb in enumerate(palette_rgb):
            arr[level_indices == i] = rgb
        return arr

    def _color_array_height_gray(self, arr, z_min=0.0, z_max=10.0):
        """Fill *arr* in-place with grayscale terrain colours."""
        z_min = float(z_min)
        z_max = float(z_max)
        if not np.isfinite(z_min):
            z_min = 0.0
        if not np.isfinite(z_max) or z_max <= z_min:
            z_max = z_min + max(float(self.dz), 1.0)
        z_vals = np.maximum(0.0, self.zt.astype(float))
        frac = np.clip((z_vals - z_min) / (z_max - z_min), 0.0, 1.0)
        gray = np.rint(255.0 * frac).astype(np.uint8)
        arr[:, :, 0] = gray
        arr[:, :, 1] = gray
        arr[:, :, 2] = gray
        return arr

    def _color_array_soil(self, arr):
        """Fill *arr* in-place with soil colours only."""
        arr[:] = self._hex_to_rgb("#8f7a5a")
        soil_fb = {
            1: "#c2b280", 2: "#b49a6a", 3: "#9f8458",
            4: "#8b6f47", 5: "#6e5438", 6: "#4f3c2c",
        }
        for tid, color in soil_fb.items():
            arr[self.soil_type == tid] = self._hex_to_rgb(color)
        for type_id, defn in (
            self.surface_config.get("soil", {}).get("types", {}).items()
        ):
            color = defn.get("display", {}).get("color")
            if color:
                arr[self.soil_type == int(type_id)] = self._hex_to_rgb(color)
        return arr

    def get_color_array_rgb(
        self,
        view_mode="landcover",
        visible_layers=None,
        show_height_background=False,
        show_soil_background=False,
        height_bg_min=0.0,
        height_bg_max=10.0,
        z_min=0.0,
        z_max=None,
        z_step=1.0,
        levels=10,
    ):
        """Return an ``(ny, nx, 3)`` uint8 RGB array for the current grid.

        Vectorised equivalent of calling :meth:`get_color` for every cell.
        Layer priority is identical to :meth:`get_color`:

            water > building > pavement > vegetation > bare soil (white)

        Parameters mirror those of :meth:`get_color`.
        """
        ny, nx = self.ny, self.nx
        # White = bare / erased cell (default for landcover)
        arr = np.full((ny, nx, 3), 255, dtype=np.uint8)
        _hx = self._hex_to_rgb

        if view_mode == "heightmap":
            return self._color_array_heightmap(arr, z_min, z_step, levels)

        if view_mode == "soil":
            # Soil-view: every non-building, non-water cell shows its soil colour.
            # Start with the fallback-of-fallback colour.
            self._color_array_soil(arr)
            # Step 3: buildings → black
            arr[
                (self.building_id > self.INT_FILL) | (self.building_height > 0.0)
            ] = (0, 0, 0)
            # Step 4: water (highest priority)
            self._apply_water_to_array(arr)
            return arr

        # ---- landcover (default) -----------------------------------------
        visible_layers = set(visible_layers) if visible_layers is not None else {
            "vegetation", "pavement", "water", "building"
        }
        if show_height_background:
            self._color_array_height_gray(
                arr,
                z_min=height_bg_min,
                z_max=height_bg_max,
            )
        elif show_soil_background:
            self._color_array_soil(arr)
        # Apply lowest → highest priority so each layer overwrites the previous.

        # Priority 1 (lowest): vegetation
        if "vegetation" in visible_layers:
            for type_id, defn in (
                self.surface_config.get("vegetation", {}).get("types", {}).items()
            ):
                c = defn.get("display", {}).get("color")
                if c:
                    arr[self.vegetation_type == int(type_id)] = _hx(c)

        # Priority 2: pavement (overwrites vegetation where present)
        if "pavement" in visible_layers:
            for type_id, defn in (
                self.surface_config.get("pavement", {}).get("types", {}).items()
            ):
                c = defn.get("display", {}).get("color")
                if c:
                    arr[self.pavement_type == int(type_id)] = _hx(c)

        # Priority 3: building → black
        if "building" in visible_layers:
            arr[
                (self.building_id > self.INT_FILL) | (self.building_height > 0.0)
            ] = (0, 0, 0)

        # Priority 4 (highest): water
        if "water" in visible_layers:
            self._apply_water_to_array(arr)

        return arr

    # ------------------------------------------------------------------
    # Compatibility helpers (used by create_sd, load_sd, report)
    # ------------------------------------------------------------------

    def to_legacy_dict(self):
        """Return a {(row, col): pixel_dict} mapping.

        Compatible with create_sd.Save() and report.generate_report().
        All layer arrays are extracted in bulk via numpy before building
        the dict, avoiding per-cell indexed accesses.
        """
        zt_f   = self.zt.ravel().astype(float)
        veg_f  = self.vegetation_type.ravel().astype(int)
        soil_f = self.soil_type.ravel().astype(int)
        pav_f  = self.pavement_type.ravel().astype(int)
        wat_f  = self.water_type.ravel().astype(int)
        bid_f  = self.building_id.ravel().astype(int)
        bh_f   = self.building_height.ravel().astype(float)
        bt_f   = self.building_type.ravel().astype(int)
        wt_f   = self.water_pars[0].ravel().astype(float)
        return {
            (r, c): {
                "zt":                float(zt_f[i]),
                "vegetation_type":   int(veg_f[i]),
                "soil_type":         int(soil_f[i]),
                "pavement_type":     int(pav_f[i]),
                "water_type":        int(wat_f[i]),
                "building_id":       int(bid_f[i]),
                "building_height":   float(bh_f[i]),
                "building_type":     int(bt_f[i]),
                "water_temperature": float(wt_f[i]),
            }
            for i, (r, c) in enumerate(np.ndindex(self.ny, self.nx))
        }

    @classmethod
    def from_legacy_dict(cls, pixel_dict, nx, ny, res, dz=None, surface_config=None, quantize=False):
        """Build a GridModel from the {(row, col): pixel_dict} format
        returned by load_sd.Load().
        """
        model = cls(nx, ny, res, dz, surface_config)
        for (row, col), data in pixel_dict.items():
            model.set_pixel(row, col, quantize=quantize, **data)
        return model
