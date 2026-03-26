# Changelog

All notable changes to PALMPaint are documented here.

The versioning follows [Semantic Versioning](https://semver.org/):
- **dev branch** → `MAJOR.MINOR.PATCH-alpha.N` — work in progress, untested
- **main branch** → `MAJOR.MINOR.PATCH-beta.N` — merged and manually verified
- **Release** → `MAJOR.MINOR.PATCH` — stable, fully tested

---
## [0.4.1-alpha] — dev branch (unreleased)

### Added
- Autosave: project is periodically saved to rotating autosave slots; slot count and interval are configurable via the autosave options dialog
- Keyboard shortcuts for Save (`Ctrl+S`) and Save As (`Ctrl+Shift+S`)

### Changed
- Improved single-tree canvas representation: overlay cells now use a clearly inset rectangle with Beer-Lambert stipple shading so they are visually distinct from the grid lines at all zoom levels

### Fixed
- Several bugs in the Tree Generator (crown geometry edge cases and generator preset handling)

---

## [0.4.0-alpha] — dev branch (unreleased)

### Added
- Single-tree tool: place resolved 3-D trees directly on the canvas (left-click = place, right-click = remove)
- `tree_generator_core.py`: LAD field generation using crown shapes and extinction model similar to palm_csd
- `tree_generator_dialog.py`: interactive Tree Generator dialog with live matplotlib preview and preset save/load
- `tree_species.py`: built-in catalog of ~90 tree species with default geometry (crown shape, height, LAI, BAD/LAD ratio, trunk diameter) from PALM documentation
- Species selector and shape combobox in the single-tree tool bar
- Support for 6 crown shapes (Spherical, Cylindrical, Conical, Inv. Conical, Paraboloid, Inv. Paraboloid)
- BAD (Basal Area Density) output toggle ("Write BAD" checkbox)
- `GridModel.tree_instances`: list of editable per-tree objects with id, position, and geometry
- `GridModel.resolved_vegetation`: 3D LAD/BAD/tree_id/zlad arrays rebuilt from `tree_instances`
- `GridModel._loaded_rv`: immutable base layer preserving vegetation loaded from existing NetCDF files
- `GridModel.remove_loaded_lad_at()`: cell-level removal of externally-loaded vegetation without a tree instance
- NetCDF read/write for `lad`, `bad`, `tree_id`, and `zlad` variables in `load_sd` and `create_sd`

### Bugfix
- The report now displays the correct building heights

## [0.3.0-alpha] — dev branch (unreleased)

### Added
- Hover preview system on canvas (`show_hover_preview`, `clear_hover_preview`)
- "Load Existing Project" button in the welcome screen (file dialog for `.nc` files)
- Improved canvas scroll mechanism using `bbox`-relative `xview_moveto` / `yview_moveto`

### Changed
- Replaced `start_x`, `start_y`, `end_x`, `end_y`, `current_item` with unified `active_cell`
- `welcome_screen` result tuple now prefixed with action type: `("new", nx, ny, res)` or `("load", path)`
- Vegetation definitions moved out of `palmpaint.py` into `surface_config`
- Version bumped to `0.3.0-alpha`

---

## [0.2.1] — dev branch (not yet merged to main)

### Added
- Height view (heightmap editing mode)
- Soil view with configurable surface types
- Configurable surfaces via external surface config

---

## [0.2.0] — 2025 (main)

### Changed
- Major refactor of `GridModel` and `TkBackend`
- Various bugfixes

---

## [0.1.x] — earlier development

### Added
- Undo and redo functionality
- Bucket fill tool
- Report window
- Coordinates display in meters
- New project function with start screen
- Load and save options (NetCDF)
- `base/` package structure (refactored from flat layout)
- `requirements.txt` and `environment.yml`

### Fixed
- NetCDF load errors
- Repainting issues
- Build height spinner edge cases (`0/0` origin)

---

## [0.1.0] — initial release

- First working version of PALMPaint
- Basic painting tools for PALM static driver files
- PEP8 code style cleanup
