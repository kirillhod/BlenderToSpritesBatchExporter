# Blender To Sprites Batch Exporter

Addon for Blender 5.2, which renders scene collections into separate sprites
with an automatically adjusted orthographic camera.

## Features

- Batch rendering of selected collections.
- Automatic fitting of the orthographic camera to the collection bounds.
- Isolation through `Exclude` collections or `hide_render` objects.
- Support for compositor File Output nodes.
- Settings for resolution, padding, format and transparency.
- Saving and restoring the scene state after export.

## Installation

### As a legacy add-on

1. Copy the entire `blender_to_sprites_batch_exporter` folder into the Blender
   add-ons directory:
   `scripts/addons/blender_to_sprites_batch_exporter/`.
2. Enable the add-on in `Edit > Preferences > Add-ons`.
3. The panel appears in `View3D > Sidebar (N) > Batch Export`.

### As a Blender Extension

Build the zip:

```powershell
./tools/build_zip.ps1
```

The archive appears in `dist/`. Install it through
`Edit > Preferences > Get Extensions > Install from Disk`.

## Structure

```
blender_to_sprites_batch_exporter/
  __init__.py        registration and bl_info
  properties.py      scene.bts_settings
  logic.py           paths, camera, bounds, isolation, nodes, state
  operators.py       bts.* operators
  ui.py              sidebar panels
```

The old single file version 1.2.1 is saved in `legacy/` only as a reference.
Do not install it at the same time as the package.

## Tests

Pure function unit tests do not require Blender:

```powershell
./tests/run_unit_tests.ps1
```

Smoke test requires Blender 5.2:

```powershell
./tests/run_tests.ps1
./tests/run_tests.ps1 -StrictCamera
```

`-StrictCamera` checks that the user camera named
`_BTS_OrthoCamera` is not reused or deleted.

## Compatibility

- Blender: 5.2.
- Operator `bl_idname` values and `scene.bts_settings` properties are preserved.
- Scenes created in 1.2.x open without settings migration.

## Limitations of the current version

- Files are currently overwritten without a separate policy.
- Long exports cannot be cancelled.
- Preview and export share a temporary camera object marked with
  `bts_owned_camera`.
