# Changelog

All notable changes to the project. Versions follow semantic versioning.

## [Unreleased]

### Added
- Documentation of the improvement plan and detailed implementation sequence.
- UX review of the File Output "Collection Goes To" modes and a revised stage
  4-5 plan for node output layouts, duplicate-token detection and path preview.
- Smoke test `tests/smoke_blender.py` and launchers for Windows/POSIX.

## [2.0.0] - 2026-11-10

New interface, collection selection, path preview, presets and reports.

### Added
- Per-collection target list with checkboxes, search, All/None/Active and
  Make Active actions, plus size/status text from analysis.
- Separate Always Include list, migrated once from the legacy
  `keep_collections` string.
- `AUTO` and `FILENAME` node layouts. New scenes default to Automatic; saved
  1.4.x scenes keep their previous layout through a one-time marker.
- Output path preview for main-render and File Output plans, conflict count and
  the resolved node layout.
- Problem panel grouped by ERROR, WARNING and INFO with code, collection and
  fix hint.
- Main panel status and progress readout, Analyze, Cancel and export actions.
- Built-in presets, JSON preset save/load and unknown-field warnings.
- Report panel with the written file list, Copy Report, Open Log and Open
  Output Folder.
- Confirmation dialogs for Remove Camera and Unhide Everything.

### Changed
- The user-facing node control is renamed to Node Output Layout. Tooltips
  describe the resulting paths.
- Format and color controls are hidden for node-only output, which states that
  File Output writes multilayer EXR.
- The panel reads the analysis cache instead of scanning nodes and bounds in
  `draw()`.

### Fixed
- Empty target or Always Include lists no longer fall back to stale legacy
  strings after migration.
- The export report includes every planned main-render and node file.

## [1.4.0] - 2026-11-10

Preflight, `BatchJob`, cancellation and a complete node output plan.

### Added
- `Problem` and `ProblemCollector` with deduplication and ERROR/WARNING/INFO
  ordering.
- Preflight analysis: targets, bounds, output paths, node layouts, collisions,
  existing files, linked data, format and render-state checks, all without
  rendering.
- Cached analysis and a new `bts.analyze` operator with an Analyze button in the
  panel.
- `BatchJob` with a synchronous `run()` path, a step-based modal path and scene
  restoration through a single `finish()`.
- `bts.cancel_export` and cancellation between collections; the current render
  is allowed to finish.
- `NodeOutputPlan` for every collection and active File Output node, including
  `AUTO` and `FILENAME` internal layouts, duplicate-token detection and
  existing-file checks for node outputs.
- Preflight overwrite confirmation includes both main-render and node paths.

### Changed
- `logic.py` is now a compatibility facade over `core/common.py`,
  `core/output.py`, `core/scene.py`, `core/framing.py` and `core/job.py`.
- `BatchExport` uses preflight and `BatchJob`; the operator body only handles
  context, confirmation and reporting.
- In Blender 5.2, `file_output_items` are treated as layer names. Prefix and
  Subfolder layouts no longer rename layers.
- Prefix mode skips a collection token that is already present in the File
  Output file name.
- Node-only mode reports that File Output writes multilayer EXR and does not
  imply the add-on PNG/JPEG format.

### Fixed
- Existing files produced only by File Output nodes are now checked during
  preflight and follow the overwrite policy, including the default
  `{blend_name}` file name.
- Analysis cache is cleared on file load and invalidated by setting, collection
  and node changes.
- Scene state verification warnings are collected in `JobResult` instead of
  being scattered through the render loop.

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
