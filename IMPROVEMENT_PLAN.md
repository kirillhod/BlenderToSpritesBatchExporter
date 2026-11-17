# Improvement plan for Blender To Sprites Batch Exporter 3.x

Date: 2026-11-11
Baseline version: 2.0.4
Base branch: `main` (the repository has no `master` branch)
Work branch: `feature/improvements-v3`
Status: in progress. Stage U is released as 2.1.0 and its review fixes as
2.1.1, 2.1.2 and 2.1.3. Next: 2.2.0, per-collection overrides.

This plan replaces the previous 3.x draft. The draft grew into a platform
roadmap with atlas packing, CLI, pivots, metadata, a shared global canvas and a
large module split. None of that is needed now. Version 3 is a focused workflow
release with five features.

---

## 1. Scope

Version 3 does five things:

| # | Feature | Release |
|---|---|---|
| 1 | UI cleanup: tooltips, density, automatic collection sync, readable status | 2.1.0 |
| 2 | Per-collection overrides for view, framing and resolution | 2.2.0 |
| 3 | Multi-view export with 4- and 6-direction presets and one naming policy | 2.3.0 |
| 4 | Animation export: every action of a collection, its frame range and its name | 3.1.0 |
| 5 | Blender 5.3 compatibility | 3.0.0 |

Releases are incremental: **2.1.0-2.1.3**, **2.2.0**, **2.3.0**, **3.0.0** and
**3.1.0**. There is no 3.2.

Each stage ships a testable build instead of waiting for the final release. UI
cleanup is 2.1.0 with review patches through 2.1.3, overrides are 2.2.0,
multi-view and naming are 2.3.0, and Blender 5.3 plus the combined verification
is 3.0.0. Animation is 3.1.0 because it reuses the naming and canvas rules
introduced in 2.3.0. The 3.1.0 work is not optional polish; it is the animation
feature.

### 1.1. Explicit non-goals

These are not planned for version 3. They are listed so they do not creep back
into the work:

- atlas / spritesheet packing;
- CLI or JSON build pipeline;
- pivots, anchors, metadata manifests;
- localization;
- exporting individual objects instead of collections;
- one shared canvas for the whole run;
- pixel-grid snapping;
- a rewrite of bounds for arbitrary depsgraph instances;
- splitting `job.py`, `output.py` or `scene.py`;
- parallel background rendering;
- new operator IDs.

Reasons are in section 12.

---

## 2. Baseline state at 2.0.4

The 2.0.x line already provides the reliable core: target list, preflight,
cancellable job, predictable paths, File Output support, presets, report and log.
The remaining friction is in daily use:

1. **Interface noise.** Static help text is drawn as labels, so panels are tall
   and repetitive. Hints should be tooltips.
2. **Manual refresh.** The target list is only updated by Analyze or by pressing
   `Refresh Targets`. Adding a collection in the Outliner does not show it.
3. **Unclear status.** After Analyze a row can show `1.00 x 1.03`, which is the
   bounds size in world units. It does not answer "how big will the sprite be?".
4. **One global configuration.** Padding, view axis and resolution are global,
   although different collections often need different values.
5. **One view per run.** `camera_axis` is a single value, so a directional set
   needs several exports and manual renaming.
6. **No animation.** Only the current frame is rendered.
7. **Blender 5.3.** Released today; compatibility has to be verified.

### 2.1. Current state after 2.1.3

Stage U and its review fixes are complete:

- static help labels moved to tooltips; Problems shows complete messages;
- the target list follows collection creation, deletion and renaming;
- `export_source` filters both the visible target list and the export;
- the active Outliner collection and the active target row follow each other;
- enabled flags and the full target registry survive export-mode switches;
- the target list is a fixed two-column table with `Collection` and
  `Canvas / status` headers;
- Path Preview is a hideable, scrollable compact list; File Output node
  information is one compact, scrollable list;
- the Report tab is now `Log`, is always open, and contains only `Copy Log` and
  `Open Log`;
