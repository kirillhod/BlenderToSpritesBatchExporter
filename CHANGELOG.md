# Changelog

All notable changes to the project. Versions follow semantic versioning.

## [Unreleased]

### Added
- Documentation of the improvement plan and detailed implementation sequence.
- Smoke test `tests/smoke_blender.py` and launchers for Windows/POSIX.

## [1.3.0] - 2026-11-10

### Changed
- The add-on is split into a package of five modules: `__init__.py`, `properties.py`,
  `logic.py`, `operators.py`, `ui.py`. Operator `bl_idname` values and
  `scene.bts_settings` properties are unchanged.
- The single-file 1.2.1 version has been moved to `legacy/` as a reference and
  must not be installed alongside the package.
- Added `blender_manifest.toml`, `tools/build_zip.ps1` and a README with two
  installation methods.

### Added
- Unit tests for pure path and framing functions using the standard `unittest`;
  they run without Blender.
- Launchers `tests/run_unit_tests.ps1` and `tests/run_unit_tests.sh`.

## [1.2.1] - 2026-11-10

Hotfix based on the analysis of version 1.2.0.

### Fixed
- The temporary camera is now marked with the custom property `bts_owned_camera`.
  The add-on no longer reuses or deletes a user camera named
  `_BTS_OrthoCamera`; on a name conflict, Blender creates an object with a suffix.
- `remove_camera()` removes only cameras owned by the add-on and clears their
  data only when `users == 0`.
- The original scene camera is restored correctly, including when there was no
  camera before export or when `auto_cleanup_camera` is disabled.
- Writing `hide_render` no longer crashes on linked/override objects.
  Failed attempts are collected and reported in one aggregated warning; the
  remaining objects are processed and the state is restored.

## [1.2.0] - baseline

- Initial version before the improvement plan. Tagged `v1.2.0-baseline`.
