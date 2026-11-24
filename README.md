<h1 align="center">Blender To Sprites Batch Exporter</h1>

<p align="center"><a href="https://github.com/kirillhod/BlenderToSpritesBatchExporter/releases"><img alt="Latest release" src="https://img.shields.io/github/v/release/kirillhod/BlenderToSpritesBatchExporter?sort=semver&label=release"></a> <a href="https://docs.blender.org/manual/en/5.2/"><img alt="Blender 5.2 or newer" src="https://img.shields.io/badge/Blender-5.2%2B-orange"></a> <a href="LICENSE"><img alt="License: GPL-3.0-or-later" src="https://img.shields.io/badge/license-GPL--3.0--or--later-blue"></a></p>

<p align="center"><a href="#features">Features</a> · <a href="#requirements">Requirements</a> · <a href="#installation">Installation</a> · <a href="#quick-start">Quick start</a> · <a href="#collections">Collections</a> · <a href="#preview">Preview</a> · <a href="#canvas-grid">Canvas Grid</a> · <a href="#presets">Presets</a> · <a href="#license">License</a></p>

---

The add-on frames each
[collection](https://docs.blender.org/manual/en/5.2/scene_layout/collections/index.html)
with an
[orthographic camera](https://docs.blender.org/manual/en/5.2/render/cameras.html),
renders it alone and saves it as a separate file. It is made for 2D games,
pixel art, isometric assets and any workflow that needs many clean renders.

## Features

| Feature | What it does |
| --- | --- |
| **One sprite per collection** | Frames each collection automatically and saves one file per selected view. |
| **Multi-view** | Top, bottom, front, back, right and left; all selected views share one canvas and one orthographic scale per collection. |
| **Collections list** | Checkbox table with All, None, Active and Activate; it follows collection creation, deletion and renaming without a manual refresh. |
| **Always Include** | Keeps lights, props or shared parts visible in every render. |
| **Per-collection overrides** | View, Framing and Resolution can be overridden for one collection without touching the globals. |
| **Preview and canvas grid** | Camera-view preview of the selected collection and an output-pixel grid with the canvas resolution, both without rendering. |
| **Output** | Transparent background, padding, pixel scale, square output, and PNG, JPEG, WebP, EXR and other main-render formats. |
| **Naming and File Output** | `{collection}` and `{axis}` templates; Image and Multi-Layer EXR nodes add their socket name. |
| **Presets and preflight** | 4 and 6 direction presets, JSON presets, path preview, Problems, report and log. |
| **Overwrite policy** | Overwrite by default; Ask, Error, Skip and Add Suffix are also available. |

## Requirements

**Blender 5.2 or newer.** Tested with 5.2.3 LTS and 5.3.

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

## Quick start

1. Put each sprite in its own collection.
2. In the **Batch Export** tab, open
   [**Collections**](https://docs.blender.org/manual/en/5.2/scene_layout/collections/index.html)
   and tick the collections you want.
3. In **Camera & Framing**, choose one or more views.
4. Choose an **Output Directory** and set **Pixels / Unit**, **Padding** and
   **Filter Size**.
5. Press **Analyze** to check paths and problems.
6. Press **Batch Export**.

## Collections

The target list follows the scene automatically. New collections appear and
deleted collections disappear; renaming is treated as a delete plus an add.
Enabled flags and per-collection settings survive a sync. **Refresh Targets**
is only a manual fallback.

The **Export** menu filters both the visible list and the actual export:

| Mode | Shows |
| --- | --- |
| **All Collections** | Every collection in the scene. |
| **Only Included** | Collections that are not excluded from the view layer. |
| **Active Collection** | The collection selected in the Outliner. |
| **Top-Level Only** | Collections directly under the scene collection. |

The full target registry and its enabled flags are kept when the mode changes.
Selecting a collection in the Outliner also selects its target row, and
selecting a target row selects that collection in the Outliner.

After **Analyze**, each row shows the canvas that will be produced, for example
`512x304` or `512x512, 4 views`. The row is empty before an analysis and after
any setting change that invalidates it.

### Views

**Camera & Framing** shows six toggle buttons in a 3x2 grid: Top, Bottom,
Front, Back, Right and Left. All selected views of one collection share the
largest canvas and the same orthographic scale, so a wide side view does not
produce a smaller sprite. The legacy **View Axis** value is kept for old
presets and scripts but is no longer shown.

At least one view is required for every target. An empty set blocks the export
in preflight.

### Preview

Select a collection and click **Preview** in **Collections** to switch the 3D
View to camera view for that collection. It uses the same canvas, camera and
overrides as the export and updates when you select another target row, toggle
a view or change framing or resolution values. The Outliner stays on the
previewed collection; a target hidden in the Outliner is shown while previewed
and returns to its hide state on exit.

> **Preview is a viewport mode, not a render.** It uses the current viewport
> shading and writes no files. Switch to **Material Preview** or **Rendered**
> to see materials.

Preview shows the first active view in Top, Bottom, Front, Back, Right, Left
order. **Exit Preview** or leaving camera view restores the camera, resolution
and visibility. Starting an export exits Preview first.

### Canvas Grid

Turn on **Canvas Grid** next to **Preview** to draw the orthographic camera
canvas in camera view. The frame is the output canvas; its resolution is shown
in a badge above the top-left corner, lines snap to output pixels and the step
grows as you zoom out. In Preview it follows the active collection's canvas and
overrides. It is a viewport guide and is not rendered.

### Per-collection overrides

Select a target row to open its **View**, **Framing** and **Resolution**
groups. Each is a checkbox row that opens a collapsible section when on.

| Group | Overrides |
| --- | --- |
| **View** | The six view toggles. |
| **Framing** | Margin, Padding Mode and Padding. |
| **Resolution** | Pixels / Unit, Round To, Square Output, Min Res and Max Res. |

<details>
<summary><strong>Override rules</strong></summary>

- A group that is off uses the global value and draws no fields. Turning it on
  copies the global values once; turning it off and on copies them again.
- Output directory, format, naming, overwrite policy, isolation, Always Include
  and node settings stay global.

</details>

## Pixel art

| Setting | Tip |
| --- | --- |
| [Filter Size](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html) | Use `0.01-0.1` for crisp pixels. Blender's default `1.5` softens small details. |
| [Transparent Film](https://docs.blender.org/manual/en/5.2/render/eevee/render_settings/film.html) | Keep it on when sprites need alpha. |
| **Pixels / Unit** | Controls the final sprite size. |
| **Round To Multiple Of** | Helps keep sprite sizes consistent. |

## Presets

Built-in presets change global settings but not the output directory, naming or
file format. Collections with an active override keep their override values.

| Preset | Settings | Best for |
| --- | --- | --- |
| **4 Directions** | Front, back, right and left views; `{collection}_{axis}` names | Characters and props with four sides |
| **6 Directions** | All six views; `{collection}_{axis}` names | Full turntable-style sprite sets |
| **Pixel Art Top** | Top view, 32 px per unit, 1 px padding, square sprites | Crisp top-down tiles |
| **Platformer Front** | Front view, 64 px per unit, 2 px padding | Side-view characters and props |
| **High Resolution Top** | Top view, 128 px per unit, 8 px padding | Detailed top-down art |

## Output names

Normal renders use the **Name Template** with `{collection}` and `{axis}`:

```text
One view:      {collection}           -> Body.png
Several views: {collection}_{axis}    -> Body_front.png
```

Without `{axis}` in a multi-view run, the add-on appends `_{axis}` and reports
it in Problems. Axis words are lowercase: `top`, `bottom`, `front`, `back`,
`right`, `left`. With one active view, `{axis}` and its separator are omitted,
so `{collection}_{axis}` writes `Body.png`.

Unknown tokens, padding on string tokens, empty names and two targets that
resolve to the same file block the export before rendering.

File Output nodes use the resolved stem and the socket name:

```text
Body, socket Normal        -> Body_Normal.png
Body_front, socket Normal  -> Body_front_Normal.png
Body, empty socket         -> Body.png
```

Node names and labels are not used. Each socket of a node gets its own file.

## Output modes

| Mode | Writes |
| --- | --- |
| **Main render** | One file per collection and view in the chosen format. |
| [**File Output nodes**](https://docs.blender.org/manual/en/5.2/compositing/types/output/file_output.html) | The compositor writes Image or Multi-Layer EXR files through the node. Enable **Also Save Main Render** to write both. |

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

Licensed under [GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html).
See [LICENSE](LICENSE) for the full text.
