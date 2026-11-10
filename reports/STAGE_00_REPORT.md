# Report: stage 0 - preparation and baseline

Date: 2026-11-10
Branch: `feature/improvements-v2`
Baseline tag: `v1.2.0-baseline`

## Status

Stage 0 is partially complete: the branch, baseline tag, smoke harness and
documentation are prepared. Running the smoke test in Blender was not possible
at that time: `blender` was not found in PATH or the standard installation
directories. Blender was installed later and the smoke test passed; see
`reports/STAGE_03_REPORT.md`.

## What was done

1. Created branch `feature/improvements-v2`.
2. Tagged the baseline commit (`Export overhaul`) as `v1.2.0-baseline`.
3. Added smoke test `tests/smoke_blender.py`:
   - creates two collections with geometry, an empty collection, a light and a camera;
   - runs `bts.batch_export`;
   - checks file names and presence;
   - checks restoration of camera, resolution, format, `exclude` and `hide_render`;
   - checks removal of the temporary camera;
   - supports the strict case with a user camera named `_BTS_OrthoCamera`
     through `BTS_STRICT_CAMERA=1` (hotfix 1.2.1 target).
4. Added launchers:
   - `tests/run_tests.ps1` (Windows, looks for `BLENDER_EXE` and standard paths);
   - `tests/run_tests.sh` (Linux/macOS).
5. Added `tests/BASELINE.md` with the expected 1.2.0 behavior and the known
   failing camera case.

## Verification

> Historical note: this section records the state at the end of stage 0.
> Blender was installed later and the smoke test passed in Blender 5.2.3 LTS;
> see `reports/STAGE_03_REPORT.md`.

- `python -m py_compile blender_to_sprites_batch_exporter.py tests/smoke_blender.py` - passed.
- Blender smoke test - pending at the time: Blender was not installed.
- `pytest` - not installed at the time; unit tests were added in stage 2.

## Repository notes

- Empty directories found: `blender_to_sprites/compositor`,
  `blender_to_sprites/operators`, `blender_to_sprites/ui`, `blender_to_sprites/utils`.
  They are not tracked by git and were not changed.
- `__pycache__` from `py_compile` remains in the root; it is ignored by `.gitignore`.
- `README.md` is still almost empty; documentation will be updated
  step by step.

## Next step

Stage 1: hotfix 1.2.1 - temporary camera ownership and safe `hide_render`
writes. After this, the strict camera smoke case must pass.
