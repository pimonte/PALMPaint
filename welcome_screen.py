import tkinter as tk
from tkinter import ttk, PhotoImage
import os

class WelcomeForm(tk.Toplevel):
    def __init__(self, master=None, default_nx=16, default_ny=16, default_res=4, logo_path=None):
        super().__init__(master)
        self.title("Welcome to PALMPaint")
        self.configure(bg="white")
        self.result = None  # Will hold the tuple (nx, ny, res)
        self.default_nx = default_nx
        self.default_ny = default_ny
        self.default_res = default_res
        self.logo_path = "./Pictures/palmpaint_small.png" # predetermined logo path set by the project
        
        # Set ttk styles to have a white background
        style = ttk.Style(self)
        style.configure("TFrame", background="white")
        style.configure("TLabel", background="white")
        style.configure("TLabelframe", background="white")
        style.configure("TLabelframe.Label", background="white")

        # Use ttk for a modern look and add padding via a container frame.
        container = ttk.Frame(self, padding=20)
        container.grid()

        # Welcome text
        welcome_label = ttk.Label(container, text="Welcome to PALMPaint!", font=("Helvetica", 16, "bold"))
        welcome_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Display the predetermined logo if provided and exists.
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.logo_image = PhotoImage(file=self.logo_path)
                logo_label = ttk.Label(container, image=self.logo_image)
                logo_label.grid(row=1, column=0, columnspan=1, pady=(0, 5))
            except Exception as e:
                logo_label = ttk.Label(container, text="   ")
                logo_label.grid(row=1, column=0, columnspan=1, pady=(0, 5))

        # Group nx and ny in a Labelframe called "Number of Grid Cells"
        grid_frame = ttk.Labelframe(container, text="Number of Grid Cells", padding=10)
        grid_frame.grid(row=2, column=0, columnspan=2, pady=10, padx=5, sticky="ew")

        ttk.Label(grid_frame, text="nx:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.nx_entry = ttk.Entry(grid_frame, width=10)
        self.nx_entry.insert(0, str(default_nx))
        self.nx_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(grid_frame, text="ny:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.ny_entry = ttk.Entry(grid_frame, width=10)
        self.ny_entry.insert(0, str(default_ny))
        self.ny_entry.grid(row=0, column=3, padx=5, pady=5)

        # Group res in a Labelframe called "Grid Width"
        width_frame = ttk.Labelframe(container, text="Grid Width", padding=10)
        width_frame.grid(row=3, column=0, columnspan=2, pady=10, padx=5, sticky="ew")

        ttk.Label(width_frame, text="res:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.res_entry = ttk.Entry(width_frame, width=10)
        self.res_entry.insert(0, str(default_res))
        self.res_entry.grid(row=0, column=1, padx=5, pady=5)

        # Create the action button with updated text.
        action_button = ttk.Button(container, text="Create New Static Driver Project", command=self.on_ok)
        action_button.grid(row=4, column=0, columnspan=2, pady=15)

        # Ensure closing the window sets default values.
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Center the window on the screen.
        self.update_idletasks()  # Ensure dimensions are calculated
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def on_ok(self):
        try:
            nx = int(self.nx_entry.get()) if self.nx_entry.get() != "" else self.default_nx
        except ValueError:
            nx = self.default_nx
        try:
            ny = int(self.ny_entry.get()) if self.ny_entry.get() != "" else self.default_ny
        except ValueError:
            ny = self.default_ny
        try:
            res = int(self.res_entry.get()) if self.res_entry.get() != "" else self.default_res
        except ValueError:
            res = self.default_res

        self.result = (nx, ny, res)
        self.destroy()

    def on_close(self):
        # Use default values if the user closes the form.
        self.result = (self.default_nx, self.default_ny, self.default_res)
        self.destroy()

def get_welcome_input(master, default_nx=16, default_ny=16, default_res=4, logo_path=None):
    welcome = WelcomeForm(master, default_nx, default_ny, default_res, logo_path=logo_path)
    master.wait_window(welcome)
    return welcome.result
