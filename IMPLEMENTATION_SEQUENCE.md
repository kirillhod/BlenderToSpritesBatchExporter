# Detailed implementation sequence

Date: 2026-11-09
Base: `IMPROVEMENT_PLAN.md` (revision 2)
Current addon version: 1.2.0, one file `blender_to_sprites_batch_exporter.py` (1137 lines)

The document describes the specific work order: tasks, dependencies, affected files and functions, checks and readiness criteria. Estimates are indicative, for one developer.

---

## 1. Results of re-checking the plan

The plan is checked for contradictions and dependencies. Corrected:

1. **Overwrite Policy.** The plan was “Overwrite by default” and the UI layout was “Ask”. Accepted: by default `Ask`, for headless - `Error`; silent overwrite is no longer the default behavior.
2. **Versioning.** Clarified: 1.3.0 - intermediate transition to the package without changing behavior, 2.0.0 - new UI, output policies and sprite capabilities.
3. **Smoke test.** Clarified: Workbench is for a quick basic test, EEVEE is a separate script for the File Output branch, since Workbench does not check the composer.
4. **Roadmap** Stage 3 is no longer called "rest of P0/P1": cancellation and everything that requires `BatchJob` has been explicitly moved to stage 4.
5. **Preflight cameras.** The wording “no camera” has been replaced with “cannot create or bind a temporary camera.”
6. **Single canvas.** Clarified: new option is enabled in new presets; old scenes remain in the same mode until explicitly turned on.
7. **`Ask` preflight dependency.** Resolved: Basic path check and rewrite confirmation appear in step 3; a full-fledged preflight with an aggregated report - at stage 4. Before preflight appears, confirmation shows only a list of conflicting files.

### Open decisions that need to be made before the appropriate stage

| Solution | When | Preferred Option |
|---------|-------|-----------|
| Storing selected collections | stage 5 | `CollectionProperty` with collection name + existence check; `PointerProperty` on Collection - only if tested on linked/undo |
| Mapping instances to collections | stage 7 | First a prototype on `depsgraph.object_instances`; for controversial cases - the instancer collection; otherwise fallback to the current bypass |
| Analysis result cache | stage 4 | Modular cache by `scene.as_pointer()` + invalidation token; do not store heavy data in `.blend` |
| `Keep Lights` | stage 3 | v1: automatically save entire collections with light + warning; v2: hide non-light objects inside them |
| Cancel | stage 4 | Cancel between tasks; current `bpy.ops.render.render` is being played out |
| CI | stage 0/2 | Local smoke run is required; CI with Blender - optional |

---

## 2. Execution rules

- One commit = one logically completed task from this document.
- Before commit: `python -m py_compile` of all modules + smoke test in Blender.
- After each stage: installation on a clean Blender (factory startup), checking `bl_idname` and `scene.bts_settings`.
- Do not change behavior during refactoring. New functions - only after the appropriate stage.
- Maintain backward compatibility: old scenes should be opened, old settings should be read.
- All new checks and errors - through `Problem`/`ProblemCollector`, without scattered `self.report` in a cycle.
- For each task, update `CHANGELOG.md` and, where necessary, README.

---

## 3. Dependency map and critical path

```
S0 (baseline)
 └─ H1/H2 (hotfix)
     └─ R1–R9 (5 files)
         ├─ F1–F5 (paths, nodes, state, isolation)
         ├─ J1–J9 (preflight, BatchJob, cancellation)
         │   └─ U1–U10 (UI)
         │       └─ A1–A7 (shared canvas, multi-view, templates)
         │           └─ B1–B7 (bounds, animation, metadata)
         └─ tests and documentation run in parallel
```

Critical path: **S0 → H1/H2 → R1–R6 → F1–F3 → J1–J7 → U1–U5 → A1–A5 → B1–B4**.

You can conduct in parallel:

- F2/F3 (nodes and state) and J1/J2 (problem model) after R1–R6;
- U1/U2 (properties and UIList) after R1–R6;
- unit tests - immediately after the appearance of pure functions;
- documentation - as stages are completed.

---

## 4. Stage 0. Preparing and committing baseline

**Result:** known current behavior, reproducible smoke test, safe branch.
**Estimate:** 0.5–1 day.

### S0.1. Branch and baseline
- **Depends:** no.
- **Actions:**
1. Create branch `feature/improvements-v2`.
2. Place the `v1.2.0-baseline` tag on the current commit.
3. Record the start of work in `CHANGELOG.md`.
- **Check:** `git status` is clean, the tag exists.
- **Done:** any experiment can be rolled back to baseline.

### S0.2. Smoke-framework of the current addon
- **Files:** `tests/smoke_blender.py`, `tests/run_tests.ps1`, `tests/run_tests.sh`.
- **Actions:**
1. The script creates a scene: 2 collections with meshes, 1 empty, light in a separate collection, camera.
2. Adds a File Output node in a separate script.
3. Launches the current `bts.batch_export` with a temporary folder and low resolution.
4. Checks: files are created, names/sizes are expected, empty collection is skipped.
5. Checks recovery: camera, resolution, format, exclude, hide_render, node paths.
6. Returns exit code 0/1, prints a report.
- **Check:** the script runs on the current version; add `--factory-startup` if necessary.
- **Done:** the smoke test can be launched with one command.

