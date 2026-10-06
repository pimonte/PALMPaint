"""
Editor/session state for PALMPaint.

Keeps UI-facing, non-persistent settings such as active view, per-layer
visibility, paint locks, and view-specific display options.
"""

from dataclasses import dataclass, field


LAYER_KEYS = ("vegetation", "pavement", "water", "building", "irrigation", "shf", "ssws")


@dataclass
class EditorState:
    """Mutable editor state that is intentionally separate from project data."""

    active_view: str = "landcover"
    layer_visibility: dict = field(
        default_factory=lambda: {layer: True for layer in LAYER_KEYS}
    )
    layer_locks: dict = field(
        default_factory=lambda: {layer: False for layer in LAYER_KEYS}
    )
    view_settings: dict = field(
        default_factory=lambda: {
            "landcover": {
                "show_height_background": False,
                "show_soil_background": False,
                "height_bg_min": 0.0,
                "height_bg_max": 10.0,
            },
            "soil": {},
            "heightmap": {
                "z_min": 0.0,
                "levels": 10,
            },
        }
    )
    selection_cells: set = field(default_factory=set)
    selection_anchor: tuple = None
    selection_mode: str = "replace"

    def is_layer_visible(self, layer_name):
        return bool(self.layer_visibility.get(layer_name, True))

    def set_layer_visible(self, layer_name, visible):
        self.layer_visibility[layer_name] = bool(visible)

    def is_layer_locked(self, layer_name):
        return bool(self.layer_locks.get(layer_name, False))

    def set_layer_locked(self, layer_name, locked):
        self.layer_locks[layer_name] = bool(locked)

    def get_view_settings(self, view_name):
        return self.view_settings.setdefault(view_name, {})

    def visible_layers(self):
        """Return visible layers as a set for rendering helpers."""
        return {
            layer_name
            for layer_name in LAYER_KEYS
            if self.is_layer_visible(layer_name)
        }

    def clear_selection(self):
        self.selection_cells.clear()
        self.selection_anchor = None
        self.selection_mode = "replace"

    def set_selection(self, cells, anchor=None, mode="replace"):
        self.selection_cells = {tuple(cell) for cell in cells}
        if anchor is None and self.selection_cells:
            anchor = next(iter(self.selection_cells))
        self.selection_anchor = None if anchor is None else tuple(anchor)
        self.selection_mode = str(mode)

    def add_selection_cell(self, row, col):
        self.selection_cells.add((int(row), int(col)))
        self.selection_anchor = (int(row), int(col))
        self.selection_mode = "add"

    def toggle_selection_cell(self, row, col):
        cell = (int(row), int(col))
        if cell in self.selection_cells:
            self.selection_cells.remove(cell)
        else:
            self.selection_cells.add(cell)
        self.selection_anchor = cell
        self.selection_mode = "toggle"
