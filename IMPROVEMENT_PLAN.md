# Improvement plan for Blender To Sprites Batch Exporter

Date: 2026-11-09
Current version: 1.2.0 (one file, 1137 lines)
Goal: to increase reliability, expand the capabilities of the sprite pipeline, speed up work and bring the interface to the level of a full-fledged tool, gradually dividing the monolithic module into layers.

> The plan is based on code analysis from `ADDON_STATE.txt`. Time estimates are indicative and are given for one developer; priorities can be changed.
>
> Revision: the architectural section has been revised - starting with 5 files, growing to 9–10 as needed; splitting into 16+ modules has been postponed until the real growth of the code base.

---

## 1. Principles and procedures

1. **Data security first, then new features.** Any mistake should not delete the user's camera, change scene settings without recovery, or overwrite someone else's files.
2. **Critical hotfixes first, then refactoring without changing behavior, then other fixes and new features.** Hotfix removes the risk of data loss immediately; refactoring after it does not change the behavior and is easier to check.
3. **Logic separate from UI.** `logic` (later `core`) should not import panels and operators; The UI only displays state and invokes operations.
4. **Everything is checked before rendering.** A separate preflight stage collects errors and warnings and prevents the launch of obviously problematic exports.
5. **Single source of state.** Settings, scene snapshots, problems and results are formatted by dataclasses, rather than transmitted in long tuples.
6. **Compatibility.** Keep `bl_idname` operators, property name `scene.bts_settings` and old settings so as not to break existing scenes and scripts.
7. **Testability.** Pure functions are covered by unit tests, and rendering is covered by a smoke test in `blender --background`.

---

## 2. Architecture: incremental partitioning without premature fragmentation

The current file is 1137 lines. This is enough to make mixing UI, settings and rendering awkward, but not enough to justify 16+ modules. Therefore, the architecture is introduced in two steps: first, minimal separation, then only as real growth occurs.

### 2.1. Step 1 - Minimal Separation (Recommended Now)

```
blender_to_sprites_batch_exporter/
├── __init__.py       # bl_info, register/unregister, version
├── properties.py     # BTS_Settings and PropertyGroup (data schema)
├── logic.py          # all non-UI logic: paths, bounds, camera, isolation,
│                     # compositor, scene state, render loop
├── operators.py      # operator wrappers
└── ui.py             # panels, UIList, drawing

tests/                # outside the package; does not affect installation and is not
                      # considered add-on fragmentation
```

What does it give:

- logic is separated from the interface - the main goal;
- the settings are described in one place and are not spread across panels;
- operators become thin;
- `logic.py` can be covered with tests;
- installation and reboot remain simple.

`logic.py` will temporarily be ~600-700 lines. This is normal: one visible module is better than five half-empty ones.

### 2.2. Step 2 - separation of logic after growth

When preflight, `BatchJob`, multi-view and animation appear, `logic.py` will grow to ~1500 lines. Then, and only then, is it worth dividing:

```
blender_to_sprites_batch_exporter/
├── __init__.py
├── properties.py
├── core/
│   ├── __init__.py
│   ├── common.py     # constants, paths, names, logging
│   ├── scene.py      # collections, bounds, isolation, scene state
│   ├── framing.py    # axes, padding, compute_frame, pixel snap, shared canvas
│   ├── output.py     # File Output nodes, path planning, name templates
│   └── job.py        # BatchJob, preflight, ProblemCollector, cancellation
├── operators.py
└── ui.py
```

Total ~10 files of 150–350 lines. Further fragmentation (`ui/` on panels and lists, `compat/`, separate `problems.py`) - only when real volume appears in a specific module, and not in advance.

### 2.3. Why not 16 files at once?

- **Half-empty modules.** `problems.py`, `preflight.py`, `compat.py`, `naming.py` at the current volume contain 30-80 lines and only reduce cohesion.
- **Extra imports and cycles.** The more boundaries, the greater the chances of circular imports and registration errors.
- **More difficult to install and develop.** A package of many files requires a careful reboot; Blender's import cache may be hiding changes.
- **Risk when refactoring.** Moving 1137 lines into 16 files at once increases the likelihood of losing behavior.
- **Splitting is a means, not an end.** Splitting should be based on the reason for the change, not on the number of lines.

Practical criteria for when to divide a module further:

- the file contains more than ~350-400 lines;
- it has two independent reasons for the change;
- you need to import tests;
- changes occur in it more often than in neighboring files.