### S0.3. Baseline report
- **Files:** `tests/BASELINE.md`.
- **Actions:** write down the current results: how many files, what names, what is restored and what is not; Please note known issues separately.
- **Check:** the report matches the actual behavior.
- **Done:** there is a standard for comparison after refactoring.

### S0.4. Test scenes
- **Files:** `tests/scenes/*.blend` or scripts for their creation.
- **Actions:** prepare scenes: simple, with nested collections, with a linked object, with instances, with File Output nodes, with Render Border.
- **Check:** each scene opens in Blender 5.2.
- **Done:** There are reproducible cases for the following steps.

---

## 5. Stage 1. Hotfix P0 in the current monolith

**Result:** the addon no longer deletes someone else's camera and does not crash on linked objects.
**Estimate:** 0.5–1 day.

### H1.1. Ownership of temporary camera
- **Depends on:** S0.
- **Files:** `blender_to_sprites_batch_exporter.py`; functions `ensure_camera` (current lines 757–771), `remove_camera` (774–784), `BTS_OT_PreviewCamera`, `BTS_OT_Cleanup`, `BTS_OT_BatchExport`.
- **Actions:**
1. Add the constant `BTS_OWNED_PROP = "bts_owned_camera"`.
2. In `ensure_camera`, search for an existing camera by custom property, and not just by name.
3. If an object with the name `_BTS_OrthoCamera` already exists, but does not belong to the addon, create a new object - Blender itself will add the suffix `.001`.
4. Mark the created camera `cam_obj[BTS_OWNED_PROP] = True`.
5. Do not reuse the user camera or change its data.
- **Check:** scene with custom camera `_BTS_OrthoCamera`; export/preview does not change its transformation and data.
- **Done:** camera ownership is uniquely determined by the property.

### H1.2. Safe removal and recovery of camera
- **Depends on:** H1.1.
- **Actions:**
1. `remove_camera` deletes only objects with `BTS_OWNED_PROP`.
2. Delete `bpy.data.cameras` only if `users == 0`.
3. Use new logic in `BTS_OT_Cleanup` and `BTS_OT_BatchExport`; `scene.camera` restore only if the original camera exists.
4. Add handling of the situation when the user deleted the temporary camera manually.
- **Check:** repeated cleanup is safe; the original scene camera is restored; temporary is deleted.
- **Done:** there is no path where the addon deletes someone else's camera.

### H1.3. Regression tests of camera
- **Depends:** H1.1–H1.2.
- **Actions:**
1. Smoke case: the user camera with the name of the addon remains untouched.
2. Smoke case: a temporary camera is created with a suffix and deleted after export.
3. Smoke case: `auto_cleanup_camera=False` leaves a temporary chamber, the original `scene.camera` is restored.
- **Check:** all three cases are green.
- **Done:** camera behavior recorded by tests.

### H2.1. Safe installation `hide_render`
- **Depends:** S0.
- **Files:** `snapshot_hide_render`, `restore_hide_render`, `isolate_collection_by_hide` (current 598–624).
- **Actions:**
1. Enter helper `set_hide_render_safe(ob, value, problems)` with try/except.
2. Use it in isolation and restoration.
3. Return/accumulate a list of objects that could not be changed.
4. In the operator’s report, display one aggregated warning, and not per object.
- **Check:** a linked object or an object with a write ban does not cause a crash; the remaining objects are processed.
- **Done:** An error on one object does not cancel the entire export.

### H2.2. Linked/override object test
- **Depends:** H2.1.
- **Actions:**
1. Create a scene with a linked collection/object.
2. Start export in `HIDE` mode.
3. Make sure that the statement has completed, the state has been restored, and there is WARNING.
- **Check:** no exception; the stage is not broken.
- **Ready:** the case is covered with smoke test.

### H3. Tag hotfix
- **Actions:** raise the version to 1.2.1, update CHANGELOG, put the `v1.2.1` tag.
- **Check:** installation on a clean Blender, smoke test.
- **Done:** hotfix can be released separately.

---

## 6. Stage 2. Minimum division into 5 files

**Result:** logic, settings, operators and UI are separated; the behavior has not changed.
**Estimate:** 1.5–2.5 days.

### R1.1. Package frame
- **Depends on:** H3.
- **Actions:**
1. Create the folder `blender_to_sprites_batch_exporter/`.
2. Create `__init__.py`, `properties.py`, `logic.py`, `operators.py`, `ui.py`.
3. Transfer `bl_info` to `__init__.py`.
4. Set up relative imports.
5. Leave the old single `.py` in the repository as a reference, but do not install it simultaneously with the package; describe the transition in the README.
- **Check:** `python -m py_compile` all files; Blender sees the package.
- **Ready:** frame is installed.

