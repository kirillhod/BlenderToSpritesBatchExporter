# Blender smoke test

The smoke suite runs inside Blender, loads the working tree and exercises the
operators, rendering, File Output nodes, target filtering and UI draw. It is
not a unit test.

## Before running

- Use `$env:BLENDER_EXE` when it is set.
- If it is not set, ask the user for the Blender executable path. Never
  hardcode a machine-specific path in the repository.
- Do not claim a Blender version passed unless that executable actually ran.

## Run

From the repository root, PowerShell:

```powershell
$env:BLENDER_EXE = '<path to blender.exe>'
& $env:BLENDER_EXE -b --factory-startup --python tests\smoke_blender.py
```

Bash or Git Bash:

```bash
BLENDER_EXE=/path/to/blender ./tests/run_tests.sh
```

`tests/run_tests.ps1` and `tests/run_tests.sh` check `BLENDER_EXE`, then
`blender` on `PATH`.

Optional environment variables:

| Variable | Effect |
| --- | --- |
| `BTS_REPO` | repository root; defaults to the parent of `tests/` |
| `BTS_STRICT_CAMERA=1` | also test a user camera named like the temporary one |
| `BTS_KEEP_OUTPUT=1` | keep rendered files for inspection |

## Success

- stdout contains `SMOKE PASS`;
- the process exits with code 0;
- on failure stdout contains `SMOKE FAIL` and a traceback, and the output
  directory is kept for inspection.

## Coverage

The entry point is `run_test()` in `tests/smoke_blender.py`. It calls:

| Function | Covers |
| --- | --- |
| `run_policy_checks` | overwrite policy, naming, file plan |
| `run_compositor_test` | File Output nodes, isolated render |
| `run_analysis_and_cancel_test` | analysis cache, cancellation, restore |
| `run_target_list_test` | target rows, enabled flags, All/None |
| `run_list_density_test` | 0/2/50 collections, search, content-sized lists |
| `run_override_property_test` | override seeding, analysis token, .blend persistence |
| `run_view_property_test` | view migration, View override, empty-view preflight |
| `run_multi_view_export_test` | four axes, shared canvas, axis names, node suffix |
| `run_view_override_export_test` | six global axes, a two-view target override, per-collection canvases |
| `run_override_export_test` | per-collection padding/PPU, report, no-override fallback |
| `run_override_ui_test` | active override row, three collapsible groups, view grid, search and export-mode filters, draw path |
| `run_preview_test` | preview camera, target isolation, resolution and camera view; row switching keeps the target and Outliner selection; export exits preview; exit restores the scene |
| `run_collision_test` | sanitized name collisions block the export; temporary camera |
| `run_target_sync_test` | automatic sync and Outliner linkage |
| `run_target_filter_test` | `export_source` filter and registry persistence |
| `run_ui_draw_probe` | every panel draws in every mode |
| `run_ui_icon_probe` | icon identifiers resolve |

Add a check here when the change touches target filtering, Outliner linkage,
output lists, preflight or rendering. Pure logic belongs in the unit suite.

## Notes

- PNG file hashes are unstable across runs. Compare decoded pixels, not file
  hashes.
- 5.2.3 and 5.3 are separate runs. Record which executable was used; a passing
  5.3 run does not verify 5.2.
- At 2.3.0 both 5.2.3 LTS and 5.3 pass on Windows x64. When 5.2.3 is not
  installed, unpack a portable build outside the repository and point
  `BLENDER_EXE` at it.
- Preview checks enter and exit the mode; the camera-view switch itself needs a
  GUI and is checked visually.
- Preview value drags refresh immediately. Update smoothness needs a GUI; it is
  checked with a timer that changes a framing value and records camera updates.