### 2.4. Dependency direction

```
__init__.py ──> properties
     ├──> operators ──> logic ──> bpy / mathutils
     └──> ui ──> properties + operators (and read-only access to logic data)
```

Rules:

- `logic` **does not import** `ui` and `operators`.
- `ui.py` does not count dimensions, does not scan nodes and does not change the scene - only `draw()` and operator calls.
- `operators.py` contains a minimum of code: context validation, calling logic, reporting to the user.
- `properties.py` is the only place to describe properties; panels and logic read them, but don't create them.
- Differences between Blender versions are first localized in small helper functions inside `logic.py`; a separate `compat` is created only when shims accumulate.

### 2.5. Key Entities of Logic

Introduced gradually, as needed:

```python
@dataclass
class Bounds:
    min: Vector
    max: Vector
    valid: bool

@dataclass
class FrameSpec:
    res_x: int
    res_y: int
    ortho_scale: float
    center: Vector
    width: float
    height: float

# Later, at the preflight/job stage:
@dataclass
class Target:
    collection: Collection
    bounds: Bounds
    frame: FrameSpec
    output_paths: list[str]
    skip_reason: str | None

@dataclass
class NodeOutputPlan:
    collection: str
    node_name: str
    layout: str
    base_path: str
    file_name: str
    path: str
    layer_names: list[str]
    exists: bool
    notes: list[str]

@dataclass
class Problem:
    severity: Literal["ERROR", "WARNING", "INFO"]
    code: str
    message: str
    collection: str | None = None
    fix_hint: str | None = None

class BatchJob:
    def preflight(self) -> list[Problem]: ...
    def analyze(self) -> list[Target]: ...
    def run(self, progress, cancel_check) -> JobResult: ...
    def restore(self) -> list[Problem]: ...
```

`BTS_OT_BatchExport.execute` after stage 4 (introduction of `BatchJob`) turns into ~20–40 lines: collect the config, call `job.preflight()`, show problems, run job, display the result.

### 2.6. Refactoring order (safe commits)

1. **Commit 0.** Branch + smoke-base: fix the current behavior, add a simple test script.
2. **Commit 1 (hotfix).** Fix critical issues directly in the monolith: camera ownership and secure recording `hide_render`. This is not refactoring yet.
3. **Commit 2.** Commit `properties.py`; registration does not change.
4. **Commit 3.** Move `logic.py`: move functions without changing the code, leaving thin wrappers. Check with a smoke test.
5. **Commit 4.** Move `operators.py`, `ui.py`, `__init__.py`; check `bl_idname`, `scene.bts_settings` and package installation.
6. **Commit 5.** Add unit tests to pure functions `logic.py`.
7. **Commit 6.** The remaining P0/P1 fixes are already in the new structure.
8. **Commit 7.** When the logic grows, divide `logic.py` by `core/*` (step 2).
9. **Commit 8.** Translate to Blender Extension, upgrade version, add `blender_manifest.toml`, zip build script and CHANGELOG.
10. **Commit 9.** Only after this - new functions and behavior changes.

At each step: `python -m py_compile` + smoke test in Blender + checking that `bl_idname` and `scene.bts_settings` have not changed.

### 2.7. Compatibility when splitting

- `bl_info` remains in `__init__.py`; when switching to Extension, add `blender_manifest.toml` (it is better to support both installation methods for the transition period).
- Save all `bl_idname`: `bts.batch_export`, `bts.preview_camera`, `bts.cleanup`, `bts.restore_collections`, `bts.open_output_folder`.
- Save `bpy.types.Scene.bts_settings` and existing property names.
- For a new list of collections, instead of the string `keep_collections`, make a migration: at the first start, parse the old string into `CollectionProperty` and mark it with the `settings_migrated` flag.
- Changing from a single `.py` to a folder - breaking change of setup, but not scene data. Indicate in README and CHANGELOG. For intermediate batch refactoring, use 1.3.0; Assign 2.0.0 after behavior changes (new UI, output policies, sprite capabilities).

---

## 3. Error correction (based on code analysis results)

Priorities: **P0** - data loss/impossibility of operation, **P1** - noticeable problems, **P2** - inconvenience, **P3** - code cleanliness.

