# Detailed implementation sequence for 3.x

Date: 2026-11-11
Base: `IMPROVEMENT_PLAN.md` (v3 revision, 2026-11-11)
Baseline add-on version: 2.0.4
Target releases: 2.1.0, 2.1.1, 2.1.2, 2.1.3, 2.2.0, 2.3.0, 3.0.0, 3.1.0

The repository uses `main` as its default branch. `feature/improvements-v3`
was created from `origin/main` at `1710a0e`. Stage U is implemented and
released as 2.1.0; its UI follow-up fixes are 2.1.1, 2.1.2 and 2.1.3. Stage O
is implemented and released as 2.2.0.

This sequence covers only the five features in the plan. It is intentionally
smaller than the previous draft: no module splits, no atlas, no CLI, no pivots,
no shared global canvas.

---

## 1. Starting point

### 1.1. Verified baseline

| Check | State at 2.0.4 |
|---|---|
| Add-on version | `bl_info` and `blender_manifest.toml`: 2.0.4 |
| Unit tests | 54 tests, all pass |
| Blender smoke | Passes in Blender 5.2.3 LTS with an isolated profile |
| Blender 5.3 | Released today; baseline run must be recorded in S0 |
| Package contract | pins version `(2, 0, 4)` and the exact operator ID set |
| Working tree | two modified planning documents, no code changes |

### 1.2. Code that v3 will touch

| Area | File | Notes |
|---|---|---|
| Settings | `properties.py` | override fields, view booleans, animation fields |
| Target list and migration | `core/targets.py` | auto-sync, status strings, export filter, Outliner link, view migration |
| Axis and framing | `core/framing.py` | per-axis canvas, one canvas per collection |
| Bounds | `core/scene.py` | `get_collection_bounds` is reused unchanged; target gathering applies the export filter |
| Preflight and job | `core/job.py` | task loop, overrides, animation sampling |
| Paths | `core/output.py` | per-task names |
| Node output | `core/output.py` | per-task stems for File Output nodes |
| UI | `ui.py` | tooltips, target table, output lists, collapsible overrides, views, dynamic lists, animation |
| Presets | `core/presets.py` | view fields, 4/6 direction presets |
| Registration | `__init__.py` | load/depsgraph handlers, version |
| Facade | `logic.py` | re-export new modules |
| Contract | `tests/test_package_contract.py` | version, operator IDs, panel IDs and UIList IDs |

### 1.3. Evidence to capture before the first feature commit

1. `./tests/run_unit_tests.ps1`: record 54/54.
2. `./tests/run_tests.ps1`: record PASS in Blender 5.2.3.
3. The same smoke run in Blender 5.3: record PASS or the exact failure.
4. A small reference export with 2 collections: names, sizes and SHA-256 hashes.
   Store it outside the repository, for example in
   `C:\Users\kiril\AppData\Local\Temp\opencode\bts-v3-baseline\`.
5. Note the four open manual checks from 2.0: modal Cancel, preset file dialogs,
   linked File Output nodes, preview undo.

Do not commit the reference export.

---

## 2. Execution rules

- One commit = one task from this document.
- Before each commit: `python -m py_compile` for all modules and tests.
- After each stage: unit tests plus the smoke test in 5.2.3.
- 5.3 compatibility is re-checked at C1 and before each release.
- Refactor-free: this plan does not move existing modules. New modules are added
  next to the old ones.
- No new operator IDs. The package contract test changes only its version
  assertion.
- Keep every existing `bl_idname`, `scene.bts_settings` property and enum
  identifier.
- New behavior is off by default unless it is pure presentation.
- All scene changes go through snapshots and `finally` restoration.
- Warnings and errors go through `Problem` and `ProblemCollector`.
- English only in code, comments, docs, tests and commit messages.
- Update `CHANGELOG.md` under `[Unreleased]` as tasks land; at release time
  rename it to the stage version.
- Tag every version commit with `vX.Y.Z`. Do not push unless explicitly asked.

### 2.1. Definition of a safe commit

1. `py_compile` is clean.
2. Unit tests pass.
3. Smoke passes in 5.2.3.
4. With all new toggles off, the reference export matches.
5. The add-on enables and disables without errors.

---

## 3. Dependency map

```
S0 baseline
 |
 +-- U1-U7  UI cleanup (2.1.0-2.1.3)
 |
 +-- O1-O5  per-collection overrides (2.2.0)
 |
 +-- V1-V6  multi-view, canvas, naming and list density (2.3.0)
 |      |
 |      +-- C1  Blender 5.3 verification
 |             |
 |             +-- C2  3.0.0 release
 |                    |
 |                    +-- A1-A8  animation (3.1.0)