- built-in preset explanations live in the preset menu tooltips;
- the manifest, package contract and changelog are at 2.1.3.

Verification at 2.1.3: the unit suite passes, the Blender 5.3 smoke suite
passes, and the zip installs and registers. Blender 5.2.3 was not installed in
the test environment, so the 5.2 side of the matrix remains open until C1.

Next work starts at stage O: per-collection framing and resolution overrides.

---

## 3. Compatibility contract

These rules apply to every task:

1. Keep every existing `bl_idname`, `scene.bts_settings` property name and enum
   identifier. No operator is added or removed in v3.
2. New behavior is opt-in where it can change output:
   - overrides are off by default and resolve to the global values;
   - multi-view defaults to the current single Top view;
   - animation export is off by default.
3. Old scenes keep their current output until the user changes something.
4. Existing UI operators stay, including `bts.refresh_targets`, even when the
   list updates automatically.
5. Presets stay version 1. New fields are optional on load; old presets with
   `camera_axis` map to the matching view boolean.
6. GPL-3.0-or-later, English-only code, comments, docs and commit messages.
7. `blender_manifest.toml` keeps `blender_version_min = "5.2.0"`. Both 5.2 LTS
   and 5.3 are supported.

---

## 4. Feature 1: interface cleanup (released 2.1.0-2.1.3)

### 4.1. Hints become tooltips

Rule: if a string explains **what a control does or how to use it**, it belongs
in a Blender tooltip. If it reports **current state or a problem**, it stays on
screen.

| Current on-screen text | New home |
|---|---|
| `Examples: {collection} -> Body.png` | `name_template` property description |
| `Use 0.01-0.1 for crisp pixel art.` | `filter_size` property description |
| `Details are in the Problems panel.` | removed |
| `Run Analyze to validate settings.` | removed; the Problems panel already reports it |
| Node layout explanations | `node_naming` and related property descriptions |
| `Light collections are included automatically...` | `keep_lights` description; no inline warning |
| `Warnings do not block export; errors do.` | `bts.analyze` operator description |
| `Multi-view presets arrive with 2.1.` | removed |
| Preset descriptions | per-preset tooltips in the built-in preset menu |

Blender does not support tooltips on plain labels or UIList rows. A shared
`bts.apply_preset` operator also cannot show a different tooltip per button. The
final solution uses an `EnumProperty` preset menu whose items carry the
descriptions as menu tooltips. Text that cannot become a tooltip is either
removed, turned into a self-explanatory value, or moved to the README. Property
descriptions become full sentences with examples and defaults.

### 4.2. Density

- Remove full-width separators between closely related rows and use
  `separator(factor=0.5)` where a visual break is still useful.
- Use one warning box per issue group instead of nested boxes.
- Keep `use_property_split = True` and `use_property_decorate = False` for
  property rows. UIList wrappers set `use_property_split = False`, otherwise
  rows are laid out as property values and appear centred.
- Use `scale_y` 0.85-0.9 only for secondary text such as problem entries.
- Keep Presets closed by default. `Log` is always open and contains only its
  two buttons.
- Target list 8 rows, Always Include 3 rows, Path Preview 4 rows, File Output
  nodes 3 rows. All lists scroll.
- Main action buttons use the standard row height; they are not enlarged.

### 4.3. Collections update automatically and follow the Outliner

- A lightweight handler on `depsgraph_update_post` compares a cheap fingerprint
  of the available source collections and the active Outliner collection with
  the current target list and marks the scene as pending. A debounced one-shot
  timer applies the sync outside the depsgraph callback.
- `load_post` may sync directly.
- The sync runs only when no preflight or job is active, and it is suppressed
  while the add-on itself changes visibility or excludes during export.
- Enabled flags, overrides and the active index are preserved by collection
  name.
- `export_source` is a filter over a persistent target registry. It controls
  both the visible list and the exported set, so `Active Collection` shows only
  the active Outliner collection. Switching back to another mode restores the
  previous registry and flags.
