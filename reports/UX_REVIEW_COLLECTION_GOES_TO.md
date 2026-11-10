# UX review: File Output and "Collection Goes To"

Date: 2026-11-10
Scope: `scene.bts_settings.node_naming` and File Output nodes in Blender 5.2.3.
Status: stage 4 backend implemented in 1.4.0 (`NodeOutputPlan`, duplicate-token
guard, preflight node paths). The UI choices, default and path preview remain
in stage 5.

## 1. What the add-on does today

There are two output paths.

1. **Main render path** (no File Output nodes, or node usage disabled).
   For every collection the add-on calls `render(write_still=True)` with
   `filepath = <Output Directory>/<sanitized collection name>`. The result is
   `<Output Directory>/<Collection>.<ext>`.

2. **File Output node path** (`Use File Output Nodes` is enabled and at least
   one connected File Output node exists). Before each collection render the
   add-on rewrites node paths according to `Collection Goes To`.

In Blender 5.2.3 a File Output node writes **one multilayer EXR file per node**.
The file name comes from `node.file_name`. The entries in
`node.file_output_items` are **layer names inside that EXR**, not separate
files. This was confirmed with a probe scene:

```text
node.file_name = "MyFile", items = ["Sprite"]  ->  MyFile.exr
node.file_name = "Multi",  items = ["Beauty", "Mask"]  ->  Multi.exr
```

The current code still treats `file_output_items` as if they were output file
names. `PREFIX` mode renames both `node.file_name` and every layer name.

## 2. Current modes in practice

Assume one active File Output node with `node.file_name = "Sprite"` and a
collection named `Body`, and an output directory `sprites/`.

| Mode | Effective path | What actually happens |
|---|---|---|
| Main render path | `sprites/Body.png` | One sprite per collection. This is the familiar behavior. |
| `Subfolder` | `sprites/Body/Sprite.exr` | The collection name becomes a folder; the sprite file keeps the node name. Layer names are kept apart from path-separator sanitization. |
| `Filename Prefix` | `sprites/Body_Sprite.exr` | The collection name is prepended to the node file name. Layer names are also prefixed by the current code. |
| `Don't Modify` | node path + `Sprite.exr` | No paths change. Every collection writes the same files, so only a single-target run is safe. |

If the node is already named after the collection (`node.file_name = "Body"`),
`Filename Prefix` produces `Body_Body.exr` and prefixes every layer name with
`Body_`. That is the duplication the review is about.

## 3. Why the choices feel disconnected

- **`Subfolder` is a grouping mode, not a sprite naming mode.** It is useful
  when one render emits several files per collection (for example Beauty and
  Mask nodes) and the pipeline imports a folder as one sprite set. For a simple
  one-file-per-collection job it produces a folder plus an authored file name,
  which does not match the main render path.
- **`Filename Prefix` is only meaningful when the authored node name carries
  output identity** (`Sprite`, `Mask`, `Normal`). If the author already put the
  collection name into `node.file_name`, the prefix duplicates it. There is no
  duplicate-token check.
- **`Don't Modify` is an escape hatch, not a batch mode.** It is correct for a
  single manually configured collection, or for a hand-authored compositor.
  With several collections the same paths are overwritten. Stage 3 therefore
  rejects it for multi-target exports.
- **The missing mode is the obvious one:** with one File Output node and one
  output file per collection, the user expects
  `<Output Directory>/<Collection>.exr`, the same identity as the main render
  path. No current mode produces that.
- **Node mode is EXR-only in Blender 5.2.** The add-on file format selector is
  hidden when `Also Write Main Render` is off, but the Output panel does not say
  that the result will be a multilayer EXR. A user who expects PNG sprites is
  surprised.
- **There is no path preview.** The labels describe the implementation
  (`base/<Collection>/`, `base/<Collection>_<file>`) instead of showing the
  actual files. Users cannot see the duplication or the folder layout until
  after a render.

## 4. Usage scenarios

