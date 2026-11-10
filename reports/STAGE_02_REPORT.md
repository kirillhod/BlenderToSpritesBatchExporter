# Report: stage 2 - minimum division into 5 files (1.3.0)

Date: 2026-11-10
Branch: `feature/improvements-v2`
Addon version: `1.3.0`
Package: `blender_to_sprites_batch_exporter/`

## Status

Stage 2 complete: the monolith is split into a package of five modules without
behavior changes. All function and class definitions were moved verbatim; the
AST comparison found no differences. The old single file 1.2.1 is preserved in
`legacy/`.

The smoke test could not run in Blender at that time: `blender` was missing from
the environment. Instead, static checks were run, the package was imported with
`bpy` stubs, and pure functions were covered by unit tests. Blender was
installed later and the smoke test passed; see `reports/STAGE_03_REPORT.md`.

## R1.1–R1.6. Package structure

```
blender_to_sprites_batch_exporter/
  __init__.py        bl_info, registration, classes tuple
  properties.py      BTS_Settings and only bpy.props/PropertyGroup
  logic.py           paths, bounds, camera, isolation, nodes, state
  operators.py       bts.batch_export, preview, cleanup, restore, open folder
  ui.py              five sidebar panels
  blender_manifest.toml
```

- `logic.py` does not import `ui.py` and `operators.py`.
- `operators.py` imports the necessary functions and constants from `.logic`.
- `ui.py` imports only `DEPTH_CAPABLE`, `collect_file_outputs`,
`is_relative_unsaved`.
- `__init__.py` registers `BTS_Settings`, then operators, then panels;
`unregister` removes `bts_settings` and classes in reverse order.

## R1.7. Checking for no behavior changes

A temporary AST comparator was written that compared the source file 1.2.1 and
package:

- `missing: []` - not a single definition was lost;
- `extra: []` - there are no unnecessary definitions;
- `changed: []` - the source code of all 54 functions and classes matches
character by character (up to line breaks).

Additionally checked:

- `python -m py_compile` of all modules of the package, tests and legacy file - successful;
- import of package with stubs `bpy`/`mathutils` - successful;
- 11 classes registered in expected order;
- `bl_idname` operators and panels have not changed;
- the set of properties `BTS_Settings` has not changed (25 properties).

## R1.8. Unit tests

Added tests using the standard `unittest` library (without `pytest` and without Blender):

- `tests/test_logic_unit.py` - 17 tests:
  - `sanitize_filename`, `safe_join`, `ensure_slash`, `split_base`,
    `make_relative_slot`, `slot_path_is_absolute`, `unique_dirs`,
    `is_relative_unsaved`, `ensure_dir`, `prefix_new_files`;
  - `compute_frame`: axes, padding, square output, min/max, multiple, degenerate bounds.
- `tests/test_package_contract.py` - 5 tests:
  - `bl_info` version;
  - operator and panel `bl_idname` values;
  - `BTS_Settings` property set;
  - absence of UI/operator imports in `logic.py`.

Result: **22 tests, all pass**.

`tests/stub_bpy.py` - minimal `bpy` and `mathutils` stubs for unit tests only.
They are not used in Blender.

## R1.9. Blender Extension and packaging

- Added `blender_manifest.toml`:
- `id = "blender_to_sprites_batch_exporter"`;
- `version = "1.3.0"`;
- `blender_version_min = "5.2.0"`;
- `license = ["SPDX:GPL-3.0-or-later"]`.
- Added `tools/build_zip.ps1`: builds
  `dist/blender_to_sprites_batch_exporter-1.3.0.zip` with the top-level
  package folder, excluding `__pycache__` and `*.pyc`.
- Verified the archive contents: the manifest and all five modules are present.

## R1.10. Version and documentation

- Version raised to `1.3.0` in `bl_info` and in the manifest.
- `CHANGELOG.md` updated with the 1.3.0 section.
- `README.md` describes installation as a legacy add-on and as an Extension,
  the package structure, tests and limitations.
- `legacy/README.md` explains that the old file must not be installed alongside
  the package.

## Verification

| Check | Result |
|---|---|
| `py_compile` all modules | OK |
| AST comparison with 1.2.1 | 54 definitions, no differences |
| Package import with stubs | OK, 11 classes |
| Unit tests | 22/22 OK |
| Zip build | OK, 1.3.0 |
| Blender 5.2 smoke test | pending at the time (passed in stage 3) |

## Limitations and risks

- Importing with stubs does not replace real registration in Blender:
you need to check the installation of the package and enable/disable the addon.
- `blender_manifest.toml` requires license confirmation. It currently specifies
  GPL-3.0-or-later as typical for Blender addons; if necessary
  replace with the actual project license.
- Old `.py` moved to `legacy/`; if someone needs it as a separate
file, it can be taken from the `v1.2.0-baseline` tag or from the git history.

## Next step

Stage 3: predictable paths and overwrite policy, node checks, advanced
render state, `Keep Lights` and scene-root objects. Before starting,
the smoke test must be run in Blender 5.2 on the package version.
