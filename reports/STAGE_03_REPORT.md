# Report: stage 3 - predictable paths, node checks, state and isolation (1.3.1)

Date: 2026-11-10
Branch: `feature/improvements-v2`
Add-on version: `1.3.1`
Package: `blender_to_sprites_batch_exporter/`

## Status

Stage 3 is implemented and verified. The extended smoke test was executed in
**Blender 5.2.3 LTS** with `--factory-startup`: the base scenario, the strict
camera scenario and the compositor scenario all pass.

Static verification: `py_compile` for all modules and tests, package import with
`bpy` stubs, and **33 unit tests pass**. The stage closes tasks F1.1-F1.4,
F2.1-F2.4, F3.1-F3.2 and F4.1-F4.4 from `IMPLEMENTATION_SEQUENCE.md`.

## F1.1. Output path planning

`logic.py` now has a dedicated path planning section:

- `OutputPlan` dataclass: collection, sanitized name, base path without
  extension, path with extension, absolute path, existence flag, skip reason,
  collision source and notes.
- `sanitize_path_component()` sanitizes the whole component, not only the file
  stem. It also prefixes Windows reserved names (`CON`, `NUL`, `COM1`...`LPT9`)
  and trims trailing dots and spaces.
- `format_extension()` and `build_output_path()` compute the extension from the
  selected format and never add it twice.
- `MAX_OUTPUT_PATH` protects against over-long Windows paths by shortening only
  the file component.
- `plan_output_paths()` builds a plan for every collection before rendering and
  detects duplicate absolute paths.

## F1.2. Overwrite policy

Added `overwrite_policy` to `BTS_Settings` with `Ask`, `Error`, `Skip`,
`Overwrite` and `Add Suffix`; the default is `Ask`.

`apply_overwrite_policy()` checks existing files and duplicates and returns
plans, blocking errors, confirmation conflicts and explanatory notes:

- `Error` stops the export before any file is touched.
- `Skip` excludes collections whose files already exist.
- `Overwrite` keeps the planned name.
- `Add Suffix` selects the first free `_2`, `_3`... name.
- `Ask` collects conflicts for a confirmation dialog.
- In background mode (`bpy.app.background`) `Ask` becomes `Error`.

`BTS_OT_BatchExport.invoke()` shows a confirmation dialog with up to eight
affected files. `execute()` refuses to overwrite when the dialog was not
confirmed, so a scripted call cannot silently overwrite files.

## F1.3. Name collisions

- `plan_output_paths()` records which earlier collection owns the same path.
- `plan_node_name_collisions()` and `resolve_node_safe_names()` repeat the check
  for node-based output, where only the sanitized collection name is available.
- Collisions follow the selected policy: error, skip or a unique suffix.
- Unit test `test_collision_suffix_and_skip` covers `A/B` and `A\B`.
- The smoke test adds a separate scene with `A/B` and `A\B` and expects
  `A_B.png` plus `A_B_2.png`.

## F1.4. Integration into rendering

- `BTS_OT_BatchExport` now uses `plan.base_path` for `render.filepath` instead
  of `safe_join(output_dir, safe_name)`.
- Node modes use the resolved sanitized names from the same plan.
- `Don't Modify` mode stops an export with more than one collection, because
  every collection would write to the same node paths.
- `prefix_new_files` is no longer automatic. It runs only when
  `use_prefix_fallback` is enabled (emergency option for external pipelines
  that depend on post-rename).

## F2.1. Conditional node checks

`validate_node_settings()` checks the setup according to the actual mode:

- `Override Base Paths` and `Also Write Main Render` are validated only when
  File Output nodes are used.
- A scene with nodes but `use_compositor_nodes = False` no longer requires a
  base directory.
- If nodes are enabled but none are connected, the operator reports a warning
  and falls back to the main render path.

## F2.2. Relative node paths

- Every File Output node directory is checked with `is_relative_unsaved()`, not
  only the global Output Directory.
- The error message includes the node name.
- The check is skipped when `Override Base Paths` replaces the node directory
  with an absolute path.

