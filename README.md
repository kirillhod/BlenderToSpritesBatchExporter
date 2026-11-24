<h1 align="center">Blender To Sprites Batch Exporter</h1>

<p align="center">
  Turn Blender collections into individual sprite images with an auto-fitted
  orthographic camera.
</p>

<p align="center">
  <a href="https://github.com/kirillhod/BlenderToSpritesBatchExporter/releases">
    <img alt="Latest release" src="https://img.shields.io/github/v/release/kirillhod/BlenderToSpritesBatchExporter?sort=semver&label=release">
  </a>
  <a href="https://docs.blender.org/manual/en/5.2/">
    <img alt="Blender 5.2 or newer" src="https://img.shields.io/badge/Blender-5.2%2B-orange">
  </a>
  <a href="LICENSE">
    <img alt="License: GPL-3.0-or-later" src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue">
  </a>
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#requirements">Requirements</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#collections">Collections</a> ·
  <a href="#preview">Preview</a> ·
  <a href="#canvas-grid">Canvas Grid</a> ·
  <a href="#presets">Presets</a> ·
  <a href="#license">License</a>
</p>

---

The add-on frames each
[collection](https://docs.blender.org/manual/en/5.2/scene_layout/collections/index.html)
with an
[orthographic camera](https://docs.blender.org/manual/en/5.2/render/cameras.html),
renders it alone and saves it as a separate file. It is made for 2D games,
pixel art, isometric assets and any workflow that needs many clean renders.

Blender terms in this guide link to the
[official Blender 5.2 Manual](https://docs.blender.org/manual/en/5.2/).

## Features

| Feature | What it does |
| --- | --- |
| **One sprite per collection** | Frames each collection automatically and saves one file per selected view. |
| **Multi-view** | Top, bottom, front, back, right and left views; all selected views share one canvas and one orthographic scale per collection. |
| **Collections list** | Checkbox table with All, None, Active and Activate. It follows collection creation, deletion and renaming without a manual refresh. |
| **Per-collection overrides** | View, Framing and Resolution can be overridden for one collection without touching the global settings. |
| **Always Include** | A separate list for lights, props or shared parts that stay visible in every render. |
| **Output control** | Transparent background, padding, pixel scale, square output, and min and max resolution. |
| **Formats** | PNG, JPEG, WebP, EXR and other [main-render formats](https://docs.blender.org/manual/en/5.2/render/output/properties/format.html). |
| **File Output nodes** | [Image](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html) and [Multi-Layer EXR](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html) nodes. |
| **Naming** | `{collection}` and `{axis}` templates; File Output names add the socket, for example `Body_front_Normal.png`. |
| **Viewport preview** | Fits the 3D View to the selected collection in camera view, without rendering. |
| **Canvas grid** | Output-pixel grid with an adaptive step, a center cross and the canvas resolution. |
| **Preflight and log** | Path preview, Problems panel, export report and log before and after rendering. |
| **Presets** | Built-in 4 and 6 directions plus custom JSON presets with descriptions. |
| **Overwrite policy** | Overwrite by default; Ask, Error, Skip and Add Suffix are also available. |

## Requirements

| | |
| --- | --- |
| **Blender** | 5.2 or newer. Tested with 5.2.3 LTS and 5.3. |
| **Add-on** | Install the latest zip from the [Releases page](https://github.com/kirillhod/BlenderToSpritesBatchExporter/releases). |
| **License** | GPL-3.0-or-later; free to use, including in commercial projects. |

## Installation

1. Open the
   [Releases page](https://github.com/kirillhod/BlenderToSpritesBatchExporter/releases)
   and download the latest `.zip` file. Do not unpack it.
2. In Blender open **Edit > Preferences** and click
   [**Get Extensions**](https://docs.blender.org/manual/en/5.2/editors/preferences/extensions.html).
3. Click **Install from Disk** and choose the downloaded zip.
4. Enable **Blender To Sprites Batch Exporter**.
5. In the 3D View press <kbd>N</kbd> and open the **Batch Export** tab in the
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

| Mode | Shows |
| --- | --- |
| **All Collections** | Every collection in the scene. |
| **Only Included** | Collections that are not excluded from the view layer. |
| **Active Collection** | The collection selected in the Outliner. |
| **Top-Level Only** | Collections directly under the scene collection. |

The full target registry and its enabled flags are kept when the mode changes,
so switching back restores the previous selection. Selecting a collection in
the Outliner also selects its target row, and selecting a target row selects
that collection in the Outliner.

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

### Preview

Select a collection and click **Preview** in **Collections** to switch the 3D
View to camera view for that collection. The preview uses the same canvas,
camera and overrides as the export, and it updates when you select another
target row, toggle a view or change a framing or resolution value. Changes apply
immediately. The Outliner stays on the previewed collection. A target that is
hidden in the Outliner is shown while it is previewed; its hide state returns on
exit.

> **Preview is a viewport mode, not a render.** It uses the current viewport
> shading and writes no files. Switch the viewport to **Material Preview** or
> **Rendered** to see materials.

When a collection has several views, Preview shows the first active view in the
Top, Bottom, Front, Back, Right, Left order. Click **Exit Preview** or leave
camera view to restore the scene camera, resolution and visibility. Starting an
export exits Preview first, so the preview camera and hidden collections do not
reach the rendered frames.

### Canvas Grid

Turn on **Canvas Grid** next to **Preview** in **Collections** to draw the
orthographic camera canvas as a grid in camera view. The outer frame is the
output canvas, its resolution is shown in a badge above the top-left corner of
the frame, lines snap to output pixels and the step grows as you zoom out. In
Preview it follows the active collection's canvas and overrides. It is a
viewport guide and is not rendered.

### Per-collection overrides

Select a target row to open its **View**, **Framing** and **Resolution**
override groups below the list. Each group is a checkbox row; turning it on
opens a collapsible section with the checkbox in the header.

| Group | Overrides |
| --- | --- |
| **View** | The six view toggles. |
| **Framing** | Margin, Padding Mode and Padding. |
| **Resolution** | Pixels / Unit, Round To, Square Output, Min Res and Max Res. |

<details>
<summary><strong>Override rules</strong></summary>

- A target with any active override shows the override marker in the list.
- A group that is off uses the global value and draws no fields.
- Turning a group on copies the current global values once. Later changes to
  the global settings do not affect that collection.
- Turning the group off and on again copies the current global values again.
- Output directory, format, naming, overwrite policy, isolation, Always Include
  and node settings stay global.
- Overrides belong to the target. Renaming a collection is treated as delete
  plus add, so the new name starts with defaults.

</details>

## Pixel art

| Setting | Tip |
| --- | --- |
| [Filter Size](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html) | Use `0.01-0.1` for crisp pixels. Blender's default `1.5` softens small details. |
| [Transparent Film](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html) | Keep it on when sprites need alpha. |
| **Pixels / Unit** | Controls the final sprite size. |
| **Padding** | Keeps sprites away from the image edge. |
| **Round To Multiple Of** | Helps keep sprite sizes consistent. |

## Presets

Built-in presets change global settings. The framing presets do not touch the
output directory, naming or file format. Collections with an active override
keep their override values.

| Preset | Settings | Best for |
| --- | --- | --- |
| **4 Directions** | Front, back, right and left views; `{collection}_{axis}` names | Characters and props with four sides |
| **6 Directions** | All six views; `{collection}_{axis}` names | Full turntable-style sprite sets |
| **Pixel Art Top** | Top view, 32 px per unit, 1 px padding, square sprites | Crisp top-down tiles |
| **Platformer Front** | Front view, 64 px per unit, 2 px padding | Side-view characters and props |
| **High Resolution Top** | Top view, 128 px per unit, 8 px padding | Detailed top-down art |

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

| Mode | Writes |
| --- | --- |
| **Main render** | One file per collection and selected view in the chosen format. |
| [**File Output nodes**](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html) | The compositor writes the files. Set the node's Media Type to **Image** for PNG or JPEG, or to **Multi-Layer EXR** for layered files. Enable **Also Save Main Render** to write both. |

## Notes

- **Don't Modify** is a manual single-collection mode.
- Cancel stops between collections; the render that is already running finishes
  first.

## For developers

The add-on code is in `blender_to_sprites_batch_exporter/`.

```powershell
./tests/run_unit_tests.ps1      # unit tests, Blender-free
./tests/run_tests.ps1           # Blender smoke suite
./tools/build_zip.ps1           # release zip
```

## License

This add-on is licensed under the
[GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0.html).
See [LICENSE](LICENSE) for the full text.

You can use it for free, including in commercial projects. If you share a
modified version, it must stay under the same license.

---

<p align="center">
  <a href="https://github.com/kirillhod/BlenderToSpritesBatchExporter/releases/latest">
    <strong>Download the latest release</strong>
  </a>
</p>
