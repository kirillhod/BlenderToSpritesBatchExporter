# Hotfix report: version 2.0.3

Date: 2026-11-10
Status: implemented and verified headless in Blender 5.2.3 LTS.

## Result

Version 2.0.3 fixes single-layer File Output naming.

Blender 5.2 uses two different File Output naming rules:

| Node format | Actual file name |
|---|---|
| Single-layer image (PNG, JPEG, ...) | `<node.file_name><socket name><ext>` |
| Multilayer EXR | `<node.file_name><ext>` |

The add-on previously treated both as one-file nodes and set
`node.file_name` to `<collection>_<socket>`. For a single-layer PNG node,
Blender then appended the socket name again:

- expected `Building_Conveyor_Horizontal_Normal.png`
- actual `Building_Conveyor_Horizontal_NormalNormal.png`

An empty socket also fell back to the node file name, which could add an
unwanted node identity such as `_Color`.

## Fix

- Single-layer nodes now receive only the collection prefix:
  - named socket: `node.file_name = "<collection>_"` -> `<collection>_<socket>.png`
  - empty socket: `node.file_name = "<collection>"` -> `<collection>.png`
  - subfolder layout: `node.file_name = ""` -> `<collection>/<socket>.png`
- The node name, node label and node file name are never used as a fallback
  suffix.
- A node with several single-layer sockets produces one planned file per
  socket, and every file is checked for collisions and reported.
- Multilayer EXR nodes keep one file per node and use the joined socket names
  as the previous version did.

## Verified user case

Scene: collection `Building_Conveyor_Horizontal`, two single-layer PNG nodes:

- node `Color`, empty socket
- node `Normal`, socket `Normal`

Result:

```text
Building_Conveyor_Horizontal.png
Building_Conveyor_Horizontal_Normal.png
```

No `_Color` suffix and no duplicated `Normal`.

## Tests

| Check | Result |
|---|---|
| Unit tests | 54/54 OK |
| Base smoke | PASS |
| Strict camera smoke | PASS |
| Extension validate/install | OK |

Smoke renders single-layer PNG nodes and checks:

- `Body_Sprite.png`, not `Body_SpriteSprite.png`
- `Body.png` for an empty socket, not `Body_Color.png`

## Note

This fix applies to the currently installed 2.0.3 zip. Reinstall it before
testing; the old 2.0.2 extension still contains the previous naming logic.