## F2.3. Only connected nodes

- `collect_file_outputs(scene, reachable_only=True)` traverses input links from
  `CompositorNodeComposite` / `CompositorNodeViewer` / group outputs and also
  keeps File Output nodes that receive data through an input link. File Output
  nodes are side branches, so the input-link check is what distinguishes a
  working node from a disconnected one.
- Nested node groups are traversed through reachable or connected group nodes.
- `nodes_connected_only` defaults to `True`; the Output panel exposes it.
- Disconnected nodes are ignored for path planning and for restore verification.
- If a tree has no output node at all, all nodes are used as a conservative
  fallback.

## F2.4. Linked nodes

- `node_is_linked()` checks `node.id_data.library`.
- Linked nodes produce a WARNING and are excluded from snapshots and writes.
- Restore only touches nodes that were actually modified.

## F3.1. Extended snapshot

`RENDER_STATE_ATTRS` and `snapshot_render_state()` now cover:

- resolution and percentage, filepath;
- image format, color mode and color depth;
- `film_transparent` and `use_compositing`;
- `use_border` and `use_crop_to_border`;
- `use_stamp` and every `use_stamp_*` flag;
- `use_file_extension`;
- the scene camera name.

`prepare_render_state()` sets safe values for the duration of the export:
border, crop and stamp are disabled, file extension is enabled, resolution
percentage is 100. `restore_render_state()` restores every captured value even
after an exception.

## F3.2. Restore verification

- `verify_render_state()`, `verify_excludes()`, `verify_hide_render()` and
  `verify_nodes()` compare the scene with the snapshots after restoration.
- `verify_scene_state()` also checks the scene camera, catches each check
  independently and never raises from the operator's `finally` block.
- Mismatches are reported as one aggregated WARNING with a short preview.
- The smoke test checks border, crop, stamp and stamp-date restoration.

## F4.1. Keep Lights in Exclude mode

- `collections_with_lights()` finds collections that directly contain
  `LIGHT`/`LIGHT_PROBE` objects.
- `extend_keep_with_lights()` adds them to the keep list only in Exclude mode
  and only when `keep_lights` is enabled.
- A WARNING lists added collections that also contain non-light objects,
  because those objects may appear in the frame.
- The Source panel now shows `keep_lights` in both isolation modes and explains
  the automatic behavior.

## F4.2. Scene-root objects

- `hide_root_objects()` hides objects linked directly to `scene.collection`
  during Exclude-mode exports, except cameras, kept objects and lights.
- The same safe `hide_render` path is used, and the original state is restored
  and verified.
- The smoke test places a cube in the Scene Collection and checks that its
  `hide_render` value is restored.

## F4.3. Format validation

- `IMAGE_FORMAT_RULES` describes valid color modes and depths per format.
- `normalize_image_settings()` corrects invalid combinations with a WARNING
  instead of swallowing `TypeError`:
  - PNG + 32 bit becomes 16 bit;
  - JPEG + RGBA becomes RGB;
  - unsupported depths for other formats are corrected as well.
- `apply_image_settings()` reports failures to set a value instead of ignoring
  them.
- The Output panel runs the same validation while drawing and shows alert
  boxes for invalid combinations.
- The smoke test still sets a valid PNG/RGBA/8-bit combination.

## F4.4. Preview and Undo

`bts.preview_camera` already declared `bl_options = {'REGISTER', 'UNDO'}`, and
the temporary camera is created as a normal object, so Blender's undo system can
restore the camera and resolution. No new operator state outside Blender's undo
system was introduced. A manual Ctrl+Z check remains in the Blender checklist.

## New and changed settings

| Setting | Default | Purpose |
|---|---|---|
| `overwrite_policy` | `Ask` | Behavior when output files exist |
| `nodes_connected_only` | `True` | Use only reachable File Output nodes |
| `use_prefix_fallback` | `False` | Emergency post-render rename |

All existing `bl_idname` values and existing `scene.bts_settings` properties are
preserved. Old scenes open with the new defaults.

