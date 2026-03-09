"""
Tkinter Canvas rendering backend for PALMPaint.

Owns the tk.Canvas widget and all canvas-drawing operations.
Reads colour information from a GridModel instance but never
modifies it — all data changes go through the GridModel.

    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

import tkinter as tk


class TkCanvasBackend:
    """Renders a GridModel onto a Tkinter Canvas.

    Parameters
    ----------
    root : tk.Tk or tk.Frame
        Parent widget. The canvas frame is packed into this widget.
    model : GridModel
        The data model to render. Can be replaced at runtime via
        ``backend.model = new_model`` before calling update_grid().
    nx, ny : int
        Initial grid dimensions.
    res : float
        Initial display resolution (pixels per grid cell).
    """

    def __init__(self, root, model, nx, ny, res):
        self.model  = model
        self.pixels = {}   # {(row, col): {"id": canvas_id, "outline": colour}}
        self.show_grid_lines = True
        self.view_mode = "landcover"
        self.height_view_min = 0.0
        self.height_view_step = 1.0
        self.height_view_levels = 10
        self._setup_canvas(root, nx, ny, res)

    # ------------------------------------------------------------------
    # Canvas setup
    # ------------------------------------------------------------------

    def _setup_canvas(self, root, nx, ny, res):
        self.canvas_frame = tk.Frame(root, width=nx * res, height=ny * res)
        self.canvas_frame.pack(side="right", expand="yes", fill="both")
        self.canvas = tk.Canvas(
            self.canvas_frame,
            background="white",
            width=nx * res,
            height=ny * res,
            scrollregion=(0, 0, nx * res, ny * res),
        )
        self._create_scroll_bars()
        self.canvas.pack(side=tk.RIGHT, expand=tk.YES, fill=tk.BOTH)

    def _create_scroll_bars(self):
        x_scroll = tk.Scrollbar(self.canvas_frame, orient="horizontal")
        x_scroll.pack(side="bottom", fill="x")
        x_scroll.config(command=self.canvas.xview)
        y_scroll = tk.Scrollbar(self.canvas_frame, orient="vertical")
        y_scroll.pack(side="right", fill="y")
        y_scroll.config(command=self.canvas.yview)
        self.canvas.config(
            xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set
        )

    # ------------------------------------------------------------------
    # Grid drawing
    # ------------------------------------------------------------------

    def draw_grid(self, nx, ny, res):
        """Create fresh canvas rectangles and initialise the pixel registry.

        Called when a new project is started or after loading.
        Existing canvas objects are NOT deleted here — call clear() first
        if you need to wipe the canvas.
        """
        self.pixels = {}
        outline_color = "white" if self.show_grid_lines else ""
        for row in range(ny):
            for col in range(nx):
                x1, y1 = col * res, (ny - 1 - row) * res
                x2, y2 = x1 + res, y1 + res
                rect = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill="brown", outline=outline_color
                )
                self.pixels[(row, col)] = {"id": rect, "outline": outline_color}
                
    def set_grid_lines_visible(self, visible):
        """Show or hide grid cell outlines."""
        self.show_grid_lines = bool(visible)
        outline_color = "white" if visible else ""

        for pixel in self.pixels.values():
            self.canvas.itemconfig(pixel["id"], outline=outline_color)
            pixel["outline"] = outline_color
            
    def update_grid(self, nx, ny, res):
        """Redraw all canvas rectangles from the current model state."""
        outline_color = "white" if self.show_grid_lines else ""
        z_min = z_max = None
        if self.view_mode == "heightmap":
            z_min = self.height_view_min
            z_max = self.height_view_min + self.height_view_step * self.height_view_levels

        for row in range(ny):
            for col in range(nx):
                x1, y1 = col * res, (ny - 1 - row) * res
                x2, y2 = x1 + res, y1 + res
                color = self.model.get_color(
                    row,
                    col,
                    view_mode=self.view_mode,
                    z_min=z_min,
                    z_max=z_max,
                    z_step=self.height_view_step,
                    levels=self.height_view_levels,
                )
                pixel_info = self.pixels.get((row, col))

                if pixel_info is None:
                    rect = self.canvas.create_rectangle(
                        x1, y1, x2, y2, fill=color, outline=outline_color
                    )
                    self.pixels[(row, col)] = {"id": rect, "outline": outline_color}
                else:
                    self.canvas.coords(pixel_info["id"], x1, y1, x2, y2)
                    self.canvas.itemconfig(
                        pixel_info["id"], fill=color, outline=outline_color
                    )
                    pixel_info["outline"] = outline_color

    def update_pixel(self, row, col):
        """Refresh the fill colour of a single canvas rectangle."""
        self.canvas.itemconfig(
            self.pixels[(row, col)]["id"],
            fill=self.model.get_color(
                row,
                col,
                view_mode=self.view_mode,
                z_min=self.height_view_min,
                z_step=self.height_view_step,
                levels=self.height_view_levels,
            ),
        )

    def set_view_mode(self, view_mode):
        """Set active display mode used for color lookup."""
        self.view_mode = view_mode

    def set_height_view_config(self, z_min, z_step, levels):
        """Set fixed discrete normalization used by the heightmap view."""
        self.height_view_min = float(z_min)
        self.height_view_step = max(1e-6, float(z_step))
        self.height_view_levels = max(1, int(levels))

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom(self, factor):
        """Scale all canvas objects and update the scroll region."""
        self.canvas.scale("all", 0, 0, factor, factor)
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self):
        """Delete all canvas objects and reset the pixel registry."""
        self.canvas.delete("all")
        self.pixels = {}
