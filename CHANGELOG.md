# Changelog

All notable changes to PALMPaint are documented here.

The versioning follows [Semantic Versioning](https://semver.org/):
- **dev branch** → `MAJOR.MINOR.PATCH-alpha.N` — work in progress, untested
- **main branch** → `MAJOR.MINOR.PATCH-beta.N` — merged and manually verified
- **Release** → `MAJOR.MINOR.PATCH` — stable, fully tested

---
## [0.4.3-alpha] — dev branch (unreleased)

### Added
- **Eraser tool**: new toolbar entry that resets all surface and building layers of the painted cells to fill values
- **Validation module** (`base/validation.py`): standalone surface-layer consistency checker with 8 rules + coordinate range check (DRV0001); returns a `violations` list and a per-cell `invalid_mask` boolean array
  - Rule 1: vegetation / pavement / water are mutually exclusive
  - Rule 2: building cells must not carry a surface type
  - Rule 3: all non-building cells need a surface type once any is in use
  - Rule 4: `water_pars` only on water cells
  - Rules 5a/5b: soil_type required on vegetation/pavement cells; fill required on building/water cells
  - Rule 6: LAD only where a surface type is set
  - Rule 7: `building_type` requires `building_id`
  - Rule 8: `building_id` must be a positive signed 32-bit integer
  - DRV0001: `origin_lon` ∈ [−180, 180] and `origin_lat` ∈ [−90, 90]
- **Validation error overlay** in the canvas: cells involved in at least one rule violation are highlighted with a red inset border; toggleable via *Extras → Show Error Overlay*
- **Validate before Save** option in Extras menu (default: on); pre-save validation check with "Save anyway?" dialog
- **Clean Static Driver** action: automatic repair of common inconsistencies (invalid zt, LAD/BAD inside buildings, orphaned soil/surface/water_pars assignments, missing soil types, auto-assigned building IDs); runs validation afterward and shows a detailed summary
- **PALM Preflight tools** (`base/palm_preflight.py`) exposed via Extras menu (preview + apply):
  - *Filter Sweep*: PALM-style 1-cell hole filling and narrow-cavity removal; preview highlights affected cells in the overlay before applying
  - *Split Building IDs*: detects disconnected building footprints sharing the same `building_id` and reassigns unique IDs
  - *Align Building Terrain*: aligns terrain height within each building group to PALM's `oro_max` logic
- `GridModel.validate()`, `GridModel.clean_static_driver()`, and all preflight methods added as thin wrappers on the model
- `add_tree()` now returns a placement summary `{tree_id, clipped_voxels, placed_voxels}`; trees placed entirely within building volume are automatically discarded; a warning dialog is shown when a crown is partially or fully clipped

### Changed
- `GridModel.__init__` derives `vegetation_type` and `soil_type` defaults from `surface_config` instead of hardcoding `1`; `surface_config.py` gained a top-level `"default_type": 3` for vegetation
- `_apply_brush()`, `eraser tool path`, and fill-all action now use the shared `_reset_pixel_payload()` helper
- Paint tools (vegetation / pavement / water / fill-all) skip cells that already carry building or tree data
- `_rebuild_resolved_vegetation()` refactored to use `_iter_tree_voxels()` and `_build_tree_generator_params()` helpers and a building-volume mask; preserves source metadata via `_resolved_vegetation_source_metadata()`
- Domain border drawn as a persistent canvas item (`_draw_domain_border()`), raised above all overlays; `clear()` resets its ID

### Fixed
- `get_color()` returned `None` for fully-erased (all-fill) cells, leaving their canvas rectangle transparent; `return "white"` moved to a function-level fallback
- `has_building` and `has_bld_id` in `validation.py` used `INT_FILL = -127` as threshold for `building_id`, masking values between −9999 and −128 as non-fill; corrected to use `BUILDING_ID_FILL = -9999`
- `draw_grid()` rendered all cells with `fill="brown"` on first load instead of reading `model.get_color()`

---

## [0.4.2-alpha] — dev branch (unreleased)

### Added
- Separate vertical grid spacing `dz` (independent from horizontal `res`): configurable in the new-project dialog, stored in and loaded from the NetCDF file, exposed throughout the application
- `buildings_3d` export: optional 3D voxel building layer in the NetCDF output (toggle via *Extras → Export buildings_3d*); buildings below `dz/2` are replaced with asphalt and a warning is shown
- "Discretize Project to dz" menu action: re-snaps all terrain and building heights of the whole project to the current `dz` raster in one step
- Lower-left origin mode for the coordinate display: checking the checkbox in the *Change Origin* dialog switches the meter readout from local grid coordinates (0/0) to absolute projected coordinates offset by `origin_x` / `origin_y`
- `x` / `y` coordinate variables and CRS grid-mapping attributes (`grid_mapping`) are now written to all spatial variables in the saved NetCDF file
- Building height spinbox step and tree height spinbox step now use `dz` instead of `res`

### Changed
- `GridModel` now stores `dz` as a first-class attribute; `set_pixel()` applies `dz`-based quantization for terrain and building heights by default (can be disabled with `quantize=False`)
- `quantize_building_height()` and `quantize_terrain_height()` extracted as public static methods on `GridModel`
- `infer_vertical_step()` replaces the old `infer_dz_from_zlad()` internals with improved leading-half-step detection
- `Save()` signature extended: accepts `dz`, `georef`, and `export_buildings_3d`; returns a summary dict with deleted/replaced building counts
- `Load()` now returns `(grid, nx, ny, res, dz, origin, resolved_vegetation, georef)` and reads `dz` and the full `GeoReference` from the file
- `BUILDING_ID_FILL` changed from `-127` to `-9999` to avoid ambiguity with `INT_FILL`
- Grid-spacing Labelframe in the new-project dialog renamed from "Grid Width" to "Grid Spacing" and extended with a `dz` entry field
- Sidebar label now shows both horizontal `res` and vertical `dz`
- Tree generator receives `(res, res, dz)` grid config instead of a single resolution value
- `zlad` generation for tree instances now re-uses the loaded zlad array as a base and extends it only if needed

### Fixed
- Several bugs in the Tree Generator (crown geometry edge cases and generator preset handling)

---

## [0.4.1-alpha] — dev branch (unreleased)

### Added
- Autosave: project is periodically saved to rotating autosave slots; slot count and interval are configurable via the autosave options dialog
- Keyboard shortcuts for Save (`Ctrl+S`) and Save As (`Ctrl+Shift+S`)
- Dedicated georeferencing module with UTM-based lat/lon <-> projected-meter conversion, CRS metadata handling, and PALM-style `crs` / `lat` / `lon` / `E_UTM` / `N_UTM` output

### Changed
- Improved single-tree canvas representation: overlay cells now use a clearly inset rectangle with Beer-Lambert stipple shading so they are visually distinct from the grid lines at all zoom levels
- Origin editing now uses the project CRS and keeps geographic and projected coordinates in sync

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