- Selecting a collection in the Outliner selects its target row. Selecting a
  target row selects that collection in the Outliner. The active-index update is
  suppressed while sync writes the row, preventing a feedback loop.
- `All` and `None` apply only to collections visible in the current export
  mode.
- The manual `bts.refresh_targets` button stays as a fallback and is
  non-destructive.
- Renaming a collection is treated as remove + add: the new name starts with
  defaults. This is documented.

### 4.4. Readable status

The world-unit string is removed. After Analyze, each row shows the canvas it
will produce. The list has `Collection` and `Canvas / status` headers:

| Case | Row text |
|---|---|
| Single view, still | `512x304` |
| Several views | `512x512, 4 views` |
| Animation | `512x512, 12 frames` |
| Skipped | `skipped`; the row stays compact |
| Before analysis | empty |

The main panel summary shows the enabled and visible target counts for the
current export mode, the view count and, after Analyze, the task count. The
strings carry their units and counts, so no legend is needed. Long paths and
long collection names are clipped by the panel width, but the lists scroll and
the panel can be widened.

### 4.5. Panel map

| Panel | Change |
|---|---|
| Main | enabled/visible target summary, views, task count after Analyze; compact action rows |
| Collections | export-mode filter, target table, Outliner-linked selection, Always Include list |
| Camera & Framing | framing values; view toggles and view presets arrive in 2.3 |
| Resolution | unchanged fields; global values until overrides arrive in 2.2 |
| Output & Naming | main or node output, compact Path Preview list, File Output node list |
| Problems | every message, collection and fix hint in full |
| Presets | one built-in preset menu with per-item tooltips; JSON save/load |
| Log | always open; `Copy Log` and `Open Log` only |
| Animation | new in 3.1 |

The former Report panel is now `Log`; its `BTS_PT_report` ID is preserved for
compatibility.

---

## 5. Feature 2: per-collection overrides

Overrides cover only the two categories that need per-asset values, split into
three groups:

| Group | Fields |
|---|---|
| View | the six view booleans |
| Framing | `camera_margin`, `padding_mode`, `padding_pixels`, `padding_units` |
| Resolution | `pixels_per_unit`, `resolution_multiple`, `square_output`, `min_resolution`, `max_resolution` |

Everything else stays global by design: output directory, format, naming,
overwrite policy, isolation, Always Include and node settings. Mixing those per
collection would make the report and the file plan hard to read.

Rules:

1. Each group has one toggle. Off means "use the global value".
2. Turning a toggle on copies the current global values into the collection, so
   the user edits from a working baseline.
3. Effective values are resolved once per target in preflight and the same
   object is used by the job. The UI shows the same numbers.
4. Overrides are part of the analysis token, so changing one invalidates the
   cached preview.
5. Overrides are not stored in presets. A preset changes the globals only;
   collections with an active override keep their values.
6. The report lists only the groups that are overridden for that collection.
7. Validation is the same as for globals: a value that fails validation is a
   preflight error with the collection name.

Storage: the override fields live on `BTS_TargetItem`. There is one entry per
collection, so no second list and no name lookup is needed. Deleting a
collection deletes its entry and its overrides. The View group is wired together
with the view controls in feature 3; Framing and Resolution are independent of
it.

UI: below the target list, a box for the selected collection shows the three
group checkboxes. When a group is off, a single muted row says `Using global`.
When on, the controls appear in place.

Compatibility: all toggles default to off, so existing scenes and presets
produce exactly the 2.0.4 result.

---

## 6. Feature 3: multi-view

### 6.1. Controls

- Six booleans: `view_top`, `view_bottom`, `view_front`, `view_back`,
  `view_right`, `view_left`, shown as toggle buttons in **Camera & Framing**.
- `camera_axis` is kept as the legacy value. When exactly one view is selected,
  it mirrors that view so old presets and scripts keep working. With several
  views it is ignored.
- `views_migrated` maps the old `camera_axis` to the matching boolean once.
- A collection with `override_view` uses its own six booleans.
- At least one view must be selected per target; an empty set is a preflight
  error.