| # | Priority | Problem | Place | Consequence | Solution |
|---|-----------|----------|-------|-------------|---------|
| 1 | P0 | The camera is searched/deleted only by name `_BTS_OrthoCamera` | `ensure_camera`, `remove_camera` | Overwriting or deleting a custom camera | Mark the created camera custom property `bts_owned=True`; if the name matches, create `_BTS_OrthoCamera.001`; delete only owned; store a link to the source camera |
| 2 | P0 | File Output “Don't Modify” mode writes all collections to the same paths | `apply_node_paths` | Silent file overwriting | Preflight planning of all paths; detect duplicates and suggest/require policy (error, omission, overwrite, suffix) |
| 3 | P0 | Write `hide_render` without error handling | `isolate_collection_by_hide` | Crash on linked/override objects | try/except on object + Problem; preflight checks `ob.library`/override and suggests Exclude |
| 4 | P0 | No collision detection after name sanitization (`a/b` and `a\b` → `a_b`) | `logic.py` (path functions), `execute` | Overwriting results | Plan names in advance; in case of collision, add `_2`, `_3` or give an error |
| 5 | P0 | Emergency renaming based on mtime and snapshot difference | `prefix_new_files` | Can rename extraneous fresh files; expensive on large folders | Remove for regular scenarios: names are known in advance. Leave fallback only as an explicit option with an exact list of expected paths |
| 6 | P0 | No cancellation of long export | `BTS_OT_BatchExport` | The user waits until the end | Modal operator with timer/cancellation check between collections and frames; correct `finally`-restore |
| 7 | P1 | `keep_lights` does not work in Exclude mode | `isolate_collection_by_exclude` | Light from a separate collection disappears | Automatically save collections with light (and only light in them - via hide_render), or explicitly document and move the option to Advanced |
| 8 | P1 | Objects are not directly isolated in the Scene Collection | `isolate_collection_by_exclude` | Garbage in every frame | For objects outside collections, use hide_render; add warning to preflight |
| 9 | P1 | Checks `node_override_base`/`write_main_output` work even without nodes | `execute` | False error "Base Dir is empty" | Check only with `using_nodes` / `write_still` |
| 10 | P1 | Relative `//` is checked only for Output Directory | `execute` | Nodes can write to nowhere in an unsaved file | Validate all node base directories after path resolution |
| 11 | P1 | All File Output nodes are collected, including unconnected ones | `collect_file_outputs` | Extra files, unexpected entries | Bypass only nodes reachable from the Composite output (with the “all nodes” option) |
| 12 | P1 | Editing nodes from linked library | `apply_node_paths` | Posting errors, broken links | Skip `id_data.library` with WARNING; do not try to change and “restore” |
| 13 | P1 | Render Border/Crop/Stamp and similar settings are not reset | `execute` | Cropped or captioned sprites | Expand snapshot: `use_border`, `use_crop_to_border`, `use_stamp`, `use_stamp_*`, `use_file_extension`; set safe values during rendering |
| 14 | P1 | No check that the engine supports transparency/format | `preflight` | Unpredictable result | Warn for Workbench and incompatible format/color/depth combinations |
| 15 | P2 | Incorrect color depth is silently ignored (eg 32 for PNG) | `apply_image_settings` | The user does not understand the result | Table of acceptable values by format; validation in preflight and UI |
| 16 | P2 | No handling of Windows reserved names (CON, NUL, COM1...) | `sanitize_filename` | Write Error | List of reserved names + prefix `_` |
| 17 | P2 | Progress does not take into account skipped collections | `execute` | Inaccurate progress | Count completed attempts, separately show skipped/failed |
| 18 | P2 | Composer scan every time the panel is redrawn | `BTS_PT_Output.draw` | UI brakes on complex scenes | Cache with invalidation by scene/node tree or update only by button/handler |
| 19 | P2 | Preview changes scene resolution forever | `BTS_OT_PreviewCamera` | Unexpected settings change | Add `{'UNDO'}` and/or “restore after preview” option |
| 20 | P3 | Dead code/flags (`node_is_multilayer`, second element `get_compositor_tree`) | `logic.py` (nodes) | Confusion | Remove or use as intended |
| 21 | P3 | Strange check `cam_obj.name not in scene.collection.objects` | `ensure_camera` | Fragility | Explicitly check `scene.collection.objects.get(name)` |
| 22 | P3 | Wide `except Exception: pass` | Everywhere in modules | Hidden errors | Log with context, collect Problem |
| 23 | P3 | No `{'UNDO'}` from Batch Export | `bl_options` | Settings changes cannot be rolled back | Either add UNDO or explicitly warn and always restore the state |
| 24 | P1 | "Collection Goes To" has no layout that reproduces normal naming; Prefix duplicates a collection token already present in the node file name; Subfolder is a grouping mode; Don't Modify is manual-only | `properties.py`, `logic.py`, `ui.py` | The user cannot predict node output paths; simple compositor exports do not produce `<Collection>.exr` | Add `NodeOutputPlan`, Collection Name and Automatic layouts, duplicate-token detection and a path preview; preserve the old enum identifiers |

