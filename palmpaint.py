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
import tkinter.filedialog as fd

import base.report as report
import base.framework as framework
import base.gridmodel as gridmodel
import base.tkbackend as tkbackend
from base.create_sd import Save
from base.load_sd import Load
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
        "vegetation", "pavement", "bare_soil", "water", "building")
    selected_tool_bar_function = tool_bar_functions[0]
    
    
    
    def execute_selected_method(self):
        self.current_item = None
        func = getattr(
            self, self.selected_tool_bar_function, self.function_not_defined)
        func()
        
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
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col,
                                  vegetation_type=3,
                                  soil_type=3,
                                  pavement_type=-127,
                                  water_type=-127,
                                  building_id=-127,
                                  building_height=-127,
                                  building_type=-127)
                self.update_canvas(row, col)

    def bucket_fill(self):
        self.save_state()
        if self.selected_tool_bar_function == "vegetation":
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col,
                                vegetation_type=3,
                                soil_type=3,
                                pavement_type=-127,
                                water_type=-127,
                                building_id=-127,
                                building_height=-127,
                                building_type=-127)
                self.update_canvas(row, col)
        elif self.selected_tool_bar_function == "pavement":
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col,
                                pavement_type=1,
                                soil_type=1,
                                vegetation_type=-127,
                                water_type=-127,
                                building_id=-127,
                                building_height=-127,
                                building_type=-127)
                self.update_canvas(row, col)
        elif self.selected_tool_bar_function == "bare_soil":
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col,
                                soil_type=1,
                                vegetation_type=1,
                                pavement_type=-127,
                                water_type=-127,
                                building_id=-127,
                                building_height=-127,
                                building_type=-127)
                self.update_canvas(row, col)
        elif self.selected_tool_bar_function == "water":
            for (row, col) in self.pixels.keys():
                self.update_pixel(row, col,
                                water_type=1,
                                pavement_type=-127,
                                vegetation_type=-127,
                                soil_type=-127,
                                building_id=-127,
                                building_height=-127,
                                building_type=-127)
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
                self.update_canvas(row, col)
        
    def pavement(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col,
                                  pavement_type=1,
                                  soil_type=1,
                                  vegetation_type=-127,
                                  water_type=-127,
                                  building_id=-127,
                                  building_height=-127,
                                  building_type=-127)
                self.update_canvas(row, col)
        
    def bare_soil(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col,
                                  soil_type=1,
                                  vegetation_type=1,
                                  pavement_type=-127,
                                  water_type=-127,
                                  building_id=-127,
                                  building_height=-127,
                                  building_type=-127)
                self.update_canvas(row, col)
        
    def water(self):
        
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, 
                                  water_type=1, 
                                  pavement_type=-127, 
                                  vegetation_type=-127, 
                                  soil_type=-127,
                                  building_id=-127, 
                                  building_height=-127,
                                  building_type=-127, 
                                  color="blue")
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
        Save(self.model.to_legacy_dict(), self.original_res, self.origin)
        
    def save_as_netcdf(self):
        file_path = fd.asksaveasfilename(
            defaultextension="",
            filetypes=[("All files", "*"), ("NetCDF files", "*.nc") ]
        )
        if not file_path:
            return
        Save(self.model.to_legacy_dict(), self.original_res, self.origin, file_path)
        
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
        self.model = gridmodel.GridModel.from_legacy_dict(grid, nx, ny, res)
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
        self.building_id = 1
        self.building_height = self.original_res  # Start at grid width step
        self.building_type = 2
        
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
        self.model = gridmodel.GridModel(nx, ny, self.original_res)
        self.create_gui()  # backend is created inside create_gui
        self.backend.draw_grid(self.nx, self.ny, self.res)
        self.bind_mouse()
        self.bind_shortcuts()
        
    # ------------------ Initialize Grid ------------------    

    def draw_grid(self, nx, ny, res):
        """Reset the data model and redraw the full canvas grid."""
        self.model = gridmodel.GridModel(nx, ny, self.original_res)
        self.backend.model = self.model
        self.backend.clear()
        self.backend.draw_grid(nx, ny, res)

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
        self.create_current_coordinate_label()
        self.create_meter_coordinate_label()
        self.create_menu()
        self.create_brush_size_slider()
        self.create_gridwith_label()
        
        
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
        display_name = function_name.replace("_", " ").capitalize() + ":"
        tk.Label(self.top_bar, text=display_name).pack(side="left")
        top_text = str(function_name)
        label = tk.Label(self.top_bar, text=top_text)
        label.pack(side="left")

    def create_tool_bar(self):
        self.tool_bar = tk.Frame(self.root, relief="raised", width=50)
        self.tool_bar.pack(fill="y", side="left", pady=3)

    def create_tool_bar_buttons(self):
        for index, name in enumerate(self.tool_bar_functions):
            button_text = name.replace("_", " ")
            self.button = tk.Button(
                self.tool_bar, text=button_text, 
                command=lambda index=index: self.on_tool_bar_button_clicked(index))
            self.button.grid(
                row=index // 2, column=1 + index % 2, sticky='nsew')
    
    def on_tool_bar_button_clicked(self, button_index):
        self.selected_tool_bar_function = self.tool_bar_functions[button_index]
        self.remove_options_from_top_bar()
        self.display_options_in_the_top_bar()
        self.bind_mouse()
        
    def remove_options_from_top_bar(self):
        for child in self.top_bar.winfo_children():
            child.destroy()
            
    def display_options_in_the_top_bar(self):
        """Display options for the selected tool in the top bar."""
        self.show_selected_tool_icon_in_top_bar(
            self.selected_tool_bar_function)
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
            'View- Zoom in/Ctrl+ Up Arrow/self.canvas_zoom_in,Zoom Out/Ctrl+Down Arrow/self.canvas_zoom_out',
            'Edit - Undo/Ctrl + z/self.undo, Redo/Ctrl + y/self.redo, Bucket Fill//self.bucket_fill',
            'Extras - Generate Report//self.generate_report, Change Origin//self.change_origin',
        )
        self.build_menu(menu_definitions)
    def bind_shortcuts(self):
        self.root.bind("<Control-Up>", self.canvas_zoom_in)
        self.root.bind("<Control-Down>", self.canvas_zoom_out)
        self.root.bind("<Control-z>", self.undo)
        self.root.bind("<Control-y>", self.redo)
        
        
    def canvas_zoom_in(self, event=None):
        self.res *= 1.2
        self.backend.zoom(1.2)

    def canvas_zoom_out(self, event=None):
        self.res *= 0.8
        self.backend.zoom(0.8)
        
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