# Baseline: version 1.2.0 behavior

Date: 2026-11-10
Add-on version: 1.2.0
File: `blender_to_sprites_batch_exporter.py`

## Smoke test scene

- Collection `Body` - a 1×1×1 cube at the origin.
- Collection `Weapon` - a 0.5×0.5×0.5 cube with an offset.
- Collection `EmptyCollection` - no objects.
- Collection `Lights` - a point light.
- User camera `MyCamera` (in strict mode, named `_BTS_OrthoCamera`).
- One object in `Body` has `hide_render = True`.
- Render engine: Workbench (Blender is not available in the current environment; the test has not been run).

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

Blender is not installed in the development environment (`blender` is not in
PATH or in the standard installation directories). The smoke test is written
and syntax-checked but has not been run. It must be run in Blender 5.2 before
releasing the hotfix.
