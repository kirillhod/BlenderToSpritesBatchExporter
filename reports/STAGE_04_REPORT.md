# Stage 4 report: preflight, BatchJob and cancellation

Date: 2026-11-10
Version: 1.4.0
Status: implemented and verified in Blender 5.2.3 LTS.

## Result

Stage 4 introduces a single preflight pass, a problem model, an analysis cache,
`BatchJob` and cancellation. The batch export operator is now a thin wrapper
around those pieces. The stage also performs the planned `logic.py` split into
`core/*` and adds `NodeOutputPlan` from the node output layout review.

## Delivered tasks

### J1. Problem model

- `Problem(severity, code, message, collection, fix_hint)`.
- `ProblemCollector` deduplicates messages and sorts them ERROR, WARNING, INFO.
- Problems are used by preflight, the job and the final report.

### J2. Analysis model

- `Bounds`, `FrameSpec`, `Target`, `JobConfig`, `JobResult`.
- `AnalysisResult` carries targets, main plans, node plans, conflicts and the
  cached analysis token.
- `NodeOutputPlan` is defined in `core/output.py`.

### J3. Preflight

Preflight runs without rendering and checks:

- empty collection list, empty output directory and unsaved relative paths;
- node settings, linked nodes and node layout compatibility;
- `Collection Name` with several nodes and `Don't Modify` with several targets;
- duplicate main paths and duplicate node paths;
- existing files under the current overwrite policy;
- image format, color mode and color depth;
- Render Border, Crop To Border and Stamp (they will be disabled);
- linked objects in Disable-in-Renders isolation;
- collection bounds with temporary include-all and guaranteed restore.

### J3.1. Node output plan

- `resolve_node_layout(layout, active_nodes)` resolves `AUTO` to `FILENAME`
  with one File Output node and to `SUBFOLDER` with several.
- `plan_node_output_paths()` returns effective directory, file name, layer
  names and final path for every collection and active node.
- `FILENAME` uses the sanitized collection name and is valid only for one node.
- `PREFIX` does not duplicate a collection token that is already present.
- Blender 5.2 `file_output_items` remain layer names and are not renamed.
- `{blend_name}` in `node.file_name` is resolved for path planning, so the
  default File Output name is checked on disk correctly.
- Node existing-file checks and overwrite policies are handled by
  `apply_node_overwrite_policy()`.

### J4. Analysis cache and Analyze operator

- Cache key includes scene pointer, all export settings, target names, node
  tree state, engine and frame.
- A setting, collection or node change invalidates the cache.
- `bts.analyze` runs preflight and fills the cache.
- The cache is cleared on file load.
- The main panel shows target/error/warning counts from the cached result.

### J5. BatchJob

- Rendering moved from the operator into `BatchJob`.
- `start()`, `step()`, `finish()` and synchronous `run()`.
- All snapshots and restoration live in `finish()`, including node paths,
  collections, `hide_render`, render settings and the camera.
- The operator only collects context, confirms overwrite, runs the job and
  reports the result.

### J6. Cancel

- `bts.cancel_export` requests cancellation.
- The modal UI export runs one collection per timer step and processes events
  between collections.
- Cancellation keeps files already written and restores the scene.
- The current render is allowed to finish; cancellation is between tasks.

### J7. Ask through preflight

- `Ask` is evaluated in preflight and lists both main-render and node paths.
- Background mode falls back to `Error`.
- After confirmation the job reruns preflight with existing files allowed.
- Name collisions remain errors and are not hidden by confirmation.

### J8. Recovery and error verification

- A render error is collected as a problem, increments `failed` and does not
  abort the remaining collections.
- Scene restoration warnings are collected in `JobResult.problems`.
- The job never raises from the restore path.

### J9. Tests and version

- 1.4.0 in `bl_info` and `blender_manifest.toml`.
- Unit tests for the problem model, node layouts, duplicate-token guard, layer
  protection and Ask confirmation.
- Smoke tests for analysis, cache invalidation, cancellation, node preflight,
  Background Ask, and the existing base, strict-camera, policy, collision and
  compositor cases.

### J10. `logic.py` split

`logic.py` is now a compatibility facade. The implementation lives in:

```
core/common.py    constants, path helpers, image format rules
core/output.py    path planning, File Output nodes, policies
core/scene.py     collections, bounds, isolation, state restoration
core/framing.py   camera framing and ownership
core/job.py       preflight, cache, BatchJob, cancellation
```

`logic.py` is 12 lines. Existing imports from `logic` continue to work.

## Tests

### Static

- `py_compile` for all package modules and tests.
- No Cyrillic in project files.

### Unit

`python -m unittest discover -s tests -p "test_*.py"`

Result: **42 tests, all pass**.

### Blender 5.2.3 LTS smoke

Isolated profile outside the Blender installation folder and outside the
project, with `--factory-startup` and redirected `BLENDER_USER_*`, `TEMP` and
`TMP`.

| Command | Result |
|---|---|
| `./tests/run_tests.ps1` | SMOKE PASS |
| `./tests/run_tests.ps1 -StrictCamera` | SMOKE PASS |

The smoke test now also covers:

- preflight without rendering;
- analysis cache reuse and invalidation;
- `bts.analyze` and the cached result;
- `BatchJob.start/request_cancel/finish` with zero rendered files;
- `NodeOutputPlan` `FILENAME`, `AUTO` and `SUBFOLDER` decisions on a real node;
- `Don't Modify` multi-target preflight rejection;
- Background `Ask` rejection.

## Verification summary

| Check | Result |
|---|---|
| Unit tests | 42/42 OK |
| Base smoke | PASS |
| Strict camera smoke | PASS |
| Analysis and cancel smoke | PASS |
| Node output plan smoke | PASS |
| `logic.py` split | 12-line facade |
| Extension manifest validation | OK |
| Install from the 1.4.0 zip into an isolated profile | OK |
| Package version | 1.4.0 |
| Manifest version | 1.4.0 |

## Known limitations

- The modal UI cancel path is covered by code inspection and the step-based
  job test, but the button interaction itself needs a manual check in the
  Blender GUI.
- Linked File Output nodes still need a manual check with an actual linked
  library.
- `AUTO` and `FILENAME` are internal layout values in 1.4.0. The enum entries,
  default, migration and path preview are exposed in 2.0.0 as planned.
- Node-only output is multilayer EXR in Blender 5.2; this is reported as a
  warning when the selected add-on format differs.

## Next step

Stage 5: new UI with collection selection, presets, problem panel, progress and
the node layout choices from the UX review.