### 6.2. Presets

- **4 Directions**: front, back, right, left.
- **6 Directions**: all six.
- Both set the template to `{collection}_{axis}` and use the global framing and
  resolution values.

### 6.3. One canvas per collection

All directions of one collection share one canvas: the largest result of the
selected axes. The same 3D bounds are projected differently per axis, so the
add-on computes the required resolution per axis and keeps the maximum width,
height and orthographic scale.

This keeps the scale identical between directions and prevents a wide side view
from producing a smaller sprite. Different collections keep their own canvas, as
in 2.0.4. In 3.1 the same rule extends across animation frames.

### 6.4. Naming policy

Tokens in 3.0: `{collection}`, `{axis}`. In 3.1: `{action}`, `{frame}`.
Integer padding is supported: `{frame:04d}`.

Axis words are lowercase: `top`, `bottom`, `front`, `back`, `right`, `left`.

The canonical names are:

| Case | Example |
|---|---|
| One view, still | `Body.png` |
| Several views | `Body_front.png` |
| Animation, one view | `Body_Walk_0001.png` |
| Animation, several views | `Body_Walk_front_0001.png` |

If several views are selected and the template does not contain `{axis}`, the
add-on appends `_{axis}` and reports an INFO note with the resolved template.
The same rule adds `_{action}` and `_{frame:04d}` in animation runs. Tokens that
are present are respected; missing tokens are appended at the end in the order
action, axis, frame.

The recommended complete template is
`{collection}_{action}_{axis}_{frame:04d}`; parts that are not active are
omitted. The canonical examples above use either the default `{collection}`
template or that complete template. With a partial template the auto-appended
tokens follow the existing text, so the preview always shows the exact result;
write the complete template when the order matters.

The template remains global. Per-collection templates are not planned: they
would multiply the collision cases without a clear need.

A custom oblique or isometric camera is not part of v3.

---

## 7. Feature 4: animation export (3.1.0)

### 7.1. What is exported

`export_animations` is off by default. When it is on:

- each target collection is scanned recursively for objects with
  `animation_data`;
- the active action and actions referenced by NLA strips are collected;
- actions are deduplicated by datablock, and their owner objects are remembered;
- an action that no object references is not exported.

A collection without actions still exports its current frame as a still.

### 7.2. Frame range

For each action:

- if `action.use_frame_range` is set, use `frame_start` and `frame_end`;
- otherwise use `action.frame_range`;
- round outward to whole frames;
- apply `animation_frame_step` (default 1);
- `{frame}` is the scene frame number.

The ranges are shown in Analyze before launch.

### 7.3. Evaluation and restore

For every action:

1. Assign it to its owner object and select a compatible action slot.
2. Mute the other NLA tracks of that owner.
3. Set the scene frame and render a still.
4. Restore the action, slot, NLA mute states and frame in `finally`.

Other objects keep their own animation. Actions are evaluated by Blender at the
chosen frame, so constraints and modifiers work, but NLA blending and layered
action mixes are not baked. This limitation is documented in the UI and README.

### 7.4. One size for every frame

The canvas of a collection is the union over **all exported actions and all
sampled frames**. Every selected view is projected from that same union, so the
directions keep one scale. Every file of that collection has the same
resolution and scale, including frames of different actions. This is the
requirement that makes an animation sequence usable in an engine.

Sampling costs `actions x frames`; rendering costs `actions x views x frames`.
Preflight shows the task count and warns above 1000 tasks. Cancel works between
frames; the frame already rendering finishes.

### 7.5. Tasks and names

Task order is fixed: `collection -> action -> axis -> frame`.

Default names follow section 6.4. Overwrite policies apply per produced file;
`Skip` skips an existing file, not the whole collection.

---

## 8. Feature 5: Blender 5.3

- Keep support for 5.2.3 LTS and 5.3. The manifest minimum stays 5.2.0.
- Verify: install, enable, disable, render, File Output nodes (image and
  multilayer EXR), image settings, depsgraph bounds, action slots, NLA, and
  `frame_set`.
