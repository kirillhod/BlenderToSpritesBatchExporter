# Hotfix report: version 2.0.2

Date: 2026-11-10
Status: implemented and verified headless in Blender 5.2.3 LTS.

## Result

Version 2.0.2 fixes the confusing node-format preflight message shown after
Analyze.

Previously the add-on always warned when the selected add-on format was not
EXR, even when the File Output node itself wrote the same format. For example,
a PNG File Output node with PNG selected produced both:

- `node_format_mismatch: Selected format PNG will not be used...`
- `node_format: File Output nodes write PNG...`

The warning is now emitted only when the node format family and the selected
add-on format actually differ.

## Behavior

- File Output nodes write PNG and the add-on format is PNG: only the INFO note
  is shown.
- File Output nodes write EXR multilayer and the add-on format is PNG: WARNING
  `Selected format PNG is ignored; File Output nodes write EXR multilayer.`
- Single-layer EXR and multilayer EXR are treated as the same EXR family.
- The visible label `Also Save Main Render` is used consistently in messages.

## Tests

| Check | Result |
|---|---|
| Unit tests | 50/50 OK |
| Base smoke | PASS |
| Strict camera smoke | PASS |
| Extension validate/install | OK |

Smoke now checks both cases: matching PNG node format produces no mismatch
warning, while an EXR node with PNG selected still produces one.

## Note

This is only a message/preflight clarification. Node output still uses the
format configured on the File Output node. The add-on Format selector applies
to the main render path, which is written only when `Also Save Main Render` is
enabled.