**Separately:** add to preflight checks that are currently missing:

- cannot create or bind a temporary camera to the scene;
- Output Directory inside the addon/system folder;
- paths are too long;
- the collection is empty or all objects are `hide_render`;
- several collections with the same final name;
- compositing with nodes is enabled, but the nodes are not connected to the Composite;
- the scene has a Render Border/Stamp;
- the selected format does not support the selected Color/Depth;
- File Output nodes are located in the linked library;
- the node layout is incompatible with the setup: `Collection Name` with
  several File Output nodes, or `Don't Modify` with several target collections;
- two active File Output nodes resolve to the same final path;
- node-only mode will write EXR multilayer while the selected add-on format is
  PNG/JPEG/WebP;
- for the selected isolation mode there are objects that cannot be hidden.

Problem output format: one aggregated report in the panel and in `self.report` at the end, without duplicate messages for each collection.

### 3.1. UX review: "Collection Goes To" and File Output nodes

Date: 2026-11-10. Full scenario matrix and acceptance criteria:
`reports/UX_REVIEW_COLLECTION_GOES_TO.md`.

Observed in Blender 5.2.3: a File Output node writes **one multilayer EXR per
node**. `node.file_name` is the file name; `node.file_output_items` are layer
names inside that EXR, not separate output files.

Consequences for the current modes:

- `Subfolder` only changes `node.directory`. The result is
  `<base>/<Collection>/<node file name>.exr`, not `<Collection>.exr`. It is a
  grouping layout for several files per collection, not a sprite naming mode.
- `Filename Prefix` writes `<base>/<Collection>_<node file name>.exr`. If the
  node is already named after the collection, the result is `Body_Body.exr`.
  The current code also prefixes the layer names, which is unnecessary.
- `Don't Modify` leaves the authored paths untouched. One compositor tree
  cannot route different collections to different files, so it is safe only
  for a single target; multi-target use is already rejected in stage 3.
- No mode produces `<base>/<Collection>.exr`, the node-mode equivalent of the
  familiar main render path. That missing layout is the source of the
  confusion.
- Node-only mode is EXR multilayer only. The UI hides the format selector but
  does not say that the result is EXR, so PNG expectations are not met.
- There is no path preview, so the user cannot see the effect of a layout
  before rendering.

Decisions:

1. Introduce `NodeOutputPlan` for every `(collection, active File Output node)`
   pair: effective base directory, file name, layout, full path, existing-file
   state and duplicate-token notes.
2. Add `Collection Name` (`FILENAME`): `node.file_name = <Collection>`, layer
   names unchanged. Valid only with exactly one active File Output node.
3. Add `Automatic` (`AUTO`): `Collection Name` for one node, `Subfolder` for
   several. New scenes use Automatic; the resolved layout is displayed.
4. Keep `Subfolder` and `Prefix` and document them as grouping and flat
   multi-output layouts. Neither changes layer names in 5.2.
5. Make `Prefix` duplicate-safe: if the authored name already equals the
   collection or starts with `<Collection>_`, do not add the token again.
6. Keep `Don't Modify` as a manual single-target mode with an actionable error
   for multi-target runs.
7. Treat node mode as an advanced EXR path: show the actual node format, and
   show the add-on format controls only when the main render is also written.
8. Add a path preview in the Output panel and full path/collision output in
   preflight. The preview and the job use the same resolver.
9. Rename the user-facing control to "Node Output Layout". Preserve the
   property `node_naming` and the identifiers `SUBFOLDER`, `PREFIX`, `NONE`;
   add `FILENAME` and `AUTO`; migrate old scenes to their previous layout.

Scheduling:

- Stage 4 (1.4.0): `NodeOutputPlan`, effective path resolution, duplicate-token
  guard, preflight checks for node paths and existing files. No UI redesign.
