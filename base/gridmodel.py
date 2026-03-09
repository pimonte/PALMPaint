"""
Data model for the PALMPaint grid.

Holds all surface layer data as numpy arrays with shape (ny, nx).
Contains no Tkinter or display logic — can be used by any view backend
or a future 3D viewer.

    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

import copy
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

    def __init__(self, nx, ny, res):
        """
        Parameters
        ----------
        nx, ny : int
            Number of grid cells in x and y direction.
        res : float
            Physical grid width in metres (dx = dy = res).
        """
        self.nx  = nx
        self.ny  = ny
        self.res = res  # physical resolution in metres

        # Default: bare soil everywhere
        self.vegetation_type = np.full((ny, nx), 1,              dtype=np.int8)
        self.soil_type       = np.full((ny, nx), 1,              dtype=np.int8)
        self.pavement_type   = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)
        self.water_type      = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)
        self.building_id     = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)
        self.building_height = np.full((ny, nx), self.FLOAT_FILL, dtype=np.float32)
        self.building_type   = np.full((ny, nx), self.INT_FILL,  dtype=np.int8)

        # Future USM per-surface properties — populated by 3D editor?
        #self.building_surface_pars = {}

    # ------------------------------------------------------------------
    # Pixel-level access
    # ------------------------------------------------------------------

    def set_pixel(self, row, col, **kwargs):
        """Write data layer values for a single pixel.

        Unknown keys (e.g. 'color', 'outline', 'id') are silently ignored,
        so the method is safe to call with legacy pixel dicts.
        """
        layer_map = {
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

    def get_pixel(self, row, col):
        """Return all data layer values for one pixel as a plain dict."""
        return {
            "vegetation_type": int(self.vegetation_type[row, col]),
            "soil_type":       int(self.soil_type[row, col]),
            "pavement_type":   int(self.pavement_type[row, col]),
            "water_type":      int(self.water_type[row, col]),
            "building_id":     int(self.building_id[row, col]),
            "building_height": float(self.building_height[row, col]),
            "building_type":   int(self.building_type[row, col]),
        }

    def get_color(self, row, col):
        """Derive display colour from layer data.

        Priority order:
          water > building > pavement > vegetation > bare soil
        """
        if self.water_type[row, col]    > self.INT_FILL:
            return "blue"
        if self.building_id[row, col]   > self.INT_FILL:
            return "black"
        if self.pavement_type[row, col] > self.INT_FILL:
            return "grey"
        if self.vegetation_type[row, col] > 1:
            return "green"
        return "brown"  # bare soil / default

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
    def from_legacy_dict(cls, pixel_dict, nx, ny, res):
        """Build a GridModel from the {(row, col): pixel_dict} format
        returned by load_sd.Load().
        """
        model = cls(nx, ny, res)
        for (row, col), data in pixel_dict.items():
            model.set_pixel(row, col, **data)
        return model
