# Stage 5 report: new interface

Date: 2026-11-10
Version: 2.0.0
Status: implemented and verified headless in Blender 5.2.3 LTS.

## Result

Stage 5 turns the sidebar into a target-driven UI. Collections are selected in
a list, analysis feeds the problem and path previews, presets are portable, and
the last export is available as a report and a log. The node output layout is
now exposed as Automatic, Collection Name, Subfolder, Prefix and the manual
Don't Modify mode.

## Delivered tasks

### U1. Target and Always Include properties

- `BTS_TargetItem` with collection name, `enabled` and `size_status`.
- `BTS_CollectionRef` for the separate Always Include list.
- `target_items`, `always_include_items`, list indices and filter string.
- One-time migration:
  - `export_source` fills `target_items`;
  - `keep_collections` fills `always_include_items`;
  - saved 1.4.x scenes keep their previous node layout.
- `export_source` is now the starting filter; the target list is the source of
  truth for preflight and export.
- `name_template` for the main render path.
- `AUTO` and `FILENAME` added to `node_naming`; the old identifiers remain.

### U2. Collection list

- `BTS_UL_Targets` with checkbox, name and analysis status.
- Filter by collection name.
- All, None, Active and Make Active actions.
- Separate `BTS_UL_AlwaysInclude` list with Add Active and Remove.
- Export and analysis use only enabled target items.

### U3. Main panel

- Target/angle/frame summary.
- Batch Export, Analyze and Cancel buttons.
- Live job status with current/total and rendered/skipped/failed counters.
- Cached analysis summary.

### U4. Problems panel

- Problems grouped by ERROR, WARNING and INFO.
- Each entry shows code, message, collection and fix hint.
- Long lists are truncated with a remaining count.
- Analyze and Copy Report actions.
- Warnings are explicitly marked as non-blocking.

### U5. Output and naming panel

- User-facing control renamed to Node Output Layout.
- Resolved layout shown next to the setting.
- Automatic resolves to Collection Name for one node and Subfolder for several.
- Collection Name and Don't Modify show an immediate warning when the current
  target/node count makes them invalid.
- Path preview uses the same plans as preflight and the job.
- Conflict count and up to three conflicting paths are shown.
- Main-render name template with examples.
- Node-only mode shows EXR multilayer and hides the add-on format controls.
- Existing overwrite policy and Open Output Folder actions are retained.

### U6. Presets

- Built-in Pixel Art Top, Platformer Front and High Resolution Top presets.
- JSON export and import with version field.
- Unknown fields are reported and ignored.
- Save and Load operators use the user CONFIG directory as the default.

### U7. Report and log

- `format_job_report` lists status, counts, duration, node layout, written files
  and problems.
- The last report is stored in `scene.bts_settings.last_report`.
- Log is written outside the sprite output folder.
- Report panel: Copy Report, Open Log, Open Output Folder.

### U8. Cache and performance UI

- Panels read `peek_cached_analysis`; they do not scan nodes or calculate bounds
  in `draw()`.
- Target list has a filter and no per-row geometry measurement.
- A UI draw probe calls every panel path in Blender to catch layout errors.

### U9. Naming, help and confirmations

- Renamed ambiguous controls: Node Output Layout, Override Node Base Paths,
  Also Save Main Render, Base Directory / Fallback Directory.
- Tooltips describe the resulting path for each node layout.
- Confirmation dialogs added to Remove Camera and Unhide Everything.
- RU/EN localization remains optional and was not added in this stage.

### U10. Manual checklist

Automated checks completed:

- clean Blender start with the package;
- registration of all panels, lists and operators;
- target migration and disabled-target export;
- preset apply, save and load;
- analysis, path preview and problem panel draw paths;
- export, overwrite policies, node layouts and cancellation at job level.

Manual GUI checks still recommended:

- click through the new panels at 100+ collections;
- use the Cancel button during a real modal export;
- test Save/Load preset file dialogs;
- verify the report/log buttons on Windows;
- check the one-time migration by opening an old 1.3.x scene.

## Tests

### Unit

`python -m unittest discover -s tests -p "test_*.py"`

Result: **46 tests, all pass**.

New coverage includes name templates, preset round-trip, unknown preset fields
and unsupported preset versions.

### Blender 5.2.3 LTS smoke

Isolated profile outside the Blender installation and project, with
`--factory-startup`, redirected `BLENDER_USER_*`, `TEMP` and `TMP`.

| Command | Result |
|---|---|
| `./tests/run_tests.ps1` | SMOKE PASS |
| `./tests/run_tests.ps1 -StrictCamera` | SMOKE PASS |

Smoke now also covers:

- target list rebuild and disabled-target exclusion;
- name-template output paths;
- preset core and operator save/load;
- UI draw probe for every panel in main, node and problem states.

## Verification summary

| Check | Result |
|---|---|
| Unit tests | 46/46 OK |
| Base smoke | PASS |
| Strict camera smoke | PASS |
| UI draw probe | all panels OK |
| `py_compile` package and tests | OK |
| Extension manifest validate | OK |
| Install 2.0.0 zip in an isolated profile | OK |
| Package / manifest version | 2.0.0 |

## Known limitations

- Multi-view selection and its 4/6 presets belong to stage 6. The current
  built-in presets are single-view.
- The panel reads the cached analysis; after changing export settings, run
  Analyze again to refresh path previews. Operators still validate the cache
  token before launching.
- The modal Cancel button and file-dialog interactions need a manual GUI pass.
- Linked File Output nodes and the Ctrl+Z preview rollback remain manual
  checks from earlier stages.
- `logic.py` is still a facade; stage 6 may grow the modules further.

## Next step

Stage 6: uniform canvas, pixel snap, multi-view and name templates across axes
and frames (version 2.1.0).
