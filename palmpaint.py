"""
Paint Application is a Tkinter-based pixel painting program for creating
simple SDs for PALM.

    Copyright (C) 2025  Pierre Monteyne

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

import json
import math
import os
import tkinter as tk
import tkinter.filedialog as fd

import framework
from create_sd import Save
from load_sd import Load
import welcome_screen




class PaintApplication(framework.Framework):
    
    start_x = 0
    start_y = 0
    end_x = 0
    end_y = 0
    current_item = None
    brush_size = 1
    
    # Initialize attributes for building tool
    building_id = 1
    building_height = 10
    building_type = 2

    tool_bar_functions = (
        "vegetation", "pavement", "soil", "water", "building")
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
        row = int(self.start_y // self.res)
        
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
    
    def update_canvas(self, y, x):
        """Update the canvas for a specific pixel."""
        self.canvas.itemconfig(self.pixels[(y, x)]["id"], 
                               fill=self.pixels[(y, x)]["color"])

    def update_pixel(self, row, col, **kwargs):
        """Update pixel attributes."""
        for key, value in kwargs.items():
            self.pixels[(row, col)][key] = value
            
    def vegetation(self):
        """Apply vegetation tool to affected pixels."""
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, 
                                  pavement_type=-127, 
                                  vegetation_type=3, 
                                  soil_type=1,
                                  building_id=-127, 
                                  building_height=-127,
                                  building_type=-127, 
                                  color="green")
                self.update_canvas(row, col)
        
        # row, col = self.get_pixel_position()
        
        # if (row, col) in self.pixels:
        #     self.update_pixel(row, col, pavement_type=-127, vegetation_type=3, soil_type=1, color="green")
        #     self.update_canvas(row, col)
        
    def pavement(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, 
                                  pavement_type=1, 
                                  soil_type=1, 
                                  vegetation_type=-127,
                                  building_id=-127, 
                                  building_height=-127,
                                  building_type=-127,
                                  color="grey")
                self.update_canvas(row, col)
        
    def soil(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, 
                                  soil_type=1,
                                  pavement_type=-127, 
                                  vegetation_type=-127, 
                                  building_id=-127, 
                                  building_height=-127,
                                  building_type=-127,  
                                  color="brown")
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

        self.canvas.delete("all")
        
        new_nx, new_ny, new_res = welcome_screen.get_welcome_input(self.root)
        self.nx = new_nx
        self.ny = new_ny
        self.original_res = new_res
        self.res = new_res 

        self.draw_grid(self.nx, self.ny, self.res)
        
    def confirm_action(self, title, message):
        return tk.messagebox.askyesno(title, message)
        
        
    def save_netcdf(self):
        Save(self.pixels, self.original_res)
        
    def load_project_netcdf(self):
        """
        Open a file dialog to let the user choose a NetCDF project file,
        then load it using load_sd.Load() and update the canvas.
        """
        file_path = fd.askopenfilename(
            defaultextension=".nc",
            filetypes=[("NetCDF files", "*.nc"), ("All files", "*.*")]
        )
        if not file_path:
            return  # User cancelled

        try:
            grid, nx, ny, res = Load(file_path)
        except Exception as e:
            print(f"Error loading NetCDF file: {e}")
            return
        
        self.canvas.delete("all")
        # Update grid parameters and replace the current grid
        self.pixels = grid
        self.nx = nx
        self.ny = ny
        self.res = res
        
        

        # Redraw the grid to reflect the loaded data
        self.update_grid(self.nx, self.ny, self.res)
        print(f"Loaded NetCDF project from {file_path}")    
        
        
    def save_project(self, filename="quicksave.json"):
        """
        Save the current grid state to a JSON file.
        Non-serializable properties (like canvas IDs) are excluded.
        """
        data = {
            "nx": self.nx,
            "ny": self.ny,
            "res": self.original_res,
            "pixels": {}
        }
        for (row, col), pixel in self.pixels.items():
            # Create a serializable pixel dictionary, excluding the canvas "id"
            pixel_data = {k: v for k, v in pixel.items() if k != "id"}
            # Use a string key for JSON (e.g., "row,col")
            key = f"{row},{col}"
            data["pixels"][key] = pixel_data

        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Project saved to {os.path.abspath(filename)}")

    def load_project(self, filename="quicksave.json"):
        """
        Load the grid state from a JSON file and update the view.
        The grid is redrawn based on the loaded data.
        """
        try:
            with open(filename, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            print("No saved project found!")
            return
        
        self.canvas.delete("all")
        self.nx = data.get("nx", self.nx)
        print(self.nx)
        self.ny = data.get("ny", self.ny)
        print(self.ny)
        self.res = data.get("res", self.res)
        print(self.res)

        # Update each pixel; we assume the grid is already created
        for key, pixel_data in data["pixels"].items():
            row, col = map(int, key.split(","))
            if (row, col) in self.pixels:
                # Update existing pixel (except canvas id)
                self.pixels[(row, col)].update(pixel_data)
            else:
                # If grid dimensions changed, add the pixel
                self.pixels[(row, col)] = pixel_data

        # Redraw the grid to reflect loaded state
        self.update_grid(self.nx, self.ny, self.res)
        print(f"Project loaded from {os.path.abspath(filename)}")
        
    def save_as_project(self):
        """
        Save the current grid state to a JSON file using a file save dialog.
        """
        file_path = fd.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return  # User cancelled the dialog

        data = {
            "nx": self.nx,
            "ny": self.ny,
            "res": self.original_res,
            "pixels": {}
        }
        for (row, col), pixel in self.pixels.items():
            # Exclude non-serializable items like canvas "id"
            pixel_data = {k: v for k, v in pixel.items() if k != "id"}
            key = f"{row},{col}"
            data["pixels"][key] = pixel_data

        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
        print(f"Project saved to {os.path.abspath(file_path)}")

    def load_from_json(self):
        """
        Load the grid state from a JSON file chosen by the user.
        """
        file_path = fd.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return  # User cancelled the dialog

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading file: {e}")
            return
        
        self.canvas.delete("all")
        self.nx = data.get("nx", self.nx)
        self.ny = data.get("ny", self.ny)
        self.res = data.get("res", self.res)

        # Update pixels with loaded data
        for key, pixel_data in data["pixels"].items():
            row, col = map(int, key.split(","))
            if (row, col) in self.pixels:
                self.pixels[(row, col)].update(pixel_data)
            else:
                self.pixels[(row, col)] = pixel_data

        self.update_grid(self.nx, self.ny, self.res)  # Redraw the grid to reflect the loaded state
        print(f"Project loaded from {os.path.abspath(file_path)}")
    
    def function_not_defined(self):
        pass
    
    def __init__(self, root,  nx=16, ny=16, res=4):
        self.nx = nx
        self.ny = ny
        self.original_res = res
        self.res = res
        
        # Get screen dimensions
        # screen_width = root.winfo_screenwidth()
        # screen_height = root.winfo_screenheight()
        # print(screen_width, screen_height)
        # desired_width = int(screen_width * 0.8)
        # desired_height = int(screen_height * 0.8)
        # computed_display_res = int(min(desired_width / nx, desired_height / ny))
        # self.res = computed_display_res
        super().__init__(root)
        self.create_gui()
        self.draw_grid(self.nx, self.ny, self.res)
        self.bind_mouse()
        self.bind_shortcuts()
        
    # ------------------ Initialize Grid ------------------    

    def draw_grid(self, nx, ny, res):
        """Create a grid of pixels and store their IDs in a dictionary"""
        self.pixels = {}
        for row in range(ny):
            for col in range(nx):
                x1, y1 = col * res, row * res
                x2, y2 = x1 + res, y1 + res
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, 
                                                    fill="brown", outline="gray")
                #print(rect)
                # Store the pixel data in a dictionary
                self.pixels[(row, col)] = {"id": rect,
                                           "vegetation_type": -127,
                                           "pavement_type": -127,
                                           "water_type": -127,
                                           "building_id": -127,
                                           "building_height": -127,
                                           "building_type": -127,
                                           "soil_type": 1,
                                           "color": "brown",
                                           "outline": "gray",}
        #print(self.pixels)
        
    def update_grid(self, nx, ny, res):
        """Update the grid after changes in resolution."""
        #self.canvas.delete("all")
        for row in range(ny):
            for col in range(nx):
                x1, y1 = col*res, row*res
                x2, y2 = x1 + res, y1 + res
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, 
                                                    fill=self.pixels[(row, col)]["color"], 
                                                    outline=self.pixels[(row, col)]["outline"])
                self.pixels[(row, col)]["id"] = rect
                
                
        
    # ------------------ GUI ------------------     
    def create_gui(self):
        self.create_top_bar()
        self.show_selected_tool_icon_in_top_bar(str(self.tool_bar_functions[0]))
        self.create_tool_bar()
        self.create_tool_bar_buttons()
        
        self.create_drawing_canvas()
        self.create_current_coordinate_label()
        self.create_menu()
        self.create_brush_size_slider()
        
        
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
            button_text = name
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
          
    def create_current_coordinate_label(self):
        self.current_coordinate_label = tk.Label(
            self.tool_bar, text='x:0\ny: 0 ')
        self.current_coordinate_label.grid(
            row=13, column=1, columnspan=2, 
            pady=5, padx=1, sticky='w')

    def show_current_coordinates(self, event=None):
        """Update the current coordinate label based on mouse movement."""
        x_coordinate = self.canvas.canvasx(event.x) // self.res
        y_coordinate = self.canvas.canvasx(event.y) // self.res
        coordinate_string = "x:{0}\ny:{1}".format(x_coordinate, y_coordinate)
        self.current_coordinate_label.config(text=coordinate_string)
        
    def create_drawing_canvas(self):
        self.canvas_frame = tk.Frame(self.root, width=self.nx * self.res, height=self.ny * self.res)
        self.canvas_frame.pack(side="right", expand="yes", fill="both")
        self.canvas = tk.Canvas(self.canvas_frame, background="white",
                                width=self.nx*self.res, height=self.ny*self.res, 
                                scrollregion=(0, 0, self.nx * self.res, self.ny * self.res))
        self.create_scroll_bar()
        self.canvas.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.BOTH)

    def create_scroll_bar(self):
        x_scroll = tk.Scrollbar(self.canvas_frame, orient="horizontal")
        x_scroll.pack(side="bottom", fill="x")
        x_scroll.config(command=self.canvas.xview)
        y_scroll = tk.Scrollbar(self.canvas_frame, orient="vertical")
        y_scroll.pack(side="right", fill="y")
        y_scroll.config(command=self.canvas.yview)
        self.canvas.config(
            xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
    
    # ------------------ Mouse ------------------
    
    def bind_mouse(self):
        self.canvas.bind("<Button-1>", self.on_mouse_button_pressed)
        self.canvas.bind(
            "<Button1-Motion>", self.on_mouse_button_pressed_motion)
        self.canvas.bind(
            "<Button1-ButtonRelease>", self.on_mouse_button_released)
        self.canvas.bind("<Motion>", self.on_mouse_unpressed_motion)

    def on_mouse_button_pressed(self, event):
        self.start_x = self.end_x = self.canvas.canvasx(event.x)
        self.start_y = self.end_y = self.canvas.canvasy(event.y)
        self.execute_selected_method()



    def on_mouse_button_released(self, event):
        self.end_x = self.canvas.canvasx(event.x)
        self.end_y = self.canvas.canvasy(event.y)

    def on_mouse_unpressed_motion(self, event):
        self.show_current_coordinates(event)
        

# ------------------ Extras ------------------

    def create_menu(self):
        self.menubar = tk.Menu(self.root)
        menu_definitions = (
            'File - New Project//self.new_project, Save to NetCDF//self.save_netcdf, Save Project//self.save_project, Save Project as ...//self.save_as_project, sep,'+
            'Load from NetCDF//self.load_project_netcdf, Load Project//self.load_project, Load Project from JSON//self.load_from_json, sep, Exit//self.root.quit',
            'View- Zoom in/Ctrl+ Up Arrow/self.canvas_zoom_in,Zoom Out/Ctrl+Down Arrow/self.canvas_zoom_out',
        )
        self.build_menu(menu_definitions)
    def bind_shortcuts(self):
        self.root.bind("<Control-Up>", self.canvas_zoom_in)
        self.root.bind("<Control-Down>", self.canvas_zoom_out)
        
    def canvas_zoom_in(self, event=None):
        self.canvas.scale("all", 0, 0, 1.2, 1.2)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        # update coordinates in dictionary
        self.res *= 1.2
        self.update_grid(self.nx, self.ny, self.res)
        

    def canvas_zoom_out(self, event=None):
        self.canvas.scale("all", 0, 0, .8, .8)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        # update coordinates in dictionary
        self.res *= .8
        self.update_grid(self.nx, self.ny, self.res)
        
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
            self.top_bar, from_=1, to=200, width=3, textvariable=initial_height, command=self.update_building_attributes)
        self.building_height_spinbox.pack(side="left")
        tk.Label(self.top_bar, text='building_type:').pack(side="left", padx=5)
        self.building_type_spinbox = tk.Spinbox(
            self.top_bar, from_=1, to=6, width=3, textvariable=initial_type, command=self.update_building_attributes)
        self.building_type_spinbox.pack(side="left")
               
    def update_building_attributes(self):
        """
        Update the current building attributes based on spinbox values.
        """
        self.building_id = self.building_id_spinbox.get()
        self.building_height = self.building_height_spinbox.get()
        self.building_type = self.building_type_spinbox.get()
        
        
if __name__ == '__main__':
    # Ask the user for grid settings at startup
    root = tk.Tk()
    root.withdraw()
    nx, ny, res = welcome_screen.get_welcome_input(root)
    root.deiconify()
    root.title("PALMPaint")
    app = PaintApplication(root, nx, ny, res)
    root.mainloop()