"""
Tkinter Canvas rendering backend for PALMPaint.

Owns the tk.Canvas widget and all canvas-drawing operations.
Reads colour information from a GridModel instance but never
modifies it — all data changes go through the GridModel.

    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

import tkinter as tk
import numpy as np


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
        self.nx = nx
        self.ny = ny
        self.res = res
        self.pixels = {}   # {(row, col): {"id": canvas_id, "outline": colour}}
        self.show_grid_lines = True
        self.view_mode = "landcover"
        self.height_view_min = 0.0
        self.height_view_step = 1.0
        self.height_view_levels = 10
        self.domain_border_id = None
        self.domain_border_color = "black"
        self.domain_border_width = 2
        
        self.hover_items = []
        self.default_outline_color = "white"
        self.hover_outline_color = "#ffd166"
        self.hover_outline_width = 2
        self.normal_outline_width = 1
        self._setup_canvas(root, nx, ny, res)
        
        self.tree_overlay_items = []
        self.tree_overlay_color = "#0b5d1e"
        self.tree_overlay_extinction_k = 0.15
        self.tree_overlay_outline_width = 1
        self.show_tree_overlay = True

        self.error_overlay_items = []
        self.error_overlay_color = "red"
        self.error_overlay_width = 2
        self.show_error_overlay = False

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

    def _get_base_outline_color(self):
        return self.default_outline_color if self.show_grid_lines else ""

    def _draw_domain_border(self):
        """Draw or update the visible border of the paintable domain."""
        x2 = self.nx * self.res
        y2 = self.ny * self.res

        if self.domain_border_id is None:
            self.domain_border_id = self.canvas.create_rectangle(
                0,
                0,
                x2,
                y2,
                fill="",
                outline=self.domain_border_color,
                width=self.domain_border_width,
            )
        else:
            self.canvas.coords(self.domain_border_id, 0, 0, x2, y2)
            self.canvas.itemconfig(
                self.domain_border_id,
                outline=self.domain_border_color,
                width=self.domain_border_width,
            )

        self.canvas.tag_raise(self.domain_border_id)
    
    # ------------------------------------------------------------------
    # Grid drawing
    # ------------------------------------------------------------------

    def draw_grid(self, nx, ny, res):
        """Create fresh canvas rectangles and initialise the pixel registry.

        Called when a new project is started or after loading.
        Existing canvas objects are NOT deleted here — call clear() first
        if you need to wipe the canvas.
        """
        self.nx = nx
        self.ny = ny
        self.res = res
        self.pixels = {}
        outline_color = self._get_base_outline_color()
        for row in range(ny):
            for col in range(nx):
                x1, y1 = col * res, (ny - 1 - row) * res
                x2, y2 = x1 + res, y1 + res
                color = self.model.get_color(row, col, view_mode=self.view_mode)
                rect = self.canvas.create_rectangle(
                    x1, y1, x2, y2, fill=color, outline=outline_color, width=self.normal_outline_width
                )
                self.pixels[(row, col)] = {"id": rect, "outline": outline_color, "width": self.normal_outline_width}
        self._draw_domain_border()
        self.canvas.config(scrollregion=(0, 0, nx * res, ny * res))
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)
        # Defer tree-overlay drawing until update_grid() so loaded projects use
        # the final cell geometry instead of a too-early first draw.
            
    def set_grid_lines_visible(self, visible):
        self.show_grid_lines = bool(visible)
        outline_color = self._get_base_outline_color()

        for pixel in self.pixels.values():
            self.canvas.itemconfig(
                pixel["id"],
                outline=outline_color,
                width=self.normal_outline_width,
            )
            pixel["outline"] = outline_color
            pixel["width"] = self.normal_outline_width
            
    def update_grid(self, nx, ny, res):
        """Redraw all canvas rectangles from the current model state."""
        self.nx = nx
        self.ny = ny
        self.res = res
        outline_color = self._get_base_outline_color()
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
                        x1, y1, x2, y2, fill=color, outline=outline_color, width=self.normal_outline_width
                    )
                    self.pixels[(row, col)] = {"id": rect, "outline": outline_color, "width": self.normal_outline_width}
                else:
                    self.canvas.coords(pixel_info["id"], x1, y1, x2, y2)
                    self.canvas.itemconfig(
                        pixel_info["id"], fill=color, outline=outline_color, width=self.normal_outline_width
                    )
                    pixel_info["outline"] = outline_color
                    pixel_info["width"] = self.normal_outline_width
        self._draw_domain_border()
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        self.redraw_tree_overlay()
        
        
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

    def update_pixels(self, cells):
        """Refresh fill colours for a batch of (row, col) cells.

        All canvas itemconfig() calls are deferred to a single pass here
        so callers can do all model mutations first and then update the view
        in one sweep — much cheaper than calling update_pixel() per cell.
        """
        for row, col in cells:
            pixel_info = self.pixels.get((row, col))
            if pixel_info is None:
                continue
            self.canvas.itemconfig(
                pixel_info["id"],
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

    def canvas_to_grid(self, canvas_x, canvas_y):
        """Convert canvas coordinates to grid (row, col), correctly handling zoom.

        Uses the actual current canvas geometry of cell (0, 0) as a reference so
        results are correct regardless of how many times / how the view was zoomed.
        """
        if not self.pixels:
            return 0, 0
        x1, _y1, x2, y2 = self.canvas.coords(self.pixels[(0, 0)]["id"])
        cell_size = x2 - x1
        if cell_size <= 0:
            return 0, 0
        # x1 is the left edge of column 0; y2 is the bottom edge of row 0.
        col = int((canvas_x - x1) / cell_size)
        row = int((y2 - canvas_y) / cell_size)
        return row, col

    def zoom(self, factor, anchor_x=None, anchor_y=None):
        """
        Scale all canvas objects and update the scroll region.

        If an anchor point is provided, zoom around that canvas position so the
        point under the mouse stays visually stable. If no anchor is given,
        fall back to the visible canvas center.
        """
        # Fallback: zoom around the visible center of the canvas.
        if anchor_x is None or anchor_y is None:
            widget_x = self.canvas.winfo_width() / 2
            widget_y = self.canvas.winfo_height() / 2
            anchor_x = self.canvas.canvasx(widget_x)
            anchor_y = self.canvas.canvasy(widget_y)
        else:
            # Convert the anchor from canvas coordinates back to widget coordinates.
            # We need the widget position later so we can restore the same visual
            # mouse location after scaling.
            widget_x = self.canvas.winfo_width() / 2
            widget_y = self.canvas.winfo_height() / 2

        # Remember where the anchor currently appears in widget coordinates.
        before_x = self.canvas.canvasx(widget_x)
        before_y = self.canvas.canvasy(widget_y)

        # Scale everything around the chosen anchor point.
        self.canvas.scale("all", anchor_x, anchor_y, factor, factor)

        # Update the scroll region after scaling.
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

        # After scaling, the canvas-to-widget mapping changed.
        after_x = self.canvas.canvasx(widget_x)
        after_y = self.canvas.canvasy(widget_y)

        # Compute the drift introduced by zooming.
        dx = after_x - before_x
        dy = after_y - before_y

        # Shift the view back so the anchor remains visually stable.
        bbox = self.canvas.bbox(tk.ALL)
        if bbox:
            x1, y1, x2, y2 = bbox
            total_width = x2 - x1
            total_height = y2 - y1

            if total_width > 0:
                left = self.canvas.canvasx(0) - dx
                self.canvas.xview_moveto((left - x1) / total_width)

            if total_height > 0:
                top = self.canvas.canvasy(0) - dy
                self.canvas.yview_moveto((top - y1) / total_height)
                
    # ------------------------------------------------------------------
    # Hover effects
    # ------------------------------------------------------------------
    def clear_hover_preview(self):
        """Remove all temporary hover overlay rectangles."""
        for item_id in self.hover_items:
            self.canvas.delete(item_id)
        self.hover_items = []

    def show_hover_preview(self, cells):
        """Draw a hover outline overlay for a collection of grid cells."""
        self.clear_hover_preview()

        for row, col in cells:
            pixel = self.pixels.get((row, col))
            if pixel is None:
                continue

            x1, y1, x2, y2 = self.canvas.coords(pixel["id"])
            hover_id = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=self.hover_outline_color,
                width=self.hover_outline_width,
                fill=""
            )
            self.hover_items.append(hover_id)
            self.canvas.tag_raise(hover_id)

        if self.domain_border_id is not None:
            self.canvas.tag_raise(self.domain_border_id)
            
    # ------------------------------------------------------------------
    # Tree overlay
    # ------------------------------------------------------------------
    def clear_tree_overlay(self):
        for item_id in self.tree_overlay_items:
            self.canvas.delete(item_id)
        self.tree_overlay_items = []

    def _to_rgb255(self, color):
        """Resolve any Tk color string to 8-bit RGB."""
        r16, g16, b16 = self.canvas.winfo_rgb(color)
        return (r16 // 257, g16 // 257, b16 // 257)

    def _blend_colors(self, base_color, overlay_color, alpha):
        """Blend overlay_color over base_color with alpha in [0, 1]."""
        alpha = min(max(float(alpha), 0.0), 1.0)
        br, bg, bb = self._to_rgb255(base_color)
        or_, og, ob = self._to_rgb255(overlay_color)
        r = int(round((1.0 - alpha) * br + alpha * or_))
        g = int(round((1.0 - alpha) * bg + alpha * og))
        b = int(round((1.0 - alpha) * bb + alpha * ob))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _tree_cell_style(self, lai_value, cell_size, base_color):
        """Return geometry and fill styling for one tree overlay cell.

        Beer-Lambert transparency is approximated by blending the tree color
        with the displayed ground color of the cell. This gives a smoother,
        continuous response than Tk's coarse stipple patterns.
        """
        cell_size = max(1.0, float(cell_size))
        lai_value = max(0.0, float(lai_value))

        # Keep grid lines and corners visible by drawing inside the cell.
        inset = max(0.25, 0.12 * cell_size)
        inset = min(inset, 0.35 * cell_size)
        transparency = float(np.exp(-self.tree_overlay_extinction_k * lai_value))
        alpha = 1.0 - transparency
        fill_color = self._blend_colors(base_color, self.tree_overlay_color, alpha)

        return inset, fill_color
        
    def set_tree_overlay_visible(self, visible):
        self.show_tree_overlay = visible
        if visible:
            self.redraw_tree_overlay()
        else:
            self.clear_tree_overlay()

    def redraw_tree_overlay(self):
        self.clear_tree_overlay()
        if not self.show_tree_overlay:
            return

        rv = getattr(self.model, "resolved_vegetation", None)
        if not rv:
            return

        tree_id = rv.get("tree_id")
        lad = rv.get("lad")

        if lad is not None and np.any(lad > 0):
            zlad = rv.get("zlad")
            dz = self.model.infer_dz_from_zlad(zlad, self.model.dz)
            lai_2d = np.where(lad > 0, lad, 0.0).sum(axis=0) * dz
            mask2d = lai_2d > 0
        elif tree_id is not None and np.any(tree_id > 0):
            mask2d = np.any(tree_id > 0, axis=0)
            lai_2d = None
        else:
            return
        rows, cols = np.where(mask2d)

        for row, col in zip(rows, cols):
            pixel = self.pixels.get((row, col))
            if pixel is None:
                continue
            x1, y1, x2, y2 = self.canvas.coords(pixel["id"])
            cell_size = min(x2 - x1, y2 - y1)
            lai_value = float(lai_2d[row, col]) if lai_2d is not None else 0.0
            base_fill = self.canvas.itemcget(pixel["id"], "fill") or "white"
            inset, fill_color = self._tree_cell_style(lai_value, cell_size, base_fill)
            rect_kwargs = dict(
                outline=self.tree_overlay_color,
                width=self.tree_overlay_outline_width,
                fill=fill_color,
            )
            item = self.canvas.create_rectangle(
                x1 + inset, y1 + inset, x2 - inset, y2 - inset,
                **rect_kwargs,
            )
            self.tree_overlay_items.append(item)
            self.canvas.tag_raise(item)

        if self.domain_border_id is not None:
            self.canvas.tag_raise(self.domain_border_id)

    # ------------------------------------------------------------------
    # Validation error overlay
    # ------------------------------------------------------------------

    def clear_error_overlay(self):
        for item_id in self.error_overlay_items:
            self.canvas.delete(item_id)
        self.error_overlay_items = []

    def set_error_overlay_visible(self, visible):
        self.show_error_overlay = visible
        if visible:
            self._redraw_error_overlay()
        else:
            self.clear_error_overlay()

    def update_error_overlay(self, invalid_mask):
        """Store *invalid_mask* and redraw the overlay if currently visible.

        Parameters
        ----------
        invalid_mask : numpy bool array of shape (ny, nx)
            True for every cell involved in at least one validation violation.
        """
        self._error_invalid_mask = invalid_mask
        if self.show_error_overlay:
            self._redraw_error_overlay()

    def _redraw_error_overlay(self):
        self.clear_error_overlay()
        if not self.show_error_overlay:
            return
        mask = getattr(self, "_error_invalid_mask", None)
        if mask is None or not np.any(mask):
            return
        rows, cols = np.where(mask)
        inset = max(1.0, 0.1 * self.res)
        inset = min(inset, 0.3 * self.res)
        for row, col in zip(rows, cols):
            pixel = self.pixels.get((row, col))
            if pixel is None:
                continue
            x1, y1, x2, y2 = self.canvas.coords(pixel["id"])
            item = self.canvas.create_rectangle(
                x1 + inset, y1 + inset, x2 - inset, y2 - inset,
                outline=self.error_overlay_color,
                width=self.error_overlay_width,
                fill="",
            )
            self.error_overlay_items.append(item)
            self.canvas.tag_raise(item)
        if self.domain_border_id is not None:
            self.canvas.tag_raise(self.domain_border_id)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self):
        """Delete all canvas objects and reset the pixel registry."""
        self.canvas.delete("all")
        self.pixels = {}
        self.domain_border_id = None
        self.hover_items = []
        self.clear_tree_overlay()
        self.clear_error_overlay()
