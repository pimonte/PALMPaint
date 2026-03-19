# Changelog

All notable changes to PALMPaint are documented here.

The versioning follows [Semantic Versioning](https://semver.org/):
- **dev branch** → `MAJOR.MINOR.PATCH-alpha.N` — work in progress, untested
- **main branch** → `MAJOR.MINOR.PATCH-beta.N` — merged and manually verified
- **Release** → `MAJOR.MINOR.PATCH` — stable, fully tested

---

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