## Tests

Unit tests added in `tests/test_logic_unit.py`:

- `sanitize_path_component`: separators, Windows reserved names, trailing dots,
  Unicode.
- `build_output_path`: extension handling and reserved names.
- `plan_output_paths`: `A/B` vs `A\B` collision.
- `apply_overwrite_policy`: Error, Skip, Overwrite, Ask, Suffix, background Ask,
  collision suffix, collision skip, collision error.
- `resolve_node_safe_names` and `plan_node_name_collisions`.
- `normalize_image_settings`: valid PNG, PNG 32-bit correction, JPEG RGBA.
- `collect_file_outputs(reachable_only=True)` with fake connected and
  disconnected File Output nodes.
- `apply_node_paths` in Prefix mode: directory, file name and item name update
  and restore.

Result: **33 tests, all pass** with the standard `unittest` runner.

Smoke test in `tests/smoke_blender.py`:

- base export: files, camera, resolution, format, excludes, `hide_render`;
- strict camera case with a user camera named `_BTS_OrthoCamera`;
- temporary camera kept when `auto_cleanup_camera` is disabled;
- overwrite policies Error, Skip, Suffix and Overwrite against existing files;
- collision scene with `A/B` and `A\B`;
- Render Border, Crop To Border, Stamp and Stamp Date restoration;
- scene-root object `hide_render` restoration;
- compositor scenario: a connected File Output writes `Body/Unsaved.exr`,
  directory, file name and item names are restored, and a disconnected File
  Output is not modified and writes no file;
- Prefix mode on the same node writes `Body_Unsaved.exr` and restores the node
  afterwards.

The compositor test confirmed that File Output nodes are side branches rather
than ancestors of Composite. The reachability check was corrected to keep File
Output nodes that receive data through an input link while still excluding
completely disconnected nodes. It also showed that Blender 5.2 stores the output
file name in `node.file_name`, separately from `node.directory`; Prefix mode now
updates and restores that property.

Execution results on Blender 5.2.3 LTS:

| Command | Result |
|---|---|
| `./tests/run_tests.ps1` | SMOKE PASS |
| `./tests/run_tests.ps1 -StrictCamera` | SMOKE PASS |


## Verification summary

| Check | Result |
|---|---|
| `py_compile` package and tests | OK |
| Package import with stubs | OK |
| Unit tests | 33/33 OK |
| Added unit-test count | 11 new tests |
| Blender 5.2.3 smoke test (`run_tests.ps1`) | SMOKE PASS |
| Blender 5.2.3 strict camera (`-StrictCamera`) | SMOKE PASS |
| Compositor File Output, Subfolder and Prefix | PASS |
| Extension manifest validation | OK |
| Install from zip into an isolated profile | OK |
| Manual check of linked File Output nodes | pending in Blender |
| Manual Ctrl+Z preview check | pending in Blender |

The extension manifest was validated with Blender's
`--command extension validate` and the zip was installed with
`--command extension install-file` into an isolated user profile. During this
check the manifest `tagline` was shortened to the 64-character limit.

## Known limitations

- Existing-file checks cover paths written by the main render. Files produced
  only by File Output nodes are protected by name collision checks but are not
  inspected on disk before rendering.
- If a compositor tree has no output node at all, File Output nodes that receive
  data through an input link are still detected.
- The linked File Output node scenario needs a manual check with a linked
  library; the code path is guarded but cannot be exercised locally.
- `logic.py` is now about 1500 lines, which exceeds the J10 split criterion
  (700-800 lines). Per `IMPLEMENTATION_SEQUENCE.md`, the `core/*` split belongs
  to stage 4 after `BatchJob`; it should be performed there instead of adding
  more code to the module.

## Next step

Stage 4: `Problem` model, preflight analysis cache, `BatchJob`, cancellation,
`Ask` through preflight, recovery/error verification and version 1.4.0.
The linked-node and Ctrl+Z manual checks remain for the stage 4 checklist.
