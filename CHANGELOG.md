# Changelog

All notable changes to the project. Versions follow semantic versioning.

## [3.0.1] - 2026-11-24

### Fixed
- An unchecked View, Framing or Resolution override group no longer leaves a
  blank row between headers while the group is expanded.

## [3.0.0] - 2026-11-24

### Added
- Blender 5.3 support. Blender 5.2.3 LTS remains supported.
- File Output nodes, image settings, depsgraph bounds, action slots, NLA and
  frame changes are verified in both versions.

### Changed
- `Fit Camera` and `Activate` replace longer button labels; the full operator
  names stay in tooltips.
- The target actions use one even four-column row, so all four labels fit at
  the default sidebar width.

### Tests
- Unit and smoke suites pass in Blender 5.2.3 LTS and 5.3.
- The reference scene with the new toggles off matches the 2.0.4 export pixel
  for pixel.

## [2.3.0] - 2026-11-24

### Added
- Multi-view export from top, bottom, front, back, right and left. All views of
  a collection share one canvas and one orthographic scale.
- A **View** override group with six per-collection toggles.
- **4 Directions** and **6 Directions** built-in presets.
- `{axis}` names and strict template validation. Unknown tokens, empty names
  and sanitized name collisions block the export before rendering.

### Changed
- The Overrides box is replaced by three full-width collapsible groups with the
  checkbox in the header. The View group is off by default.
- The legacy `camera_axis` control is hidden; the property remains for old
  presets and scripts.
- Target list, Always Include, Path Preview and File Output list heights follow
  their content.
- The path preview, report and row status include the view axis or view count.
- The 3x2 view grid replaces the single axis control in Camera & Framing.

## [2.2.0] - 2026-11-19

### Added
- Per-collection framing and resolution override properties on targets. A group
  toggle copies the current global values on first enable, keeps the stored
  values across a `.blend` round trip and invalidates the analysis cache when
  it changes.
- The Collections panel shows an Overrides box for the selected target with
  separate Framing and Resolution groups. A disabled group shows one muted
  `Using global` row; the box is disabled when no visible target is selected.

### Changed
- Preflight and the render loop use the resolved per-collection framing and
  resolution values. The export report lists collections with active overrides.

## [2.1.3] - 2026-11-11

### Fixed
- `Export` modes now filter both the visible target list and the actual
  export. `Active Collection` shows only the active Outliner collection even
  after switching from `All Collections`.
- Selecting a collection in the Outliner selects and activates its target row.
  Selecting a target row selects that collection in the Outliner.
- `All` and `None` affect only the collections visible in the current export
  mode. The full target registry and its enabled flags survive mode switches.

## [2.1.2] - 2026-11-11

### Changed
- The target list uses a fixed two-column table with `Collection` and
  `Canvas / status` headers. The list no longer inherits property split, so
  every row starts on the same left edge and the canvas value is not pushed
  out by long names.
- `Path Preview` is a compact, scrollable list with a `Collection` / `Path`
  header. A checkbox hides or shows it, and the full path list no longer
  stretches the panel.
- File Output node information is a compact scrollable list that replaces the
  separate "active File Output node(s)" and "Node output" hints.

## [2.1.1] - 2026-11-11

### Changed
- The Problems panel lists every message, collection and fix hint in full.
- Built-in presets use one dropdown menu; each preset explanation is shown only
  as a hover tooltip.
- `Batch Export Collections` and the secondary actions use compact rows.
- The Report tab is now `Log`, stays open, and contains only `Copy Log` and
  `Open Log`; the report body and the duplicate Output Folder button are gone.

### Removed
- The inline hint under `Also Save Main Render`; the same information is in the
  property tooltip.
- The inline note about objects in light collections; the `Always Keep Lights`
  tooltip already explains it.

## [2.1.0] - 2026-11-11

### Added
- `LICENSE` file with the GNU General Public License v3.0 or later.
- Documentation of the improvement plan and detailed implementation sequence.
- UX review of the File Output "Collection Goes To" modes and a revised stage
  4-5 plan for node output layouts, duplicate-token detection and path preview.
- Smoke test `tests/smoke_blender.py` and launchers for Windows/POSIX.
- Automatic target-list sync: the Collections panel now follows collection
  creation, deletion and filtering without pressing Refresh Targets.