### R1.2. `properties.py`
- **Depends on:** R1.1.
- **Actions:**
1. Migrate `BTS_Settings` (current 631–671) without changing property names and default values.
2. Import `bpy.props` and `PropertyGroup` here only.
3. Leave the format/type constants in `logic.py` until the splitting step `core`.
- **Check:** `scene.bts_settings` is available, old values are being read.
- **Done:** data schema isolated.

### R1.3. `logic.py`
- **Depends:** R1.2.
- **Actions:**
1. Transfer all non-UI functions: paths, bounds, camera, isolation, composer, state, render loop.
2. Do not change algorithms and function names.
3. Save the constants `ADDON_CAM_NAME`, `GEOMETRY_TYPES`, `MAX_INSTANCE_DEPTH`, `DEPTH_CAPABLE`, `EXT_BY_FORMAT`.
4. Make sure that `logic.py` does not import `ui` and `operators`.
5. Delete the dead code (`node_is_multilayer`, unused second element `get_compositor_tree`) or use it for its intended purpose.
- **Check:** smoke test gives the same files and state as baseline.
- **Done:** all the logic is in one module, the UI does not contain it.

### R1.4. `operators.py`
- **Depends:** R1.3.
- **Actions:**
1. Transfer `BTS_OT_BatchExport`, `BTS_OT_PreviewCamera`, `BTS_OT_Cleanup`, `BTS_OT_RestoreCollections`, `BTS_OT_OpenOutputFolder`.
2. Save all `bl_idname` and `bl_options`.
3. Import logic from `.logic`.
- **Check:** all operators are available through F3 search and work.
- **Done:** statements are separated from logic.

### R1.5. `ui.py`
- **Depends:** R1.2, R1.4.
- **Actions:**
1. Transfer panels `BTS_PT_MainPanel`, `BTS_PT_Source`, `BTS_PT_Camera`, `BTS_PT_Resolution`, `BTS_PT_Output`.
2. Import only `properties` and operators.
3. Do not call heavy calculations in `draw()`; Keep the current behavior for now.
- **Check:** panels are displayed, buttons work.
- **Done:** UI isolated.

### R1.6. Registration
- **Depends on:** R1.1–R1.5.
- **Actions:**
1. In `__init__.py`, collect tuples of classes from `properties`, `operators`, `ui`.
2. Order: first `PropertyGroup`, then operators, then panels.
3. `bpy.types.Scene.bts_settings = PointerProperty(type=BTS_Settings)`.
4. `unregister` in reverse order; delete `bts_settings` before classes.
- **Check:** enabling/disabling the addon without errors; restart works.
- **Done:** registration is stable.

### R1.7. Installation and regression
- **Depends on:** R1.6.
- **Actions:**
1. Install the package as legacy-addon (folder in `scripts/addons` or zip).
2. Run a smoke test.
3. Compare with `tests/BASELINE.md`.
4. Check `bl_idname`, `scene.bts_settings`, default values.
- **Check:** behavior is identical to baseline; there are no differences.
- **Done:** refactoring complete.

### R1.8. Unit tests of pure functions
- **Depends:** R1.3.
- **Actions:**
1. Add `sanitize_filename`, `safe_join`, `split_base`, `make_relative_slot`, `ensure_slash` to tests.
2. Add tests `compute_frame`: padding, square, min/max, multiplicity.
3. Add axis tests.
- **Test:** `pytest` passes without Blender for pure functions.
- **Done:** basic mathematics covered with tests.

### R1.9. Blender Extension and assembly
- **Depends on:** R1.7.
- **Actions:**
1. Add `blender_manifest.toml` with version, `blender_version_min = "5.2.0"`, license and tags.
2. Add zip build script without `tests/`.
3. Check the installation both as legacy-addon (folder) and as Extension (zip).
4. Update README: two installation methods, differences.
- **Check:** both installations work on pure Blender 5.2.
- **Done:** The package can be distributed.

### R1.10. Tag 1.3.0
- **Actions:** version 1.3.0, CHANGELOG, tag.
- **Check:** clean installation, smoke.
- **Done:** batch version without behavior change.

---

## 7. Stage 3. Other P0/P1 without `BatchJob`

**Result:** predictable paths, safe nodes, correct render state, working light isolation.
**Estimate:** 2-3 days.

### F1.1. Output path planning
- **Depends on:** R1.7.
- **Files:** `logic.py`; new block `naming/paths planning`.
- **Actions:**
1. Enter `build_output_path(output_dir, collection_name, format, template=None)`.
2. Sanitize each component separately, not just the bottom line.
3. Determine extension by format; don't add it twice.
4. Process reserved names Windows (`CON`, `NUL`, `COM1`...) and path length.
5. Return `OutputPlan` with a list of paths and the reason for skipping.
- **Check:** unit tests for collisions `a/b` and `a\b`, empty name, Unicode, reserved names.
- **Done:** path known before rendering.

