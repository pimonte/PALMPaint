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
import json
import math
import os
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
    start_x = 0
    start_y = 0
    end_x = 0
    end_y = 0
    current_item = None
    brush_size = 1
    

    tool_bar_functions = (
        "vegetation", "pavement", "water", "building")
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
    
    vegetation_categories = {
        "Ground": [1, 9, 10, 12, 13],
        "Grass & Crops": [2, 3, 8, 11],
        "Trees": [4, 5, 6, 7, 17, 18],
        "Shrubs & Wetlands": [14, 15, 16],
    }
    
    vegetation_definitions = {
        1:  {"label": "bare soil", "color": "brown",       "category": "Ground"},
        2:  {"label": "crops, mixed farming", "color": "yellowgreen", "category": "Grass & Crops"},
        3:  {"label": "short grass", "color": "green",     "category": "Grass & Crops"},
        4:  {"label": "evergreen needleleaf trees", "color": "darkgreen", "category": "Trees"},
        5:  {"label": "deciduous needleleaf trees", "color": "forestgreen", "category": "Trees"},
        6:  {"label": "evergreen broadleaf trees", "color": "limegreen", "category": "Trees"},
        7:  {"label": "deciduous broadleaf trees", "color": "olivedrab", "category": "Trees"},
        8:  {"label": "tall grass", "color": "lawngreen",  "category": "Grass & Crops"},
        9:  {"label": "desert", "color": "khaki",          "category": "Ground"},
        10: {"label": "tundra", "color": "darkseagreen",   "category": "Ground"},
        11: {"label": "irrigated crops", "color": "chartreuse", "category": "Grass & Crops"},
        12: {"label": "semidesert", "color": "tan",        "category": "Ground"},
        13: {"label": "ice caps and glaciers", "color": "aliceblue", "category": "Ground"},
        14: {"label": "bogs and marshes", "color": "mediumseagreen", "category": "Shrubs & Wetlands"},
        15: {"label": "evergreen shrubs", "color": "seagreen", "category": "Shrubs & Wetlands"},
        16: {"label": "deciduous shrubs", "color": "yellowgreen", "category": "Shrubs & Wetlands"},
        17: {"label": "mixed forest/woodland", "color": "green4", "category": "Trees"},
        18: {"label": "interrupted forest", "color": "darkolivegreen", "category": "Trees"},
    }  
    
    def execute_selected_method(self):
        self.current_item = None
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
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        step = float(self.original_res) if self.original_res > 0 else 1.0

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
            self.update_canvas(row, col)

    def soil_tool(self):
        """Paint soil types, but never overwrite water or building cells."""
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)

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
            self.update_canvas(row, col)
        
    def on_mouse_button_pressed_motion(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        #self.canvas.delete(self.current_item)
        self.execute_selected_method()  
                       
    def get_pixel_position(self):
        col = int(self.start_x // self.res)     
        #row = int(self.start_y // self.res)
        row = (self.ny - 1) - int(self.start_y // self.res)
        
        return row, col
    
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
            
    def vegetation(self):
        """Apply vegetation tool to affected pixels."""
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        veg_type = self.selected_vegetation_type
        
        veg_def = self.get_vegetation_definition(veg_type)
        soil_type = veg_def.get("soil_type", self.surface_config["soil"]["default_type"])

        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(
                    row, col,
                    vegetation_type=veg_type,
                    soil_type= soil_type,
                    pavement_type=-127,
                    water_type=-127,
                    building_id=-127,
                    building_height=-127,
                    building_type=-127,
                )
                self.model.clear_water_parameters(row, col)
                self.update_canvas(row, col)

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
                self.update_canvas(row, col)
            return

        if self.selected_tool_bar_function == "vegetation":
            veg_type = self.selected_vegetation_type
            veg_def = self.get_vegetation_definition(veg_type)
            soil_type = veg_def.get("soil_type", self.surface_config["soil"]["default_type"])
            for (row, col) in self.pixels.keys():
                self.update_pixel(
                    row, col,
                    vegetation_type=veg_type,
                    soil_type= soil_type,
                    pavement_type=-127,
                    water_type=-127,
                    building_id=-127,
                    building_height=-127,
                    building_type=-127
                )
                self.model.clear_water_parameters(row, col)
                self.update_canvas(row, col)
        elif self.selected_tool_bar_function == "pavement":
            pavement_type = self.selected_pavement_type
            soil_type = self.surface_config["soil"]["default_type"]

            for (row, col) in self.pixels.keys():
                self.update_pixel(
                    row, col,
                    pavement_type=pavement_type,
                    soil_type=soil_type,
                    vegetation_type=-127,
                    water_type=-127,
                    building_id=-127,
                    building_height=-127,
                    building_type=-127
                )
                self.model.clear_water_parameters(row, col)
                self.update_canvas(row, col)
        elif self.selected_tool_bar_function == "water":
            self.update_water_temperature()
            water_type = self.selected_water_type
            water_temperature = self.selected_water_temperature

            for (row, col) in self.pixels.keys():
                self.update_pixel(
                    row, col,
                    water_type=water_type,
                    pavement_type=-127,
                    vegetation_type=-127,
                    soil_type=-127,
                    building_id=-127,
                    building_height=-127,
                    building_type=-127
                )
                self.model.set_water_parameter(0, row, col, water_temperature)
                self.update_canvas(row, col)
        elif self.selected_tool_bar_function == "building":
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col,
                                building_id=self.building_id,
                                building_height=self.building_height,
                                building_type=self.building_type,
                                pavement_type=-127,
                                vegetation_type=-127,
                                soil_type=-127,
                                water_type=-127)
                self.model.clear_water_parameters(row, col)
                self.update_canvas(row, col)
        
    def pavement(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        pavement_type = self.selected_pavement_type
        pav_def = self.get_pavement_definition(pavement_type)
        soil_type = pav_def.get("soil_type", self.surface_config["soil"]["default_type"])
    
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col,
                                  pavement_type=pavement_type,
                                  soil_type=soil_type,
                                  vegetation_type=-127,
                                  water_type=-127,
                                  building_id=-127,
                                  building_height=-127,
                                  building_type=-127)
                self.model.clear_water_parameters(row, col)
                self.update_canvas(row, col)
        
    def water(self):
        """Apply water tool to affected pixels."""
        self.update_water_temperature()
        
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)

        water_type = self.selected_water_type
        water_temperature = self.selected_water_temperature

        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(
                    row, col,
                    water_type=water_type,
                    pavement_type=-127,
                    vegetation_type=-127,
                    soil_type=-127,
                    building_id=-127,
                    building_height=-127,
                    building_type=-127
                )
                self.model.set_water_parameter(0, row, col, water_temperature)
                self.update_canvas(row, col)
        
    def building(self):
        
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, 
                                  building_id=self.building_id, 
                                  building_height=self.building_height, 
                                  building_type=self.building_type,
                                  pavement_type=-127, 
                                  vegetation_type=-127, 
                                  soil_type=-127, 
                                  water_type=-127, 
                                  color="black")
                self.model.clear_water_parameters(row, col)
                self.update_canvas(row, col)
                
 # ------------------ File Menu Operations ------------------
    
    def new_project(self):
        if not self.confirm_action("New Project", "Are you sure you want to start a new project? Unsaved work will be lost."):
         return

        self.backend.clear()

        new_nx, new_ny, new_res = welcome_screen.get_welcome_input(self.root)
        self.nx = new_nx
        self.ny = new_ny
        self.original_res = new_res
        self.res = new_res 

        self.draw_grid(self.nx, self.ny, self.res)
        
    def confirm_action(self, title, message):
        return tk.messagebox.askyesno(title, message)
        
        
    def save_netcdf(self):
        Save(self.model.to_legacy_dict(), self.original_res, self.origin, self.surface_config)
        
    def save_as_netcdf(self):
        file_path = fd.asksaveasfilename(
            defaultextension="",
            filetypes=[("All files", "*"), ("NetCDF files", "*.nc") ]
        )
        if not file_path:
            return
        Save(self.model.to_legacy_dict(), self.original_res, self.origin, self.surface_config, file_path)
        
    def load_project_netcdf(self):
        """
        Open a file dialog to let the user choose a NetCDF project file,
        then load it using load_sd.Load() and update the canvas.
        """
        file_path = fd.askopenfilename(
            defaultextension="",
            filetypes=[("All files", "*"), ("NetCDF files", "*.nc")]
        )
        if not file_path:
            return  # User cancelled

        try:
            grid, nx, ny, res, origin = Load(file_path)
        except Exception as e:
            print(f"Error loading NetCDF file: {e}")
            return
        
        self.nx = nx
        self.ny = ny
        self.original_res = res
        self.res = res
        self.origin = origin
        self.model = gridmodel.GridModel.from_legacy_dict(grid, nx, ny, res, self.surface_config)
        self.backend.model = self.model
        self.rescale_grid()
        self.backend.clear()
        self.backend.update_grid(self.nx, self.ny, self.res)
        print(f"Loaded NetCDF project from {file_path}")    
    
    def save_state(self):
        self.undo_stack.append(copy.deepcopy(self.model))
        
    def undo(self, event=None):
        if self.undo_stack:
            state = self.undo_stack.pop()
            self.redo_stack.append(copy.deepcopy(self.model))
            self.model = state
            self.backend.model = self.model
            self.backend.update_grid(self.nx, self.ny, self.res)
        else:
            print("Nothing to undo.")

    def redo(self, event=None):
        if self.redo_stack:
            state = self.redo_stack.pop()
            self.undo_stack.append(copy.deepcopy(self.model))
            self.model = state
            self.backend.model = self.model
            self.backend.update_grid(self.nx, self.ny, self.res)
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

        self.active_view = "landcover"
        self.selected_height_tool_bar_function = self.height_tool_bar_functions[0]
        self.height_set_value = 0.0
        self.height_view_min = 0.0
        self.height_view_levels = 10

        self.undo_stack = []
        self.redo_stack = []
        # Get screen dimensions
        # screen_width = root.winfo_screenwidth()
        # screen_height = root.winfo_screenheight()
        # print(screen_width, screen_height)
        # desired_width = int(screen_width * 0.8)
        # desired_height = int(screen_height * 0.8)
        # computed_display_res = int(min(desired_width / nx, desired_height / ny))
        # self.res = computed_display_res
        
        super().__init__(root)
        self.rescale_grid()
        self.model = gridmodel.GridModel(nx, ny, self.original_res, self.surface_config)
        self.create_gui()  # backend is created inside create_gui
        self.backend.draw_grid(self.nx, self.ny, self.res,)
        self.bind_mouse()
        self.bind_shortcuts()
        
    # ------------------ Initialize Grid ------------------    

    def draw_grid(self, nx, ny, res):
        """Reset the data model and redraw the full canvas grid."""
        self.model = gridmodel.GridModel(nx, ny, self.original_res, self.surface_config)
        self.backend.model = self.model
        self.backend.clear()
        self.backend.draw_grid(nx, ny, res)
        self.backend.set_grid_lines_visible(self.show_grid_lines)

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

    def show_current_coordinates(self, event=None):
        """Update the current coordinate label based on mouse movement."""
        x_coordinate = int(self.canvas.canvasx(event.x) // self.res)
        #y_coordinate = int(self.canvas.canvasx(event.y) // self.res)
        y_coordinate = (self.ny - 1) - int(self.canvas.canvasy(event.y) // self.res)
        coordinate_string = "nx:{0}\nny:{1}".format(x_coordinate, y_coordinate)
        self.current_coordinate_label.config(text=coordinate_string)
        
    def create_meter_coordinate_label(self):
        # Create a second label for meter coordinates and position it below the grid coordinate label
        self.meter_coordinate_label = tk.Label(self.tool_bar, text='x:0\ny:0')
        self.meter_coordinate_label.grid(row=20, column=1, columnspan=2, pady=5, padx=1, sticky='w')

    def show_meter_coordinates(self, event=None):
        """Update the meter coordinate label based on mouse movement."""
        # Get grid indices as before
        grid_x = self.canvas.canvasx(event.x) // self.res
        grid_y = self.canvas.canvasy(event.y) // self.res
        
        # Conversion factor: adjust this factor if each grid cell is not 1 meter.
        #conversion_factor = self.original_res / 2
        
        meter_x = (grid_x + 0.5) * self.original_res
        meter_y = (grid_y + 0.5) * self.original_res

        coordinate_string = "x:{:.2f}\ny:{:.2f}".format(meter_x, meter_y)
        self.meter_coordinate_label.config(text=coordinate_string)
        
    # ------------------ Mouse ------------------
    
    def bind_mouse(self):
        self.canvas.bind("<Button-1>", self.on_mouse_button_pressed)
        self.canvas.bind(
            "<Button1-Motion>", self.on_mouse_button_pressed_motion)
        self.canvas.bind(
            "<Button1-ButtonRelease>", self.on_mouse_button_released)
        self.canvas.bind("<Motion>", self.on_mouse_unpressed_motion)

    def on_mouse_button_pressed(self, event):
        self.save_state()
        self.start_x = self.end_x = self.canvas.canvasx(event.x)
        self.start_y = self.end_y = self.canvas.canvasy(event.y)
        self.execute_selected_method()



    def on_mouse_button_released(self, event):
        self.end_x = self.canvas.canvasx(event.x)
        self.end_y = self.canvas.canvasy(event.y)

    def on_mouse_unpressed_motion(self, event):
        self.show_current_coordinates(event)
        self.show_meter_coordinates(event)
        

# ------------------ Extras ------------------

    def create_menu(self):
        self.menubar = tk.Menu(self.root)
        menu_definitions = (
            'File - New Project//self.new_project, Save to NetCDF//self.save_netcdf, Save NetCDF as ...//self.save_as_netcdf, sep,'+
            'Load from NetCDF//self.load_project_netcdf, sep, Exit//self.root.quit',
            'View- Landcover View//self.set_landcover_view, Heightmap View//self.set_heightmap_view, Soil View//self.set_soil_view, sep, Zoom in/Ctrl+ Up Arrow/self.canvas_zoom_in,Zoom Out/Ctrl+Down Arrow/self.canvas_zoom_out, Toggle Gridlines/Ctrl+G/self.toggle_gridlines',
            'Edit - Undo/Ctrl + z/self.undo, Redo/Ctrl + y/self.redo, Bucket Fill//self.bucket_fill',
            'Extras - Generate Report//self.generate_report, Change Origin//self.change_origin',
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
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        self.root.bind("<Control-g>", self.toggle_gridlines)

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
        report.generate_report(self.root, self.model.to_legacy_dict(), self.nx, self.ny, self.original_res, self.origin)
        
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
    # Ask the user for grid settings at startup
    root = tk.Tk()
    root.withdraw()
    nx, ny, res = welcome_screen.get_welcome_input(root)
    root.deiconify()
    root.title("PALMPaint")
    app = PaintApplication(root, nx, ny, res)
    root.mainloop()