- Fix only actual breakages. No opportunistic rewrite.
- Add 5.3 to the smoke matrix and record both versions in the reports.
- If an API used by the add-on is removed without a 5.2 fallback, requiring 5.3
  is acceptable, but only with a documented reason.

---

## 9. Architecture

No module split in v3. The existing layout stays. Four small modules are added
where the new logic has a clear boundary:

| Module | Purpose |
|---|---|
| `core/overrides.py` | resolve global values plus per-collection overrides into one settings object |
| `core/naming.py` | strict token formatter, auto-suffix and collision checks |
| `core/tasks.py` | expand collections, actions and views into `RenderTask` objects |
| `core/animation.py` | action discovery, ranges, slot assignment and NLA isolation |

Dependency rules stay as before: `ui` and `operators` call `logic`; `core.*`
never imports `ui` or `operators`; `properties.py` remains the only place where
properties are declared.

`job.py` keeps the render loop, `output.py` keeps main-render paths, and
`scene.py` keeps bounds, isolation and snapshots. They are large, but splitting
them is not part of the user-visible goal and would add review risk.

---

## 10. Testing

### 10.1. Unit tests

- template formatting: every token, padding, unknown token, empty result,
  auto-suffix order, collisions;
- override resolution: group off, group on, edge values, invalid values;
- view migration: each legacy axis maps to one boolean;
- task expansion: collection x action x axis x frame order and counts;
- canvas: one size across views, one size across frames, per-collection
  isolation;
- action range: manual range, `frame_range`, step, reversed range;
- status strings: still, views, frames, skipped;
- UI helpers: target status labels, text wrapping, default search filtering;
  target-mode filtering and output-list population are smoke checks.

Unit tests stay Blender-free and use `tests/stub_bpy.py`. `animation.py` is
tested with fake objects that expose `animation_data`, tracks and actions.
The suite must stay green; the exact count is reported by the runner and is
not pinned here, because it grows with every stage.

### 10.2. Smoke tests in Blender 5.2.3 and 5.3

- UI draws in every panel and every mode;
- target filters: `All`, `Included`, `Active` and `Top-Level` show and export
  the expected subset, while the registry and enabled flags survive switches;
- Outliner and target list follow each other in both directions;
- Path Preview and File Output node lists are populated after Analyze;
- two collections with different overrides produce different padding and scale;
- 4- and 6-direction runs produce unique names and one canvas per collection;
- animation with two actions and two views produces stable sizes, correct names
  and restores the action, frame and NLA state;
- cancel during a sequence restores the scene;
- old scene and old preset load with unchanged output.

At 2.1.3 the smoke suite passes in Blender 5.3. Blender 5.2.3 is not installed
in the current environment, so that half of the matrix is still open for C1.

### 10.3. Manual checks

- tooltips are readable and no static hint labels remain;
- adding or deleting a collection updates the list without pressing anything;
- switching `Export` to `Active Collection` leaves only the Outliner collection
  in the list;
- selecting another Outliner collection updates the active target row;
- the row status and the `Canvas / status` header are understandable without a
  legend;
- Path Preview hides with its checkbox and scrolls;
- per-collection padding is visible in the rendered files;
- 5.3 clean install runs a small export;
- panel height stays reasonable with 50+ collections.

---

## 11. Roadmap

| Release | Scope | Estimate |
|---|---|---|
| **2.1.0** | UI cleanup | 3 days |
| **2.1.1** (intermediate) | UI review fixes: Log, preset tooltips, compact actions | 1 day |
| **2.1.2** | compact Path Preview and File Output node lists | 1 day |
| **2.1.3** | target filter and Outliner link | 1 day |
| **2.2.0** | per-collection overrides | 4 days |
| **2.3.0** | multi-view, canvas and naming | 3 days |
| **3.0.0** | Blender 5.3 and combined verification | 2 days |
| **3.1.0** | animation export | 2 weeks |