### F1.2. Rewrite policy
- **Depends on:** F1.1.
- **Actions:**
1. Add enum `Ask`, `Error`, `Skip`, `Overwrite`, `Suffix`.
2. Implement checking of existing files and applying the policy.
3. `Suffix` adds `_2`, `_3`... without name race.
4. `Ask` shows confirmation before launch: number and list of files.
5. For a headless call, use `Error`.
- **Test:** tests for each policy; restarting does not overwrite at `Error`.
- **Done:** no silent overwrite.

### F1.3. Name collisions
- **Depends:** F1.1.
- **Actions:**
1. Before rendering, build the `final path -> collection` map.
2. If there is a match, an error or suffix according to the policy.
3. Separately check the case when two collections after sanitization give the same name.
- **Check:** the smoke scene with the `A/B` and `A\B` collections does not overwrite files.
- **Done:** collisions are detected before rendering.

### F1.4. Embedding in the main render
- **Depends on:** F1.1–F1.3.
- **Actions:**
1. Replace `safe_join(output_dir, safe_name)` with the scheduler result.
2. For node mode, build a plan based on `node.directory` and slot names.
3. In `NONE` mode, detect identical paths for different collections and generate an error.
4. Disable `prefix_new_files` in the standard scenario; leave it only as an explicit emergency option with a precise list of expected paths.
- **Check:** smoke: normal render and node mode; NONE mode warns.
- **Done:** all output paths are monitored.

### F2.1. Checking nodes according to the condition
- **Depends:** R1.7.
- **Actions:**
1. Check `node_override_base` only with `using_nodes`.
2. Check `write_main_output` only with `write_still`.
3. Remove false errors when nodes are disabled.
- **Check:** a scene with nodes and node usage disabled does not require Base Dir.
- **Done:** checks correspond to actual mode.

### F2.2. Relative paths of nodes
- **Depends:** F1.1.
- **Actions:**
1. After allowing the base node directories, check `//` in the unsaved `.blend`.
2. Check every `node.directory`, and not just the Output Directory.
3. Give an error with the node name.
- **Check:** unsaved file + relative node path → clear error.
- **Done:** no “to nowhere” rendering.

### F2.3. Only connected nodes
- **Depends:** R1.7.
- **Actions:**
1. Traverse the graph from the Composite output using input connections.
2. Add the “all nodes” option for backward compatibility.
3. By default, use only reachable File Output nodes.
- **Check:** an unconnected node does not create files; connected - creates.
- **Done:** unnecessary entries have been excluded.

### F2.4. Linked nodes
- **Depends:** R1.7.
- **Actions:**
1. Check `node.id_data.library`.
2. Skip linked nodes with WARNING.
3. Do not try to restore what has not been changed.
- **Check:** the linked node group scene does not crash, files are written by accessible nodes.
- **Done:** linked data is not modified.

### F3.1. Extended snapshot
- **Depends:** R1.7.
- **Files:** `snapshot_*`/`restore_*` to `logic.py`.
- **Actions:**
1. Add `use_border`, `use_crop_to_border`, `use_stamp`, `use_stamp_*`, `use_file_extension` to the snapshot.
2. During rendering, set safe values: border/crop/stamp disabled, extension enabled.
3. Restore all values even if there is an error.
- **Check:** the scene with Render Border/Stamp renders the full frame without captions; After export, the settings are restored.
- **Done:** rendering does not depend on random scene settings.

### F3.2. Recovery verification
- **Depends on:** F3.1.
- **Actions:**
1. After restore, compare the key values: camera, resolution, format, exclude, hide_render, node paths.
2. If there is a discrepancy - WARNING and recording in the log.
3. Do not throw an exception from `finally` if the recovery partially failed.
- **Check:** artificially broken recovery gives a warning, not a crash.
- **Ready:** status is verifiable.

### F4.1. `Keep Lights` v1
- **Depends:** R1.7.
- **Actions:**
1. Find collections containing `LIGHT`/`LIGHT_PROBE`.
2. In Exclude mode, automatically add them to the keep list.
3. Display a warning: extraneous objects from this collection may be rendered along with the light.
4. Optionally hide non-light objects via `hide_render` (v2, if v1 is not enough).
- **Check:** light from a separate collection is present; the scene is restored.
- **Done:** lighting does not disappear in Exclude mode.

### F4.2. Objects at the scene root
- **Depends:** H2.1.
- **Actions:**
1. Find objects that are not included in the target/keep collections.
2. In Exclude mode, hide them through the secure `hide_render`.
3. Restore after rendering.
- **Check:** an object in the Scene Collection is not included in the frame.
- **Done:** isolation works for root objects too.

### F4.3. Validation of formats
- **Depends on:** R1.7.
- **Actions:**
1. Enter a table of valid `color_mode`/`color_depth` by format.
2. Hide/disable invalid values in the UI.
3. Validate before rendering; do not swallow `TypeError` silently.
4. Warn if the selected engine does not support transparency/format.
- **Check:** PNG + 32 bit and JPEG + RGBA give a clear warning/correction.
- **Done:** Color settings are predictable.

