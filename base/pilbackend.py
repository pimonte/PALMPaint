"""
PIL/Pillow-accelerated canvas rendering backend for PALMPaint.

Replaces the per-cell tkinter Rectangle approach of TkCanvasBackend with a
single tk.PhotoImage that is rebuilt from a numpy array via PIL. This allows
grids of 500×500 and beyond to be rendered in well under a second instead of
hanging for many seconds.

Public API is intentionally identical to TkCanvasBackend so the two classes
are drop-in replacements for each other.

    Copyright (C) 2025  Pierre Lampe
    Licensed under the GNU General Public License v3 or later.
"""

import tkinter as tk

import numpy as np
from PIL import Image, ImageDraw, ImageTk


class PilCanvasBackend:
    """Renders a GridModel onto a Tkinter Canvas using a PIL PhotoImage.

    One ``tk.PhotoImage`` (= one canvas item) replaces the 250 000 individual
    rectangles that TkCanvasBackend creates for a 500×500 grid.

    Parameters
    ----------
    root : tk.Tk or tk.Frame
        Parent widget.
    model : GridModel
        Data model to render.
    nx, ny : int
        Initial grid dimensions.
    res : float
        Initial display resolution (pixels per grid cell).
    """

    # Maximum side length (px) of the display PhotoImage.
    # Keeps memory usage bounded (~48 MB at 4096×4096 RGB).
    # At 1729×1729 cells this limits zoom to ≈2.4 px/cell, i.e. the whole
    # grid always fits on screen at the initial view.
    _MAX_SIDE = 4096

    def _cap_er(self, er, nx=None, ny=None):
        """Clamp *er* (pixels per cell) so the display image stays ≤ _MAX_SIDE."""
        nx = nx if nx is not None else self.nx
        ny = ny if ny is not None else self.ny
        max_er = self._MAX_SIDE / max(nx, ny, 1)
        return max(0.25, min(float(er), max_er))

    def __init__(self, root, model, nx, ny, res):
        self.model = model
        self.nx = nx
        self.ny = ny
        # effective_res tracks the current zoom level (pixels per cell).
        # It is a float so fractional zoom steps accumulate correctly.
        self.effective_res = self._cap_er(res, nx, ny)

        # PIL image state
        self._base_image = None    # 1 px/cell PIL Image (ny × nx RGB)
        self._photo_image = None   # scaled tk.PhotoImage shown on canvas
        self._tk_photo = None      # underlying tk.PhotoImage (for partial put() updates)
        self._image_id = None      # canvas item id for the photo image

        # Pixel registry – kept as a plain dict {(row, col): {}} so that all
        # palmpaint.py code that tests ``(r, c) in self.pixels`` or iterates
        # ``self.pixels.keys()`` continues to work without modification.
        self.pixels = {}

        # View settings (must match TkCanvasBackend attribute names exactly)
        self.show_grid_lines = True
        self.view_mode = "landcover"
        self.height_view_min = 0.0
        self.height_view_step = 1.0
        self.height_view_levels = 10

        # Domain border
        self.domain_border_id = None
        self.domain_border_color = "black"
        self.domain_border_width = 2

        # Hover
        self.hover_items = []
        self.default_outline_color = "white"
        self.hover_outline_color = "#ffd166"
        self.hover_outline_width = 2
        self.normal_outline_width = 1

        self._setup_canvas(root, nx, ny, res)

        # Tree overlay
        self.tree_overlay_items = []
        self.tree_overlay_color = "#0b5d1e"
        self.tree_overlay_extinction_k = 0.15
        self.tree_overlay_outline_width = 1
        self.show_tree_overlay = True

        # Error overlay
        self.error_overlay_items = []
        self.error_overlay_color = "red"
        self.error_overlay_width = 2
        self.show_error_overlay = False
        self._error_invalid_mask = None

    # ------------------------------------------------------------------
    # Canvas setup (identical to TkCanvasBackend)
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
    # Internal PIL helpers
    # ------------------------------------------------------------------

    def _rebuild_base_image(self):
        """Rebuild the 1-px-per-cell PIL Image from the model colour array."""
        arr = self.model.get_color_array_rgb(
            view_mode=self.view_mode,
            z_min=self.height_view_min,
            z_step=self.height_view_step,
            levels=self.height_view_levels,
        )
        # Flip row axis: grid row 0 is at the bottom of the canvas,
        # PIL y=0 is the top → invert so they align.
        # np.ascontiguousarray ensures a C-contiguous buffer so PIL's
        # internal tobytes() takes the fast path instead of copying row-by-row.
        self._base_image = Image.fromarray(np.ascontiguousarray(arr[::-1]), "RGB")

    def _rebuild_display_image(self):
        """Scale the base image to the current effective_res and regenerate
        the tk.PhotoImage.

        Tree and error overlays are baked into the PIL image here via
        ImageDraw (C-level, no Tk canvas items).  Grid lines are drawn only
        when cells are >= 16 display pixels wide.
        """
        er = self.effective_res
        w = max(1, int(round(self.nx * er)))
        h = max(1, int(round(self.ny * er)))

        display = self._base_image.resize((w, h), Image.NEAREST)
        draw = None  # created lazily; avoids allocation when no overlay is needed

        # --- Tree overlay (baked, replaces per-cell canvas rectangles) ---
        if self.show_tree_overlay:
            rv = getattr(self.model, "resolved_vegetation", None)
            if rv:
                lad = rv.get("lad")
                tree_id_arr = rv.get("tree_id")
                if lad is not None and np.any(lad > 0):
                    zlad = rv.get("zlad")
                    dz = self.model.infer_dz_from_zlad(zlad, self.model.dz)
                    lai_2d = np.where(lad > 0, lad, 0.0).sum(axis=0) * dz
                    mask2d = lai_2d > 0
                elif tree_id_arr is not None and np.any(tree_id_arr > 0):
                    mask2d = np.any(tree_id_arr > 0, axis=0)
                    lai_2d = None
                else:
                    mask2d = None

                if mask2d is not None:
                    if draw is None:
                        draw = ImageDraw.Draw(display)
                    tree_rgb = self.model._hex_to_rgb(self.tree_overlay_color)
                    t_inset = int(round(max(0.25, 0.12 * er)))
                    t_inset = min(t_inset, int(round(0.35 * er)))
                    base_arr = np.asarray(self._base_image)  # (ny, nx, 3) read-only
                    alpha_arr = 1.0 - np.exp(
                        -self.tree_overlay_extinction_k *
                        (lai_2d if lai_2d is not None else np.zeros((self.ny, self.nx)))
                    )
                    tr, tg, tb = tree_rgb
                    rows_t, cols_t = np.where(mask2d)
                    for r, c in zip(rows_t.tolist(), cols_t.tolist()):
                        br, bg, bb = (int(v) for v in base_arr[self.ny - 1 - r, c])
                        alpha = float(alpha_arr[r, c])
                        a1 = 1.0 - alpha
                        fill = (
                            int(round(a1 * br + alpha * tr)),
                            int(round(a1 * bg + alpha * tg)),
                            int(round(a1 * bb + alpha * tb)),
                        )
                        x1d = int(round(c * er))
                        y1d = int(round((self.ny - 1 - r) * er))
                        x2d = int(round((c + 1) * er)) - 1
                        y2d = int(round((self.ny - r) * er)) - 1
                        ix1 = x1d + t_inset; iy1 = y1d + t_inset
                        ix2 = x2d - t_inset; iy2 = y2d - t_inset
                        if ix1 <= ix2 and iy1 <= iy2:
                            draw.rectangle(
                                (ix1, iy1, ix2, iy2),
                                fill=fill,
                                outline=tree_rgb,
                            )

        # --- Error overlay (baked, replaces per-cell canvas rectangles) ---
        if self.show_error_overlay:
            mask = getattr(self, "_error_invalid_mask", None)
            if mask is not None and np.any(mask):
                if draw is None:
                    draw = ImageDraw.Draw(display)
                err_rgb = self.model._hex_to_rgb(self.error_overlay_color)
                e_inset = max(1, int(round(0.1 * er)))
                e_inset = min(e_inset, int(round(0.3 * er)))
                rows_e, cols_e = np.where(mask)
                for r, c in zip(rows_e.tolist(), cols_e.tolist()):
                    x1d = int(round(c * er))
                    y1d = int(round((self.ny - 1 - r) * er))
                    x2d = int(round((c + 1) * er)) - 1
                    y2d = int(round((self.ny - r) * er)) - 1
                    ix1 = x1d + e_inset; iy1 = y1d + e_inset
                    ix2 = x2d - e_inset; iy2 = y2d - e_inset
                    if ix1 <= ix2 and iy1 <= iy2:
                        draw.rectangle(
                            (ix1, iy1, ix2, iy2),
                            outline=err_rgb,
                            width=self.error_overlay_width,
                        )

        # --- Grid lines on top (only when cells are >= 16 display px wide) ---
        if self.show_grid_lines and er >= 16:
            if draw is None:
                draw = ImageDraw.Draw(display)
            white = (255, 255, 255)
            for col in range(self.nx + 1):
                x = min(int(round(col * er)), w - 1)
                draw.line([(x, 0), (x, h - 1)], fill=white, width=1)
            for row in range(self.ny + 1):
                y = min(int(round(row * er)), h - 1)
                draw.line([(0, y), (w - 1, y)], fill=white, width=1)

        self._photo_image = ImageTk.PhotoImage(display)
        # Cache the underlying tk.PhotoImage so update_pixel/update_pixels can
        # call tk.PhotoImage.put() for O(cells) partial updates without a full rebuild.
        self._tk_photo = self._photo_image._PhotoImage__photo

    def _put_cell(self, row, col, color_str):
        """Write one cell directly into the displayed tk.PhotoImage via put().

        Modifies only the er×er pixel block for this cell. Far cheaper than
        _rebuild_display_image() for brush strokes: no image allocation, no
        full Tcl/PhotoImage copy.
        """
        if self._tk_photo is None:
            return
        er = self.effective_res
        x1 = int(round(col * er))
        y1 = int(round((self.ny - 1 - row) * er))
        x2 = int(round((col + 1) * er))
        y2 = int(round((self.ny - row) * er))
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        row_str = " ".join([color_str] * w)
        data = " ".join(["{" + row_str + "}"] * h)
        self._tk_photo.put(data, to=(x1, y1))
        if self.show_grid_lines and er >= 16:
            # Overlay 1-px white grid lines on the top and left edges of the cell.
            white_row = "{" + " ".join(["#ffffff"] * w) + "}"
            self._tk_photo.put(white_row, to=(x1, y1))
            white_col = " ".join(["{#ffffff}"] * h)
            self._tk_photo.put(white_col, to=(x1, y1))

    def _cell_coords(self, row, col):
        """Return canvas (x1, y1, x2, y2) for the given grid cell."""
        er = self.effective_res
        x1 = col * er
        y1 = (self.ny - 1 - row) * er
        return x1, y1, x1 + er, y1 + er

    # ------------------------------------------------------------------
    # Domain border
    # ------------------------------------------------------------------

    def _draw_domain_border(self):
        """Draw or reposition the visible domain-edge border rectangle."""
        x2 = self.nx * self.effective_res
        y2 = self.ny * self.effective_res
        if self.domain_border_id is None:
            self.domain_border_id = self.canvas.create_rectangle(
                0, 0, x2, y2,
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
        """Create (or replace) the PhotoImage canvas item for the full grid."""
        self.nx = nx
        self.ny = ny
        self.effective_res = self._cap_er(res, nx, ny)
        er = self.effective_res

        # Populate pixel registry for palmpaint.py compatibility
        self.pixels = {(r, c): {} for r in range(ny) for c in range(nx)}

        self._rebuild_base_image()
        self._rebuild_display_image()

        if self._image_id is None:
            self._image_id = self.canvas.create_image(
                0, 0, anchor="nw", image=self._photo_image
            )
        else:
            self.canvas.itemconfig(self._image_id, image=self._photo_image)

        self._draw_domain_border()
        self.canvas.config(
            scrollregion=(0, 0, int(round(nx * er)), int(round(ny * er)))
        )
        self.canvas.xview_moveto(0.0)
        self.canvas.yview_moveto(0.0)

    def update_grid(self, nx, ny, res):
        """Redraw the entire grid from the current model state."""
        self.nx = nx
        self.ny = ny
        self.effective_res = self._cap_er(res, nx, ny)
        er = self.effective_res

        # Refresh pixel registry (dimensions may have changed)
        self.pixels = {(r, c): {} for r in range(ny) for c in range(nx)}

        self._rebuild_base_image()
        self._rebuild_display_image()

        if self._image_id is None:
            self._image_id = self.canvas.create_image(
                0, 0, anchor="nw", image=self._photo_image
            )
        else:
            self.canvas.itemconfig(self._image_id, image=self._photo_image)

        self._draw_domain_border()
        self.canvas.config(
            scrollregion=(0, 0, int(round(nx * er)), int(round(ny * er)))
        )

    def update_pixel(self, row, col):
        """Refresh one cell.

        When er >= 1 each cell maps to at least one display pixel, so a cheap
        partial put() is used.  Below er=1 multiple cells share a display pixel;
        the display image is tiny in that case so a full rebuild is just as fast
        and avoids sub-pixel coordinate arithmetic.
        """
        color_str = self.model.get_color(
            row, col,
            view_mode=self.view_mode,
            z_min=self.height_view_min,
            z_step=self.height_view_step,
            levels=self.height_view_levels,
        )
        if self._base_image is not None:
            self._base_image.putpixel(
                (col, self.ny - 1 - row), self.model._hex_to_rgb(color_str)
            )
        if self.effective_res < 1.0:
            if self._image_id is not None:
                self._rebuild_display_image()
                self.canvas.itemconfig(self._image_id, image=self._photo_image)
        else:
            self._put_cell(row, col, color_str)

    def update_pixels(self, cells):
        """Refresh a batch of cells.

        Same er-based dispatch as update_pixel: partial put() above er=1,
        single full rebuild below (display image is tiny at low zoom).
        """
        for row, col in cells:
            color_str = self.model.get_color(
                row, col,
                view_mode=self.view_mode,
                z_min=self.height_view_min,
                z_step=self.height_view_step,
                levels=self.height_view_levels,
            )
            if self._base_image is not None:
                self._base_image.putpixel(
                    (col, self.ny - 1 - row), self.model._hex_to_rgb(color_str)
                )
            if self.effective_res >= 1.0:
                self._put_cell(row, col, color_str)
        if self.effective_res < 1.0 and self._image_id is not None:
            self._rebuild_display_image()
            self.canvas.itemconfig(self._image_id, image=self._photo_image)

    # ------------------------------------------------------------------
    # Grid lines
    # ------------------------------------------------------------------

    def set_grid_lines_visible(self, visible):
        self.show_grid_lines = bool(visible)
        if self._photo_image is not None:
            self._rebuild_display_image()
            self.canvas.itemconfig(self._image_id, image=self._photo_image)

    # ------------------------------------------------------------------
    # View mode / height config
    # ------------------------------------------------------------------

    def set_view_mode(self, view_mode):
        self.view_mode = view_mode

    def set_height_view_config(self, z_min, z_step, levels):
        self.height_view_min = float(z_min)
        self.height_view_step = max(1e-6, float(z_step))
        self.height_view_levels = max(1, int(levels))

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def canvas_to_grid(self, canvas_x, canvas_y):
        """Convert canvas pixel coordinates to grid (row, col)."""
        er = self.effective_res
        if er <= 0:
            return 0, 0
        col = int(canvas_x / er)
        # Canvas y=0 is the top of the image → grid row ny-1
        row = self.ny - 1 - int(canvas_y / er)
        return row, col

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def zoom(self, factor, anchor_x=None, anchor_y=None):
        """Zoom by *factor* around a canvas anchor point.

        The image is regenerated at the new resolution; overlays are also
        redrawn so they remain correctly positioned.
        """
        old_er = self.effective_res

        # Determine anchor in canvas coordinates
        if anchor_x is None or anchor_y is None:
            anchor_x = self.canvas.canvasx(self.canvas.winfo_width() / 2)
            anchor_y = self.canvas.canvasy(self.canvas.winfo_height() / 2)

        # Widget-relative position of the anchor (needed to restore scroll later)
        origin_x = self.canvas.canvasx(0)
        origin_y = self.canvas.canvasy(0)
        widget_anchor_x = anchor_x - origin_x
        widget_anchor_y = anchor_y - origin_y

        # Update effective_res — keep within [1, _MAX_SIDE/max(nx,ny)] range.
        self.effective_res = self._cap_er(old_er * factor)
        new_er = self.effective_res
        new_w = int(round(self.nx * new_er))
        new_h = int(round(self.ny * new_er))

        # Rebuild display image at new resolution
        self._rebuild_display_image()
        if self._image_id is not None:
            self.canvas.itemconfig(self._image_id, image=self._photo_image)
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

        # Reposition scroll so the anchor point stays visually stable.
        # The canvas position of the anchor scales linearly with effective_res.
        new_anchor_x = anchor_x * (new_er / old_er)
        new_anchor_y = anchor_y * (new_er / old_er)
        new_origin_x = new_anchor_x - widget_anchor_x
        new_origin_y = new_anchor_y - widget_anchor_y
        if new_w > 0:
            self.canvas.xview_moveto(max(0.0, new_origin_x / new_w))
        if new_h > 0:
            self.canvas.yview_moveto(max(0.0, new_origin_y / new_h))

        # Reposition canvas overlays (they don't scale automatically)
        self._draw_domain_border()
        self.clear_hover_preview()

    # ------------------------------------------------------------------
    # Hover effects
    # ------------------------------------------------------------------

    def clear_hover_preview(self):
        for item_id in self.hover_items:
            self.canvas.delete(item_id)
        self.hover_items = []

    def show_hover_preview(self, cells):
        self.clear_hover_preview()
        for row, col in cells:
            if (row, col) not in self.pixels:
                continue
            x1, y1, x2, y2 = self._cell_coords(row, col)
            hover_id = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=self.hover_outline_color,
                width=self.hover_outline_width,
                fill="",
            )
            self.hover_items.append(hover_id)
            self.canvas.tag_raise(hover_id)
        if self.domain_border_id is not None:
            self.canvas.tag_raise(self.domain_border_id)

    # ------------------------------------------------------------------
    # Tree overlay
    # ------------------------------------------------------------------

    def clear_tree_overlay(self):
        # Tree overlay is baked into the display image; no canvas items to delete.
        self.tree_overlay_items = []

    def _to_rgb255(self, color):
        """Resolve any Tk colour string to 8-bit RGB via winfo_rgb."""
        r16, g16, b16 = self.canvas.winfo_rgb(color)
        return (r16 // 257, g16 // 257, b16 // 257)

    def _blend_colors(self, base_color, overlay_color, alpha):
        alpha = min(max(float(alpha), 0.0), 1.0)
        br, bg, bb = self._to_rgb255(base_color)
        or_, og, ob = self._to_rgb255(overlay_color)
        r = int(round((1.0 - alpha) * br + alpha * or_))
        g = int(round((1.0 - alpha) * bg + alpha * og))
        b = int(round((1.0 - alpha) * bb + alpha * ob))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _tree_cell_style(self, lai_value, cell_size, base_color):
        cell_size = max(1.0, float(cell_size))
        lai_value = max(0.0, float(lai_value))
        inset = max(0.25, 0.12 * cell_size)
        inset = min(inset, 0.35 * cell_size)
        transparency = float(np.exp(-self.tree_overlay_extinction_k * lai_value))
        alpha = 1.0 - transparency
        fill_color = self._blend_colors(base_color, self.tree_overlay_color, alpha)
        return inset, fill_color

    def set_tree_overlay_visible(self, visible):
        self.show_tree_overlay = visible
        if self._base_image is not None:
            self._rebuild_display_image()
            if self._image_id is not None:
                self.canvas.itemconfig(self._image_id, image=self._photo_image)

    def redraw_tree_overlay(self):
        """Rebuild the display image so the baked tree overlay is up to date."""
        if self._base_image is None:
            return
        self._rebuild_display_image()
        if self._image_id is not None:
            self.canvas.itemconfig(self._image_id, image=self._photo_image)

    # ------------------------------------------------------------------
    # Validation error overlay
    # ------------------------------------------------------------------

    def clear_error_overlay(self):
        # Error overlay is baked into the display image; no canvas items to delete.
        self.error_overlay_items = []

    def set_error_overlay_visible(self, visible):
        self.show_error_overlay = visible
        if self._base_image is not None:
            self._rebuild_display_image()
            if self._image_id is not None:
                self.canvas.itemconfig(self._image_id, image=self._photo_image)

    def update_error_overlay(self, invalid_mask):
        self._error_invalid_mask = invalid_mask
        if self.show_error_overlay and self._base_image is not None:
            self._rebuild_display_image()
            if self._image_id is not None:
                self.canvas.itemconfig(self._image_id, image=self._photo_image)

    def _redraw_error_overlay(self):
        """Rebuild the display image so the baked error overlay is up to date."""
        if self._base_image is None:
            return
        self._rebuild_display_image()
        if self._image_id is not None:
            self.canvas.itemconfig(self._image_id, image=self._photo_image)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self):
        """Delete all canvas objects and reset state."""
        self.canvas.delete("all")
        self.pixels = {}
        self._image_id = None
        self._base_image = None
        self._photo_image = None
        self._tk_photo = None
        self.domain_border_id = None
        self.hover_items = []
        self.clear_tree_overlay()
        self.clear_error_overlay()
