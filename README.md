# Blender To Sprites Batch Exporter

Turn Blender collections into individual sprite images.

The add-on frames each collection with an orthographic camera, renders it
alone, and saves it as a separate file. It is made for 2D games, pixel art,
isometric assets and any workflow that needs many clean renders.

## Features

- One sprite per collection, framed automatically.
- Checkbox list of collections with All, None and Active buttons.
- Separate **Always Include** list for lights, props or shared parts.
- Transparent background, padding, pixel scale and square output.
- PNG, JPEG, WebP, EXR and other main-render formats.
- Optional File Output node support:
  - Image nodes (PNG, JPEG, ...)
  - Multilayer EXR nodes
- Names built from the collection and the File Output socket: `Body_Normal.png`.
- Path preview and a Problems panel before rendering.
- Overwrite existing files by default. Ask, Error, Skip and Add Suffix are
  also available.
- Built-in presets and your own JSON presets with descriptions.
- Export report and log.

## Requirements

- Blender 5.2.

## Installation

1. Open the
   [latest release](https://github.com/kirillhod/BlenderToSpritesBatchExporter/releases/latest).
2. Download the `.zip` file. Do not unpack it.
3. In Blender open **Edit > Preferences > Get Extensions**.
4. Click **Install from Disk** and choose the downloaded zip.
5. Enable **Blender To Sprites Batch Exporter**.
6. In the 3D View press **N** and open the **Batch Export** tab.

If an older version is already installed, remove it before installing the new
one.

## Quick start

1. Put each sprite in its own collection.
2. In **Batch Export > Collections**, tick the collections you want.
3. Choose an **Output Directory**.
4. Set **Pixels / Unit**, **Padding** and **Filter Size**.
5. Press **Analyze** to check paths and problems.
6. Press **Batch Export**.

## Pixel art

- **Filter Size**: use `0.01-0.1` for crisp pixels. Blender's default `1.5`
  softens small details.
- **Transparent Film**: keep it on when sprites need alpha.
- **Pixels / Unit**: controls the final sprite size.
- **Padding**: keeps sprites away from the image edge.
- **Round To Multiple Of**: helps keep sprite sizes consistent.

## Output names

Normal renders use the collection name:

```text
Body.png
```

File Output nodes use the collection and the node's socket name:

```text
Body + socket Normal -> Body_Normal.png
Body + empty socket  -> Body.png
```

Node names and labels are not used. If a node has several sockets, each socket
gets its own file.

## Output modes

- **Main render** - one file per collection in the selected format.
- **File Output nodes** - the compositor writes the files. Set the node's
  **Media Type** to **Image** for PNG or JPEG, or to **Multi-Layer EXR** for
  layered files. Enable **Also Save Main Render** if you want both.

## Notes

- **Don't Modify** is a manual single-collection mode.
- Cancel stops between collections; the render that is already running
  finishes first.
- Multi-view and 4/6-direction presets are planned for the next version.

## For developers

The add-on code is in `blender_to_sprites_batch_exporter/`.

- Unit tests: `./tests/run_unit_tests.ps1`
- Blender smoke test: `./tests/run_tests.ps1`
- Release zip: `./tools/build_zip.ps1`