### F4.4. Preview and UNDO
- **Depends:** R1.7.
- **Actions:**
1. Add `{'UNDO'}` to the preview operator.
2. Optionally restore resolution after preview.
3. Do not change `scene.camera` without the possibility of a rollback.
- **Check:** Ctrl+Z returns camera/resolution.
- **Done:** the preview leaves no unexpected changes.

### F5. Tests and tag 1.3.1
- **Actions:**
1. Smoke: collisions, policies, border/stamp, keep lights, root objects, linked nodes.
2. Unit: paths, reserved names, policies.
3. Version 1.3.1, CHANGELOG, tag.
- **Ready:** all P0/P1 of stage 3 are closed.

---

## 8. Stage 4. Preflight, `BatchJob`, cancel

**Result:** all checks before rendering, thin operator, cancel and guaranteed recovery.
**Estimate:** 2-4 days.

### J1. Problem Model
- **Depends on:** Stage 3.
- **Files:** `logic.py` (later `core/job.py`).
- **Actions:**
1. Enter `Problem(severity, code, message, collection, fix_hint)`.
2. Enter `ProblemCollector`: add, deduplicate, sort ERROR→WARNING→INFO.
3. Replace the scattered `self.report` in the cycle with a collection of problems.
- **Verification:** unit tests of deduplication and sorting.
- **Done:** uniform error format.

### J2. Analysis model and job
- **Depends on:** J1.
- **Actions:**
1. Enter `Bounds`, `FrameSpec`, `Target`, `JobConfig`, `JobResult`.
2. `Target` stores the collection, bounds, frame, output paths, skip reason.
3. `JobConfig` - axes, frames, policy, format, isolation mode.
4. `JobResult` — rendered/skipped/failed, time, problems, list of files.
- **Check:** types are used in preflight and render; mypy is optional, but the imports are clean.
- **Done:** data is not transmitted in long tuples.

### J3. Preflight
- **Depends on:** J1, J2, F1–F4.
- **Actions:**
1. Collect targets without changing the scene.
2. Check: empty collections, bounds, camera, paths, collisions, existing files, nodes, linked data, format/color, border/stamp, isolation.
3. Do not render or change user settings (except for safe reading/evaluation).
4. If for measurement you need to temporarily change the visibility/exclude, use `SceneState` and restore until the result is returned.
5. Return `AnalysisResult` with problems and plan.
- **Check:** smoke scenes with each error give the expected code and message; there are no false positives.
- **Done:** user sees problems before launch.

### J4. Analysis cache and "Analysis" operator
- **Depends:** J3.
- **Actions:**
1. Cache for `scene.as_pointer()` + token (settings/scene/node tree/`target_items`/`always_include_items`).
2. Invalidation when changing key settings; reset when downloading a file.
3. `BTS_OT_Analyze` fills the cache and displays a short report.
4. UI reads the cache, not counting the bounds in `draw()`.
- **Check:** calling again without changes does not recalculate; after changing the settings it recalculates.
- **Done:** “Analysis” works and does not slow down the panel.

### J5. `BatchJob`
- **Depends on:** J2, J3.
- **Actions:**
1. Transfer the body `execute` (current 863–1072) to `BatchJob.run()`.
2. `BTS_OT_BatchExport.execute` leaves: context, call `preflight`, error handling, `run`, report.
3. Inside job: `try/finally` with restoration; one source of state.
4. Log timings: analysis, isolation, rendering, recording.
- **Check:** smoke test is identical to baseline; operator <50 lines.
- **Done:** The rendering logic is separated from the UI operator.

### J6. Cancel
- **Depends:** J5.
- **Actions:**
1. Modal operator or timer: check the cancel flag before each collection/axis/frame.
2. The current `bpy.ops.render.render` is being played out.
3. If canceled - `finally`-restore, `JobResult.cancelled=True`, clear report.
4. “Cancel” button in the UI.
- **Check:** canceling after the first collection leaves the scene in its original state; the files of the first collection remain.
- **Done:** long export can be aborted.

### J7. `Ask` via preflight
- **Depends:** J3, J4.
- **Actions:**
1. If the policy `Ask` and there are existing files, show a dialog with the quantity and list.
2. Confirmation starts job; failure - `CANCELLED`.
3. For headless - `Error`.
- **Check:** restart asks for confirmation; refusing doesn't change anything.
- **Done:** secure overwrite.

### J8. Recovery and error verification
- **Depends:** J5.
- **Actions:**
1. After job, check the status; write WARNING if there is a discrepancy.
2. An error in rendering one collection does not interrupt the others (or interrupts it by setting).
3. Assemble `failed` and show it as a result.
- **Check:** artificial rendering error; the remaining collections are being processed and the state has been restored.
- **Ready:** fault tolerance confirmed.

### J9. Tests and tag 1.4.0
- **Actions:** smoke on preflight, cancel, ask, restore; unit on `ProblemCollector`; version 1.4.0.
- **Done:** preflight/job are stable.

### J10. Dividing `logic.py` into `core/*` (by criterion)
- **When:** `logic.py` > ~700–800 rows or independent reasons for the change appeared.
- **Actions:** remove `common`, `scene`, `framing`, `output`, `job`; keep the imported façade `logic.py` for the transition period.
- **Check:** smoke; importing from old places is not broken.
- **Done:** modularity without premature fragmentation.

