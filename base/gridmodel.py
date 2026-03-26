"""
Data model for the PALMPaint grid.

Holds all surface layer data as numpy arrays with shape (ny, nx).
Contains no Tkinter or display logic — can be used by any view backend
or a future 3D viewer.

    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

import numpy as np


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

    @staticmethod
    def infer_dz_from_zlad(zlad, fallback):
        """Infer a representative vertical spacing from a zlad coordinate array.

        Some external files contain a leading zero followed by regularly spaced
        layer coordinates (for example ``0, 2, 6, 10, ...``). Using only the
        first difference would underestimate dz in that case, so we use the
        median positive spacing instead.
        """
        if zlad is None:
            return float(fallback)
        zlad = np.asarray(zlad, dtype=np.float32)
        if zlad.size < 2:
            return float(fallback)
        diffs = np.diff(zlad)
        diffs = diffs[np.isfinite(diffs) & (diffs > 0.0)]
        if diffs.size == 0:
            return float(fallback)
        return float(np.median(diffs))

    def __init__(self, nx, ny, res, surface_config=None):
        """
        Parameters
        ----------
        nx, ny : int
            Number of grid cells in x and y direction.
        res : float
            Physical grid width in metres (dx = dy = res).
        surface_config : dict, optional
            Configuration for vegetation types and categories.
        """
        self.nx  = nx
        self.ny  = ny
        self.res = res  # physical resolution in metres
        self.show_grid_lines = True
        self.surface_config = surface_config

        # Default: bare soil everywhere
        self.zt = np.full((ny, nx), 0.0, dtype=np.float32)
        self.vegetation_type = np.full((ny, nx), 1,              dtype=np.int8)
        self.soil_type       = np.full((ny, nx), 1,              dtype=np.int8)
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
        self.next_tree_id += 1
        self._rebuild_resolved_vegetation()

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
        dz = self.infer_dz_from_zlad(zlad, self.res)
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

    def _rebuild_resolved_vegetation(self):
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

        dz = float(self.res)
        max_height = max(t["tree_height"] for t in self.tree_instances)
        nz = int(np.ceil(max_height / dz)) + 1
        if has_loaded:
            nz = max(nz, self._loaded_rv["lad"].shape[0])
        zlad = np.array([k * dz for k in range(nz)], dtype=np.float32)

        lad = np.zeros((nz, self.ny, self.nx), dtype=np.float32)
        bad = np.zeros((nz, self.ny, self.nx), dtype=np.float32)
        tree_id_arr = np.zeros((nz, self.ny, self.nx), dtype=np.int32)

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
            tr = tree["row"]
            tc = tree["col"]
            tid = tree["id"]
            gp = tree.get("generator_params")

            # --- Always use generate_tree() (palm_extinction) ---
            # If no generator_params are stored (old data / compatibility), build
            # a sensible default dict from the per-tree geometry attributes.
            if gp is None:
                h_tree   = float(tree["tree_height"])
                cd       = float(tree["crown_diameter"])
                ch_tree  = float(tree.get("crown_height") or 0.6 * h_tree)
                cr_ratio = ch_tree / cd if cd > 0.0 else 1.0
                gp = {
                    "max_tree_height":   h_tree,
                    "crown_diameter":    cd,
                    "trunk_diameter":    float(tree.get("trunk_diameter") or 0.3),
                    "crown_shape":       1,       # ellipsoid default
                    "crown_ratio":       cr_ratio,
                    "alpha":             5.0,
                    "beta":              3.0,
                    "lai":               float(tree["lai"]),
                    "lad_model":         "palm_extinction",
                    "palm_extinction_k": 0.6,
                    "bad_lad_ratio":     0.025,
                }

            from base.tree_generator_core import generate_tree, TreeParams, Grid
            _grid = Grid(dx=dz, dy=dz, dz=dz, pad_xy=0.0, pad_z=0.0)
            try:
                result = generate_tree(TreeParams(**gp), _grid)
            except Exception:
                # Degenerate fallback: write a single voxel at ground level
                lad[0, tr, tc] += float(tree["lai"]) / dz if dz > 0 else float(tree["lai"])
                tree_id_arr[0, tr, tc] = tid
                continue

            lad_tree = result["lad"]         # (nz_t, ny_t, nx_t)
            bad_tree = result["bad"]         # (nz_t, ny_t, nx_t)
            z_tree   = result["coords"]["z"] # 1-D cell-centre z coords
            nz_t, ny_t, nx_t = lad_tree.shape
            cx_t = nx_t // 2
            cy_t = ny_t // 2
            for iz_t in range(nz_t):
                z_val = z_tree[iz_t]
                # floor maps cell-centre z=(k+0.5)*dz correctly to layer index k
                # (Python's round() uses banker's rounding and would skip odd layers)
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
                        if v > 0.0:
                            lad[iz_g, rr, cc] += v
                            tree_id_arr[iz_g, rr, cc] = tid
                        if b > 0.0:
                            bad[iz_g, rr, cc] += b

        self.resolved_vegetation = {
            "zlad": zlad,
            "lad": lad,
            "bad": bad,
            "tree_id": tree_id_arr,
        }

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

    def set_pixel(self, row, col, **kwargs):
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
        for key, value in kwargs.items():
            if key in layer_map:
                layer_map[key][row, col] = value
            elif key == "water_temperature":
                self.water_pars[0, row, col] = value

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

    def get_color(
        self,
        row,
        col,
        view_mode="landcover",
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

        if self.water_type[row, col] > self.INT_FILL:
            return self.get_water_color(row, col)
        # Robust building detection for legacy files with wrapped building_id values.
        if self.building_id[row, col] > self.INT_FILL or self.building_height[row, col] > 0.0:
            return "black"
        if self.pavement_type[row, col] > self.INT_FILL:
            pav_type = int(self.pavement_type[row, col])
            
            pavement_section = self.surface_config.get("pavement", {})
            pavement_types = pavement_section.get("types", {})
            pavement_def = pavement_types.get(pav_type, {})
            display = pavement_def.get("display", {})
            color = display.get("color")
            if color:
                return color
        if self.vegetation_type[row, col] > self.INT_FILL:
            veg_type = int(self.vegetation_type[row, col])
            
            vegetation_section = self.surface_config.get("vegetation", {})
            vegetation_types = vegetation_section.get("types", {})
            vegetation_def = vegetation_types.get(veg_type, {})
            display = vegetation_def.get("display", {})
            color = display.get("color")
            if color:
                return color
            
            return "white"  # unknown vegetation types

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
    def from_legacy_dict(cls, pixel_dict, nx, ny, res, surface_config=None):
        """Build a GridModel from the {(row, col): pixel_dict} format
        returned by load_sd.Load().
        """
        model = cls(nx, ny, res, surface_config)
        for (row, col), data in pixel_dict.items():
            model.set_pixel(row, col, **data)
        return model
