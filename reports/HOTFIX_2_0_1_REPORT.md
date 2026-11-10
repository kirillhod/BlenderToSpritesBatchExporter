# Hotfix report: version 2.0.1

Date: 2026-11-10
Status: implemented and verified headless in Blender 5.2.3 LTS.

## Result

The 2.0.1 fix pass addresses the issues found in the 2.0.0 interface:

- File Output names are built from the collection and the socket name.
- Automatic mode uses the socket name and is no longer layout-dependent on the
  number of nodes.
- The Emergency Prefix Rename feature and its post-render fallback were removed.
- Overwrite is the default policy and replaces existing files.
- The Problems panel no longer crashes on an invalid Blender icon.
- The Always Include section is compact when empty.
- Presets have descriptions, and custom JSON presets store a description.

## File Output naming

The node name and label are ignored. The socket names from
`node.file_output_items` are the naming source.

| Layout | Result |
|---|---|
| Automatic | `<Collection>_<socket>.exr` |
| Collection + Socket | `<Collection>_<socket>.exr` |
| Collection Folder | `<Collection>/<socket>.exr` |
| Collection Only | `<Collection>.exr` (legacy; ignores sockets) |
| Don't Modify | Authored node path |

If a socket already contains the collection token (`Body` or `Body_*`), the
collection is not duplicated. If a node has several sockets, their names are
joined in the file name; the layer names themselves are never changed. If a
node has no sockets, the node file name is used as a fallback.

## Removed fallback

`use_prefix_fallback` and the post-render `prefix_new_files` path are gone.
When a File Output node cannot be updated, the collection is reported and
skipped. The add-on no longer renames files after rendering, which avoids
breaking external `.meta` files and makes the result predictable.

## Overwrite default

The default policy is now **Overwrite**, so a repeated export simply replaces
existing files. Ask, Error, Skip and Add Suffix remain available. In background
mode Ask still falls back to Error, as before.

## UI fixes

- `icon='WARNING'` was replaced with `STATUS_WARNING`; the old identifier does
  not exist in Blender 5.2 and crashed the Problems panel during Analyze.
- The Always Include list is only drawn when it has items, so an empty section
  no longer reserves three rows.
- Preset cards show a short description for each built-in preset.
- A Preset Description field is shown in the Presets panel. It is written to
  the JSON file and restored on load.

## Tests

| Check | Result |
|---|---|
| Unit tests | 48/48 OK |
| Base smoke | PASS |
| Strict camera smoke | PASS |
| UI draw probe | all panels OK |
| UI icon probe | all literal icons valid in Blender 5.2 |
| `py_compile` package and tests | OK |
| Extension manifest validate | OK |
| Install 2.0.1 zip in an isolated profile | OK |

The smoke test now checks exact File Output names:

- Subfolder export writes `Body/Sprite.exr`.
- Prefix export writes `Body_Sprite.exr`.
- Automatic plans resolve to `Body_Sprite.exr` and `Body_Unused.exr`.

## Known limitations

- Node mode is still multilayer EXR in Blender 5.2. Use the main render path for
  PNG/JPEG/WebP sprites.
- Collection Only is a legacy layout and does not include the socket name.
- The modal Cancel button, preset file dialogs and linked File Output nodes
  still need a manual GUI pass.
- Multi-view and 4/6-direction presets remain in stage 6.

## Files changed

- `blender_to_sprites_batch_exporter/core/output.py`
- `blender_to_sprites_batch_exporter/core/job.py`
- `blender_to_sprites_batch_exporter/core/presets.py`
- `blender_to_sprites_batch_exporter/properties.py`
- `blender_to_sprites_batch_exporter/operators.py`
- `blender_to_sprites_batch_exporter/ui.py`
- `blender_to_sprites_batch_exporter/__init__.py`
- `blender_to_sprites_batch_exporter/blender_manifest.toml`
- `tests/smoke_blender.py`
- `tests/test_logic_unit.py`
- `tests/test_package_contract.py`
- `README.md`
- `CHANGELOG.md`