---

## 9. Stage 5. New interface

**Result:** driven UI with collection selection, analysis, problems, progress and presets.
**Estimate:** 4-6 days.

### U1. Properties for the list of collections and tasks
- **Depends on:** stage 4.
- **Files:** `properties.py`.
- **Actions:**
1. `BTS_TargetItem`: collection name, `enabled`, size/status cache; `CollectionProperty` `target_items` to `BTS_Settings`.
2. `BTS_CollectionRef`: collection name for "Always Include"; separate `CollectionProperty` `always_include_items`; migration of old string `keep_collections`.
3. Rebuild `target_items` from View Layer when the scene changes, saving `enabled` by collection name; Do not store `PointerProperty` on a Collection without checking linked/undo.
4. Properties for axes (later), policy, name template, canvas size.
5. Do not mix the list of goals and the “Always Include” list: these are different sets.
6. `export_source` to be used only as a starting filter for filling `target_items`; after filling, the source of truth is `target_items`.
- **Check:** old scenes are opened, the list is filled, the migration is one-time.
- **Done:** data for UIList is available.

### U2. UIList collections
- **Depends:** U1.
- **Files:** `ui.py` (or `ui/collection_list.py` when growing).
- **Actions:**
1. Checkbox, name, calculated size/status.
2. Search/filter, “All”, “Nothing”, “Active”.
3. Double click/button - make active in Outliner.
4. After “Analysis”, show the size and warnings.
5. Export always uses `enabled` from `target_items` and not `export_source` directly.
- **Check:** selection is saved; export uses exactly the selected collections.
- **Done:** explicit goal management.

### U3. Main panel
- **Depends on:** U2.
- **Actions:**
1. Heading: number of targets, angles, frames.
2. Buttons: “Analysis”, “Batch Export”, “Cancel”.
3. Progress: current task, ETA, rendered/skipped/failed.
4. Warning block with a link to details.
- **Check:** the panel is not blocking Blender; the status is updated.
- **Done:** the main scenario is clear from the first screen.

### U4. Problem panel
- **Depends on:** J4, U3.
- **Actions:**
1. Group ERROR/WARNING/INFO.
2. Show code, collection, hint.
3. Buttons “Go to settings”, “Ignore for launch”.
4. Do not duplicate messages in `self.report`.
- **Check:** each problem from preflight is displayed once.
- **Done:** user understands what to fix.

### U5. Output and name panel
- **Depends:** F1, U1.
- **Actions:**
1. Name template field + 2–3 examples.
2. List of conflicts before launch.
3. Rewrite policy (`Ask` by default).
4. Format/color/depth with dependent fields.
5. “Open folder” button.
- **Check:** preview matches actual names; invalid values are not available.
- **Done:** output is configured predictably.

### U6. Presets
- **Depends on:** U3–U5.
- **Actions:**
1. Built-in presets: Pixel Art Top, Platformer Front, Multi-view 4/6.
2. Saving/loading JSON to `bpy.utils.user_resource('CONFIG')`.
3. Preset format version and error handling.
- **Check:** saving/loading on a clean Blender; unknown fields are ignored with a warning.
- **Done:** settings are portable.

### U7. Report and log
- **Depends:** J5, U3.
- **Actions:**
1. Summary: files, time, skipped/failed, paths.
2. Buttons “Open folder”, “Open log”, “Copy report”.
3. Log with timings and debug mode.
- **Check:** after export, the report matches the files.
- **Done:** we check the result without the console.

### U8. Cache and performance UI
- **Depends on:** J4, U2.
- **Actions:**
1. Do not scan nodes and bounds in `draw()`.
2. Use analysis cache; invalidate by button/change.
3. Test redrawing on a scene with 100+ collections.
- **Check:** the panel opens without noticeable delay.
- **Done:** UI is not a bottleneck.

### U9. Signatures, warnings, localization
- **Depends:** U3–U5.
- **Actions:**
1. Rename ambiguous parameters.
2. Add tooltips and examples.
3. Confirmations for “Unhide Everything”, deleting camera, overwriting.
4. Optional RU/EN via `bpy.app.translations`.
- **Check:** the user understands the parameters without reading the code.
- **Done:** The UI is clear.

### U10. Manual checklist UI
- **Actions:** installation, enable/disable, migration, presets, analysis, export, cancel, error, restart.
- **Done:** checklist passed; tag 2.0.0.

---

## 10. Stage 6. Sprite capabilities

**Result:** single canvas, pixel snap, multi-view, name templates.
**Estimate:** 4-7 days.

### A1. `FrameSpec` and a single canvas
- **Depends:** stage 5.
- **Actions:**
1. Expand `FrameSpec`: `canvas_w`, `canvas_h`, `fit_mode`, `anchor`.
2. Calculate the total canvas using the union bounds of all targets.
3. Modes `Contain`, `Cover`, `Stretch`.
4. 3x3 alignment.
5. Fixed size from preset.
- **Check:** unit tests for contain/cover/align; smoke: all files are the same size.
- **Done:** Sprites are consistent in size.