| # | User intent | Setup | Current result | Problem | Target behavior |
|---|---|---|---|---|---|
| S1 | One PNG sprite per collection | No nodes | `sprites/Body.png` | None | Keep unchanged |
| S2 | One EXR per collection through compositing | One File Output node, one output | `sprites/Body/Sprite.exr` by default | Folder and generic file name; not `Body.exr` | `sprites/Body.exr` with Automatic or Collection Name |
| S3 | Several outputs per collection (Beauty, Mask) | Two File Output nodes | `sprites/Body/Beauty.exr`, `sprites/Body/Mask.exr` | Subfolder works, but it is the default even for one output; Prefix is flat and also valid | Keep both layouts; Automatic selects Subfolder for several nodes; duplicate paths are preflighted |
| S4 | Manual compositor paths | One collection, `Don't Modify` | Authored paths | Correct only for one target | Keep as a single-target manual mode with a clear label |
| S5 | Node name already contains the collection | `node.file_name = "Body"`, Prefix | `Body_Body.exr`, layers `Body_*` | Duplicated identity; layer names changed | Detect the token and do not duplicate; leave layer names untouched |
| S6 | Linked File Output node | Node group from a library | Warning; node skipped | Correct | Keep; mark in the path preview |
| S7 | User expects PNG while nodes are enabled | Nodes exist, main render off | EXR multilayer only | Hidden format change | Show the actual node format and explain how to get PNG (disable nodes or enable Also Write Main Render) |
| S8 | Check names before rendering | Any node setup | No preview | Modes are opaque | Show resolved relative paths and collisions in the UI and in preflight |

## 5. Decisions

1. **Introduce a resolved node output model.** A `NodeOutputPlan` describes the
   effective directory, file name, layout and full path for every
   `(collection, File Output node)` pair. Preflight uses this model for
   collisions, existing files and the final report.
2. **Add a Collection Name layout.** It sets `node.file_name` to the sanitized
   collection name and leaves layer names alone. It is valid only when there is
   exactly one active File Output node, because one node produces one file.
3. **Add an Automatic layout for new scenes.** Automatic resolves to
   Collection Name when there is one active File Output node and to Subfolder
   when there are several. The resolved layout and paths are shown in the UI;
   the user is not expected to infer it.
4. **Keep Subfolder and Prefix, but explain their purpose.** Subfolder is the
   grouping layout for several outputs per collection. Prefix is the flat
   layout. Both remain useful and both must preserve layer names.
5. **Make Prefix duplicate-safe.** If the authored file name already equals the
   collection name or starts with `<Collection>_`, do not add the token again.
   Report what was detected. Compare case-insensitively for Windows.
6. **Keep Don't Modify as a manual single-target mode.** For several targets it
   stays an error, but the message must explain that one compositor tree cannot
   route different collections to different paths automatically.
7. **Do not rename `file_output_items` in Blender 5.2.** They are layer names.
   Any compatibility helper for older Blender versions stays behind a
   capability check; the 5.2 path never treats them as file names.
8. **Show node mode as an advanced EXR path.** In node-only mode the Output
   panel shows `EXR multilayer (from the node)`. The add-on format controls are
   shown only when the main render is also written.
9. **Preview paths before rendering.** The Output panel shows up to a few
   resolved relative paths for the active or first target, and the analysis
   operator lists every conflict. The preview and the final report use the same
   function as the job.
10. **Preserve compatibility.** Existing enum identifiers `SUBFOLDER`, `PREFIX`
    and `NONE` stay valid. New scenes default to Automatic; old scenes are
    migrated to their previous layout with a schema marker. The property
    `node_naming` and all `bl_idname` values stay unchanged.
11. **Rename the user-facing control.** "Collection Goes To" becomes "Node
    Output Layout"; the tooltips state the resulting path for each choice.

## 6. Planned split by version

| Version | Work |
|---|---|
| 1.4.0 | `NodeOutputPlan`, effective path resolution, duplicate-token guard, preflight collisions and existing-file checks for node outputs. No UI redesign. |
| 2.0.0 | New enum values `FILENAME` and `AUTO`, migration marker, output layout UI, path preview, node format notice, renamed control and tooltips. |
| 2.1.0 | Name templates reuse the node plan and add `{node}` alongside `{collection}`; collision checks and preview cover both paths. |

## 7. Acceptance criteria

- A scene with one connected File Output node and Automatic layout exports
  `<Output Directory>/<Collection>.exr`; layer names are unchanged.
- A scene with two File Output nodes and Automatic layout exports
  `<Collection>/<node file name>.exr` for both nodes; duplicate file names are
  reported before rendering.
- Prefix mode with `node.file_name = "Body"` and collection `Body` exports
  `Body.exr`, not `Body_Body.exr`.
- Subfolder and Prefix modes do not change `file_output_items` names.
- Don't Modify with several target collections is rejected with an actionable
  message; with one target it produces exactly the authored paths.
- The Output panel shows the resolved layout and a path preview that matches
  the files written by the job.
- Node-only mode states that the output is EXR multilayer and does not offer a
  misleading PNG/JPEG selector.
- Old scenes keep their stored layout; new scenes start with Automatic.
