"""
Paint Application is a Tkinter-based pixel painting program for creating
simple SDs for PALM.

    Copyright (C) 2025  Pierre Lampe

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import copy
import math
import os
import time
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.filedialog as fd

import base.report as report
import base.framework as framework
import base.gridmodel as gridmodel
import base.tkbackend as tkbackend
from base.create_sd import Save
from base.load_sd import Load
import base.surface_config as surface_config
import base.welcome_screen as welcome_screen




class PaintApplication(framework.Framework):
    origin = (52.50965, 13.3139, 3455249.0, 5424815.0) # lat, lon, projected x, projected y
    brush_size = 1
    active_cell = None
    

    tool_bar_functions = (
        "vegetation", "pavement", "water", "building", "single_tree")
    height_tool_bar_functions = ("zt_set", "zt_raise", "zt_lower")
    soil_tool_bar_functions = ()
    selected_tool_bar_function = tool_bar_functions[0]
    selected_height_tool_bar_function = height_tool_bar_functions[0]
    selected_soil_type = 1
    
    def get_vegetation_categories(self):
        return self.surface_config["vegetation"]["categories"]

    def get_vegetation_types(self):
        return self.surface_config["vegetation"]["types"]

    def get_vegetation_definition(self, vegetation_type):
        return self.surface_config["vegetation"]["types"][vegetation_type]
    
    def get_pavement_categories(self):
        return self.surface_config["pavement"]["categories"]

    def get_pavement_types(self):
        return self.surface_config["pavement"]["types"]

    def get_pavement_definition(self, pavement_type):
        return self.surface_config["pavement"]["types"][pavement_type]
    
    def get_water_categories(self):
        return self.surface_config["water"]["categories"]

    def get_water_types(self):
        return self.surface_config["water"]["types"]

    def get_water_definition(self, water_type):
        return self.surface_config["water"]["types"][water_type]

    def get_soil_types(self):
        return self.surface_config["soil"]["types"]

    def get_soil_definition(self, soil_type):
        return self.surface_config["soil"]["types"][soil_type]
    
    def refresh_project_info_labels(self):
        """Refresh sidebar labels that depend on the currently loaded project."""
        if hasattr(self, "static_label"):
            self.static_label.config(text=f"Grid width: {self.original_res} m")
    
    def execute_selected_method(self):
        if self.active_cell is None:
            return
        if self.active_view == "heightmap":
            self.height_tool()
            return
        if self.active_view == "soil":
            self.soil_tool()
            return
        func = getattr(
            self, self.selected_tool_bar_function, self.function_not_defined)
        func()

    def quantize_height(self, value):
        """Quantize to original_res steps and clamp to non-negative heights."""
        step = float(self.original_res) if self.original_res > 0 else 1.0
        quantized = round(float(value) / step) * step
        return max(0.0, quantized)

    def height_tool(self):
        """Apply height editing mode (Raise/Lower/Set Height) to brush pixels."""
        center_row, center_col = self.active_cell
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        step = float(self.original_res) if self.original_res > 0 else 1.0

        affected = []
        for row, col in affected_pixels:
            if (row, col) not in self.pixels:
                continue

            current = max(0.0, float(self.model.zt[row, col]))
            if self.selected_height_tool_bar_function == "zt_raise":
                new_height = self.quantize_height(current + step)
            elif self.selected_height_tool_bar_function == "zt_lower":
                new_height = max(0.0, self.quantize_height(current - step))
            else:
                new_height = self.quantize_height(self.height_set_value)

            self.update_pixel(row, col, zt=new_height)
            affected.append((row, col))
        self.backend.update_pixels(affected)

    def soil_tool(self):
        """Paint soil types, but never overwrite water or building cells."""
        row, col = self.active_cell
        affected_pixels = self.get_pixels_in_brush(row, col)

        affected = []
        for row, col in affected_pixels:
            if (row, col) not in self.pixels:
                continue

            is_water = self.model.water_type[row, col] > self.model.INT_FILL
            is_building = (
                self.model.building_id[row, col] > self.model.INT_FILL
                or self.model.building_height[row, col] > 0.0
            )
            if is_water or is_building:
                continue

            self.update_pixel(row, col, soil_type=self.selected_soil_type)
            affected.append((row, col))
        self.backend.update_pixels(affected)
    
    def get_pixels_in_brush(self, center_row, center_col):
        """
        Get all pixels within the brush radius around the center pixel.
        """
        affected_pixels = []
        for row in range(center_row - self.brush_size // 2, center_row + self.brush_size // 2  + 1):
            for col in range(center_col - self.brush_size // 2, center_col + self.brush_size // 2 + 1):
                # Calculate the distance from the center
                if (0 <= row < self.ny) and (0 <= col < self.nx):  # Ensure within bounds
                    distance = math.sqrt((center_row - row)**2 + (center_col - col)**2)
                    if distance <= self.brush_size:
                        affected_pixels.append((row, col))
        return affected_pixels
    
    @property
    def canvas(self):
        """Convenience accessor — delegates to the active render backend."""
        return self.backend.canvas

    @property
    def pixels(self):
        """Convenience accessor — delegates to the active render backend."""
        return self.backend.pixels

    def update_canvas(self, y, x):
        """Update the canvas for a specific pixel."""
        self.backend.update_pixel(y, x)

    def update_pixel(self, row, col, **kwargs):
        """Write data layer values to the model. Display keys are ignored."""
        kwargs.pop("color", None)
        kwargs.pop("outline", None)
        self.model.set_pixel(row, col, **kwargs)
            
    def _apply_brush(self, pixel_data, *, water_temp=None):
        """Reset all surface layers to fill values, then apply pixel_data to
        every cell in the current brush.

        Parameters
        ----------
        pixel_data : dict
            Only the fields that should be set to a meaningful value.
            All other surface layers are automatically reset to the model's
            fill constants (INT_FILL / FLOAT_FILL).
        water_temp : float or None
            When given, calls set_water_parameter(0, row, col, water_temp).
            When None (default), calls clear_water_parameters instead.
        """
        fi = self.model.INT_FILL
        ff = self.model.FLOAT_FILL
        reset = dict(
            vegetation_type=fi, soil_type=fi,
            pavement_type=fi, water_type=fi,
            building_id=fi, building_height=ff, building_type=fi,
        )
        reset.update(pixel_data)
        row, col = self.active_cell
        affected = [
            (r, c)
            for r, c in self.get_pixels_in_brush(row, col)
            if (r, c) in self.pixels
        ]
        for r, c in affected:
            self.update_pixel(r, c, **reset)
            if water_temp is not None:
                self.model.set_water_parameter(0, r, c, water_temp)
            else:
                self.model.clear_water_parameters(r, c)
        self.backend.update_pixels(affected)

    def vegetation(self):
        """Apply vegetation tool to affected pixels."""
        veg_type = self.selected_vegetation_type
        veg_def = self.get_vegetation_definition(veg_type)
        soil_type = veg_def.get("soil_type", self.surface_config["soil"]["default_type"])
        self._apply_brush(dict(vegetation_type=veg_type, soil_type=soil_type))
        
    def pavement(self):
        pavement_type = self.selected_pavement_type
        pav_def = self.get_pavement_definition(pavement_type)
        soil_type = pav_def.get("soil_type", self.surface_config["soil"]["default_type"])
        self._apply_brush(dict(pavement_type=pavement_type, soil_type=soil_type))
        
    def water(self):
        """Apply water tool to affected pixels."""
        self.update_water_temperature()
        self._apply_brush(
            dict(water_type=self.selected_water_type),
            water_temp=self.selected_water_temperature,
        )
        
    def building(self):
        self._apply_brush(dict(
            building_id=self.building_id,
            building_height=self.building_height,
            building_type=self.building_type,
        ))

    def single_tree(self):
        """Place a single resolved tree at the active cell using palm_extinction."""
        from base.tree_species import SHAPE_DEFAULT_K
        self.update_single_tree_attributes()
        self._on_shape_selected()
        row, col = self.active_cell
        # If the Tree Generator dialog was applied, use those params verbatim so
        # that lad_max mode (and any other generator settings) are honoured.
        if self._active_generator_params is not None:
            gen_params = self._active_generator_params
        else:
            gen_params = {
                "max_tree_height":   self.selected_tree_height,
                "crown_diameter":    self.selected_crown_diameter,
                "trunk_diameter":    self.selected_trunk_diameter,
                "crown_ratio":       self.selected_crown_ratio,
                "crown_shape":       self.selected_crown_shape,
                "alpha":             5.0,
                "beta":              3.0,
                "lai":               self.selected_lai,
                "lad_model":         "palm_extinction",
                "palm_extinction_k": SHAPE_DEFAULT_K.get(self.selected_crown_shape, 0.6),
                "bad_lad_ratio":     self.selected_bad_lad_ratio,
            }
        self.model.add_tree(
            row, col,
            tree_height=self.selected_tree_height,
            crown_diameter=self.selected_crown_diameter,
            trunk_diameter=self.selected_trunk_diameter,
            crown_height=self.selected_tree_height * self.selected_crown_ratio,
            lai=self.selected_lai,
            generator_params=gen_params,
        )
        self.backend.redraw_tree_overlay()

    def single_tree_options(self):
        """Display species selector and tree parameter spinboxes in the top bar."""
        from base.tree_species import SPECIES_NAMES, SHAPE_DISPLAY_VALUES, SHAPE_LABELS
        inc = float(self.original_res)

        # --- Species selector ---
        tk.Label(self.top_bar, text="Species:").pack(side="left", padx=(5, 2))
        self._tree_species_var = tk.StringVar(value="Default")
        species_cb = ttk.Combobox(
            self.top_bar, textvariable=self._tree_species_var,
            values=SPECIES_NAMES, state="readonly", width=14,
        )
        species_cb.pack(side="left")
        species_cb.bind("<<ComboboxSelected>>", self._on_species_change)

        ttk.Separator(self.top_bar, orient="vertical").pack(
            side="left", fill="y", padx=6, pady=2)

        # --- Shape dropdown ---
        tk.Label(self.top_bar, text="Shape:").pack(side="left", padx=(4, 2))
        self._tree_shape_var = tk.StringVar(
            value=SHAPE_LABELS.get(self.selected_crown_shape, "1 - Spherical"))
        shape_cb = ttk.Combobox(
            self.top_bar, textvariable=self._tree_shape_var,
            values=SHAPE_DISPLAY_VALUES, state="readonly", width=16,
        )
        shape_cb.pack(side="left")
        shape_cb.bind("<<ComboboxSelected>>", self._on_shape_selected)

        # --- Crown ratio ---
        tk.Label(self.top_bar, text="H/D ratio:").pack(side="left", padx=(6, 2))
        self.tree_ratio_var = tk.StringVar(value=str(self.selected_crown_ratio))
        sb = tk.Spinbox(self.top_bar, from_=0.1, to=5.0, increment=0.1, width=5,
                        textvariable=self.tree_ratio_var,
                        command=self._refresh_single_tree_controls)
        sb.pack(side="left")
        sb.bind("<FocusOut>", self._refresh_single_tree_controls)
        sb.bind("<Return>",   self._refresh_single_tree_controls)
        sb.bind("<KeyRelease>", self._refresh_single_tree_controls)

        # --- Crown diameter ---
        tk.Label(self.top_bar, text="Crown Diam.:").pack(side="left", padx=(6, 2))
        self.tree_crown_var = tk.StringVar(value=str(self.selected_crown_diameter))
        sb = tk.Spinbox(self.top_bar, from_=1.0, to=30.0, increment=inc, width=5,
                        textvariable=self.tree_crown_var,
                        command=self._refresh_single_tree_controls)
        sb.pack(side="left")
        sb.bind("<FocusOut>", self._refresh_single_tree_controls)
        sb.bind("<Return>",   self._refresh_single_tree_controls)
        sb.bind("<KeyRelease>", self._refresh_single_tree_controls)

        # --- Tree height ---
        tk.Label(self.top_bar, text="Tree Height:").pack(side="left", padx=(6, 2))
        self.tree_height_var = tk.StringVar(value=str(self.selected_tree_height))
        sb = tk.Spinbox(self.top_bar, from_=1.0, to=50.0, increment=inc, width=5,
                        textvariable=self.tree_height_var,
                        command=self._refresh_single_tree_controls)
        sb.pack(side="left")
        sb.bind("<FocusOut>", self._refresh_single_tree_controls)
        sb.bind("<Return>",   self._refresh_single_tree_controls)
        sb.bind("<KeyRelease>", self._refresh_single_tree_controls)

        # --- LAI ---
        tk.Label(self.top_bar, text="LAI:").pack(side="left", padx=(6, 2))
        self.tree_lai_var = tk.StringVar(value=str(self.selected_lai))
        sb = tk.Spinbox(self.top_bar, from_=0.1, to=20.0, increment=0.1, width=5,
                        textvariable=self.tree_lai_var,
                        command=self._refresh_single_tree_controls)
        sb.pack(side="left")
        sb.bind("<FocusOut>", self._refresh_single_tree_controls)
        sb.bind("<Return>",   self._refresh_single_tree_controls)
        sb.bind("<KeyRelease>", self._refresh_single_tree_controls)

        # --- BAD/LAD ratio ---
        tk.Label(self.top_bar, text="BAD/LAD:").pack(side="left", padx=(6, 2))
        self.tree_bad_var = tk.StringVar(value=str(self.selected_bad_lad_ratio))
        sb = tk.Spinbox(self.top_bar, from_=0.0, to=1.0, increment=0.005, width=6,
                        textvariable=self.tree_bad_var,
                        command=self._refresh_single_tree_controls)
        sb.pack(side="left")
        sb.bind("<FocusOut>", self._refresh_single_tree_controls)
        sb.bind("<Return>",   self._refresh_single_tree_controls)
        sb.bind("<KeyRelease>", self._refresh_single_tree_controls)

        # --- Trunk diameter ---
        tk.Label(self.top_bar, text="Trunk Diam.:").pack(side="left", padx=(6, 2))
        self.tree_trunk_var = tk.StringVar(value=str(self.selected_trunk_diameter))
        sb = tk.Spinbox(self.top_bar, from_=0.1, to=5.0, increment=0.05, width=5,
                        textvariable=self.tree_trunk_var,
                        command=self._refresh_single_tree_controls)
        sb.pack(side="left")
        sb.bind("<FocusOut>", self._refresh_single_tree_controls)
        sb.bind("<Return>",   self._refresh_single_tree_controls)
        sb.bind("<KeyRelease>", self._refresh_single_tree_controls)

        ttk.Separator(self.top_bar, orient="vertical").pack(
            side="left", fill="y", padx=6, pady=2)

        ttk.Button(
            self.top_bar, text="Tree Generator (alpha)",
            command=self._open_tree_generator_dialog,
        ).pack(side="left", padx=(0, 4))

        ttk.Separator(self.top_bar, orient="vertical").pack(
            side="left", fill="y", padx=6, pady=2)

        self._bad_enabled_var = tk.BooleanVar(value=self.bad_enabled)
        tk.Checkbutton(
            self.top_bar, text="Write BAD",
            variable=self._bad_enabled_var,
            command=lambda: setattr(self, "bad_enabled", self._bad_enabled_var.get()),
        ).pack(side="left", padx=(0, 4))

        tk.Label(self.top_bar, text="  Right-click = remove",
                 fg="gray").pack(side="left", padx=8)

    def _on_species_change(self, event=None):
        """Populate all spinboxes from the selected species."""
        from base.tree_species import SPECIES_NAMES, get_species, SHAPE_LABELS
        name = self._tree_species_var.get()
        if name not in SPECIES_NAMES:
            return
        # Selecting a species overrides any active generator preset.
        self._active_generator_params = None
        sp = get_species(name)
        self.selected_crown_shape    = sp["crown_shape"]
        self.selected_crown_ratio    = sp["crown_ratio"]
        self.selected_crown_diameter = sp["crown_diameter"]
        self.selected_tree_height    = sp["max_tree_height"]
        self.selected_lai            = sp["lai_summer"]
        self.selected_bad_lad_ratio  = sp["bad_lad_ratio"]
        self.selected_trunk_diameter = sp["trunk_diameter"]
        # Push to spinboxes
        try:
            self._tree_shape_var.set(SHAPE_LABELS.get(sp["crown_shape"], "1 - Ellipsoid"))
            self.tree_ratio_var.set(str(sp["crown_ratio"]))
            self.tree_crown_var.set(str(sp["crown_diameter"]))
            self.tree_height_var.set(str(sp["max_tree_height"]))
            self.tree_lai_var.set(str(sp["lai_summer"]))
            self.tree_bad_var.set(str(sp["bad_lad_ratio"]))
            self.tree_trunk_var.set(str(sp["trunk_diameter"]))
        except AttributeError:
            pass
        self._refresh_single_tree_preview()

    def _on_shape_selected(self, event=None):
        """Read shape combobox selection and update selected_crown_shape."""
        label = self._tree_shape_var.get()
        try:
            self.selected_crown_shape = int(label.split(" ")[0])
        except (ValueError, IndexError):
            pass
        self._refresh_single_tree_preview()

    def _open_tree_generator_dialog(self):
        """Open (or show) the Tree Generator dialog (optional visual tool)."""
        from base.tree_generator_dialog import TreeGeneratorDialog
        if self._tree_gen_dialog is None or not self._tree_gen_dialog.winfo_exists():
            self._tree_gen_dialog = TreeGeneratorDialog(
                self.root,
                on_apply_callback=self._on_generator_apply,
                get_resolution=lambda: self.model.res,
            )
        else:
            self._tree_gen_dialog.deiconify()
            self._tree_gen_dialog.lift()

    def _on_generator_apply(self, params_dict):
        """Callback from TreeGeneratorDialog — sync parameters back to spinboxes."""
        from base.tree_species import SHAPE_LABELS
        mapping = [
            ("selected_tree_height",    "tree_height_var",   "max_tree_height"),
            ("selected_crown_diameter", "tree_crown_var",    "crown_diameter"),
            ("selected_lai",            "tree_lai_var",      "lai"),
            ("selected_crown_ratio",    "tree_ratio_var",    "crown_ratio"),
            ("selected_bad_lad_ratio",  "tree_bad_var",      "bad_lad_ratio"),
            ("selected_trunk_diameter", "tree_trunk_var",    "trunk_diameter"),
        ]
        for attr, var_name, key in mapping:
            val = params_dict.get(key)
            if val is not None:
                setattr(self, attr, float(val))
                try:
                    getattr(self, var_name).set(str(float(val)))
                except AttributeError:
                    pass
        # Store the full params dict so single_tree() can use it verbatim
        # (e.g. lad_max mode, beta_density model, custom alpha/beta, etc.).
        self._active_generator_params = dict(params_dict)
        shape = params_dict.get("crown_shape")
        if shape is not None:
            self.selected_crown_shape = int(shape)
            try:
                self._tree_shape_var.set(
                    SHAPE_LABELS.get(int(shape), "1 - Ellipsoid"))
            except AttributeError:
                pass
        self._refresh_single_tree_preview()

    def _clear_generator(self):
        """Reset to Default species parameters."""
        self._tree_species_var.set("Default")
        self._on_species_change()

    def update_single_tree_attributes(self, event=None):
        """Read all spinbox values for the single-tree tool."""
        for attr, var_name, cast in [
            ("selected_tree_height",    "tree_height_var",  float),
            ("selected_crown_diameter", "tree_crown_var",   float),
            ("selected_lai",            "tree_lai_var",     float),
            ("selected_crown_ratio",    "tree_ratio_var",   float),
            ("selected_bad_lad_ratio",  "tree_bad_var",     float),
            ("selected_trunk_diameter", "tree_trunk_var",   float),
        ]:
            try:
                setattr(self, attr, cast(getattr(self, var_name).get()))
            except (ValueError, AttributeError):
                pass
        # Shape is read from the combobox via _on_shape_selected; no need to reparse here.

    def _refresh_single_tree_preview(self):
        """Refresh the single-tree hover preview when toolbar values change."""
        if self.selected_tool_bar_function != "single_tree":
            return
        if self.hover_cell is None:
            return
        row, col = self.hover_cell
        if 0 <= row < self.ny and 0 <= col < self.nx:
            self.update_hover_preview(row, col)

    def _refresh_single_tree_controls(self, event=None):
        """Sync single-tree input fields and refresh the hover preview.

        Any manual spinbox change discards the active generator preset so the
        tool reverts to building params from the current spinbox values.
        """
        try:
            float(self.tree_lai_var.get())
        except (ValueError, AttributeError):
            try:
                self.tree_lai_var.set(str(self.selected_lai))
            except AttributeError:
                pass
        self._active_generator_params = None
        self.update_single_tree_attributes()
        self._refresh_single_tree_preview()

    def _erase_tree_at(self, row, col):
        """Erase tree data at (row, col). Called by both right-click and right-drag."""
        tid = self.model.get_tree_id_at(row, col)
        if tid > 0:
            matching = [t for t in self.model.tree_instances if t["id"] == tid]
            if matching:
                self.model.remove_tree_by_id(tid)
                self.backend.redraw_tree_overlay()
                return
        if self.model.has_lad_at(row, col):
            self.model.remove_loaded_lad_at(row, col)
            self.backend.redraw_tree_overlay()

    def on_right_click(self, event):
        """Remove a tree when right-clicking on any of its cells.

        Only active when the single_tree tool is selected.
        Three cases are handled in order:
        1. The cell belongs to a painted tree (has a tree_id) → remove that
           whole tree by id, regardless of which pixel was clicked.
        2. The cell has lad > 0 but no tree_id (loaded from an external file
           without per-tree IDs) → erase only that one cell from _loaded_rv.
        3. No vegetation data at this cell → do nothing.
        """
        if self.selected_tool_bar_function != "single_tree":
            return
        row, col = self.get_mouse_cell(event)
        if not (0 <= row < self.ny and 0 <= col < self.nx):
            return
        self.save_state()
        self._erase_tree_at(row, col)

    def on_right_click_drag(self, event):
        """Continue erasing while holding right mouse button (single_tree tool only)."""
        if self.selected_tool_bar_function != "single_tree":
            return
        row, col = self.get_mouse_cell(event)
        if not (0 <= row < self.ny and 0 <= col < self.nx):
            return
        self._erase_tree_at(row, col)

    def bucket_fill(self):
        self.save_state()
        if self.active_view == "soil":
            for (row, col) in self.pixels.keys():
                is_water = self.model.water_type[row, col] > self.model.INT_FILL
                is_building = (
                    self.model.building_id[row, col] > self.model.INT_FILL
                    or self.model.building_height[row, col] > 0.0
                )
                if is_water or is_building:
                    continue
                self.update_pixel(row, col, soil_type=self.selected_soil_type)
            self.backend.update_grid(self.nx, self.ny, self.res)
            return

        fi = self.model.INT_FILL
        ff = self.model.FLOAT_FILL
        reset = dict(
            vegetation_type=fi, soil_type=fi,
            pavement_type=fi, water_type=fi,
            building_id=fi, building_height=ff, building_type=fi,
        )

        if self.selected_tool_bar_function == "vegetation":
            veg_type = self.selected_vegetation_type
            veg_def = self.get_vegetation_definition(veg_type)
            soil_type = veg_def.get("soil_type", self.surface_config["soil"]["default_type"])
            pixel_data = {**reset, "vegetation_type": veg_type, "soil_type": soil_type}
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col, **pixel_data)
                self.model.clear_water_parameters(row, col)
        elif self.selected_tool_bar_function == "pavement":
            pavement_type = self.selected_pavement_type
            pav_def = self.get_pavement_definition(pavement_type)
            soil_type = pav_def.get("soil_type", self.surface_config["soil"]["default_type"])
            pixel_data = {**reset, "pavement_type": pavement_type, "soil_type": soil_type}
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col, **pixel_data)
                self.model.clear_water_parameters(row, col)
        elif self.selected_tool_bar_function == "water":
            self.update_water_temperature()
            pixel_data = {**reset, "water_type": self.selected_water_type}
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col, **pixel_data)
                self.model.set_water_parameter(0, row, col, self.selected_water_temperature)
        elif self.selected_tool_bar_function == "building":
            pixel_data = {**reset,
                          "building_id": self.building_id,
                          "building_height": self.building_height,
                          "building_type": self.building_type}
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col, **pixel_data)
                self.model.clear_water_parameters(row, col)
        self.backend.update_grid(self.nx, self.ny, self.res)
        

                
 # ------------------ File Menu Operations ------------------
    
    def new_project(self):
        if not self.confirm_discard_unsaved("New Project"):
            return

        result = welcome_screen.get_welcome_input(self.root)
        
        if result[0] == "load":
            _, file_path = result
            self.load_project_netcdf_from_path(file_path)
            return
            
        _, new_nx, new_ny, new_res = result
        self.nx = new_nx
        self.ny = new_ny
        self.original_res = new_res
        self.res = new_res
        self.rescale_grid()
        self.undo_stack.clear()
        self.redo_stack.clear()

        self.draw_grid(self.nx, self.ny, self.res)
        self.refresh_project_info_labels()
        
    def confirm_discard_unsaved(self, action_name):
        """Ask for confirmation only when the current project has unsaved changes."""
        if not self.dirty:
            return True
        return tk.messagebox.askyesno(
            action_name,
            "You have unsaved changes. Continue and discard them?",
        )

    def exit_application(self):
        """Close the application, warning first if the project is dirty."""
        if not self.confirm_discard_unsaved("Exit"):
            return
        self.root.destroy()
        
        
    def _resolved_vegetation_for_save(self):
        """Return resolved_vegetation with BAD stripped out if disabled."""
        rv = self.model.resolved_vegetation
        if rv is None or self.bad_enabled:
            return rv
        return {k: (None if k == "bad" else v) for k, v in rv.items()}

    def _save_project_to_file(self, filename="quicksave"):
        """Persist the current project to a NetCDF file."""
        Save(
            self.model.to_legacy_dict(),
            self.original_res,
            self.origin,
            self.surface_config,
            filename,
            tree_instances=self.model.tree_instances,
            resolved_vegetation=self._resolved_vegetation_for_save(),
        )
        self.dirty = False

    def save_netcdf(self, event=None):
        self._save_project_to_file()
        
    def save_as_netcdf(self, event=None):
        file_path = fd.asksaveasfilename(
            defaultextension="",
            filetypes=[("All files", "*"), ("NetCDF files", "*.nc") ]
        )
        if not file_path:
            return
        self._save_project_to_file(file_path)

    def _autosave_filename(self, slot):
        """Return the autosave path for the given rotation slot."""
        return os.path.join(os.getcwd(), f"autosave_{slot + 1}.nc")

    def _schedule_autosave(self):
        """Schedule the next autosave tick based on the current settings."""
        if self._autosave_after_id is not None:
            self.root.after_cancel(self._autosave_after_id)
            self._autosave_after_id = None

        if self.autosave_file_count <= 0 or self.autosave_interval_ms <= 0:
            return

        self._autosave_after_id = self.root.after(
            self.autosave_interval_ms,
            self._run_autosave,
        )

    def _run_autosave(self):
        """Write an autosave snapshot if the project changed since the last save."""
        self._autosave_after_id = None

        try:
            if self.dirty and self.autosave_file_count > 0:
                filename = self._autosave_filename(self._autosave_next_slot)
                self._save_project_to_file(filename)
                self._autosave_next_slot = (
                    self._autosave_next_slot + 1
                ) % self.autosave_file_count
        except Exception as exc:
            print(f"Autosave failed: {exc}")
        finally:
            self._schedule_autosave()

    def open_autosave_settings(self):
        """Open a small dialog to configure autosave interval and rotation size."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Autosave Settings")
        dialog.geometry("360x220")
        dialog.resizable(False, False)

        tk.Label(
            dialog,
            text="Autosave writes rotating NetCDF snapshots in the project folder.",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(12, 6))

        tk.Label(
            dialog,
            text=f"Folder: {os.getcwd()}",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        interval_minutes = max(1, self.autosave_interval_ms // 60000)
        interval_var = tk.StringVar(value=str(interval_minutes))
        file_count_var = tk.StringVar(value=str(self.autosave_file_count))

        form = tk.Frame(dialog)
        form.pack(fill="x", padx=12, pady=4)

        tk.Label(form, text="Interval (minutes):").grid(row=0, column=0, sticky="w", pady=4)
        tk.Entry(form, textvariable=interval_var, width=8).grid(row=0, column=1, sticky="w", pady=4)

        tk.Label(form, text="Autosave files:").grid(row=1, column=0, sticky="w", pady=4)
        tk.Entry(form, textvariable=file_count_var, width=8).grid(row=1, column=1, sticky="w", pady=4)

        tk.Label(
            dialog,
            text="Set files to 0 to disable autosave. Larger values use more disk space.",
            wraplength=320,
            justify="left",
            fg="gray",
        ).pack(anchor="w", padx=12, pady=(8, 10))

        def apply_settings():
            try:
                minutes = int(interval_var.get())
                file_count = int(file_count_var.get())
            except ValueError:
                tk.messagebox.showerror(
                    "Invalid Input",
                    "Please enter whole numbers for minutes and autosave files.",
                )
                return

            if minutes < 1:
                tk.messagebox.showerror(
                    "Invalid Input",
                    "The autosave interval must be at least 1 minute.",
                )
                return
            if file_count < 0:
                tk.messagebox.showerror(
                    "Invalid Input",
                    "The number of autosave files cannot be negative.",
                )
                return

            self.autosave_interval_ms = minutes * 60 * 1000
            self.autosave_file_count = file_count
            if self.autosave_file_count > 0:
                self._autosave_next_slot %= self.autosave_file_count
            else:
                self._autosave_next_slot = 0
            self._schedule_autosave()
            dialog.destroy()

        button_row = tk.Frame(dialog)
        button_row.pack(fill="x", padx=12, pady=8)
        tk.Button(button_row, text="Save", command=apply_settings).pack(side="left")
        tk.Button(button_row, text="Cancel", command=dialog.destroy).pack(side="left", padx=8)

        dialog.grab_set()
        dialog.wait_window()

    def load_project_netcdf_from_path(self, file_path):
        if not file_path:
            return  # No file path provided
        try:
            grid, nx, ny, res, origin, resolved_vegetation = Load(file_path)
        except Exception as e:
            print(f"Error loading NetCDF file: {e}")
            return
        
        # Replace current state with loaded project
        self.nx = nx
        self.ny = ny
        self.original_res = res
        self.res = res
        self.origin = origin
        
        self.model = gridmodel.GridModel.from_legacy_dict(grid, nx, ny, res, self.surface_config)
        self.model.tree_instances = []
        self.model._loaded_rv = resolved_vegetation
        self.model.resolved_vegetation = resolved_vegetation
        loaded_tid = resolved_vegetation.get("tree_id") if resolved_vegetation else None
        if loaded_tid is not None:
            max_id = int(loaded_tid.max())
            if max_id > 0:
                self.model.next_tree_id = max_id + 1
        self.backend.model = self.model
        self.rescale_grid()
        self.undo_stack.clear()
        self.redo_stack.clear()
        
        self.backend.clear()
        self.backend.clear_hover_preview()
        self.backend.draw_grid(self.nx, self.ny, self.res)
        self.backend.update_grid(self.nx, self.ny, self.res)
        self.backend.set_grid_lines_visible(self.show_grid_lines)

        
        self.refresh_project_info_labels()
        self.dirty = False
        
        print(f"Loaded NetCDF project from {file_path}")
            
    def load_project_netcdf(self, event=None):
        """
        Open a file dialog to let the user choose a NetCDF project file,
        then load it using load_sd.Load() and update the canvas.
        """
        if not self.confirm_discard_unsaved("Load Project"):
            return
        file_path = fd.askopenfilename(
            defaultextension="",
            filetypes=[("All files", "*"), ("NetCDF files", "*.nc")]
        )
        if not file_path:
            return  # User cancelled
        self.load_project_netcdf_from_path(file_path)
    
    def save_state(self):
        self.undo_stack.append(copy.deepcopy(self.model))
        self.redo_stack.clear()
        self.dirty = True

    def _capture_canvas_view(self):
        """Return the current canvas view fractions."""
        return self.canvas.xview()[0], self.canvas.yview()[0]

    def _restore_canvas_view(self, xview, yview):
        """Restore a previously captured canvas view."""
        self.canvas.xview_moveto(xview)
        self.canvas.yview_moveto(yview)
        
    def undo(self, event=None):
        if self.undo_stack:
            xview, yview = self._capture_canvas_view()
            state = self.undo_stack.pop()
            self.redo_stack.append(copy.deepcopy(self.model))
            self.model = state
            self.backend.model = self.model
            self.backend.update_grid(self.nx, self.ny, self.res)
            self._restore_canvas_view(xview, yview)
            self.dirty = True
        else:
            print("Nothing to undo.")

    def redo(self, event=None):
        if self.redo_stack:
            xview, yview = self._capture_canvas_view()
            state = self.redo_stack.pop()
            self.undo_stack.append(copy.deepcopy(self.model))
            self.model = state
            self.backend.model = self.model
            self.backend.update_grid(self.nx, self.ny, self.res)
            self._restore_canvas_view(xview, yview)
            self.dirty = True
        else:
            print("Nothing to redo.")

    
    def function_not_defined(self):
        pass
    
    def rescale_grid(self):
        """Rescale the grid resolution to fit 80% of the screen."""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Scale to 80% of the screen
        desired_width = int(screen_width * 0.8)
        desired_height = int(screen_height * 0.8)

        # Calculate new resolution (keep the aspect ratio)
        computed_res = int(min(desired_width / self.nx, desired_height / self.ny))

        # Apply new resolution if it differs from the current one
        if computed_res != self.res:
            self.res = computed_res

    
    def __init__(self, root,  nx=16, ny=16, res=4):
        self.nx = nx
        self.ny = ny
        self.original_res = res
        self.res = res
        
        
        self.show_grid_lines = True
        self.is_panning = False
        self.zoom_block_until = 0.0
        self._zoom_after_id = None
        self._zoom_pending_factor = 1.0
        self._zoom_pending_anchor = (None, None)

        self.building_id = 1
        self.building_height = self.original_res  # Start at grid width step
        self.building_type = 2
        
        self.surface_config = surface_config.SURFACE_CONFIG
        self.selected_vegetation_category = "Grass & Crops"
        self.selected_vegetation_type = self.get_vegetation_categories()["Grass & Crops"]["default_type"]
        
        self.selected_pavement_category = "Roads"
        self.selected_pavement_type = self.get_pavement_categories()["Roads"]["default_type"]
        
        self.selected_water_category = "Natural water"
        self.selected_water_type = self.get_water_categories()["Natural water"]["default_type"]
        self.selected_water_temperature = self.get_water_definition(self.selected_water_type)["water_temperature"]

        self.selected_soil_type = self.surface_config["soil"]["default_type"]
        self.soil_tool_bar_functions = tuple(
            [f"soil_{soil_id}" for soil_id in sorted(self.get_soil_types().keys())]
        )

        # Single-tree tool defaults (from "Default" species)
        self.selected_tree_height     = 12.0
        self.selected_crown_diameter  = 4.0
        self.selected_trunk_diameter  = 0.35
        self.selected_lai             = 3.0
        self.selected_crown_shape     = 1     # PALM shape ID 1-6
        self.selected_crown_ratio     = 1.0   # crown_height / crown_diameter
        self.selected_bad_lad_ratio   = 0.5
        self.bad_enabled              = True  # write BAD field to output
        # Full params_dict from the Tree Generator dialog, if the user last clicked
        # "Apply to Brush".  Used verbatim as generator_params in single_tree().
        # Reset to None when the user picks a species or clears the generator.
        self._active_generator_params = None

        # Tree Generator dialog (optional visual tool)
        self._tree_gen_dialog = None               # lazy-created Toplevel singleton

        self.active_view = "landcover"
        self.selected_height_tool_bar_function = self.height_tool_bar_functions[0]
        self.height_set_value = 0.0
        self.height_view_min = 0.0
        self.height_view_levels = 10

        self.undo_stack = []
        self.redo_stack = []
        self.dirty = False

        self.autosave_interval_ms = 2 * 60 * 1000
        self.autosave_file_count = 3
        self._autosave_next_slot = 0
        self._autosave_after_id = None
        
        self.active_cell = None
        self.hover_cell = None
        
        super().__init__(root)
        self.rescale_grid()
        self.model = gridmodel.GridModel(nx, ny, self.original_res, self.surface_config)
        self.create_gui()  # backend is created inside create_gui
        self.backend.draw_grid(self.nx, self.ny, self.res,)
        self.bind_mouse()
        self.bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        self._schedule_autosave()
        
    # ------------------ Initialize Grid ------------------    

    def draw_grid(self, nx, ny, res):
        """Reset the data model and redraw the full canvas grid."""
        self.model = gridmodel.GridModel(nx, ny, self.original_res, self.surface_config)
        self.backend.model = self.model
        self.backend.clear()
        self.backend.draw_grid(nx, ny, res)
        self.backend.set_grid_lines_visible(self.show_grid_lines)
        self.dirty = False

    def update_grid(self, nx, ny, res):
        """Redraw all canvas pixels from the current model state."""
        self.backend.update_grid(nx, ny, res)
                
                
        
    # ------------------ GUI ------------------     
    def create_gui(self):
        self.create_top_bar()
        self.show_selected_tool_icon_in_top_bar(str(self.tool_bar_functions[0]))
        self.create_tool_bar()
        self.create_tool_bar_buttons()
        self.backend = tkbackend.TkCanvasBackend(
            self.root, self.model, self.nx, self.ny, self.res
        )
        self.backend.set_view_mode(self.active_view)
        self.backend.set_height_view_config(self.height_view_min, self.original_res, self.height_view_levels)
        self.backend.set_grid_lines_visible(self.show_grid_lines)
        self.create_current_coordinate_label()
        self.create_meter_coordinate_label()
        self.create_cell_info_label()
        self.create_height_legend_widgets()
        self.create_menu()
        self.create_brush_size_slider()
        self.create_gridwith_label()
        self.update_height_legend_visibility()
        
        
    def create_brush_size_slider(self):
        """Create a slider to adjust the brush size."""
        self.brush_size_slider = tk.Scale(self.tool_bar, from_=1, to=10,
                                          resolution=2, orient="horizontal", label="Brush Pixel diameter")
        self.brush_size_slider.set(self.brush_size)
        self.brush_size_slider.grid(row=15, column=1, columnspan=2, 
                                    pady=5, padx=1, sticky='w')
        self.brush_size_slider.bind("<Motion>", self.update_brush_size)

    def update_brush_size(self, event=None):
        """Update the brush size from the slider."""
        self.brush_size = self.brush_size_slider.get()

            
    def create_top_bar(self):
        self.top_bar = tk.Frame(self.root, height=25, relief="raised")
        self.top_bar.pack(fill="x", side="top", pady=2)
        
    def show_selected_tool_icon_in_top_bar(self, function_name):
        if self.active_view == "heightmap":
            display_name = "Height tool:"
            top_text = self.selected_height_tool_bar_function.replace("_", " ")
        elif self.active_view == "soil":
            display_name = "Soil type:"
            soil_label = self.get_soil_definition(self.selected_soil_type)["label"]
            top_text = f"{self.selected_soil_type} {soil_label}"
        else:
            display_name = function_name.replace("_", " ").capitalize() + ":"
            top_text = str(function_name)
        tk.Label(self.top_bar, text=display_name).pack(side="left")
        label = tk.Label(self.top_bar, text=top_text)
        label.pack(side="left")

    def create_tool_bar(self):
        self.tool_bar = tk.Frame(self.root, relief="raised", width=50)
        self.tool_bar.pack(fill="y", side="left", pady=3)

    def create_tool_bar_buttons(self):
        for child in self.tool_bar.grid_slaves():
            info = child.grid_info()
            if int(info.get("row", 0)) < 4:
                child.destroy()

        if self.active_view == "heightmap":
            button_names = self.height_tool_bar_functions
            callback = self.on_height_tool_button_clicked
        elif self.active_view == "soil":
            button_names = self.soil_tool_bar_functions
            callback = self.on_soil_tool_button_clicked
        else:
            button_names = self.tool_bar_functions
            callback = self.on_tool_bar_button_clicked

        for index, name in enumerate(button_names):
            if self.active_view == "soil":
                soil_id = int(name.split("_")[-1])
                soil_label = self.get_soil_definition(soil_id)["label"]
                button_text = f"{soil_id} {soil_label}"
            else:
                button_text = name.replace("_", " ")
            self.button = tk.Button(
                self.tool_bar, text=button_text, 
                command=lambda index=index: callback(index))
            self.button.grid(
                row=index // 2, column=1 + index % 2, sticky='nsew')
    
    def on_tool_bar_button_clicked(self, button_index):
        self.selected_tool_bar_function = self.tool_bar_functions[button_index]
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()
        self.bind_mouse()

    def on_height_tool_button_clicked(self, button_index):
        self.selected_height_tool_bar_function = self.height_tool_bar_functions[button_index]
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()
        self.bind_mouse()

    def on_soil_tool_button_clicked(self, button_index):
        selected_name = self.soil_tool_bar_functions[button_index]
        self.selected_soil_type = int(selected_name.split("_")[-1])
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()
        self.bind_mouse()
        
    def remove_options_from_top_bar(self):
        for child in self.top_bar.winfo_children():
            child.destroy()
            
    def display_options_in_the_top_bar(self):
        """Display options for the selected tool in the top bar."""
        self.show_selected_tool_icon_in_top_bar(self.selected_tool_bar_function)
        if self.active_view == "heightmap":
            self.heightmap_options()
            return
        if self.active_view == "soil":
            self.soil_options()
            return

        options_function_name = "{}_options".format(self.selected_tool_bar_function)
        func = getattr(self, options_function_name, self.function_not_defined)
        func()
          
    def create_gridwith_label(self):
        """Create a static label between the brush slider and the nx/ny labels."""
        info_frame = tk.Frame(self.tool_bar, padx=5, pady=5)  # Frame with background
        info_frame.grid(row=16, column=1, columnspan=2, pady=5, padx=1, sticky='w')

        self.static_label = tk.Label(
            info_frame, 
            text=f"Grid width: {self.original_res} m", 
            fg="black",       # Text color
            justify="left"
        )
        self.static_label.pack()
    
    def create_current_coordinate_label(self):
        self.current_coordinate_label = tk.Label(
            self.tool_bar, text='nx:0\nny: 0 ')
        self.current_coordinate_label.grid(
            row=18, column=1, columnspan=2, 
            pady=5, padx=1, sticky='w')

    def show_current_coordinates(self, row, col):
        """Update the current coordinate label based on mouse movement."""
        coordinate_string = "nx:{0}\nny:{1}".format(col, row)
        self.current_coordinate_label.config(text=coordinate_string)
        
    def create_meter_coordinate_label(self):
        # Create a second label for meter coordinates and position it below the grid coordinate label
        self.meter_coordinate_label = tk.Label(self.tool_bar, text='x:0\ny:0')
        self.meter_coordinate_label.grid(row=20, column=1, columnspan=2, pady=5, padx=1, sticky='w')

    def show_meter_coordinates(self, row, col):
        """Update the meter coordinate label based on mouse movement."""
        meter_x = (col + 0.5) * self.original_res
        meter_y = (row + 0.5) * self.original_res
        coordinate_string = "x:{:.2f}\ny:{:.2f}".format(meter_x, meter_y)
        self.meter_coordinate_label.config(text=coordinate_string)
    
    def create_cell_info_label(self):
        """Create a fixed-width sidebar area that shows properties of the hovered cell."""
        self.cell_info_frame = tk.Frame(self.tool_bar, width=220, height=140)
        self.cell_info_frame.grid(
            row=22, column=1, columnspan=2,
            pady=5, padx=1, sticky="nw"
        )
        self.cell_info_frame.grid_propagate(False)

        self.cell_info_label = tk.Label(
            self.cell_info_frame,
            text="Cell info\nzt: -\nsurface: -\nsoil: -",
            justify="left",
            anchor="nw",
            width=28,          # Breite in Textzeichen
            wraplength=200,    # Umbruch in Pixeln
        )
        self.cell_info_label.pack(fill="both", expand=True)

    def _format_type_label(self, value, definition_getter):
        """Return a readable 'id (label)' string or '-' for fill values."""
        if value is None or value <= self.model.INT_FILL:
            return "-"
        try:
            definition = definition_getter(int(value))
            label = definition.get("label", "unknown")
            return f"{int(value)} ({label})"
        except Exception:
            return str(value)

    def get_cell_info_text(self, row, col):
        """Build the sidebar text for one grid cell."""
        if not (0 <= row < self.ny and 0 <= col < self.nx):
            return "Cell info\nzt: -\nsurface: -\nsoil: -"

        pixel = self.model.get_pixel(row, col)

        zt = float(pixel["zt"])
        soil_type = int(pixel["soil_type"])
        vegetation_type = int(pixel["vegetation_type"])
        pavement_type = int(pixel["pavement_type"])
        water_type = int(pixel["water_type"])
        building_id = int(pixel["building_id"])
        building_height = float(pixel["building_height"])
        building_type = int(pixel["building_type"])
        water_temperature = float(pixel["water_temperature"])

        lines = ["Cell info", f"zt: {zt:.2f} m"]

        # Dominant surface content in the same precedence as the renderer:
        # water -> building -> pavement -> vegetation
        if water_type > self.model.INT_FILL:
            water_text = self._format_type_label(water_type, self.get_water_definition)
            lines.append(f"surface: water {water_text}")
            if water_temperature > self.model.FLOAT_FILL:
                lines.append(f"water temp: {water_temperature:.2f} K")

        elif building_id > self.model.INT_FILL or building_height > 0.0:
            lines.append("surface: building")
            lines.append(f"building id: {building_id if building_id > self.model.INT_FILL else '-'}")
            lines.append(
                f"building height: {building_height:.2f} m"
                if building_height > 0.0 else "building height: -"
            )
            lines.append(
                f"building type: {building_type}"
                if building_type > self.model.INT_FILL else "building type: -"
            )

        elif pavement_type > self.model.INT_FILL:
            pavement_text = self._format_type_label(pavement_type, self.get_pavement_definition)
            lines.append(f"surface: pavement {pavement_text}")

        elif vegetation_type > self.model.INT_FILL:
            vegetation_text = self._format_type_label(vegetation_type, self.get_vegetation_definition)
            lines.append(f"surface: vegetation {vegetation_text}")

        else:
            lines.append("surface: -")

        if soil_type > self.model.INT_FILL:
            soil_text = self._format_type_label(soil_type, self.get_soil_definition)
            lines.append(f"soil: {soil_text}")
        else:
            lines.append("soil: -")

        # Tree / resolved-vegetation info
        tree_info = self.model.get_tree_info_at(row, col)
        if tree_info is not None:
            max_z = tree_info["max_height"]
            lines.append("")
            lines.append("Tree")
            lines.append("----")
            lines.append(f"tree height: {max_z:.1f} m" if max_z is not None else "tree height: -")
            lines.append(f"col LAD max: {tree_info['lad_max']:.4f} m²/m³")
            lines.append(f"col. LAI: {tree_info['lad_integral']:.4f} m²/m²")
            bad_max = tree_info["bad_max"]
            bad_integral = tree_info["bad_integral"]
            lines.append(f"col. BAD max: {bad_max:.4f} m²/m³" if bad_max is not None else "bad max: -")
            lines.append(
                f"col. BAD: {bad_integral:.4f} m²/m²"
                if bad_integral is not None else "cell ∫ BAI: -"
            )
            tid = tree_info["tree_id"]
            lines.append(f"tree id: {tid}" if tid > 0 else "tree id: -")

        return "\n".join(lines)

    def show_cell_info(self, row, col):
        """Update the sidebar cell info based on the hovered/active cell."""
        self.cell_info_label.config(text=self.get_cell_info_text(row, col))

    def clear_cell_info(self):
        """Reset the sidebar cell info when the mouse leaves the canvas."""
        self.cell_info_label.config(text="Cell info\nzt: -\nsurface: -\nsoil: -")  
    def update_hover_preview(self, row, col):
        """Preview all cells affected by the current brush."""
        if not (0 <= row < self.ny and 0 <= col < self.nx):
            self.backend.clear_hover_preview()
            return

        if self.selected_tool_bar_function == "single_tree":
            crown_radius = self.selected_crown_diameter / 2.0
            phys_res = float(self.model.res)
            r_cells = int(math.ceil(crown_radius / phys_res))
            cells = []
            for dr in range(-r_cells, r_cells + 1):
                for dc in range(-r_cells, r_cells + 1):
                    r2 = row + dr
                    c2 = col + dc
                    if 0 <= r2 < self.ny and 0 <= c2 < self.nx:
                        if (dr * phys_res) ** 2 + (dc * phys_res) ** 2 < crown_radius ** 2:
                            cells.append((r2, c2))
            if not cells:
                cells = [(row, col)]
            self.backend.show_hover_preview(cells)
        else:
            affected_pixels = self.get_pixels_in_brush(row, col)
            self.backend.show_hover_preview(affected_pixels)
        
    # ------------------ Mouse ------------------
    
    def bind_mouse(self):
        self.canvas.bind("<Button-1>", self.on_mouse_button_pressed)
        self.canvas.bind(
            "<Button1-Motion>", self.on_mouse_button_pressed_motion)
        self.canvas.bind(
            "<Button1-ButtonRelease>", self.on_mouse_button_released)
        self.canvas.bind("<Motion>", self.on_mouse_unpressed_motion)
        self.canvas.bind("<Leave>", self.on_canvas_leave)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<B3-Motion>", self.on_right_click_drag)

        self.bind_wheel_zoom()

        self.canvas.bind("<Button-2>", self.on_middle_mouse_pressed)
        self.canvas.bind("<B2-Motion>", self.on_middle_mouse_drag)
        self.canvas.bind("<ButtonRelease-2>", self.on_middle_mouse_released)
        
        
    def bind_wheel_zoom(self):
        """Bind mouse wheel zoom events."""
        self.canvas.bind("<MouseWheel>", self.on_mousewheel_zoom)
        self.canvas.bind("<Button-4>", self.on_mousewheel_zoom_linux)
        self.canvas.bind("<Button-5>", self.on_mousewheel_zoom_linux)

    def unbind_wheel_zoom(self):
        """Temporarily disable mouse wheel zoom events."""
        self.canvas.unbind("<MouseWheel>")
        self.canvas.unbind("<Button-4>")
        self.canvas.unbind("<Button-5>")

    def on_mouse_button_pressed(self, event):
        self.save_state()
        
        row, col = self.set_active_cell_from_event(event)
        self.show_current_coordinates(row, col)
        self.show_meter_coordinates(row, col)
        self.show_cell_info(row, col)
        self.update_hover_preview(row, col)

        self.execute_selected_method()
        
    def on_mouse_button_pressed_motion(self, event):
        row, col = self.set_active_cell_from_event(event)
        self.show_current_coordinates(row, col)
        self.show_meter_coordinates(row, col)
        self.show_cell_info(row, col)
        self.update_hover_preview(row, col)

        # Single-tree placement fires only on click, not on drag
        if self.selected_tool_bar_function != "single_tree":
            self.execute_selected_method()

    def on_mouse_button_released(self, event):
        pass

    def on_mouse_unpressed_motion(self, event):
        row, col = self.set_hover_cell_from_event(event)
        self.show_current_coordinates(row, col)
        self.show_meter_coordinates(row, col)
        self.show_cell_info(row, col)
        self.update_hover_preview(row, col)
        
    def on_middle_mouse_pressed(self, event):
        """
        Start canvas panning with the middle mouse button.
        """
        # Cancel any zoom that was triggered a split-second before the pan click.
        self._cancel_pending_zoom()
        self.is_panning = True
        self.zoom_block_until = time.monotonic() + 0.25
        self.unbind_wheel_zoom()
        self.canvas.config(cursor="fleur")
        self.canvas.scan_mark(event.x, event.y)
        return "break"

    def on_middle_mouse_drag(self, event):
        """
        Continue canvas panning while the middle mouse button is held.
        """
        # Extend zoom suppression while panning to ignore stray wheel events.
        self.zoom_block_until = time.monotonic() + 0.10
        self.canvas.scan_dragto(event.x, event.y, gain=1)
        return "break"

    def on_middle_mouse_released(self, event):
        """
        Restore normal input behavior after panning.
        """
        self.is_panning = False
        # Keep zoom blocked briefly after pan release to absorb delayed events.
        self.zoom_block_until = time.monotonic() + 0.25
        self.bind_wheel_zoom()
        self.canvas.config(cursor="")
        return "break"
    
    def on_canvas_leave(self, event):
        self.hover_cell = None
        self.backend.clear_hover_preview()
        self.clear_cell_info()

    def should_block_zoom(self, event=None):
        """Return True when zoom events should be ignored around panning."""
        if self.is_panning:
            return True
        if time.monotonic() < self.zoom_block_until:
            return True
        if event is not None and (event.state & 0x0200):
            return True
        return False

    def _cancel_pending_zoom(self):
        """Cancel a zoom that hasn't fired yet."""
        if self._zoom_after_id is not None:
            self.root.after_cancel(self._zoom_after_id)
            self._zoom_after_id = None
        self._zoom_pending_factor = 1.0
        self._zoom_pending_anchor = (None, None)

    def _schedule_zoom(self, factor, anchor_x, anchor_y):
        """Delay zoom execution so a pan start within 100 ms can cancel it."""
        if self._zoom_after_id is not None:
            self.root.after_cancel(self._zoom_after_id)
            self._zoom_pending_factor *= factor
            # Keep the most-recent anchor position.
            self._zoom_pending_anchor = (anchor_x, anchor_y)
        else:
            self._zoom_pending_factor = factor
            self._zoom_pending_anchor = (anchor_x, anchor_y)
        self._zoom_after_id = self.root.after(100, self._execute_pending_zoom)

    def _execute_pending_zoom(self):
        """Fire the accumulated zoom — unless panning started in the meantime."""
        self._zoom_after_id = None
        factor = self._zoom_pending_factor
        ax, ay = self._zoom_pending_anchor
        self._zoom_pending_factor = 1.0
        self._zoom_pending_anchor = (None, None)
        if self.is_panning or time.monotonic() < self.zoom_block_until:
            return
        self.res *= factor
        if ax is not None:
            self.backend.zoom(factor, ax, ay)
        else:
            self.backend.zoom(factor)

    def on_mousewheel_zoom(self, event):
        if self.should_block_zoom(event):
            return "break"
        anchor_x, anchor_y = self.get_mouse_canvas_position(event)
        factor = 1.2 if event.delta > 0 else 0.8
        self._schedule_zoom(factor, anchor_x, anchor_y)
        return "break"  # Prevent default scrolling behavior
            
    def on_mousewheel_zoom_linux(self, event):
        if self.should_block_zoom(event):
            return "break"
        
        anchor_x, anchor_y = self.get_mouse_canvas_position(event)
        if event.num == 4:
            self._schedule_zoom(1.2, anchor_x, anchor_y)
        elif event.num == 5:
            self._schedule_zoom(0.8, anchor_x, anchor_y)
        return "break"  # Prevent default scrolling behavior
    
    def get_mouse_canvas_position(self, event):
        """Translate a Tk mouse event into canvas coordinates."""
        return self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

    def get_mouse_cell(self, event):
        canvas_x, canvas_y = self.get_mouse_canvas_position(event)
        return self.backend.canvas_to_grid(canvas_x, canvas_y)
    
    def set_hover_cell_from_event(self, event):
        self.hover_cell = self.get_mouse_cell(event)
        return self.hover_cell
    
    def set_active_cell_from_event(self, event):
        self.active_cell = self.get_mouse_cell(event)
        return self.active_cell

# ------------------ Extras ------------------

    def create_menu(self):
        self.menubar = tk.Menu(self.root)
        menu_definitions = (
            'File - New Project//self.new_project, Save to NetCDF/Ctrl+S/self.save_netcdf, Save NetCDF as .../Ctrl+Shift+S/self.save_as_netcdf, sep,'+
            'Load from NetCDF//self.load_project_netcdf, sep, Exit//self.exit_application',
            'View- Landcover View//self.set_landcover_view, Heightmap View//self.set_heightmap_view, Soil View//self.set_soil_view, sep, Zoom in/Ctrl+ Up Arrow/self.canvas_zoom_in,Zoom Out/Ctrl+Down Arrow/self.canvas_zoom_out, Toggle Gridlines/Ctrl+G/self.toggle_gridlines, Toggle Tree Overlay/Ctrl+T/self.toggle_tree_overlay',
            'Edit - Undo/Ctrl + z/self.undo, Redo/Ctrl + y/self.redo, Bucket Fill//self.bucket_fill',
            'Extras - Autosave Settings//self.open_autosave_settings, Generate Report//self.generate_report, Change Origin//self.change_origin',
        )
        self.build_menu(menu_definitions)

    def set_active_view(self, view_mode):
        """Switch display mode and refresh top bar + canvas."""
        self.active_view = view_mode
        self.backend.set_view_mode(view_mode)
        self.create_tool_bar_buttons()
        self.update_height_legend_visibility()
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()
        self.backend.clear_hover_preview()
        self.backend.update_grid(self.nx, self.ny, self.res)

    def set_landcover_view(self, event=None):
        self.set_active_view("landcover")

    def set_heightmap_view(self, event=None):
        self.set_active_view("heightmap")

    def set_soil_view(self, event=None):
        self.set_active_view("soil")

    def bind_shortcuts(self):
        self.root.bind("<Control-Up>", self.canvas_zoom_in)
        self.root.bind("<Control-Down>", self.canvas_zoom_out)
        self.root.bind("<Control-s>", self.save_netcdf)
        self.root.bind("<Control-S>", self.save_as_netcdf)
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-g>", self.toggle_gridlines)
        self.root.bind("<Control-t>", self.toggle_tree_overlay)

    def toggle_tree_overlay(self, event=None):
        """Toggle visibility of the tree crown overlay on the canvas."""
        self.backend.set_tree_overlay_visible(not self.backend.show_tree_overlay)

    def toggle_gridlines(self, event=None):
        """Toggle visibility of white pixel outlines on the canvas."""
        self.show_grid_lines = not self.show_grid_lines
        self.backend.set_grid_lines_visible(self.show_grid_lines)
        
        
    def canvas_zoom_in(self, event=None):
        self.res *= 1.2
        self.backend.zoom(1.2)

    def canvas_zoom_out(self, event=None):
        self.res *= 0.8
        self.backend.zoom(0.8)
        
    def vegetation_options(self):
        """Display vegetation category buttons and type dropdown in the top bar."""
        tk.Label(self.top_bar, text="Category:").pack(side="left", padx=5)

        for category in self.get_vegetation_categories().keys():
            btn = tk.Button(
                self.top_bar,
                text=category,
                relief="sunken" if category == self.selected_vegetation_category else "raised",
                command=lambda c=category: self.set_vegetation_category_and_refresh_ui(c)
            )
            btn.pack(side="left", padx=2)

        tk.Label(self.top_bar, text="Type:").pack(side="left", padx=10)

        self.vegetation_type_var = tk.StringVar()

        self.vegetation_type_combobox = ttk.Combobox(
            self.top_bar,
            textvariable=self.vegetation_type_var,
            state="readonly",
            width=28
        )
        self.vegetation_type_combobox.pack(side="left", padx=5)

        self.refresh_vegetation_dropdown()

        self.vegetation_type_combobox.bind(
            "<<ComboboxSelected>>",
            self.on_vegetation_type_selected
        )
    def set_vegetation_category_and_refresh_ui(self, category):
        self.set_vegetation_category(category)
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()    
        
    def set_vegetation_category(self, category):
        """Set active vegetation category and refresh dropdown."""
        self.selected_vegetation_category = category
        self.refresh_vegetation_dropdown()
        
    def refresh_vegetation_dropdown(self):
        """Refresh dropdown values based on the selected vegetation category."""
        veg_ids = self.get_vegetation_categories()[self.selected_vegetation_category]["types"]
        labels = [
            f"{veg_id} - {self.get_vegetation_definition(veg_id)['label']}"
            for veg_id in veg_ids
        ]

        self.vegetation_type_combobox["values"] = labels

        # If type is not in the new category, reset to the first type of the new category
        if self.selected_vegetation_type not in veg_ids:
            self.selected_vegetation_type = veg_ids[0]

        current_label = f"{self.selected_vegetation_type} - {self.get_vegetation_definition(self.selected_vegetation_type)['label']}"
        self.vegetation_type_var.set(current_label)    
        
    def on_vegetation_type_selected(self, event=None):
        """Update selected vegetation type from the combobox."""
        selection = self.vegetation_type_var.get()
        veg_id = int(selection.split(" - ")[0])
        self.selected_vegetation_type = veg_id
        
    def set_vegetation_category(self, category):
        """Set active vegetation category and choose a sensible default."""
        self.selected_vegetation_category = category

        self.selected_vegetation_type = self.get_vegetation_categories()[category]["default_type"]

        self.refresh_vegetation_dropdown()
        
    def pavement_options(self):
        """Display pavement category buttons and type dropdown in the top bar."""
        tk.Label(self.top_bar, text="Category:").pack(side="left", padx=5)

        for category in self.get_pavement_categories().keys():
            btn = tk.Button(
                self.top_bar,
                text=category,
                relief="sunken" if category == self.selected_pavement_category else "raised",
                command=lambda c=category: self.set_pavement_category_and_refresh_ui(c)
            )
            btn.pack(side="left", padx=2)

        tk.Label(self.top_bar, text="Type:").pack(side="left", padx=10)

        self.pavement_type_var = tk.StringVar()

        self.pavement_type_combobox = ttk.Combobox(
            self.top_bar,
            textvariable=self.pavement_type_var,
            state="readonly",
            width=32
        )
        self.pavement_type_combobox.pack(side="left", padx=5)

        self.refresh_pavement_dropdown()

        self.pavement_type_combobox.bind(
            "<<ComboboxSelected>>",
            self.on_pavement_type_selected
        )
        
    def set_pavement_category(self, category):
        """Set active pavement category and choose its default type."""
        self.selected_pavement_category = category
        self.selected_pavement_type = self.get_pavement_categories()[category]["default_type"]
        self.refresh_pavement_dropdown()
        
    def set_pavement_category_and_refresh_ui(self, category):
        """Set pavement category and rebuild top bar so active button is visible."""
        self.set_pavement_category(category)
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()
        
    def refresh_pavement_dropdown(self):
        """Refresh pavement dropdown values based on selected category."""
        pavement_ids = self.get_pavement_categories()[self.selected_pavement_category]["types"]

        labels = [
            f"{pav_id} - {self.get_pavement_definition(pav_id)['label']}"
            for pav_id in pavement_ids
        ]

        self.pavement_type_combobox["values"] = labels

        if self.selected_pavement_type not in pavement_ids:
            self.selected_pavement_type = pavement_ids[0]

        current_label = (
            f"{self.selected_pavement_type} - "
            f"{self.get_pavement_definition(self.selected_pavement_type)['label']}"
        )
        self.pavement_type_var.set(current_label)
        
    def on_pavement_type_selected(self, event=None):
        """Update selected pavement type from combobox."""
        selection = self.pavement_type_var.get()
        pavement_type = int(selection.split(" - ")[0])
        self.selected_pavement_type = pavement_type
        
    def water_options(self):
        """Display water category buttons, type dropdown and temperature input."""
        tk.Label(self.top_bar, text="Category:").pack(side="left", padx=5)

        for category in self.get_water_categories().keys():
            btn = tk.Button(
                self.top_bar,
                text=category,
                relief="sunken" if category == self.selected_water_category else "raised",
                command=lambda c=category: self.set_water_category_and_refresh_ui(c)
            )
            btn.pack(side="left", padx=2)

        tk.Label(self.top_bar, text="Type:").pack(side="left", padx=10)

        self.water_type_var = tk.StringVar()

        self.water_type_combobox = ttk.Combobox(
            self.top_bar,
            textvariable=self.water_type_var,
            state="readonly",
            width=24
        )
        self.water_type_combobox.pack(side="left", padx=5)

        self.refresh_water_dropdown()

        self.water_type_combobox.bind(
            "<<ComboboxSelected>>",
            self.on_water_type_selected
        )

        tk.Label(self.top_bar, text="Temperature (K):").pack(side="left", padx=10)

        self.water_temperature_var = tk.StringVar(value=str(self.selected_water_temperature))

        self.water_temperature_entry = tk.Entry(
            self.top_bar,
            textvariable=self.water_temperature_var,
            width=8
        )
        self.water_temperature_entry.pack(side="left", padx=5)

        self.water_temperature_entry.bind("<FocusOut>", self.update_water_temperature)
        self.water_temperature_entry.bind("<Return>", self.update_water_temperature)
        
    def set_water_category(self, category):
        """Set active water category and choose its default type."""
        self.selected_water_category = category
        self.selected_water_type = self.get_water_categories()[category]["default_type"]
        self.selected_water_temperature = self.get_water_definition(self.selected_water_type)["water_temperature"]
        self.refresh_water_dropdown()   
        
    def set_water_category_and_refresh_ui(self, category):
        """Set water category and rebuild top bar."""
        self.set_water_category(category)
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()    
        
    def refresh_water_dropdown(self):
        """Refresh water dropdown values based on selected category."""
        water_ids = self.get_water_categories()[self.selected_water_category]["types"]

        labels = [
            f"{water_id} - {self.get_water_definition(water_id)['label']}"
            for water_id in water_ids
        ]

        self.water_type_combobox["values"] = labels

        if self.selected_water_type not in water_ids:
            self.selected_water_type = water_ids[0]

        current_label = (
            f"{self.selected_water_type} - "
            f"{self.get_water_definition(self.selected_water_type)['label']}"
        )
        self.water_type_var.set(current_label)
        
    def on_water_type_selected(self, event=None):
        """Update selected water type from combobox."""
        selection = self.water_type_var.get()
        water_type = int(selection.split(" - ")[0])
        self.selected_water_type = water_type

        default_temp = self.get_water_definition(water_type)["water_temperature"]
        self.selected_water_temperature = default_temp

        if hasattr(self, "water_temperature_var"):
            self.water_temperature_var.set(str(default_temp))
            
    def update_water_temperature(self, event=None):
        """Update selected water temperature from entry field."""
        try:
            self.selected_water_temperature = float(self.water_temperature_var.get())
        except ValueError:
            default_temp = self.get_water_definition(self.selected_water_type)["water_temperature"]
            self.selected_water_temperature = default_temp
            self.water_temperature_var.set(str(default_temp))
        
    def building_options(self):
        """Display options for the building tool."""
        initial_id = tk.IntVar(value=1)  # initial value
        initial_height = tk.IntVar(value=10.0)  # initial value
        initial_type = tk.IntVar(value=2)

        tk.Label(self.top_bar, text='building_id:').pack(side="left", padx=5, )
        self.building_id_spinbox = tk.Spinbox(
            self.top_bar, from_=1, to=200, width=3, textvariable=initial_id, command=self.update_building_attributes)
        self.building_id_spinbox.pack(side="left")
        tk.Label(self.top_bar, text='building_height:').pack(side="left", padx=5)
        self.building_height_spinbox = tk.Spinbox(
            self.top_bar, from_=self.original_res, to=self.original_res * 100, increment=self.original_res, width=3, textvariable=initial_height, command=self.update_building_attributes)
        self.building_height_spinbox.pack(side="left")
        tk.Label(self.top_bar, text='building_type:').pack(side="left", padx=5)
        self.building_type_spinbox = tk.Spinbox(
            self.top_bar, from_=1, to=6, width=3, textvariable=initial_type, command=self.update_building_attributes)
        self.building_type_spinbox.pack(side="left")
               
    def update_building_attributes(self):
        """
        Update the current building attributes based on spinbox values.
        """
        self.building_id = int(self.building_id_spinbox.get())
        self.building_height = int(self.building_height_spinbox.get())
        self.building_type = int(self.building_type_spinbox.get())

    def heightmap_options(self):
        """Display edit controls for terrain heights in fixed range mode."""
        tk.Label(self.top_bar, text="Set value (m):").pack(side="left", padx=8)
        self.height_set_var = tk.StringVar(value=str(self.height_set_value))
        self.height_set_spinbox = tk.Spinbox(
            self.top_bar,
            from_=0.0,
            to=10000.0,
            increment=self.original_res,
            width=8,
            textvariable=self.height_set_var,
            command=self.update_height_set_value,
        )
        self.height_set_spinbox.pack(side="left", padx=4)
        self.height_set_spinbox.bind("<FocusOut>", self.update_height_set_value)
        self.height_set_spinbox.bind("<Return>", self.update_height_set_value)

        tk.Label(self.top_bar, text="Legend min (m):").pack(side="left", padx=8)
        self.height_view_min_var = tk.StringVar(value=str(self.height_view_min))
        self.height_view_min_entry = tk.Entry(
            self.top_bar,
            textvariable=self.height_view_min_var,
            width=7,
        )
        self.height_view_min_entry.pack(side="left", padx=2)

        tk.Label(self.top_bar, text="levels:").pack(side="left", padx=4)
        self.height_levels_var = tk.StringVar(value=str(self.height_view_levels))
        self.height_levels_spinbox = tk.Spinbox(
            self.top_bar,
            from_=1,
            to=500,
            width=5,
            textvariable=self.height_levels_var,
            command=self.update_height_view_range,
        )
        self.height_levels_spinbox.pack(side="left", padx=2)
        self.height_levels_spinbox.bind("<FocusOut>", lambda event: self.update_height_view_range())
        self.height_levels_spinbox.bind("<Return>", lambda event: self.update_height_view_range())

        max_value = self.height_view_min + self.height_view_levels * self.original_res
        self.height_range_hint_label = tk.Label(
            self.top_bar,
            text=f"range: {self.height_view_min:.1f} .. {max_value:.1f} m",
        )
        self.height_range_hint_label.pack(side="left", padx=6)

        tk.Button(
            self.top_bar,
            text="Apply range",
            command=self.update_height_view_range,
        ).pack(side="left", padx=6)

    def soil_options(self):
        """Display short help for soil painting mode."""
        tk.Label(
            self.top_bar,
            text="Paint soil type directly. Water/building cells are locked.",
        ).pack(side="left", padx=8)

    def update_height_set_value(self, event=None):
        try:
            self.height_set_value = self.quantize_height(float(self.height_set_var.get()))
        except ValueError:
            self.height_set_value = 0.0
        if hasattr(self, "height_set_var"):
            self.height_set_var.set(str(self.height_set_value))

    def update_height_view_range(self):
        """Apply fixed discrete legend/rendering setup for the heightmap view."""
        try:
            new_min = max(0.0, float(self.height_view_min_var.get()))
            new_levels = max(1, int(self.height_levels_var.get()))
        except ValueError:
            new_min = self.height_view_min
            new_levels = self.height_view_levels

        self.height_view_min = new_min
        self.height_view_levels = new_levels
        self.backend.set_height_view_config(
            self.height_view_min,
            self.original_res,
            self.height_view_levels,
        )

        if hasattr(self, "height_range_hint_label"):
            max_value = self.height_view_min + self.height_view_levels * self.original_res
            self.height_range_hint_label.config(
                text=f"range: {self.height_view_min:.1f} .. {max_value:.1f} m"
            )

        self.draw_height_legend()
        if self.active_view == "heightmap":
            self.backend.update_grid(self.nx, self.ny, self.res)

    def create_height_legend_widgets(self):
        """Create a fixed terrain legend in the left sidebar."""
        self.height_legend_frame = tk.Frame(self.tool_bar, padx=4, pady=4, relief="groove", bd=1)
        self.height_legend_frame.grid(row=22, column=1, columnspan=2, sticky="w", pady=4)
        tk.Label(self.height_legend_frame, text="zt legend").pack(anchor="w")

        legend_row = tk.Frame(self.height_legend_frame)
        legend_row.pack(anchor="w")
        self.height_legend_canvas = tk.Canvas(legend_row, width=20, height=130, highlightthickness=1)
        self.height_legend_canvas.pack(side="left")
        label_col = tk.Frame(legend_row)
        label_col.pack(side="left", padx=6)
        self.height_legend_max_label = tk.Label(label_col, text="")
        self.height_legend_max_label.pack(anchor="w")
        self.height_legend_min_label = tk.Label(label_col, text="")
        self.height_legend_min_label.pack(anchor="w", pady=(100, 0))

        self.draw_height_legend()

    def draw_height_legend(self):
        """Draw discrete terrain legend for configured level count."""
        if not hasattr(self, "height_legend_canvas"):
            return

        self.height_legend_canvas.delete("all")
        h = 130
        w = 20
        levels = max(1, int(self.height_view_levels))
        palette = self.model._terrain_palette(levels)
        block_h = max(1, h // levels)

        for idx in range(levels):
            y1 = h - (idx + 1) * block_h
            y2 = h - idx * block_h
            if idx == levels - 1:
                y1 = 0
            self.height_legend_canvas.create_rectangle(
                0,
                max(0, y1),
                w,
                min(h, y2),
                outline="",
                fill=palette[idx],
            )

        max_height = self.height_view_min + levels * self.original_res
        self.height_legend_max_label.config(text=f"{max_height:.1f} m")
        self.height_legend_min_label.config(text=f"{self.height_view_min:.1f} m")

    def update_height_legend_visibility(self):
        """Show legend only in heightmap view."""
        if not hasattr(self, "height_legend_frame"):
            return
        if self.active_view == "heightmap":
            self.height_legend_frame.grid()
        else:
            self.height_legend_frame.grid_remove()
        
    def generate_report(self):
        """Trigger the analysis report."""
        report.generate_report(
            self.root,
            self.model.to_legacy_dict(),
            self.nx, self.ny, self.original_res, self.origin,
            resolved_vegetation=self.model.resolved_vegetation,
            tree_instances=self.model.tree_instances,
        )
        
    def change_origin(self):
        """Change the origin of the grid with a simple input form (prefilled with current values)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Origin")
        dialog.geometry("300x200")
        dialog.resizable(False, False)

        labels = ["Latitude (°N):", "Longitude (°E):", "Projected X (m):", "Projected Y (m):"]
        current_values = [
            str(self.origin[0]),  # Latitude
            str(self.origin[1]),  # Longitude
            str(self.origin[2]),  # Projected X
            str(self.origin[3])   # Projected Y
        ]

        entries = []

        for i, label in enumerate(labels):
            tk.Label(dialog, text=label).pack()
            entry = tk.Entry(dialog)
            entry.insert(0, current_values[i])  # Prefill with current value
            entry.pack()
            entries.append(entry)

        def submit():
            """Retrieve values and update origin."""
            try:
                lat = float(entries[0].get())
                lon = float(entries[1].get())
                x = float(entries[2].get())
                y = float(entries[3].get())

                self.origin = (lat, lon, x, y)
                self.dirty = True
                dialog.destroy()

                tk.messagebox.showinfo("Origin Updated",
                    f"New Origin Set:\nLatitude: {lat:.6f}°N\nLongitude: {lon:.6f}°E\n"
                    f"Projected X: {x:.2f} m\nProjected Y: {y:.2f} m")

            except ValueError:
                tk.messagebox.showerror("Invalid Input", "Please enter valid numeric values.")

        tk.Button(dialog, text="OK", command=submit).pack(pady=10)

        dialog.grab_set()  # Make it modal
        dialog.wait_window()

        
        
if __name__ == '__main__':
    # Ask the user what should happen at startup
    # - create new project with custom dimensions
    # - load existing project from NetCDF file
    root = tk.Tk()
    root.withdraw()
    welcome_result = welcome_screen.get_welcome_input(root)
    root.deiconify()
    root.title("PALMPaint")
    if welcome_result[0] == "load":
        _, file_path = welcome_result
        print(f"Loading project from {file_path}")
        # For loading, we initialize with dummy dimensions and resolution 
        # these will be replaced when the file is loaded.
        app = PaintApplication(root, 16, 16, 4)
        app.load_project_netcdf_from_path(file_path)
    else:
        _, nx, ny, res = welcome_result
        app = PaintApplication(root, nx, ny, res)
    root.mainloop()
