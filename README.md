# Blender To Sprites Batch Exporter

Addon for Blender 5.2, which renders scene collections into separate sprites
with an automatically adjusted orthographic camera.

## Features

- Per-collection selection list with checkboxes, search, All/None/Active,
  status, and a separate Always Include list.
- Batch rendering of selected collections.
- Automatic fitting of the orthographic camera to the collection bounds.
- Isolation through `Exclude` collections or `hide_render` objects.
- Automatic inclusion of light collections in Exclude mode and hiding of
  scene-root objects outside the target.
- Support for compositor File Output nodes, including connected-node filtering
  and linked-library protection.
- File Output files are named after the collection and the node socket
  (`<Collection>_<socket>.exr` by default); node names and labels are ignored.
- Predictable output names with collision detection and the overwrite policies
  Overwrite (default), Ask, Error, Skip and Add Suffix, including File Output
  node paths. Overwrite simply replaces existing files.
- Settings for resolution, padding, format and transparency, with format-aware
  color validation.
- Preflight analysis with a grouped problem panel, path preview and a dedicated
  Analyze button.
- Cancellable batch export between collections, with reliable scene restoration.
- Built-in presets with descriptions, plus JSON preset save/load with a custom
  description stored in the file.
- A report panel with the written files, copy, log and output-folder actions.
- Saving and restoring the scene state after export, including border, stamp
  and compositor settings, followed by a verification pass.

## Installation

### As a legacy add-on

1. Copy the entire `blender_to_sprites_batch_exporter` folder into the Blender
   user add-ons directory, for example:
   - Windows: `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\`
   - Linux: `~/.config/blender/5.2/scripts/addons/`
   - macOS: `~/Library/Application Support/Blender/5.2/scripts/addons/`
2. Enable the add-on in `Edit > Preferences > Add-ons`.
3. The panel appears in `View3D > Sidebar (N) > Batch Export`.

### As a Blender Extension

Build the zip:

```powershell
./tools/build_zip.ps1
```

The archive appears in `dist/`. Install it through
`Edit > Preferences > Get Extensions > Install from Disk` and select the zip
file. The archive can also be checked and installed from the command line:

```powershell
blender --command extension validate dist/blender_to_sprites_batch_exporter-2.0.2.zip
blender --command extension install-file dist/blender_to_sprites_batch_exporter-2.0.2.zip -r user_default --enable
```

Do not install the legacy folder and the Extension at the same time: both
provide the same `bl_idname` values and `scene.bts_settings`.

## Structure

```
blender_to_sprites_batch_exporter/
  __init__.py        registration and bl_info
  properties.py      scene.bts_settings
  logic.py           compatibility facade for core/*
  core/
    common.py        constants, paths, image format rules
    output.py        path planning, File Output nodes, overwrite policies
    scene.py         collections, bounds, isolation, state restoration
    framing.py       camera framing and temporary camera ownership
    targets.py       target lists, migration, Always Include
    presets.py       built-in and JSON presets
    job.py           preflight, analysis cache, BatchJob, cancellation
  operators.py       bts.* operators
  ui.py              sidebar panels and collection lists
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
- Operator `bl_idname` values and the existing `scene.bts_settings` fields are
  preserved. The obsolete Emergency Prefix Rename flag was removed.
- Old `keep_collections`, `export_source` and `node_naming` values are migrated
  once into the new lists and layout marker.
- Scenes created in 1.2.x open without losing their settings.

## Limitations of the current version

- File Output node mode writes multilayer EXR files in Blender 5.2. Use the main
  render path for PNG, JPEG or WebP sprites.
- In node mode, Automatic writes `<Collection>_<socket>.exr`. Collection Folder
  writes `<Collection>/<socket>.exr`. The node name and label are not used.
- `Don't Modify` is a manual single-collection mode. Multi-collection exports
  are rejected because one compositor tree cannot route every collection to a
  different file.
- Cancellation is checked between collections; the collection that is already
  rendering finishes first.
- Multi-view selection and its 4/6 presets arrive in 2.1. The current presets
  cover single-view top/front setups.
- The analysis cache may show a previous path preview until Analyze is run
  again after changing export settings.
- Preview and export share a temporary camera object marked with
  `bts_owned_camera`.
