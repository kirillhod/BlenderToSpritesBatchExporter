# Blender To Sprites Batch Exporter

Turn Blender collections into individual sprite images.

The add-on frames each
[collection](https://docs.blender.org/manual/en/5.2/scene_layout/collections/index.html)
with an
[orthographic camera](https://docs.blender.org/manual/en/5.2/render/cameras.html),
renders it alone, and saves it as a separate file. It is made for 2D games,
pixel art, isometric assets and any workflow that needs many clean renders.

Blender terms in this guide link to the
[official Blender 5.2 Manual](https://docs.blender.org/manual/en/5.2/).

## Features

- One sprite per
  [collection](https://docs.blender.org/manual/en/5.2/scene_layout/collections/index.html),
  framed automatically.
- Checkbox list of collections with All, None and Active buttons.
- Separate **Always Include** list for lights, props or shared parts.
- Transparent background, padding, pixel scale and square output.
- PNG, JPEG, WebP, EXR and other
  [main-render formats](https://docs.blender.org/manual/en/5.2/render/output/properties/format.html).
- Optional
  [File Output node](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html)
  support:
  - [Image](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html)
    nodes (PNG, JPEG, ...)
  - [Multi-Layer EXR](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html)
    nodes
- Names built from the collection and the File Output socket:
  `Body_Normal.png`.
- Path preview and a Problems panel before rendering.
- Overwrite existing files by default. Ask, Error, Skip and Add Suffix are
  also available.
- Built-in presets and your own JSON presets with descriptions.
- Export report and log.

## Requirements

- Blender 5.2.

## Installation

1. Open the
   [Releases page](https://github.com/kirillhod/BlenderToSpritesBatchExporter/releases)
   and download the latest `.zip` file. Do not unpack it.
2. In Blender open **Edit > Preferences** and click
   [**Get Extensions**](https://docs.blender.org/manual/en/5.2/editors/preferences/extensions.html).
3. Click **Install from Disk** and choose the downloaded zip.
4. Enable **Blender To Sprites Batch Exporter**.
5. In the 3D View press **N** and open the **Batch Export** tab in the
   [Sidebar](https://docs.blender.org/manual/en/5.2/editors/3dview/sidebar.html).

If an older version is already installed, remove it before installing the new
one.

## Quick start

1. Put each sprite in its own collection.
2. In the **Batch Export** tab, open
   [**Collections**](https://docs.blender.org/manual/en/5.2/scene_layout/collections/index.html)
   and tick the collections you want.
3. Choose an **Output Directory**.
4. Set **Pixels / Unit**, **Padding** and **Filter Size**.
5. Press **Analyze** to check paths and problems.
6. Press **Batch Export**.

## Pixel art

- [Filter Size](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html):
  use `0.01-0.1` for crisp pixels. Blender's default `1.5` softens small
  details.
- [Transparent Film](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html):
  keep it on when sprites need alpha.
- **Pixels / Unit**: controls the final sprite size.
- **Padding**: keeps sprites away from the image edge.
- **Round To Multiple Of**: helps keep sprite sizes consistent.

## Output names

Normal renders use the collection name:

```text
Body.png
```

[File Output nodes](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html)
use the collection and the node's socket name:

```text
Body + socket Normal -> Body_Normal.png
Body + empty socket  -> Body.png
```

Node names and labels are not used. If a node has several sockets, each socket
gets its own file.

## Output modes

- **Main render** - one file per collection in the selected format.
- [**File Output nodes**](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html) -
  the compositor writes the files. Set the node's
  [Media Type](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html)
  to **Image** for PNG or JPEG, or to
  [**Multi-Layer EXR**](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html)
  for layered files. Enable **Also Save Main Render** if you want both.

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