```

Safe parallelism:

- Stage O is complete; start V1 next. V5 and V5b touch `ui.py`, so land V1-V4
  first.
- V4 (naming) is pure Python and can start as soon as V1 defines the axis list.
- The 5.3 baseline in S0 ran before the first change.

Critical path:

```
S0 -> U3 -> U4 -> U7 -> O1 -> O2 -> O3 -> V1 -> V2 -> V3 -> V4 -> V5 -> V5b -> V6 -> C1 -> C2
```

---

## 4. Stage S0. Baseline and guard rails

### S0.1. Branch and state
- **Status:** done. `feature/improvements-v3` is based on `origin/main`
  (`1710a0e`).
- **Check:** `git status --short` shows only the two planning documents.

### S0.2. Baseline verification
- **Depends:** S0.1.
- **Actions:**
  1. Run the unit tests and the smoke test in Blender 5.2.3.
  2. Run the smoke test in Blender 5.3; record the result even if it passes.
  3. Create the reference export from 1.3.
  4. Save the commands, versions and hashes in a short baseline note outside the
     repository.
- **Check:** unit 54/54; smoke PASS or a documented 5.3 failure.
- **Done:** a comparison point exists.

### S0.3. Manual-check tracker
- **Actions:** record the four 2.x manual checks and the new v3 checks from
  section 12 in a working note.
- **Done:** every manual item has a state: open, passed or failed with a note.

---

## 5. Stage U. Interface cleanup (2.1.0-2.1.3)

**Result:** no static help labels, less vertical noise, automatic target list,
readable row status.

**Status:** complete. 2.1.0 shipped the stage; review fixes shipped as 2.1.1,
2.1.2 and 2.1.3. Tags: `v2.1.0`, `v2.1.2`, `v2.1.3`. The 2.1.1 build was an
intermediate uncommitted build; its changes are included in 2.1.2. Current
verification: the unit suite and the Blender 5.3 smoke suite pass.

### U1. Tooltip pass
- **Depends:** S0.
- **Files:** `properties.py`, `operators.py`, `ui.py`.
- **Actions:**
  1. Rewrite descriptions for every property in Collections, Camera & Framing,
     Resolution and Output & Naming. Include examples and defaults.
  2. Ensure every operator has a meaningful `bl_description`.
  3. Remove the static labels listed in plan section 4.1.
  4. Keep labels that report state or problems, for example an unsaved relative
     path, a missing output folder or a disabled compositor.
  5. Preset explanations are per-item tooltips in an `EnumProperty` menu. No
     description is drawn inline under the preset buttons.
- **Check:** manual hover in 5.2 and 5.3; `grep` shows no removed hint strings.
- **Done:** static help lives in tooltips or the README. Released in 2.1.0 and
  refined in 2.1.1.

### U2. Density pass
- **Depends:** U1.
- **Files:** `ui.py`.
- **Actions:**
  1. Replace long separators with `separator(factor=0.5)`.
  2. Remove nested boxes and keep one box per warning group.
  3. Use `scale_y` 0.85-0.9 only for secondary text such as Problems entries.
  4. Set target list rows to 8 and Always Include to 3. Final lists also use
     Path Preview 4 rows and File Output nodes 3 rows.
  5. Keep Presets closed by default. The Report tab became `Log`, is always
     open and contains only `Copy Log` and `Open Log`.
  6. Keep main action buttons at standard row height; do not enlarge them.
- **Check:** a 50-collection scene keeps the main panel usable; UI draw smoke.
- **Done:** panels are shorter without losing information. Released in 2.1.0,
  refined in 2.1.1 and 2.1.2.

### U3. Automatic target sync
- **Depends:** U2.
- **Files:** `core/targets.py`, `core/scene.py`, `core/job.py`, `__init__.py`,
  `ui.py`, `properties.py`.
- **Actions:**
  1. Add `target_fingerprint(context, settings)`: source collection names,
     `export_source`, `skip_empty` and the active Outliner collection.
  2. Add module-level sync state keyed by scene pointer (`_SYNC_PENDING`,
     `_SYNC_LAST`, `_SYNC_TIMER_REGISTERED`).
  3. The `depsgraph_update_post` handler only compares the fingerprint and marks
     the scene as pending. A one-shot `bpy.app.timers` callback applies
     `sync_target_items` outside the depsgraph callback, then unregisters.
     `load_post` may sync directly.
  4. Preserve `enabled`, override fields and the active index by name.
  5. Suppress the handler while preflight or `BatchJob` runs and while the job
     changes visibility or excludes. Use one module-level flag around those
     changes.
  6. Call `migrate_settings` in the pending sync for the scene that triggered it,
     and reuse the existing `_clear_cache_on_load` handler for the current
     scene on load. This covers files with several scenes.
  7. Keep `bts.refresh_targets` as a small icon button with an explanatory
     tooltip. Make it non-destructive: use `sync_target_items` or extend
     `rebuild_target_items` to preserve overrides and the active index. Do not
     remove the ID.
  8. Unregister the handlers and the timer in `unregister()`.
  9. Review follow-up (2.1.3): make `export_source` a filter over the persistent
     target registry. It filters both the visible list and
     `gather_target_collections`, so `Active Collection` shows and exports only
     the active Outliner collection.
  10. Review follow-up (2.1.3): selecting a collection in the Outliner sets the
      active target row, and selecting a target row sets the Outliner collection.
      Suppress the active-index update while sync writes the row.
  11. Review follow-up (2.1.3): `All` and `None` affect only the collections
      visible in the current export mode.
- **Check:** add, delete and rename a collection in the Outliner; the list
  updates without pressing anything; flags and overrides survive; the manual
  refresh does not discard overrides; export causes no churn; switching to
  `Active Collection` hides the other rows and exports only the active one;
  Outliner and target selection follow each other.
- **Done:** manual refresh is optional and the export mode is a real filter.
  Released in 2.1.0, filter and Outliner link in 2.1.3.

### U4. Readable status
- **Depends:** U3.
- **Files:** `core/targets.py`, `core/job.py`, `ui.py`.
- **Actions:**
  1. Remove the world-unit fallback from `update_target_status`.
  2. Store the canvas as `512x304` when there is one view and as
     `512x512, N views` when there are several. In 3.1 add `, N frames`.
  3. Draw the target list as a fixed two-column table with `Collection` and
     `Canvas / status` headers. A skipped target shows the short `skipped`
     marker and the row stays compact.
  4. Draw the status only when the cached analysis exists, and clear all stored
     status strings when `clear_analysis_cache` runs. A stale cache then leaves
     the rows empty instead of showing old numbers.
  5. Update the main panel summary to show enabled/visible targets, views and
     tasks. The visible count follows the current `export_source` filter.
  6. Remove `Angle: ... Frame: 1` from the summary; the views and frame are
     visible in their panels.
- **Check:** unit tests for the formatter; smoke after Analyze; left edges and
  status columns line up.
- **Done:** a row answers "how big will this sprite be?" without a legend.
  Released in 2.1.0, table layout in 2.1.2.

### U5. Panel tidy-up
- **Depends:** U4.
- **Files:** `ui.py`.
- **Actions:**
  1. Keep the existing panel order: Main, Collections, Camera & Framing,
     Resolution, Output & Naming, Problems, Presets, Log.
  2. Reserve space in Camera & Framing for the view toggles added in V5.
  3. Remove the `Multi-view presets arrive with 2.1` note.
  4. Keep Analyze in the Main panel and in the Problems panel next to the
     messages; remove the duplicate from Output. Do not draw it in three
     places.
  5. Do not compute bounds or scan nodes in `draw()`.
  6. Review follow-up: Path Preview and File Output node information are compact
     `template_list` views, not boxes that expand with the data.
  7. Review follow-up: the Report panel is `Log`, stays open and contains only
     `Copy Log` and `Open Log`; the `BTS_PT_report` ID is preserved.
- **Check:** every panel draws in an empty file and in a scene with targets.
- **Done:** the panel map matches plan section 4.5. Released through 2.1.2.

### U6. Tests and documentation
- **Depends:** U1-U5.
- **Actions:** UI draw smoke, string checks, README screenshots text, CHANGELOG.
  Set 2.1.0 in `__init__.py`, `blender_manifest.toml` and the package contract,
  then build the zip with `tools/build_zip.ps1`.
- **Check:** tests pass; the zip installs and reports 2.1.0.
- **Done:** 2.1.0 is released and stage U is functionally complete. The
  follow-up review releases are recorded in U7.

### U7. Review follow-ups (2.1.1-2.1.3)
- **Depends:** U6.
- **Files:** `ui.py`, `properties.py`, `operators.py`, `core/targets.py`,
  `core/scene.py`, `tests/`, docs.
- **Actions:**
  1. 2.1.1: Problems shows every message without truncation; preset
     explanations are menu tooltips; main actions are compact; the Report tab is
     `Log`, stays open and contains only `Copy Log` and `Open Log`; the inline
     hints under `Also Save Main Render` and `Always Keep Lights` are removed
     from the panel and kept in tooltips.
  2. 2.1.2: the target list becomes a fixed `Collection` / `Canvas / status`
     table; Path Preview becomes a hideable, scrollable compact list; File Output
     node information becomes one compact scrollable list.
  3. 2.1.3: `export_source` filters the visible list and the export; the
     Outliner and the active target row follow each other; the target registry
     and flags survive mode switches; `All`/`None` affect visible targets only.
  4. Add smoke coverage for target filtering, Outliner linkage, output-list
     population and compact UI draw. Keep the unit suite green.
  5. Bump `bl_info`, manifest and package contract for each patch; rebuild the
     zip; tag `v2.1.0`, `v2.1.2` and `v2.1.3`. The 2.1.1 build was an
     intermediate uncommitted build and is included in 2.1.2.
- **Check:** the unit suite passes; smoke passes in Blender 5.3; the 2.1.3 zip
  registers, unregisters and applies the target filter correctly.
- **Done:** Stage U and all review fixes are released.

---

## 6. Stage O. Per-collection overrides (2.2.0)

**Result:** a collection can override framing and resolution without touching
the globals. The View override is added in stage V, together with the view
properties it belongs to.

**Status:** complete and released as 2.2.0. Verification: the unit suite passes,
smoke passes in Blender 5.3.0, and the 2.2.0 zip imports, registers and
unregisters. Blender 5.2.3 was not installed, so the 5.2 side remains open until
C1.

### O1. Properties
- **Depends:** U7.
- **Files:** `properties.py`, `core/targets.py`, `core/job.py`, `tests/`.
- **Actions:**
  1. Add to `BTS_TargetItem`:
     - `override_framing`, `camera_margin`, `padding_mode`, `padding_pixels`,
       `padding_units`;
     - `override_resolution`, `pixels_per_unit`, `resolution_multiple`,
       `square_output`, `min_resolution`, `max_resolution`.
  2. The View override (`override_view` and six booleans) is added in V1
     together with the global view properties.
  3. Add hidden `override_*_seeded` flags.
  4. Add `apply_override_toggle` in `core/targets.py` and call it from the
     group callbacks: when a group is turned on and not seeded, copy the
     current global values and set seeded; when it is turned off, clear seeded.
     This prevents a file load from overwriting stored overrides.
  5. Add `TARGET_OVERRIDE_ATTRS` and `target_override_state`, and extend the
     target state in `analysis_token` with all override fields and group flags.
  6. Pin the target-item property names in the package contract and add unit
     and smoke coverage for seeding, cache invalidation and .blend persistence.
- **Check:** toggling on copies globals; toggling off restores inheritance;
  saving and loading a .blend keeps the values.
- **Done:** the data model is stable.
- **Status:** implemented and smoke-verified in Blender 5.3.0.

### O2. Resolver
- **Depends:** O1.
- **Files:** `core/overrides.py` (new), `logic.py`, `tests/test_logic_unit.py`.
- **Actions:**
  1. Add a small `TargetSettings` container with the framing and resolution
     fields used by `compute_frame`, `padding_in_units` and
     `configure_camera`, including `camera_axis` until V2 passes the axis
     explicitly.
  2. `resolve_target_settings(settings, item)` returns globals or the group
     values for each group independently. An enabled but unseeded group is
     seeded from the globals first.
  3. Add the module to `logic.py`.
- **Check:** unit tests for all combinations: no overrides, one group, both
  groups, invalid values.
- **Done:** one resolver is the only source of effective values.
- **Status:** implemented and unit-tested.

### O3. Preflight and job integration
- **Depends:** O2.
- **Files:** `core/job.py`, `core/targets.py`, `tests/`.
- **Actions:**
  1. In `_run_preflight`, resolve settings per target and compute its frame with
     the resolved values.
  2. Store the resolved object and active override groups on `Target`.
  3. In `BatchJob`, use the resolved values for `configure_camera` and any
     framing/resolution step. Global render preparation stays once per job.
  4. Set the collection's canvas from its resolved frame.
  5. Add override information to the report, for example
     `Body: overrides framing, resolution`.
  6. Compute the analysis token after seeding, so an enabled but unseeded group
     does not invalidate the cache on every run.
- **Check:** two collections with different padding and PPU produce visibly
  different files; with no overrides the reference export matches.
- **Done:** overrides work end to end.
- **Status:** implemented and smoke-verified in Blender 5.3.0.

### O4. UI
- **Depends:** O3.
- **Files:** `ui.py`, `tests/smoke_blender.py`.
- **Actions:**
  1. Below the target list, draw a box for the selected collection. Hide the
     box when the active row is filtered out by the search or export mode.
  2. Two group checkboxes in this stage: Framing and Resolution. The View group
     is added in V5 when the view properties exist.
  3. When a group is off, show one muted `Using global` row.
  4. When on, draw the fields with `layout.prop(item, ...)`.
  5. Disable the box when no target is selected.
  6. Do not add operators; `Clear` is achieved by turning the group off.
- **Check:** UI draw smoke; switching selection updates the box; values persist.
- **Done:** framing and resolution overrides are discoverable.
- **Status:** implemented and smoke-verified in Blender 5.3.0. V5 replaces the
  box with collapsible groups and removes the `Using global` row.

### O5. Tests and documentation
- **Depends:** O1-O4.
- **Actions:** unit tests, smoke with two collections that use different padding
  and PPU, README section, CHANGELOG. Set 2.2.0 in all four places and build
  the zip.
- **Check:** turning every override off uses the global values and restores the
  global canvas; the exact 2.0.4 comparison runs in C1.
- **Done:** 2.2.0 is released and stage O is complete.
- **Status:** released as 2.2.0; tag `v2.2.0`.

---

## 7. Stage V. Multi-view, canvas, naming and list density (2.3.0)

**Result:** several directions in one run, one canvas per collection,
predictable names and content-sized lists.

### V1. View properties and migration
- **Depends:** O5.
- **Files:** `properties.py`, `core/targets.py`.
- **Actions:**
  1. Add `view_top`, `view_bottom`, `view_front`, `view_back`, `view_right`,
     `view_left` to `BTS_Settings` and `BTS_TargetItem`.
  2. Add `override_view` and its seeded flag to `BTS_TargetItem`; the update
     callback copies the global view set when the group is turned on.
  3. Add `views_migrated`.
  4. In `migrate_settings`, clear all view booleans and set the one matching
     `camera_axis`, then set the marker. Unsaved new scenes keep Top.
  5. Keep `camera_axis`; do not remove it from properties or presets.
  6. Add a `sync_legacy_camera_axis(settings, item=None)` helper that mirrors the
     single selected view into `camera_axis`. Call it after a toggle or preset.
  7. Add `view_axes_for(settings, item)` to `core/overrides.py`: the active axis
     identifiers in the canonical order TOP, BOTTOM, FRONT, BACK, RIGHT, LEFT.
  8. Validate that every target has at least one view.
- **Check:** each legacy axis maps to one boolean; an empty selection is a
  preflight error; the View override copies and restores the global set.
- **Done:** view selection is stored, migrated and overridable.

### V2. Axis canvas math
- **Depends:** V1.
- **Files:** `core/framing.py`, `core/tasks.py` (new), `logic.py`.
- **Actions:**
  1. Make the axis table public: `axis_params(axis)`.
  2. Extract resolution constraints from `compute_frame` into
     `constrain_resolution(res_x, res_y, settings)`.
  3. Add `compute_axis_frame(bounds_min, bounds_max, axis, settings)`.
  4. Add `compute_collection_frame(bounds_min, bounds_max, axes, settings)`:
     compute each axis, take the maximum `res_x` and `res_y`, apply the
     constraints once, and return one frame with the bounds center.
  5. Add `configure_camera_for_axis(cam_obj, bounds_min, bounds_max, axis,
     frame, settings)`: placement and depth margin per axis, canvas from the
     shared frame.
  6. Add `RenderTask` and `expand_tasks()` in `core/tasks.py`. For 3.0 the task
     fields are `collection`, `axis`, `action=None`, `frame=None`, `canvas`,
     `output_plan`, `node_plans`, `skip_reason`.
  7. Add the new modules to `logic.py`.
- **Check:** unit tests: one axis matches `compute_frame`; several axes fit every
  direction; square/min/max/multiple are applied once.
- **Done:** one canvas per collection is pure and tested.

### V3. Preflight, task loop and node output
- **Depends:** V2.
- **Files:** `core/job.py`, `core/output.py`, `core/scene.py`.
- **Actions:**
  1. `_run_preflight` builds `analysis.tasks` with `expand_tasks`.
  2. `Target` keeps bounds and the collection canvas; a task references its
     target.
  3. `BatchJob` iterates tasks. Group consecutive tasks by collection so
     isolation is applied once per collection; then render each axis.
  4. Replace `_render_target` with `_render_task`; set resolution from the task
     canvas, configure the camera for the task axis, apply the task output plan.
  5. Node output: extend the stem passed to node plans with the axis suffix, so
     four axes write four files per socket. Keep the existing socket rules.
     Until V4 lands, build the suffix directly; V4 centralizes it.
  6. Conflicts and overwrite policies are evaluated per task file.
  7. Report lists collection, axis and path.
  8. `size_status` shows the canvas and the view count.
- **Check:** a run with four axes writes four files per collection with one
  canvas size; node mode writes axis-suffixed files.
- **Done:** multi-view works end to end.

### V4. Naming module
- **Depends:** V3.
- **Files:** `core/naming.py` (new), `core/output.py`, `core/output.py` node
  helpers, `logic.py`.
- **Actions:**
  1. Implement a strict formatter for `{collection}` and `{axis}` with optional
     integer padding syntax (accepted, used by `{frame}` in 3.1). `{action}`
     and `{frame}` become known tokens in 3.1; in 3.0 they are unknown and
     produce an actionable error.
  2. Unknown tokens and empty sanitized results are errors with the token name.
  3. Add `resolve_template(template, context, active_dimensions)`: append
     missing active tokens in the order action, axis, frame and return the
     resolved template plus INFO notes.
  4. Apply the formatter to the collection stem before path sanitization.
  5. Check collisions across all tasks after sanitization and block the export.
  6. For File Output nodes, apply the same stem and keep socket names untouched.
  7. Add the module to `logic.py`.
- **Check:** unit tests for tokens, padding, unknown token, auto suffix, 1/4/6
  axes and collisions.
- **Done:** names are predictable and validated.

### V5. Views UI and presets
- **Depends:** V1-V4, O4.
- **Files:** `ui.py`, `core/presets.py`, `tests/smoke_blender.py`.
- **Actions:**
  1. Draw the six view toggles as a 3x2 grid with short labels and tooltips;
     use `grid_flow(row_major=True, columns=3, ...)`.
  2. Hide the legacy `camera_axis` control from the panel; keep the property.
  3. Add built-in presets `4 Directions` (front, back, right, left) and
     `6 Directions` (all six). Both set `{collection}_{axis}`.
  4. Add the six view booleans to `PRESET_FIELDS`; export `camera_axis` as the
     first active view for old readers.
  5. In `apply_preset`, if a preset has `camera_axis` and no view fields, enable
     the matching view. This loads old presets correctly.
  6. Replace the Overrides `layout.box()` with three full-width
     `layout.panel` sections. Put the group checkbox in the header and draw the
     body only when the group is on. The View group starts off.
  7. Remove the separate `Using global` rows; an off group shows only its
     header.
  8. Update `_FakeLayout` in `tests/smoke_blender.py` so `panel` and
     `panel_prop` return `(self, self)`.
  9. Remove the old multi-view note if it still exists.
- **Check:** presets apply only their fields; old presets load; override and
  global toggles do not interfere; the 3x2 grid and three groups draw at 100%
  and 150% scale; the View group off adds one header row.
- **Done:** multi-view is one click away.

### V5b. List density
- **Depends:** V5.
- **Files:** `ui.py`, `tests/smoke_blender.py`, `docs/agent/ui.md`.
- **Actions:**
  1. Compute the target list height as `max(3, min(8, visible))`.
  2. Do the same for Always Include (1-3), Path Preview (1-4) and File Output
     nodes (1-3).
  3. Draw one info row instead of an empty `template_list`.
  4. Keep `filter_items` and the export-mode filter intact; do not use
     `template_list(type='COMPACT')`.
  5. Update the Current state and Layout rules sections of `docs/agent/ui.md`.
- **Check:** 0, 2 and 50 collections; 0 and 4 preview files; empty Always
  Include and no File Output nodes. Lists shrink with content, the
  50-collection scene still scrolls, and search and export-mode filtering still
  work.
- **Done:** lists no longer reserve empty rows.

### V6. Tests and documentation
- **Depends:** V1-V5b.
- **Files:** `tests/`, `README.md`, `CHANGELOG.md`, `docs/agent/ui.md`,
  `docs/agent/ui-proposals.md`, `docs/agent/smoke.md`.
- **Actions:** unit tests; smoke with 1/4/6 axes, a collection that overrides
  its views, three collapsible override groups and dynamic list heights; README
  views and naming sections; CHANGELOG; update `docs/agent/ui.md` Current state
  and panel map; mark P1.1, P1.2 and P1.7 as implemented in
  `docs/agent/ui-proposals.md`; update the coverage table in
  `docs/agent/smoke.md`; set 2.3.0 in all four places and build the zip.
- **Check:** the reference scene still matches with new toggles off; the 100%
  and 150% visual check passes.
- **Done:** 2.3.0 is released and stage V is complete.

---

## 8. Stage C. Blender 5.3 and the 3.0.0 release

### C1. Blender 5.3 verification
- **Depends:** V6.
- **Files:** `tests/`, `reports/`, docs.
- **Actions:**
  1. Run the unit tests with the current Python.
  2. Install the add-on from the working tree or a zip in a clean 5.3 profile.
  3. Run the smoke suite in 5.3 and 5.2.3.
  4. Check File Output nodes, image settings, depsgraph bounds, action slots,
     NLA and `frame_set`.
  5. Fix only actual breakages and record the API difference.
  6. Add 5.3 to the documented requirements and the test matrix.
- **Check:** both versions pass; failures have a documented reason.
- **Done:** 5.3 is supported.

### C2. Version 3.0.0 and tag
- **Depends:** C1.
- **Files:** `__init__.py`, `blender_manifest.toml`,
  `tests/test_package_contract.py`, `CHANGELOG.md`.
- **Actions:**
  1. Set 3.0.0 in all four places.
  2. Confirm the operator ID set is unchanged.
  3. Build the zip with `tools/build_zip.ps1`.
  4. Install in clean 5.2 and 5.3 profiles and run a small export.
  5. Tag `v3.0.0`.
- **Check:** versions match; install and export work; package contract passes.
- **Done:** 3.0.0 is released.

---

## 9. Stage A. Animation export (3.1.0)

**Result:** every action of a collection exported over its own range with one
stable canvas.

### A1. Properties
- **Depends:** C2.
- **Files:** `properties.py`, `core/presets.py`.
- **Actions:**
  1. Add `export_animations` (default false) and `animation_frame_step`
     (default 1, min 1).
  2. Add both to the analysis token and to `PRESET_FIELDS`.
  3. Keep all existing frame and scene settings untouched; the action defines
     its own range.
- **Check:** defaults leave 3.0 output unchanged; invalid step is rejected.
- **Done:** animation settings are stable.

### A2. Action discovery
- **Depends:** A1.
- **Files:** `core/animation.py` (new), `logic.py`.
- **Actions:**
  1. Add `ActionRef`: action, owner objects, selected slot, frame list.
  2. `collect_collection_actions(collection)` walks the collection recursively,
     reads `animation_data.action` and NLA strip actions, deduplicates by action
     and records owners.
  3. Handle Blender 5.x action slots: prefer the slot already used by the owner,
     otherwise the first compatible slot. Warn if the choice is ambiguous.
  4. Add `action_frames(action, step)`: manual range when
     `action.use_frame_range` is set, otherwise `action.frame_range`; round
     outward to integers and swap or reject reversed bounds.
  5. Add `apply_action(ref)` and `restore_animation(snapshot)` helpers that
     assign the action and slot and mute other NLA tracks.
  6. Add the module to `logic.py`.
- **Check:** unit tests with fake actions and owners; a real file reports the
  expected actions and ranges.
- **Done:** actions and owners are discovered without changing the scene.

### A3. Frame sampling and the collection canvas
- **Depends:** A2, V2.
- **Files:** `core/job.py`, `core/animation.py`, `core/framing.py`.
- **Actions:**
  1. In preflight, for each collection with actions, apply each action and
     sample its frames.
  2. At every sample: `scene.frame_set(frame)`, update the depsgraph and measure
     the collection bounds.
  3. Union the bounds over actions and frames. The axis math projects that same
     union for every selected view and produces one canvas per collection.
  4. Restore the original frame, actions, slots and NLA state in `finally`.
  5. Store `target.action_plans` and the sequence canvas. Extend the analysis
     token with the discovered action names and ranges, so editing an action
     invalidates the preview.
  6. Report the action count, frame count and task count; warn above 1000 tasks.
- **Check:** a frame far outside the current frame affects the canvas; the scene
  is restored after Analyze.
- **Done:** every frame of a collection will use one canvas.

### A4. Tasks, job loop and restore
- **Depends:** A3.
- **Files:** `core/tasks.py`, `core/job.py`.
- **Actions:**
  1. Extend `RenderTask` with `action` and `frame`; expand in the order
     collection -> action -> axis -> frame.
  2. Group tasks by collection for isolation and by action to switch the active
     action once per action.
  3. Before each task: apply the action, mute other NLA tracks, `frame_set`,
     configure the camera with the collection canvas and render a still.
  4. Snapshot and restore the current frame, active actions, slots and NLA mute
     states in `start()`/`finish()`.
  5. Cancel between tasks; the active render finishes.
  6. Report collection, action, axis and frame for every file.
- **Check:** three frames of two actions produce stable sizes and restore the
  scene; cancel mid-sequence restores everything.
- **Done:** animation works end to end.

### A5. Animation naming and preview
- **Depends:** A4, V4.
- **Files:** `core/naming.py`, `core/output.py`, `ui.py`.
- **Actions:**
  1. Enable `{action}` and `{frame}` with `{frame:04d}` padding.
  2. Auto-append `_{action}` and `_{frame:04d}` when missing, in the order
     action, axis, frame.
  3. `{frame}` resolves to the scene frame number.
  4. Apply the same stem to node outputs.
  5. Preview up to three resolved names and the conflict count.
  6. Reject collisions and invalid names before launch.
- **Check:** `Body_Walk_0001.png` and `Body_Walk_front_0001.png` are produced for
  the canonical cases; unknown tokens fail.
- **Done:** sequence names sort and match the preview.

### A6. Animation UI
- **Depends:** A4-A5.
- **Files:** `ui.py`.
- **Actions:**
  1. Add an **Animation** panel with the export toggle and frame step.
  2. Show found actions, ranges and the total task count after Analyze.
  3. Warn about large runs and add an INFO note for collections without actions.
  4. Update the main summary and the row status.
  5. State the NLA/blending limitation in the panel tooltip and README.
- **Check:** UI draw smoke; counts match the report.
- **Done:** animation is understandable before launch.

### A7. Tests and documentation
- **Depends:** A1-A6.
- **Actions:** unit tests, smoke with two actions and two views, README animation
  and limitations sections, CHANGELOG.
- **Done:** stage A is functionally complete.

### A8. Version 3.1.0 and tag
- **Depends:** A7.
- **Files:** `__init__.py`, `blender_manifest.toml`,
  `tests/test_package_contract.py`, `CHANGELOG.md`.
- **Actions:** set 3.1.0 everywhere, build the zip, install in clean 5.2 and 5.3
  profiles, run the smoke suite, tag `v3.1.0`.
- **Done:** 3.1.0 is released.

---

## 10. Test matrix

| Level | What it checks | When |
|---|---|---|
| Unit | templates, overrides, view migration, tasks, canvas, action ranges, status, UI helpers | after every pure module |
| Smoke basic | export, names, sizes, restore | every stage |
| Smoke UI | all panels, tooltip strings, 50 collections, target table, output lists, three override groups, view grid | U, O and V5 |
| Smoke targets | export-mode filtering, registry persistence, Outliner ↔ target row | U follow-up |
| Smoke overrides | two collections with different padding/PPU, global fallback | O |
| Smoke views | 1, 4 and 6 axes, a collection that overrides its views, unique names, one canvas | V and V5 |
| Smoke density | dynamic list heights, empty lists, filter still works | V5b |
| Smoke naming | tokens, padding, unknown token, auto suffix, collisions | V |
| Smoke 5.3 | install, render, nodes, action slots, NLA | C1 and A8 |
| Smoke animation | two actions, two views, stable size, names, restore, cancel | A |
| Manual | tooltips, auto-sync, target filter, status, UI density, per-collection output, clean install | before each tag |

Current results at 2.2.0: the unit suite passes; smoke passes in Blender 5.3;
the 2.2.0 zip imports, registers and unregisters. The 5.2.3 run is still
pending because that Blender version is not installed in the test environment.

Minimal local check:

```powershell
python -m py_compile blender_to_sprites_batch_exporter\*.py blender_to_sprites_batch_exporter\core\*.py
python -m unittest discover -s tests -p "test_*.py"
./tests/run_tests.ps1
```

Set `BLENDER_EXE` when Blender is not on `PATH`.

---

## 11. Milestones

| Milestone | Result | Version |
|---|---|---|
| M0 | baseline in 5.2.3 and 5.3, reference export | 2.0.4 |
| M1 | UI cleanup | 2.1.0 |
| M1a | UI review fixes (intermediate, included in 2.1.2) | 2.1.1 |
| M1b | compact Path Preview and node lists | 2.1.2 |
| M1c | target filter and Outliner link | 2.1.3 |
| M2 | per-collection overrides, released | 2.2.0 |
| M3 | multi-view, canvas, naming and list density | 2.3.0 |
| M4 | 5.3 verified, 3.0.0 released | 3.0.0 |
| M5 | animation | 3.1.0-dev |
| M6 | 3.1.0 released | 3.1.0 |

---

## 12. Manual checklist

### 2.1.0

- [x] Tooltips explain the settings; no static hint labels remain.
- [x] Adding, deleting or renaming a collection updates the list without
      pressing Refresh.
- [x] Enabled flags survive the automatic sync.
- [x] Row status shows canvas size, not world units.
- [ ] The 2.1.0 zip installs and enables in 5.2 and 5.3. (5.3 verified; 5.2.3
      was not installed.)

### 2.1.1 (intermediate, superseded by 2.1.2)

- [x] Problems lists every message, collection and fix hint in full.
- [x] Preset explanations appear only as menu tooltips.
- [x] Main action buttons use compact rows.
- [x] `Log` stays open and contains only `Copy Log` and `Open Log`.
- [x] The inline hints under `Also Save Main Render` and `Always Keep Lights`
      are gone; their tooltips explain them.

### 2.1.2

- [x] Target rows share the same left edge and the canvas column is visible.
- [x] Path Preview is hideable, scrollable and compact.
- [x] File Output node information is one compact scrollable list.

### 2.1.3

- [x] `Active Collection` shows only the active Outliner collection.
- [x] Selecting a collection in the Outliner activates its target row.
- [x] Selecting a target row selects the collection in the Outliner.
- [x] The target registry and enabled flags survive export-mode switches.
- [x] `All` and `None` affect only the visible targets.
- [x] The 2.1.3 zip installs and registers in 5.3.

### 2.2.0

- [x] Turning an override group on copies the global values.
- [x] Two collections with different padding and PPU render differently.
- [x] Turning all overrides off uses the global values and restores the global
      canvas.
- [x] README, CHANGELOG, manifest and package contract use 2.2.0.
- [x] The 2.2.0 zip imports, registers and unregisters in 5.3.
- [ ] The 2.2.0 zip installs and enables in 5.2.3; that version is not installed.

### 2.3.0

- [ ] 4-axis and 6-axis runs write unique names with one canvas.
- [ ] Unknown tokens and name collisions block the export.
- [ ] The path preview matches the written files.
- [ ] Row status shows the view count when it applies.
- [ ] A 2.0.4 scene opens with the legacy view selected.
- [ ] The 3x2 view grid fits and the legacy axis control is hidden.
- [ ] The three override groups collapse; an off View group adds one row.
- [ ] Lists shrink with content; 50 collections still scroll.
- [ ] The UI passes a visual check at 100% and 150% scale.
- [ ] The 2.3.0 zip installs and enables in 5.2 and 5.3.

### 3.0.0

- [ ] The add-on enables and disables cleanly in 5.2 and 5.3.
- [ ] A no-override export matches the 2.0.4 reference pixels.
- [ ] Preset save/load works on Windows; old presets load.
- [ ] Cancel during a real export restores camera, excludes and render state.
- [ ] The release zip installs on clean 5.2 and 5.3 profiles.

### 3.1.0

- [ ] Two actions of one collection export over their own ranges.
- [ ] All frames and actions of a collection share one canvas.
- [ ] Names include action and frame; sequences sort correctly.
- [ ] Cancel mid-sequence restores frame, action, slot, NLA and render state.
- [ ] Collections without actions still export a still.
- [ ] Large ranges show a task-count warning.
- [ ] 5.2.3 and 5.3 pass the smoke suite.

---

## 13. Risks of the sequence

- **UI work expands.** U is presentation only. Timebox it; do not add new
  panels beyond the plan.
- **Auto-sync loops.** Use a fingerprint and suppress the handler during
  preflight and export. Test add/delete/rename explicitly.
- **Filter and registry drift.** `export_source` filters the persistent target
  registry; it must never delete entries or flags. Mode-switch smoke tests cover
  `All`, `Included`, `Active` and `Top-Level`.
- **Outliner feedback loop.** Sync writes `active_target_index` while the
  property callback writes the Outliner. Suppress the callback during sync and
  keep the target-list and Outliner smoke checks.
- **Overrides drift from globals.** One resolver, used by preflight, job and UI.
  No second copy of the precedence rules.
- **Overrides lost on rename.** Documented: rename is remove + add.
- **Multi-view canvas surprises.** One canvas per collection can enlarge a
  narrow direction. Show the size before launch; PPU and max resolution remain
  available per collection.
- **Naming collisions.** Detect after sanitization and after auto suffixes.
  Block the export.
- **Node output misses the axis suffix.** Test image and multilayer EXR nodes
  with four axes.
- **Action assignment is not NLA baking.** Actions are assigned and other tracks
  are muted. Document that complex NLA blends are not reproduced.
- **Action slots in 5.x.** Prefer the owner's current slot; warn when ambiguous;
  test in 5.2 and 5.3.
- **Animation preflight is expensive.** Sample with a frame step, cache per
  collection, show the task count, warn above 1000.
- **5.3 breaks an API.** Fix only the breakage; keep a 5.2 fallback where
  possible.
- **Version drift.** Update all four version locations in the same commit.
- **Preset compatibility.** Old presets carry `camera_axis`; map it to views and
  keep the field exported.

---

## 14. Next working day

Stage O is complete and released as 2.2.0. The next work is stage V:

1. Confirm the clean tree, `v2.2.0` and the 2.2.0 zip.
2. Run the unit and smoke suites once more in Blender 5.3.
3. Start V1: add the six view booleans and migrate `camera_axis`.
4. In V5, draw the 3x2 view grid and replace the override box with three
   collapsible groups. In V5b, make list heights follow their content.
5. Keep the target filter, Outliner linkage, override values and compact output
   lists intact.
6. Commit one V task at a time and tag each release version. Do not push unless
   asked.