### A2. Single `ortho_scale` and `pixels_per_unit`
- **Depends:** A1.
- **Actions:**
1. Use a common ppu and ortho_scale for all purposes.
2. Recalculate the camera for the canvas, and not for each collection.
3. Save legacy per-collection mode.
- **Check:** the scale of objects is the same between frames.
- **Done:** no zoom jumps.

### A3. Pixel snap
- **Depends:** A2.
- **Actions:**
1. Round the center of the camera, taking into account the parity of the resolution.
2. Add integer offset test.
3. Check for animation of two frames.
- **Check:** no subpixel drift.
- **Done:** stable mesh.

### A4. Multi-view
- **Depends on:** A1.
- **Actions:**
1. Select axes (Top/Bottom/Front/Back/Right/Left).
2. Generating tasks `(collection, axis)`.
3. Union bounds along the axes.
4. Suffix `{axis}` in the name.
5. Presets 4/6 directions.
- **Check:** one run creates a set of files for all selected axes; the sizes are the same.
- **Done:** multi-view works.

### A5. Name templates
- **Depends:** F1, A4.
- **Actions:**
1. Tokens `{collection}`, `{axis}`, `{frame}`, `{index}`, `{scene}`, `{date}`.
2. Validation of unknown tokens.
3. Preview and check collisions before rendering.
4. Sanitization after substitution.
- **Verification:** unit tests for all tokens and errors.
- **Done:** names are customizable without risk.

### A6. Sprite presets
- **Depends:** A1–A5.
- **Actions:** Pixel Art Top, Platformer Front, Multi-view 4/6; save as JSON.
- **Check:** applying a preset changes only the expected parameters.
- **Done:** typical scenarios in one click.

### A7. Tests and tag 2.1.0
- **Actions:** unit + smoke on canvas, snap, axes, templates; version 2.1.0.
- **Done:** sprite export is stable.

---

## 11. Stage 7. Accurate bounds, animation, metadata

**Result:** correct dimensions of instances, animation sequences, anchors and JSON.
**Estimate:** 5-8 days.

### B1. Prototype `depsgraph.object_instances`
- **Depends:** stage 6.
- **Actions:**
1. Separate script: collect the world-space bbox of all instances.
2. Compare with the current `get_collection_bounds` on test scenes.
3. Check Geometry Nodes, particles, array, collection instances.
4. Define the collection instance ownership rule.
- **Check:** discrepancies explained; performance measured.
- **Done:** Replacement/Hybrid decision made.

### B2. Integrating the bounds index
- **Depends:** B1.
- **Actions:**
1. Build the index once per job.
2. Aggregate by collection tree.
3. Cache; consider `hide_render`.
4. Fallback to the old bypass when an error occurs.
- **Check:** smoke with instances; the old scenes have not deteriorated.
- **Done:** bounds more accurately and faster.

### B3. Fallback for empty bound_box
- **Depends:** B2.
- **Actions:**
1. For volume/curves/grease pencil/pointcloud, use evaluated geometry if bbox is empty.
2. Release temporary meshes.
3. Limit cost: only for problem objects.
- **Check:** a collection with curves/volume is not considered empty.
- **Done:** fewer false passes.

### B4. Animation
- **Depends:** A1, B2.
- **Actions:**
1. Frame Start/End/Step.
2. Union bounds by frames (selectively or by all).
3. Tasks `(collection, axis, frame)`.
4. Name with `{frame:04d}`.
5. Render as a sequence of still frames.
- **Check:** animation of 3 frames: same size/camera, correct names.
- **Done:** animation pipeline.

### B5. Anchors and metadata
- **Depends:** A1.
- **Actions:**
1. Pivot: bounds center, collection origin, active object origin, Empty, pixel offset.
2. JSON: name, size, bounds, pivot, filepath, axis/frame.
3. Option “one sprite per object”.
- **Validation:** JSON is valid; pivot corresponds to the frame.
- **Done:** data is suitable for the engine.

### B6. Performance
- **Depends:** B2–B5.
- **Actions:**
1. Measure the analysis/render on 10/50/100 collections.
2. Remove unnecessary `view_layer.update()`.
3. Check memory for temporary meshes.
- **Check:** no regression relative to 1.4.0.
- **Done:** there is a report with timings.

### B7. Tests and tag 2.2.0
- **Done:** bounds/animation/metadata covered in smoke.

---

## 12. Stage 8. Optional: atlas, CLI, parallelism

**Evaluation:** 5+ days, only after stabilization of 2.2.0.

- Atlas/sprite sheet: Blender Image API or optional dependency.
- CLI/JSON config for `blender -b --python`.
- Experimental parallel launch of background Blender processes.
- Export to GIF/APNG for preview (optional).

---

## 12.1. Cross-cutting tasks (performed at all stages)

