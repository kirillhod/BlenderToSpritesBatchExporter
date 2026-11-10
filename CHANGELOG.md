# Changelog

All notable changes to the project. Versions follow semantic versioning.

## [Unreleased]

### Added
- Documentation of the improvement plan and detailed implementation sequence.
- UX review of the File Output "Collection Goes To" modes and a revised stage
  4-5 plan for node output layouts, duplicate-token detection and path preview.
- Smoke test `tests/smoke_blender.py` and launchers for Windows/POSIX.

## [1.3.1] - 2026-11-10

Predictable output paths, safer compositor handling and a complete render state
restore.

### Added
- Output path planning with sanitized components, Windows reserved-name
  handling and a path-length guard. Duplicate paths are detected before
  rendering.
- Overwrite policy: `Ask`, `Error`, `Skip`, `Overwrite` and `Add Suffix`.
  `Ask` shows a confirmation dialog with the affected files; background mode
  uses `Error` instead.
- Only File Output nodes connected to the compositor output are used by default
  (`nodes_connected_only`). Disconnected nodes no longer affect path planning.
- Render Border, Crop To Border, Stamp and File Extension are captured in the
  scene snapshot, disabled during export and restored afterwards.
- Post-export verification of render settings, collection excludes,
  `hide_render`, node paths and the scene camera; mismatches are reported as
  aggregated warnings.
- In Exclude isolation mode, collections containing lights are added to the
  keep list automatically. Scene-root objects outside the target and keep
  collections are hidden through the safe `hide_render` path.
- Format-aware color mode and color depth validation. Invalid combinations are
  corrected with a warning instead of being silently ignored.
- New settings: `overwrite_policy`, `nodes_connected_only`,
  `use_prefix_fallback`.

### Changed
- `prefix_new_files` is no longer used automatically when a File Output node
  cannot be updated. It remains available as an explicit emergency option.
- The Output panel exposes the overwrite policy, connected-node filter and the
  emergency rename option, and warns about invalid format/color combinations.

### Fixed
- Node path checks now depend on the actual mode: `Override Base Paths` and
  `Also Write Main Render` are only validated when File Output nodes are used.
- Relative `//` paths of every File Output node are validated with the node
  name in the error message.
- Linked File Output nodes are never modified and produce a warning.
- `Don't Modify` node mode stops multi-collection exports that would write all
  collections to the same paths.
- Prefix mode now updates and restores `node.file_name` in Blender 5.2, where
  the output file name is stored separately from `node.directory`.

## [1.3.0] - 2026-11-10

### Changed
- The add-on is split into a package of five modules: `__init__.py`, `properties.py`,
  `logic.py`, `operators.py`, `ui.py`. Operator `bl_idname` values and
  `scene.bts_settings` properties are unchanged.
- The single-file 1.2.1 version has been moved to `legacy/` as a reference and
  must not be installed alongside the package.
- Added `blender_manifest.toml`, `tools/build_zip.ps1` and a README with two
  installation methods.

### Added
- Unit tests for pure path and framing functions using the standard `unittest`;
  they run without Blender.
- Launchers `tests/run_unit_tests.ps1` and `tests/run_unit_tests.sh`.

## [1.2.1] - 2026-11-10

Hotfix based on the analysis of version 1.2.0.

### Fixed
- The temporary camera is now marked with the custom property `bts_owned_camera`.
  The add-on no longer reuses or deletes a user camera named
  `_BTS_OrthoCamera`; on a name conflict, Blender creates an object with a suffix.
- `remove_camera()` removes only cameras owned by the add-on and clears their
  data only when `users == 0`.
- The original scene camera is restored correctly, including when there was no
  camera before export or when `auto_cleanup_camera` is disabled.
- Writing `hide_render` no longer crashes on linked/override objects.
  Failed attempts are collected and reported in one aggregated warning; the
  remaining objects are processed and the state is restored.

## [1.2.0] - baseline

- Initial version before the improvement plan. Tagged `v1.2.0-baseline`.