- Readable target row status after Analyze: the final canvas such as `512x304`,
  plus view and frame counts when they apply.
- Tooltips with examples and defaults for every visible setting in Collections,
  Camera & Framing, Resolution and Output & Naming.

### Changed
- Static help labels were removed from the panels; state and error labels stay.
- Collections rows are taller (8 rows), Always Include shows 3 rows, and
  related controls use tighter separators.
- Preset descriptions are one compact line per preset; the full descriptions
  moved to the README.
- `Refresh Targets` is now non-destructive: it keeps enabled flags, row state
  and the active row instead of rebuilding the list.
- Blender 5.3 compatibility was verified with the smoke suite (Blender 5.2.3
  was not installed in the test environment).

### Removed
- World-unit status text such as `1.00 x 1.03` from the target list.
- Static hint labels for examples, filter size, the Problems panel, node
  layouts, the Analyze button and the obsolete multi-view note.
- The duplicate Analyze button and analysis-cache notice in Output & Naming.

### Tests
- Unit coverage for the target status formatter and UI text contract.
- Smoke coverage for automatic target sync, status clearing, tooltip text and
  operator descriptions.

## [2.0.4] - 2026-11-10

Small interface cleanup.

### Added
- Render `Filter Size` next to Transparent Film in both main-render and node
  output panels, with a hint for crisp pixel art.
- The filter size applies to the scene render settings, so it affects normal
  F12 renders as well as batch export.

### Changed
- `Skip Empty Collections`, `Use File Output Nodes` and `Only Connected Nodes`
  are drawn as left-aligned checkboxes.
- Removed the stale `Node layout writes EXR files` note. File Output nodes can
  write Image formats (PNG/JPEG/...) or Multilayer EXR, and the panel already
  shows the actual node format.

### Tests
- Smoke UI draw probe passes with the new property rows.

## [2.0.3] - 2026-11-10

Fix single-layer File Output naming.

### Fixed
- Single-layer image File Output nodes append the socket name to
  `node.file_name`. The add-on now sets only the collection prefix, so
  `Building_Conveyor_Horizontal` + socket `Normal` writes
  `Building_Conveyor_Horizontal_Normal.png` instead of
  `..._NormalNormal.png`.
- An empty socket no longer falls back to the node name or node file name.
  It writes only the collection name.
- Multiple sockets on one single-layer node are planned as separate files, one
  per socket.
- Multilayer EXR nodes keep the existing one-file-per-node behavior.

### Tests
- Unit coverage for single-layer prefix, empty socket, multiple sockets and
  subfolder layouts.
- Smoke coverage renders single-layer PNG nodes and checks the exact file names.

## [2.0.2] - 2026-11-10

Clarify the node-format preflight messages.

### Changed
- The node-format warning is only shown when the add-on Format selector really
  differs from the node output format. A PNG node with PNG selected now shows
  only the informational note.
- Messages use the visible `Also Save Main Render` label instead of the old
  `Also Write Main Render` wording.
- The mismatch message now states which format the File Output nodes write.

### Tests
- Added unit coverage for `format_family` and `node_output_format_id`.
- Smoke coverage checks that matching and mismatching node formats produce the
  expected preflight results.

## [2.0.1] - 2026-11-10

Fix pass for the 2.0.0 interface and File Output naming.

### Added
- Descriptions for the built-in presets.
- A Preset Description field; the description is saved in custom JSON presets
  and restored when a preset is loaded.

### Changed
- Automatic node layout now writes `<Collection>_<socket name>.exr`; Collection
  Folder writes `<Collection>/<socket name>.exr`. Node names and labels are
  ignored. Collection Only remains available as a legacy mode.
- Overwrite is the default policy and simply replaces existing files.
- The Always Include section is compact when its list is empty.

### Fixed
- The Problems panel no longer passes the invalid `WARNING` icon to Blender
  5.2; it uses `STATUS_WARNING`.
- File Output names no longer depend on `node.file_name`, `node.name` or
  `node.label` when sockets are available.

### Removed
- The Emergency Prefix Rename option and the post-render prefix fallback. Node
  path failures now stop the collection cleanly instead of renaming files after
  the render.

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