### X1. Documentation
- Update `CHANGELOG.md` in each tag.
- README: installation, quick start, panel screenshot, settings table, troubleshooting.
- After stage 5, add a section about presets and name templates.
- After stage 7 - about animation, anchors and JSON.

### X2. Logging and diagnostics
- Enter the `bts` logger (without a separate module, while `logic.py` is small).
- Debug mode: timings for analysis, isolation, rendering, recording.
- Replace `except Exception: pass` with logging with context and `Problem` where it is a user error.
- Log file: output folder or temp; Do not write to system directories without permission.

### X3. Compatibility
- Before each tag: clean installation of Blender 5.2, `--factory-startup`.
- If we declare support for 5.0/5.1, add a separate smoke run; otherwise explicitly specify the minimum.
- Keep all API differences (`compositing_node_group`, `file_output_items`) in helper functions.
- Check linked data and do not write to it.

### X4. Code hygiene
- `logic.py` does not import `ui` and `operators`.
- Refactoring commits do not change behavior.
- Save `bl_idname`, `scene.bts_settings`, names of existing properties.
- New public functions - with short docstring and, where possible, type hints.
- Do not add dependencies unnecessarily; standard library + bpy/mathutils.

### X5. Release
- Build zip without `tests/` and service files.
- Checking the installation from zip on a clean Blender.
- Checking the opening of the old scene and migration of settings.
- Tag and brief description of the changes.

---

## 13. Test matrix

| Level | What checks | When |
|---------|----------------|-------|
| Unit | paths, names, templates, `compute_frame`, axes, `ProblemCollector` | after R1.8, F1, A1–A5 |
| Smoke basic | export, names, sizes, restoration | S0, after each stage |
| Smoke compositor | File Output nodes, SUBFOLDER/PREFIX/NONE, linked nodes | stages 3–4 |
| Smoke safety | camera, linked hide_render, border/stamp, cancel | stages 1, 3, 4 |
| Smoke collision | collisions, policies, Ask/Error/Skip/Overwrite/Suffix | Stage 3-4 |
| Smoke sprites | single canvas, pixel snap, multi-view, templates | stage 6 |
| Smoke animation | frame range, union bounds, names | stage 7 |
| Manual UI | panels, UIList, presets, migration, report | stage 5 |
| Performance | 10/50/100 collections, memory | stages 5, 7 |
| Compatibility | clean installation of Blender 5.2; if possible 5.0/5.1 | before each tag |

Minimal local check command:

```powershell
python -m py_compile blender_to_sprites_batch_exporter\*.py
pytest tests
blender -b --factory-startup --python tests\smoke_blender.py
```

For Windows, the path to Blender is set by the `BLENDER_EXE` variable so that the scripts do not depend on a specific installation.

---

## 14. Checkpoints and versions

| Dot | Result | Version (sentence) |
|-------|-----------|----------------------|
| M0 | Baseline and smoke | 1.2.0 |
| M1 | Hotfix cameras/hide_render | 1.2.1 |
| M2 | 5 files without behavior change | 1.3.0 |
| M3 | Paths, nodes, state, isolation | 1.3.1 |
| M4 | Preflight, `BatchJob`, cancel | 1.4.0 |
| M5 | New UI, presets, report | 2.0.0 |
| M6 | Single canvas, multi-view, templates | 2.1.0 |
| M7 | Bounds, animation, metadata | 2.2.0 |
| M8 | Atlas, CLI, parallelism | 2.3.0+ |

Before each tag:

1. `py_compile` of all modules.
2. Unit tests.
3. Smoke test in Blender 5.2 with `--factory-startup`.
4. Installation from scratch (zip/folder).
5. Checking the migration of the old scene.
6. Update README/CHANGELOG.
7. `git tag`.

---

## 15. What to do on the first working day

1. Create a branch and a baseline tag.
2. Write `tests/smoke_blender.py` for the current addon.
3. Record the baseline report.
4. Make H1.1–H1.2: camera ownership.
5. Make H2.1: safe `hide_render`.
6. Run smoke and commit hotfix.

After this, you can move on to R1.1–R1.7 - division into 5 files without adding new functions.

---

## 16. Main risks of the sequence

- **Too early optimization of bounds.** First prototype B1, then integration; do not break the current bypass until confirmed.
- **UI before ready job.** Collection list and "Analysis" can be started after R1, but export button must use `BatchJob`, otherwise temporary workarounds will appear.
- **`Ask` without preflight.** Basic version of confirmation - in stage 3; full - in stage 4. Do not release an intermediate version with silent overwrite.
- **Loss of transfer behavior.** Compare each stage with `tests/BASELINE.md`; Don't mix refactorings and new features in the same commit.
- **UI overload.** Introduce elements in stages U1–U5, do not try to create the entire layout at once.
- **Too many files.** Do not create `core/*` until step J10; the criterion is real growth and the second reason for the change.
- **Cancel inside render.** Do not promise instant stop; cancel - between tasks.
- **Linked data compatibility.** Always check `id_data.library` and do not write to other people's data.
- **Migration of settings.** New fields and lists should have safe default values; old scenes should not change behavior without explicit user action.