2.1.1 was an intermediate build; its changes are included in 2.1.2, so there is
no `v2.1.1` tag. The tagged releases are `v2.1.0`, `v2.1.2` and `v2.1.3`.

The 2.x releases do not change existing output unless the user enables a
feature. 3.1.0 changes output only when `export_animations` is on.

---

## 12. Rejected and deferred

| Item | Decision | Reason |
|---|---|---|
| Atlas / spritesheet | rejected | External tools already do this; it is not part of batch rendering. |
| CLI / JSON pipeline | rejected | No current need; the UI covers the workflow. |
| Pivots and metadata | deferred | Engine-specific; add on request. |
| Shared canvas for all collections | rejected | Per-collection canvas plus overrides and per-collection view/frame union covers the real need. |
| Pixel-grid snap | deferred | Not requested; PPU and rounding handle typical pixel art. |
| Instance-aware bounds rewrite | deferred | Revisit only if a real scene reports a wrong result. |
| `job.py` / `output.py` / `scene.py` split | deferred | Internal only; adds review risk now. |
| Localization | deferred | English-only project. |
| Object targets | deferred | The collection model is the product. |
| New operator IDs | rejected | Existing operators and presets are enough. |
| Parallel rendering | rejected | Not needed at the current scale. |

---

## 13. Definition of done

### 2.1.0

- Static hints are gone from panels; the remaining labels report state or errors.
- The collection list updates automatically and keeps enabled flags.
- Row status shows canvas size, never world units.
- README, CHANGELOG, manifest and package contract use 2.1.0.

### 2.1.1 (intermediate, superseded by 2.1.2)

- Problems lists every message, collection and fix hint in full.
- Preset explanations are menu tooltips only.
- Main action buttons use compact rows.
- The Report tab is `Log`, stays open, and contains only `Copy Log` and
  `Open Log`.
- README, CHANGELOG, manifest and package contract use 2.1.1.

### 2.1.2

- The target list is a fixed table with `Collection` and `Canvas / status`
  headers; rows share the same left edge.
- Path Preview is a hideable, scrollable compact list.
- File Output node information is one compact scrollable list.
- README, CHANGELOG, manifest and package contract use 2.1.2.

### 2.1.3

- `export_source` filters both the visible list and the export.
- `Active Collection` shows only the active Outliner collection.
- The Outliner selection and the active target row follow each other.
- The target registry and enabled flags survive export-mode switches.
- README, CHANGELOG, manifest and package contract use 2.1.3.

### 2.2.0

- A collection can override framing and resolution.
- Turning all overrides off reproduces 2.0.4 output exactly.
- README, CHANGELOG, manifest and package contract use 2.2.0.

### 2.3.0

- 4- and 6-direction runs produce correctly named files with one canvas per
  collection.
- Unknown naming tokens and name collisions are caught before rendering.
- Row status adds the view count when it applies.
- README, CHANGELOG, manifest and package contract use 2.3.0.

### 3.0.0

- Blender 5.2.3 and 5.3 both pass the smoke suite.
- The combined 2.1.0-2.3.0 behavior is verified together.
- README, CHANGELOG, manifest and package contract use 3.0.0.
- No new operator ID was introduced.

### 3.1.0

- Every action of a collection is exported over its own frame range.
- All frames of a collection have the same size and scale across actions and
  views.
- Names include the action and the frame by default.
- Cancelling a sequence restores the action, slot, NLA state, frame, camera and
  render settings.
- README, CHANGELOG, manifest and package contract use 3.1.0.

---

## 14. Summary

The 2.x work made the exporter safe. Version 3 makes it comfortable and
expressive without turning it into a platform. Releases 2.1.0-2.1.3 complete the
first feature; the remaining stages are focused on overrides, views, animation
and the final Blender compatibility pass.

The remaining goals are:

1. Remove interface noise and manual steps.
2. Let each collection use the framing and resolution it needs.
3. Export all directions in one run with predictable names.
4. Export all actions of a character with one stable canvas.
5. Keep working on the current Blender.

Everything else stays out until a real workflow asks for it.