- Stage 5 (2.0.0): new enum values and default, migration marker, layout UI,
  path preview, node-format notice, renamed control and tooltips.
- Stage 6 (2.1.0): name templates reuse the node plan and add `{node}` next to
  `{collection}`.

---

## 4. Improving algorithms

### 4.1. Single "sprite" canvas (high priority)

Now each collection receives its own resolution based on its dimensions. For sprites this is often unacceptable: frames must be the same size and scale.

Add **Uniform Canvas** mode:

- one common `pixels_per_unit` and common canvas size for all purposes;
- fit modes: `Contain` (guaranteed to fit), `Cover` (fills the canvas), `Stretch` (not recommended);
- alignment of the content inside the canvas: 3x3 (center, bottom-center, etc.);
- general `ortho_scale` and general `res_x/res_y`;
- optionally fixed canvas size from the preset (32, 64, 128, 256, 512, 1024);
- display the final size and scale factor in the UI before rendering.

This is more important than it seems: without a shared canvas, animations and sprite sets jump around in size and position.

### 4.2. Snap to pixel grid

For stable sprites and animation:

- round the camera center to half a texel: `center = round(center * ppu) / ppu` (or taking into account the parity of the resolution);
- with the same `ortho_scale` and resolution, the camera should not produce subpixel drift between frames;
- add test: two adjacent frames with a small object shift must have an integer shift.

### 4.3. Multiple angles in one run

Sprites require directions. Add a selection of axes:

- Top, Bottom, Front, Back, Right, Left (checkboxes or toggle buttons);
- one job bypasses the selected axes and adds a suffix to the name (`{axis}`);
- dimensions and the overall canvas are calculated along all axes (union) at once, so that the frames are consistent;
- presets: “4 directions”, “6 directions”, “isometry” (the latter is a separate angle setting).

### 4.4. Animation and frame range

- Frame Start / End / Step fields;
- general dimensions over the range (union bounds), and not adjustment on each frame - otherwise the camera “breathes”;
- file name with `{frame:04d}`;
- the ability to render as a sequence of still frames (preferred) or through animation;
- warning if an object goes beyond the boundaries between frames (can be checked selectively).

### 4.5. Exact dimensions taking into account instances

The current crawl takes into account only Empty.instance_collection. Improve:

- build an index of objects and their world-space bounding boxes once by `depsgraph.object_instances`;
- take into account Geometry Nodes instances, particle systems, array modifiers, instancing by vertices/faces, collection instances;
- correctly determine whether an instance belongs to a collection: for ordinary objects - `users_collection`, for instances - the instancer/parent collection; for controversial cases - a custom rule;
- for objects with an empty bound_box (volume, grease pencil, curves) use evaluated mesh/geometry fallback only when it is really needed, freeing temporary data;
- build aggregates along the collection tree in one pass, rather than recursively for each target;
- cache the result for the duration of the job; for animation - union by frames.

Difficulty: medium/high, but this is what eliminates most of the “empty” and incorrectly cropped collections.

### 4.6. Smarter isolation

- Hybrid mode: collections are isolated via exclude, and objects that cannot be excluded (scene root) are isolated via hide_render.
- `Always Include`: replace the string with commas with a normal list of collections with a picker.
- “Keep Lights”: keep the light without opening extraneous meshes; if necessary, hide non-light objects in saved collections.
- Option “Keep Objects” (list of objects) - useful for substrates, references, ground.
- Pre-launch check: which objects will remain visible in each frame (diagnostics).
- Always restore state even when canceled/excluded; verify the recovery and write to the log if something failed.

### 4.7. Planning paths and names instead of post-renaming

- Before rendering, build a complete list of output files for all collections/axes/frames.
- Check collisions, existing files, prohibited names, path length.
- Rewrite policy: `Ask`, `Error`, `Skip`, `Overwrite`, `Suffix`. Default - `Ask`: before starting, show the number and list of existing files; for headless mode - `Error`. We do not leave silent overwrite as the default behavior.
- Name templates: `{collection}`, `{axis}`, `{frame}`, `{index}`, `{scene}`, `{date}`; preview and validation of tokens.
- Leave native naming via File Output items in the main way; Remove fallback renaming from the standard script.

### 4.8. Correct work with files and states

