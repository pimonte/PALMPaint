import tkinter as tk
import framework
from create_sd import Save
import math

class PaintApplication(framework.Framework):
    
    start_x, start_y = 0, 0
    end_x, end_y = 0, 0
    nx = 16 
    ny = 16
    res = 4
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
        self.canvas.itemconfig(self.pixels[(y, x)]["id"], fill=self.pixels[(y, x)]["color"])

    def update_pixel(self, row, col, **kwargs):
        for key, value in kwargs.items():
            self.pixels[(row, col)][key] = value
            
    def vegetation(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, pavement_type=-127, vegetation_type=3, soil_type=1, color="green")
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
                self.update_pixel(row, col, pavement_type=1, soil_type=1, vegetation_type=-127, color="grey")
                self.update_canvas(row, col)
        
    def soil(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, soil_type=1, color="brown")
                self.update_canvas(row, col)
        
    def water(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, water_type=1, pavement_type=-127, vegetation_type=-127, soil_type=-127, color="blue")
                self.update_canvas(row, col)
        
    def building(self):
        center_row, center_col = self.get_pixel_position()
        affected_pixels = self.get_pixels_in_brush(center_row, center_col)
        
        for row, col in affected_pixels:
            if (row, col) in self.pixels:
                self.update_pixel(row, col, 
                                  building_id=self.building_id, building_height=self.building_height, building_type=self.building_type,
                                  pavement_type=-127, vegetation_type=-127, soil_type=-127, water_type=-127, 
                                  color="black")
                self.update_canvas(row, col)
        
    def Save_NetCDF(self):
        Save(self.pixels, self.res)
        

        
    
    def function_not_defined(self):
        pass
    
       
    def __init__(self, root):
        super().__init__(root)
        self.create_gui()
        self.draw_grid(self.nx, self.ny, self.res)
        self.bind_mouse()
        
    # ------------------ Initialize Grid ------------------    
    def draw_grid(self, nx, ny, res):
        # Create a grid of pixels and store their IDs in a dictionary
        self.pixels = {}
        for row in range(ny):
            for col in range(nx):
                x1, y1 = col*res, row*res
                x2, y2 = x1 + res, y1 + res
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill="brown", outline="gray")
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
        #self.canvas.delete("all")
        for row in range(ny):
            for col in range(nx):
                x1, y1 = col*res, row*res
                x2, y2 = x1 + res, y1 + res
                rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill=self.pixels[(row, col)]["color"], outline=self.pixels[(row, col)]["outline"])
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
        self.brush_size_slider = tk.Scale(self.tool_bar, from_=1, to=10,
                                          resolution=2, orient="horizontal", label="Brush Pixel diameter")
        self.brush_size_slider.set(self.brush_size)
        self.brush_size_slider.grid(row=15, column=1, columnspan=2, pady=5, padx=1, sticky='w')
        self.brush_size_slider.bind("<Motion>", self.update_brush_size)

    def update_brush_size(self, event=None):
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
                self.tool_bar, text=button_text, command=lambda index=index: self.on_tool_bar_button_clicked(index))
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
        self.show_selected_tool_icon_in_top_bar(
            self.selected_tool_bar_function)
        options_function_name = "{}_options".format(self.selected_tool_bar_function)
        func = getattr(self, options_function_name, self.function_not_defined)
        func()
          
    def create_current_coordinate_label(self):
        self.current_coordinate_label = tk.Label(
            self.tool_bar, text='x:0\ny: 0 ')
        self.current_coordinate_label.grid(
            row=13, column=1, columnspan=2, pady=5, padx=1, sticky='w')

    def show_current_coordinates(self, event=None):
        
        x_coordinate = self.canvas.canvasx(event.x) // self.res
        y_coordinate = self.canvas.canvasx(event.y) // self.res
        coordinate_string = "x:{0}\ny:{1}".format(x_coordinate, y_coordinate)
        self.current_coordinate_label.config(text=coordinate_string)
        
    def create_drawing_canvas(self):
        self.canvas_frame = tk.Frame(self.root, width=self.nx * self.res, height=self.ny * self.res)
        self.canvas_frame.pack(side="right", expand="yes", fill="both")
        self.canvas = tk.Canvas(self.canvas_frame, background="white",
                                width=self.nx*self.res, height=self.ny*self.res, scrollregion=(0, 0, self.nx * self.res, self.ny * self.res))
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
            'File - Save//self.Save_NetCDF, Exit//self.root.quit',
            'View- Zoom in//self.canvas_zoom_in,Zoom Out//self.canvas_zoom_out',
        )
        self.build_menu(menu_definitions)

    def canvas_zoom_in(self):
        self.canvas.scale("all", 0, 0, 1.2, 1.2)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        # update coordinates in dictionary
        self.res *= 1.2
        self.update_grid(self.nx, self.ny, self.res)
        

    def canvas_zoom_out(self):
        self.canvas.scale("all", 0, 0, .8, .8)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        # update coordinates in dictionary
        self.res *= .8
        self.update_grid(self.nx, self.ny, self.res)
        
    def building_options(self):
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
    root = tk.Tk()
    root.title("PALMPaint")
    app = PaintApplication(root)
    root.mainloop()