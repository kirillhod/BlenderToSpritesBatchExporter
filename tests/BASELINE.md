# Baseline: version 1.2.0 behavior

Date: 2026-11-10
Add-on version: 1.2.0
File: `blender_to_sprites_batch_exporter.py`

> Historical reference. This document describes the expected 1.2.0 behavior
> that later stages were compared against. See `reports/STAGE_03_REPORT.md` and
> the later reports for the current verification results.

## Smoke test scene

- Collection `Body` - a 1×1×1 cube at the origin.
- Collection `Weapon` - a 0.5×0.5×0.5 cube with an offset.
- Collection `EmptyCollection` - no objects.
- Collection `Lights` - a point light.
- User camera `MyCamera` (in strict mode, named `_BTS_OrthoCamera`).
- One object in `Body` has `hide_render = True`.
- Render engine: Workbench.

## Expected 1.2.0 behavior

- Files `Body.png` and `Weapon.png` are created.
- `EmptyCollection` and `Lights` are skipped as collections without renderable geometry.
- User camera `MyCamera` is not changed or deleted.
- Temporary camera `_BTS_OrthoCamera` is created and deleted after export.
- Resolution, format, `film_transparent`, `resolution_percentage` are restored.
- Collection `exclude` states and object `hide_render` states are restored.
- In strict mode (`BTS_STRICT_CAMERA=1`), a user camera named
  `_BTS_OrthoCamera` must remain untouched. This is an **expected failure**
  for version 1.2.0 and the target of hotfix 1.2.1.

## How to run

```powershell
./tests/run_tests.ps1
./tests/run_tests.ps1 -StrictCamera
```

```sh
BLENDER_EXE=/path/to/blender ./tests/run_tests.sh
```

## Execution status

This baseline was written before Blender was installed in the development
environment, so the first run was pending at that time. The smoke test was
later executed in Blender 5.2.3 LTS: the base and strict-camera scenarios both
pass. See `reports/STAGE_03_REPORT.md` for the first verified run and the later
stage and hotfix reports for the current state.