- Do not touch `use_compositing` unless required; If required, explicitly communicate that other compositing effects may change.
- Take a snapshot of the state using the context manager (`with SceneState(scene, view_layer, nodes):`) so that recovery is guaranteed.
- Store “what exactly was changed” and restore only that (less side effects and faster).
- After recovery, check key values (camera, resolution, exclude, hide_render, node paths) and add WARNING if recovery failed.

### 4.9. Optional for sprite pipeline

- Pivot/anchor: center bounds, origin of the collection, origin of the active object, manual Empty, offset in pixels.
- Metadata export (JSON): name, size, bounds, pivot, filepath - for import into the game engine.
- Packaging into an atlas/sprite sheet (can be done in a separate step; via the Blender Image API or an optional dependency).
- Option "one sprite per object" in addition to "per collection".
- CLI/JSON config for headless launch (`blender -b --python ...`) to be integrated into CI/pipeline.

---

## 5. Performance optimization

| Region | Now | Offered | Expected effect |
|---------|--------|--------------|------------------|
| Dimensions | Recursive traversal for each collection, repeated updates view layer | One world-bounds index, tree aggregation, cache per job | O(N) instead of O(C×N), less lag on large scenes |
| Instances | Empty.instance_collection only | Iteration `depsgraph.object_instances` | More correct and without repeated recursion |
| File Output nodes | Tree search at each iteration and each redraw of the panel | One `CompositorIndex` per job + cache for UI | Removes unnecessary bypasses and panel brakes |
| Snapshots | Snapshot of all scene objects | Snapshot of only mutable objects/properties | Less memory and time |
| Fallback renaming | `os.walk` + mtime ±2 s | Exact list of expected paths; without recursive scanning | Faster and safer |
| `view_layer.update()` | Often | Only with a real change in visibility | Fewer depsgraph recalculations |
| Progress | No cancellation, approximate | Modal loop, cancel between tasks, ETA | UI remains responsive |
| Logging | No | Timings by collections, debug log | It is clear what exactly is slowing down |

Additionally:

- Do not recalculate `depsgraph` for each target unless necessary; the rendering is still sequential, but the Python overhead can be removed.
- For very large batches (hundreds of collections), consider optionally running several Blender background processes (`--background`) to distribute collections. This is complex and risky (licenses, GPU, memory), therefore only as a separate experimental stage.
- Measure time: analysis, isolation, rendering, file recording; display the final table in the report.

---

## 6. User interface (one of the main priorities)

### 6.1. General panel structure

```
┌ Blender To Sprites ──────────────────────────────┐
│  Targets: 12 collections · 3 views · frames 1–8  │
│  [ Analyze ]  [ Batch Export ]  [ Cancel ]       │
│  Progress: ███████░░░ 42%  (14/32, 1 error)      │
│  ⚠ 2 warnings  [Details]                         │
├ ▾ Collections (12) ──────────────────────────────┤
│  ☑ Body        512×512   ☑ Weapon   256×256      │
│  ☐ UI          empty     ☑ Props    128×128      │
│  [All] [None] [Active] [Search: ______]          │
│  Always include: [Collection ▾] [+] [−]          │
├ ▾ Framing ───────────────────────────────────────┤
│  Views: [Top] [Front] [Right] [Custom…]          │
│  Fit: Contain ▾   Padding: 10%                   │
│  Anchor: ⊞   ☑ Shared canvas: 512×512 ▾          │
├ ▾ Output ────────────────────────────────────────┤
│  //sprites/  [Open]                              │
│  Name: {collection}_{axis}   Preview: ...        │
│  Format: PNG ▾  RGBA ▾  8 bit ▾                  │
│  Overwrite: Ask ▾                                │
├ ▾ Advanced ──────────────────────────────────────┤
│  Isolation: Exclude ▾  ☑ Keep lights             │
│  ☑ Use File Output nodes                         │
│  ☐ Write main render                             │
│  ☑ Remove camera after export                    │
│  [Presets…] [Save report]                        │
└──────────────────────────────────────────────────┘
```

### 6.2. Specific UI improvements

