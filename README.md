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
- Multi-view export from top, bottom, front, back, right and left, with one
  shared canvas per collection.
- Checkbox list of collections with All, None and Active buttons.
- Per-collection framing, resolution and view overrides for different asset
  scales and directions.
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
- Names built from the collection, the view axis and the File Output socket:
  `Body_front_Normal.png`.
- Path preview and a Problems panel before rendering.
- Overwrite existing files by default. Ask, Error, Skip and Add Suffix are
  also available.
- Built-in presets, including 4 and 6 directions, and your own JSON presets
  with descriptions.
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
3. In **Camera & Framing**, choose one or more views.
4. Choose an **Output Directory**.
5. Set **Pixels / Unit**, **Padding** and **Filter Size**.
6. Press **Analyze** to check paths and problems.
7. Press **Batch Export**.

## Collections

The target list follows the scene automatically. New collections appear and
deleted collections disappear without pressing anything. Renaming a collection
is treated as a delete plus an add, so the new name starts with default values.
Enabled flags and per-collection settings survive a sync. **Refresh Targets** is
only a manual fallback.

The **Export** menu filters both the visible list and the actual export:
**All Collections**, **Only Included**, **Active Collection** and
**Top-Level Only**. The full target registry and its enabled flags are kept when
the mode changes, so switching back restores the previous selection.
**Active Collection** shows only the collection selected in the Outliner.
Selecting a collection in the Outliner also selects its target row, and selecting
a target row selects that collection in the Outliner.

After **Analyze**, each row shows the canvas that will be produced, for example
`512x304` or `512x512, 4 views`. The row is empty before an analysis and after
any setting change that invalidates it. World-unit bounds are not shown.

### Views

**Camera & Framing** shows six toggle buttons in a 3x2 grid: Top, Bottom,
Front, Back, Right and Left. Select any combination. All selected views of one
collection share the largest canvas and the same orthographic scale, so a wide
side view does not produce a smaller sprite. The legacy **View Axis** value is
kept for old presets and scripts but is no longer shown.

At least one view is required for every target. An empty set blocks the export
in preflight.

### Per-collection overrides

Select a target row to open its **View**, **Framing** and **Resolution**
override groups below the list. Each group is a collapsible section with its
checkbox in the header.

- **View** overrides the six view toggles.
- **Framing** overrides Camera Distance Margin, Padding Mode and Padding.
- **Resolution** overrides Pixels / Unit, Round To Multiple Of, Square Output,
  Min Res and Max Res.
- A group that is off uses the global value and draws no fields.
- Turning a group on copies the current global values once. Later changes to
  the global settings do not affect that collection.
- Turning the group off and on again copies the current global values again.
- Output directory, format, naming, overwrite policy, isolation, Always Include
  and node settings stay global.

Overrides belong to the target. Renaming a collection is treated as delete plus
add, so the new name starts with defaults.

## Pixel art

- [Filter Size](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html):
  use `0.01-0.1` for crisp pixels. Blender's default `1.5` softens small
  details.
- [Transparent Film](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html):
  keep it on when sprites need alpha.
- **Pixels / Unit**: controls the final sprite size.
- **Padding**: keeps sprites away from the image edge.
- **Round To Multiple Of**: helps keep sprite sizes consistent.

## Presets

Built-in presets change global settings. The framing presets do not touch the
output directory, naming or file format. Collections with an active override
keep their override values.

| Preset | Settings | Best for |
|---|---|---|
| 4 Directions | Front, back, right and left views; `{collection}_{axis}` names | Characters and props with four sides |
| 6 Directions | All six views; `{collection}_{axis}` names | Full turntable-style sprite sets |
| Pixel Art Top | Top view, 32 px per unit, 1 px padding, square sprites | Crisp top-down tiles |
| Platformer Front | Front view, 64 px per unit, 2 px padding | Side-view characters and props |
| High Resolution Top | Top view, 128 px per unit, 8 px padding | Detailed top-down art |

## Output names

Normal renders use the **Name Template**. It supports `{collection}` and
`{axis}`:

```text
One view:      {collection}           -> Body.png
Several views: {collection}_{axis}    -> Body_front.png
```

If several views are selected and the template has no `{axis}`, the add-on
appends `_{axis}` and reports it in Problems. Axis words are lowercase:
`top`, `bottom`, `front`, `back`, `right`, `left`. When only one view is
active, `{axis}` is omitted with its separator, so `{collection}_{axis}`
writes `Body.png` for a single-view run.

Unknown tokens, padding on string tokens, empty names and two targets that
resolve to the same file block the export before rendering.

[File Output nodes](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html)
use the same resolved stem and the node's socket name:

```text
Body, socket Normal        -> Body_Normal.png
Body_front, socket Normal  -> Body_front_Normal.png
Body, empty socket         -> Body.png
```

Node names and labels are not used. If a node has several sockets, each socket
gets its own file.

## Output modes

- **Main render** - one file per collection and selected view in the chosen
  format.
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

## For developers

The add-on code is in `blender_to_sprites_batch_exporter/`.

- Unit tests: `./tests/run_unit_tests.ps1`
- Blender smoke test: `./tests/run_tests.ps1`
- Release zip: `./tools/build_zip.ps1`

## License

This add-on is licensed under the
[GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).
See [LICENSE](LICENSE) for the full text.

You can use it for free, including in commercial projects. If you share a
modified version, it must stay under the same license.
