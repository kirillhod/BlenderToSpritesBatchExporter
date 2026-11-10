# Hotfix report: version 2.0.4

Date: 2026-11-10
Status: implemented and verified headless in Blender 5.2.3 LTS.

## Result

Small interface cleanup requested after the 2.0.3 naming fix.

## Changes

### Filter Size

- Added `Filter Size` directly below Transparent Film in both Output panel
  variants: main render and File Output node mode.
- It edits `scene.render.filter_size`, so the value is used by normal renders
  and by batch export.
- A short hint recommends `0.01-0.1` for crisp pixel art. Blender's default is
  `1.5`, which can soften small pixel sprites.

### Left-aligned checkboxes

- `Skip Empty Collections` is now a left-aligned checkbox.
- `Use File Output Nodes` is now a left-aligned checkbox.
- `Only Connected Nodes` is now a left-aligned checkbox.
- The change uses a small `_left_checkbox` helper with
  `use_property_split = False`, so the checkbox and its label start at the
  panel's left edge.

### Removed misleading node-format note

- Removed `Node layout writes EXR files.` from the node output panel.
- File Output nodes support both Image formats (PNG/JPEG/WebP) and Multilayer
  EXR, and the panel already reports the actual node format in the
  `Node output: ...` box.
- Also updated the remaining old "Subfolder or Prefix" wording to the current
  layout names.

## Tests

| Check | Result |
|---|---|
| Unit tests | 54/54 OK |
| Base smoke | PASS |
| Strict camera smoke | PASS |
| UI draw probe | all panels OK |
| UI icon probe | all literal icons valid |
| Extension validate/install | OK |

## Note

The filter size is a scene render property, not a preset field. It persists in
the .blend and is used by both F12 and batch export.