1. **List of collections with checkboxes and sizes.** Instead of “all/only enabled/active” - explicit selection of goals; `export_source` remains only as a starting filter/button for mass filling of the list. After the “Analyze” button, show the calculated size, bounds and warnings. This dramatically increases control and reduces the number of random renders.
2. **Button “Analysis” (Preflight).** Counts dimensions, final names and sizes, checks for errors, does not render anything. The user sees what will happen.
3. **Separate panel/section “Problems”.** Grouped ERROR/WARNING/INFO with codes and tips; buttons “Open settings”, “Fix”, “Ignore for this launch”.
4. **Cancel and progress.** Modal operator: current collection/view/frame, ETA, “Cancel” button, correct state restoration.
5. **Normal “Always Include”.** Replace the string with commas with CollectionProperty + UIList + picker. Leave the line only for migration.
6. **Name template with live preview.** Show 2-3 example names and a list of conflicts before launch.
7. **Understandable captions and tooltips.** For example, `Depth` → `Color Depth`, `Camera Distance Margin` → `Camera Offset (units)`, `Padding` → `Padding (px)`; Each parameter has a short description and impact on the result.
8. **Presets.** “Pixel Art Top”, “2D Platformer Front”, “Multi-view 4/6”, “Animation Sequence”. Saving in JSON to a user config; download/export.
9. **Destructive Warnings** Confirmation for “Unhide Everything”, deleting camera, overwriting files, exporting outside project.
10. **Result after export.** Number of files, time, missed/incorrect, “Open folder”, “Open log”, “Copy report” buttons.
11. **Information panel.** Brief description of the pipeline and link to README/help; A hint is that for sprites it is better to enable a single canvas.
12. **Localization RU/EN.** English as source, Russian via `bpy.app.translations` (optional). At a minimum, remove ambiguous terms.
13. **Caching for UI.** Do not scan nodes and do not count bounds in `draw()` on each redraw; store the result of “Analysis” and invalidate by button/scene change.
14. **Keyboard/Menu.** Add an operator to the Render/Export menu and to the F3 search with a clear name; The hotkey is not assigned automatically.
15. **Accessibility.** Single icons, grouping by meaning, no default “magic” numbers, safe values for new users.

### 6.3. Default settings (suggested)

- single canvas - an option included in the new presets; old scenes retain the same mode until explicitly turned on;
- `Ask` with existing files: show the list and ask for confirmation; `Overwrite` is explicitly available;
- `Always Include` - empty list;
- auto-delete temporary camera - enabled;
- `Padding` as a percentage of the object size as a more predictable option (in addition to px/units);
- clear report after export.

---

## 7. Testing and quality control

### 7.1. Unit tests (without Blender or with minimal stubs)

- `sanitize_filename`: prohibited characters, spaces/dots, empty name, reserved names Windows, Unicode.
- `safe_join`, `split_base`, `make_relative_slot`, `ensure_slash`.
- Name patterns: token substitution, escaping, collisions, extensions.
- `compute_frame`: padding px/units, square, min/max, multiplicity, no negative dimensions, edge cases.
- Axes: correct directions and pairs of width/height axes.
- `ProblemCollector`: deduplication, aggregation, sorting.
- Preflight: logical checks on fake data.

### 7.2. Smoke test in Blender (`blender -b --factory-startup --python tests/smoke_blender.py`)

Script:

1. Create 3 collections: two with meshes, one empty; light in a separate collection; camera.
2. Add a File Output node (to check the composer branch).
3. Run `bts.batch_export` with a small resolution: Workbench - for a quick basic test, EEVEE - a separate script for the File Output branch (Workbench does not check the composer).
4. Check:
- files have been created and have the expected names/sizes;
- empty collection skipped;
- original camera, resolution, format, exclude, hide_render and node paths have been restored;
- temporary camera deleted (if enabled);
- when restarted with the `Error` policy, old files are not overwritten;
- canceling between collections leaves the scene in its original state.
5. Separate scenario: an object with Geometry Nodes instances falls into bounds.

Startup scripts: `tests/run_tests.ps1` (Windows) and `tests/run_tests.sh`. CI optional: GitHub Actions with Blender image (heavy) or local run before release.

### 7.3. Determination of Done

- No known P0/P1 errors.
- All state changes are restored; There is a test for cancellation and for rendering errors.
- Preflight covers all currently checked errors and does not generate false positives.
- Single canvas, multi-view and name templates are covered with tests.
- README/CHANGELOG updated; The installation of the package was tested on a clean Blender.
- There is a log with timings for diagnostics.

---

## 8. Documentation and release

- **README**: installation (legacy addon and Extension), quick start, panel screenshot, settings table, output examples, troubleshooting.
- **CHANGELOG.md**: semantic versioning; 1.3.0 - intermediate transition to the package without changing behavior, 2.0.0 - new UI, output policies and sprite capabilities.
- **Help inside the addon**: short Help panel or link to README.
- **Build script**: `build.ps1`/`build.py` → zip package without `tests`, with the correct version from manifest.
- **Log file**: by default in the output or temp folder; Debug option.
- **License** and attribution - explicitly indicate in manifest/README.

