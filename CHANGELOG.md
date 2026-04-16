# Changelog

All notable changes to PALMPaint are documented here.

The versioning follows [Semantic Versioning](https://semver.org/):
- **dev branch** → `MAJOR.MINOR.PATCH-alpha.N` — work in progress, untested
- **main branch** → `MAJOR.MINOR.PATCH-beta.N` — merged and manually verified
- **Release** → `MAJOR.MINOR.PATCH` — stable, fully tested

---
## [0.5.4-alpha] — dev branch (unreleased)

### Added
- **`base/building_config.py`**: building type catalogue (6 types with per-type hex colors and category grouping) plus full PALM USM parameter spec (12 arrays: `building_albedo_type`, `building_emissivity`, `building_fraction`, `building_general_pars`, `building_heat_capacity`, `building_heat_conductivity`, `building_indoor_pars`, `building_lai`, `building_roughness_length`, `building_roughness_length_qh`, `building_thickness`, `building_transmissivity`)
- **Per-type building colors**: `get_color()` and the vectorized `_color_array_rgb()` path now render each building type in its configured color instead of uniform black
- **`GridModel.building_pars`**: dict of 12 USM parameter arrays allocated at construction; included in `export_state()` / `from_state()`; cleared by `clear_building_parameters()` / `clear_building_parameters_where()` when building data is erased
- **`GridModel.padded(n_north, n_south, n_west, n_east)`**: returns a new model with fill-value border cells added on each side; tree instance positions adjusted
- **`GridModel.cropped(col_start, row_start, new_nx, new_ny)`**: returns a new model sliced to a sub-domain; tree instances outside the window are dropped
- **Clipboard operations** (`palmpaint.py`): copy, cut, paste with `_copy_selection()` / `_commit_paste()`; paste mode supports **R** / **Shift-R** for ±15°/1° CW rotation with live hover preview; **Escape** cancels
- **`_flood_select()`**: BFS flood-fill selection of all contiguous cells matching the seed cell's surface kind and type (landcover, heightmap, and soil views)
- **`_lasso_select()`**: rectangle-lasso that finds the dominant surface key inside the drag box and flood-fills its full contiguous extent across the whole grid
- **Ellipse draw mode** (`_get_ellipse_cells()`): filled axis-aligned ellipse inscribed in the drag bounding box; `force_circle` flag; integrated into `_get_shape_cells()` as a third draw mode alongside rectangle and line
- **`base/sd_plot.py`** (`SDPlotDialog`): embedded matplotlib analysis dialog with 12 plot types (XY landcover/pavement/vegetation/LAD/terrain/soil/building type and height, cross-section, height histogram, LAD profile, plan area fractions); optional — disabled gracefully without matplotlib
- **`base/threedview.py`**: PyVista 3D view launched in a daemon thread; PALM→PyVista coordinate convention; face tags in mesh cell data; optional — disabled gracefully without pyvista
- **`startup_path` CLI argument** in `palmpaint.py`: optional positional argument; when supplied, skips the welcome screen and loads the given `.nc` file directly (e.g. `python3 palmpaint.py my_project.nc`)
- `_write_4d_variable()` in `create_sd.py`: streaming 4D NetCDF write (leading-dim / z / y blocks) for multi-dimensional building parameter arrays; only written when non-fill values are present (`_has_non_fill_values()`)
- `get_4d_data()` in `load_sd.py`: 4D variable loader with shape validation and optional `storage_factory`

### Changed
- `base/framework.py`: replaced `eval(command_callback)` with `getattr(self, attr_name)` — removes arbitrary code execution risk from menu configuration
- `base/surface_config.py`: vegetation and pavement display colors converted from Tk named colors (`"green"`, `"lawngreen"`, `"tan"`, etc.) to explicit hex codes for cross-platform consistency
- `base/palm_preflight.py`: removed `DEFAULT_BUILDING_TYPE` constant; `apply_topography_filters()` now accepts `default_building_type` parameter; `preview_filter_sweep()` resolves the value from `building_config`
- `clean_model()` in `validation.py`: clears building parameters at cells outside building footprints; count reported as `building_parameters_cleared_outside_buildings`
- `base/create_sd.py`: NetCDF export now writes `vegetation_type`, `pavement_type`, and `water_type` as a set whenever any of the three surface layers is present, leaving unset layers at fill values

---
## [0.5.3-alpha] — dev branch (unreleased)

### Added
- **Select tool**: new toolbar entry for multi-cell selection
  - Click to select a single cell; Shift-click adds to selection; Ctrl-click toggles
  - *Select Same Surface* button: expands selection to all cells sharing the same surface kind
  - *Select By* dropdown + button: extends selection to all cells matching a chosen criterion (zt, building type / height, water type / temperature, vegetation / pavement / soil type)
  - Top-bar edit fields (zt, surface-specific attributes) with *Apply to Selection*: batch-edits all selected cells at once
  - Sidebar shows a selection summary (count, surface kind, common/mixed attribute values) while the tool is active
- **Layer visibility and locking** (View menu, per layer: Vegetation, Pavement, Water, Buildings):
  - *Show &lt;Layer&gt;*: hides the layer from the canvas without deleting data
  - *Lock &lt;Layer&gt;*: prevents any paint or selection edit from modifying cells on that layer
- **Background overlays** (View menu): *Add Heightmap to Background* and *Add Soilmap to Background* blend a grayscale height or soil tint behind the landcover colours
- **Draw modes** (Brush / Rectangle / Line toggle appended to the top bar for Vegetation, Pavement, Water, Building, and Eraser tools):
  - *Rectangle*: click-drag defines the bounding box; pixels are flushed on mouse release with a live preview during drag
  - *Line*: Bresenham line between press and release points with live preview
  - New helpers `_get_rectangle_cells()`, `_get_line_cells()`, `_get_shape_cells()`, `_paint_shape_cells()`
- **`EditorState`** dataclass (`base/editor_state.py`): centralises all non-persistent UI state (active view, per-layer visibility / locks, view-specific settings, selection); constructed once at startup and passed to the backend
- **`GridModel.export_state()` / `GridModel.from_state()`**: lightweight snapshot/restore for undo/redo; replaces `copy.deepcopy()` of the entire model
- **`GridModel.get_height_grayscale_color()` / `_color_array_height_gray()` / `_color_array_soil()`**: per-cell and vectorised colour helpers used by the new background overlays
- **`PilCanvasBackend.set_landcover_background_config()`**: configures height/soil tinting parameters without rebuilding the full image
- **`PilCanvasBackend.show_selection()` / `clear_selection_overlay()`**: renders a selection highlight overlay on selected cells

### Changed
- `palmpaint.py`: `save_state()` calls `model.export_state()` instead of `copy.deepcopy()`; `undo()` / `redo()` restore via `GridModel.from_state()`
- `palmpaint.py`: `canvas_zoom_in()`, `canvas_zoom_out()`, and the mousewheel handler now read `self.res` back from `backend.effective_res` after each zoom call instead of multiplying in-place
- Backend is now constructed with `editor_state=self.editor_state`; `set_view_mode()` and `set_height_view_config()` calls replaced by `_apply_editor_state_to_backend()`
- `new_project()` and `load_project_netcdf_from_path()` call `_reset_editor_state()`, `_initialize_landcover_background_range()`, `_apply_editor_state_to_backend()`, and `_sync_editor_state_to_ui()` to keep state consistent after project changes
- All paint paths (brush, fill-all, shape, selection apply) call `_is_paint_locked_at()` and skip locked-layer cells
- Right-click clear and right-click drag handlers early-exit when the select tool is active

### Fixed
- `clear_cell_info()` now shows the selection summary instead of the placeholder text while the select tool has an active selection
- `update_hover_preview()` correctly shows a single-cell preview for the select tool instead of the brush outline

---
## [0.5.2-alpha] — dev branch (unreleased)

### Added
- **`GridModel.allocate_storage()`**: allocates arrays as `np.memmap` when the requested size exceeds 64 MB (`TEMP_BACKED_ARRAY_THRESHOLD_BYTES`); otherwise returns a normal `np.ndarray`; backed by a per-model `tempfile.TemporaryDirectory` (`_temp_store`)
- **`GridModel.materialize_storage()`**: copies an existing array into regular or memmap-backed storage, respecting the size threshold
- **`GridModel._building_top_z()`**: lazy per-column top-building-height cache (replaces the full `(nz, ny, nx)` boolean volume produced by `_building_volume_mask_from_z()`); invalidated by `_invalidate_building_cache()` whenever building data is modified via `set_pixel()`
- **`_write_2d_variable()` / `_write_3d_variable()` / `_building_3d_iter()`** in `create_sd.py`: block-streaming helpers that write NetCDF variables row-by-row (2D) or z-layer-by-row-block (3D) to avoid materializing large temporary arrays
- **`SaveModel()`** in `create_sd.py`: new primary save entry point that accepts a `GridModel` directly; reads 2D arrays straight from model attributes instead of iterating a per-cell dict; `buildings_3d` and `water_pars` are written in blocks without ever allocating the full volume in RAM; old `Save()` retained as a backward-compatible wrapper
- **`LoadModel()`** in `load_sd.py`: new primary load entry point that returns a fully-populated `GridModel` instead of a legacy per-cell dict; `get_3d_data()` extended with an optional `storage_factory` callback so large 3D variables (buildings_3d, lad, bad, tree_id) are streamed slice-by-slice directly into memmap-backed arrays; old `Load()` retained as a backward-compatible wrapper

### Changed
- `palmpaint.py` now calls `SaveModel()` / `LoadModel()` directly; the intermediate `from_legacy_dict()` reconstruction step on load is removed
- `_resolved_vegetation_source_metadata()` no longer deep-copies numpy arrays into metadata (avoids doubling memory for large 3D fields)
- `_rebuild_resolved_vegetation()` allocates `lad`, `bad`, and `tree_id_arr` via `allocate_storage()` so very large tree volumes are memory-mapped automatically

### Fixed
- `_building_volume_mask_from_z()` allocated an `(nz, ny, nx)` boolean array on every `_rebuild_resolved_vegetation()` call; replaced with the cached `_building_top_z()` scalar comparison, eliminating the peak memory spike for tall domains

---
## [0.5.1-alpha] — dev branch (unreleased)

### Added
- **PIL rendering backend** (`base/pilbackend.py`): new `PilCanvasBackend` class that replaces the per-cell Tkinter `Rectangle` approach with a single `tk.PhotoImage` rebuilt from a numpy array via Pillow; grids of 500×500 and beyond render in well under a second instead of several seconds
  - Drop-in replacement for `TkCanvasBackend` (identical public API)
  - Tree and error overlays baked directly into the PIL image via `ImageDraw` (C-level, no individual canvas items)
  - Grid lines rendered only when cells are ≥ 16 display pixels wide
  - Display image side capped at 4096 px (`_MAX_SIDE`) to keep memory usage bounded (~48 MB at 4096×4096 RGB)
  - Selected automatically on startup; falls back to the Tk backend if Pillow is not available, printing the exact `ImportError` message so the cause is immediately visible
- **`--backend` CLI argument** in `palmpaint.py`: `--backend pil` (default) or `--backend tk` forces the rendering backend at startup
- **`_run_with_busy_dialog()`** in `palmpaint.py`: runs long-running callbacks in a worker thread while showing a modal dialog with an indeterminate `ttk.Progressbar`; exceptions from the worker are re-raised in the main thread
- **`GridModel.get_color_array_rgb()`**: vectorised equivalent of calling `get_color()` for every cell; returns an `(ny, nx, 3)` uint8 numpy array; supports `landcover`, `heightmap`, and `soil` view modes
- **`GridModel._hex_to_rgb()`** static method: converts Tk/CSS colour strings (`#RRGGBB`, `#RGB`, named colours) to `(R, G, B)` tuples; backed by the new module-level `_CSS_COLORS` lookup table covering the full CSS3 / X11 set including Tk-specific numbered variants (e.g. `"green4"`)

### Changed
- `base/palm_preflight.py` rewritten with fully vectorised numpy algorithms:
  - `_build_topography_classification()` builds a 3-D `(nz, ny, nx)` voxel classification array (terrain / building / air) in one pass instead of cell-by-cell BFS
  - `_fill_holes()` and `_count_solid_neighbors()` implement the 1-cell hole-fill sweep with pure numpy broadcasting; replaces the previous Python-loop BFS
  - Removed `find_building_components()`, `analyze_building_groups()`, `split_disconnected_building_ids()`, `_four_neighbors()`, `_normalize_zt_array()`, `_normalize_building_heights()`, `_next_unused_building_id()` (functionality merged into the vectorised pipeline)

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
- **PALM Preflight tool** (`base/palm_preflight.py`) exposed via Extras menu (preview + apply):
  - *Filter Sweep*: PALM-style 1-cell hole filling and narrow-cavity removal; preview highlights affected cells in the overlay before applying
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
