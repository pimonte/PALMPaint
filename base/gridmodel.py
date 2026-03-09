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
        self.building_id     = np.full((ny, nx), self.INT_FILL,  dtype=np.int16)
        self.building_height = np.full((ny, nx), self.FLOAT_FILL, dtype=np.float32)
        self.building_type   = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)

        self.water_pars = np.full((7, ny, nx), self.FLOAT_FILL, dtype=np.float32)
        # Future USM per-surface properties — populated by 3D editor?
        #self.building_surface_pars = {}
    def clear_water_parameters(self, row, col):
        """Reset all water parameters for one pixel."""
        self.water_pars[:, row, col] = self.FLOAT_FILL   
         
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
        """
        data = {}
        for row in range(self.ny):
            for col in range(self.nx):
                data[(row, col)] = self.get_pixel(row, col)
        return data

    @classmethod
    def from_legacy_dict(cls, pixel_dict, nx, ny, res, surface_config=None):
        """Build a GridModel from the {(row, col): pixel_dict} format
        returned by load_sd.Load().
        """
        model = cls(nx, ny, res, surface_config)
        for (row, col), data in pixel_dict.items():
            model.set_pixel(row, col, **data)
        return model