---

## 9. Roadmap by stages

| Stage | Contents | Result | Rating* |
|------|------------|-----------|---------|
| 0 | Branch, smoke-base, fixing current behavior | A secure base for change | 0.5 days |
| 1 | Hotfix P0: camera ownership, secure recording `hide_render` | There is no risk of deleting someone else's camera or falling on linked objects | 0.5–1 day |
| 2 | Minimum separation: `__init__ / properties / logic / operators / ui` + tests | Logic separated from UI, behavior preserved | 1.5–2.5 days |
| 3 | P0/P1 not requiring `BatchJob`: path planning and overwrite, name collisions, node and relative path checks, Render Border/Stamp (deferred to stage 4) | Predictable and secure file output | 2-3 days |
| 4 | `ProblemCollector`, preflight, `BatchJob`, cancel; with the growth of logic - division into `core/*` | All checks before rendering, pure logic | 2–4 days |
| 5 | New UI: Collection List, Analysis, Issues, Progress/Cancel, Presets | Manageable and intuitive interface | 4–6 days |
| 6 | Single canvas, pixel snap, multi-view, name templates | Full sprite export | 4–7 days |
| 7 | Animation, union bounds, exact instances, anchors/metadata | Pipeline for animations and engines | 5–8 days |
| 8 | Atlas/spritesheet, CLI/JSON, optional concurrency | Ecosystem Expansion | 5+ days |

\* Estimates are indicative; Steps 4–5 can be partially combined. If UI is more important than new features, stage 5 can be started immediately after stage 2, without waiting for preflight/BatchJob.

### What to do first (top 10)

1. Hotfix: camera ownership and secure recording `hide_render` - right in the current monolith.
2. Minimum division into 5 files without changing behavior - remove the confusion of logic and UI.
3. Path planning, rewrite policy and name collision detection.
4. Aggregated preflight and `BatchJob` instead of separate checks in `execute`.
5. Cancel export and guaranteed restoration of the scene state.
6. Correction of node checks, relative paths, Render Border/Stamp.
7. The list of collections and the “Analysis” button are the greatest increase in convenience.
8. A single canvas and pixel snap - without this, sprites are rarely suitable.
9. Multi-view, name templates and presets.
10. Animation, exact instances, anchors and metadata.

---

## 10. Risks and how to reduce them

- **Refactoring breaks registration.** At each stage, check the installation on a clean Blender, save `bl_idname` and `bts_settings`; conduct a smoke test.
- **Excessive crushing.** Do not create a module “for the future”; divide only if there is a real volume or a second reason for the change. The guideline is 5 files now, 9–10 after the logic grows.
- **Change addon format (file → package).** Specify in CHANGELOG; check both installation methods; Don't change Blender version unless necessary.
- **API of Blender 5.x is changing.** First keep all calls to compositor/file_output_items in helper functions `logic.py`, and when accumulated, move them to `core/common.py` or `compat`; add version check and clear message.
- **Accurate bounds for instances can be expensive.** First measure on real scenes; cache; fallback on bound_box.
- **Cancel during `bpy.ops.render.render`.** Blender does not always allow you to interrupt the current render; cancel should work between tasks and the current frame should complete. Don't promise an immediate stop.
- **Single canvas changes the usual behavior.** Make it an option and show a preview; keep old mode for compatibility.
- **Presets and new properties.** Consider migration and default values so that old scenes open without surprises.

---

## 11. Summary

The addon already solves the basic problem: "collection → one static sprite with an orthographic camera." The main directions for improvement:

1. **Reliability** - do not touch someone else’s camera, do not overwrite files silently, always restore the scene, validate everything in advance.
2. **Algorithms** - single canvas, pixel snap, precise instances, multi-view, animation, path planning.
3. **Interface** - explicit list of collections, “Analysis”, aggregated problems, progress with cancellation, presets, clear captions.
4. **Architecture** - step-by-step separation: first 5 files (`__init__ / properties / logic / operators / ui`), then `core/*` as they grow; tests and documentation.

This order allows you to first eliminate the risk of data loss and obtain a testable basis, and then increase the functionality of the sprite pipeline without increasing the complexity of the monolith.
