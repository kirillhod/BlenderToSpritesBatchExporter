# UI design

Single home for durable interface rules. Read this before changing `ui.py`,
adding a panel, moving a control or changing a list.

Scope: the Blender sidebar interface. User-facing behavior lives in
`README.md`; scope and rationale live in `IMPROVEMENT_PLAN.md`; task history
lives in `IMPLEMENTATION_SEQUENCE.md`.

## Principles

1. One panel, one task. A panel either runs the export, selects targets,
   configures framing, configures output or reports problems. Do not mix two
   tasks in one panel.
2. State on screen, help in tooltips. A string that reports current state or a
   problem stays visible. A string that explains what a control does belongs in
   the property description or a menu item description.
3. Primary actions stay visible. Export and Analyze are never hidden in a menu.
   Secondary actions such as Preview Camera, Cleanup and Restore may be grouped.
4. Progressive disclosure needs a summary. A collapsed section must show its
   state or count in the header, for example `Format: PNG / RGBA` or
   `Overrides: 2 active`.
5. Use Blender primitives. Do not draw custom widgets or floating toolbars.
   Panels, subpanels, `layout.panel`, `template_list`, menus and popovers are
   the allowed building blocks. A viewport overlay is allowed only as a
   render/canvas guide, never as a control.
6. Dense but scannable. Prefer one aligned row over two short rows, but do not
   compress labels until they become ambiguous.
7. Do not compute bounds, scan nodes or run preflight in `draw()`. Use the
   cached analysis and cheap counts only.

## Panel map

All panels use `bl_space_type = 'VIEW_3D'`, `bl_region_type = 'UI'` and
`bl_category = "Batch Export"`. Panel IDs are pinned in
`tests/test_package_contract.py`; preserve them.

| Panel | ID | Purpose |
|---|---|---|
| Main | `BTS_PT_main` | target summary, export and analyze actions, job status, warnings |
| Collections | `BTS_PT_source` | export mode, target table, target actions, Preview and canvas grid, three Override groups, Always Include, isolation |
| Camera & Framing | `BTS_PT_camera` | six view toggles, margin, padding, cleanup |
| Resolution | `BTS_PT_resolution` | pixels per unit, multiple, square output, min and max size |
| Output & Naming | `BTS_PT_output` | main and node output, format, Path Preview, conflicts |
| Problems | `BTS_PT_problems` | every problem, collection and fix hint in full |
| Presets | `BTS_PT_presets` | built-in preset menu, JSON save and load; closed by default |
| Log | `BTS_PT_report` | `Copy Log` and `Open Log` only; always open |

The Override groups are not panels. They belong to Collections and appear only
for the visible active target row.

## Current state

Recorded after 3.2.4. Row counts are approximate and assume two targets, one
Always Include collection and no problems.

| Panel | Open rows | Current contents |
|---|---:|---|
| Main | 5-9 | target summary; Export; Analyze and Cancel; Preview Camera and Cleanup; Restore Collections; optional job-status box; optional warnings |
| Collections | 23-29 | export mode; refresh and search; table header; 3-8 target rows; All, None, Active and Activate; Skip Empty; Preview and canvas grid; three collapsible Overrides groups; Always Include; isolation; keep lights |
| Camera & Framing | 6 | six view toggles in a 3x2 grid; margin; auto cleanup; padding mode; padding value |
| Resolution | 5 | pixels per unit; multiple; square output; min; max |
| Output & Naming | 14-26 | main or node output; format; overwrite; Path Preview; conflicts |
| Problems | 1-20 | grouped full messages, collection and fix hint; Analyze and Copy |
| Presets | 1 | closed header; built-in preset menu and JSON save/load inside |
| Log | 1 | `Copy Log` and `Open Log` only |

The default open state is typically 45-60 rows before problem messages, or
about one sidebar screen at 1080p. Content-sized lists no longer reserve empty
rows: the target list uses 3-8 rows and the smaller lists use 1-4.

### Main

The summary is one label: `Targets: enabled/visible   Views: n`, plus
`Tasks: n` after Analyze. Actions use four rows. A running job draws a box with
two text rows; there is no progress bar. The unsaved-path warning uses an alert
box; the analysis count is an alert row.

### Collections

The export mode and the search field filter the target table. A row shows the
enabled checkbox, the collection name and `Canvas / status`. It shows the
canvas after Analyze, `skipped` for an empty collection and `disabled` for an
off target.

The three Overrides groups belong to the visible active row. View, Framing and
Resolution are full-width checkbox rows while off. Checking one turns it into a
collapsible section with the group checkbox in the header; unchecking it turns
the section back into a plain row. View starts off. An off group draws no
fields, no separate `Using global` row and no empty panel body. The override
fields use `Margin` and `Round To` so their labels fit at the default width.
When the active row is filtered out, one muted row says
`Overrides: no target selected.`

The target list shrinks to its visible rows. The Always Include list uses 1-3
rows; an empty list shows one info row. Isolation and Keep Lights sit below the
Add and Remove buttons. The target actions use one even four-column row so
`All`, `None`, `Active` and `Activate` stay readable at the default width; the
long `Fit Camera to Active` and `Remove Camera` operator labels are shortened in
the Main panel and stay complete in their tooltips.

Target rows show the override marker before the status when at least one group
is on.

The **Preview** button switches the 3D View to camera view for the selected
target row and uses the export frame and overrides. It hides other collections,
keeps lights visible, uses current shading, writes no files. It refreshes after
target, override or depsgraph changes and shows the first active
view. A row change switches it; hiding collections resets the Outliner
selection, so the row is read first and the Outliner is put back. Exit,
leaving camera view, saving or unloading restores camera, resolution, visibility
and view state. The mode is not saved. **Canvas Grid** next to Preview draws
adaptive canvas-pixel lines, a center cross and the resolution in a badge above
the frame's top-left corner; it follows the Preview canvas and does not render.

### Camera & Framing

Six view toggles are drawn as a 3x2 grid with short labels and tooltips. The
legacy `camera_axis` control is hidden but the property remains for presets and
scripts. Margin, auto cleanup and padding follow the grid.

### Output & Naming

The main branch draws output directory, name template, format, overwrite,
transparency, `filter_size` and the open-folder button. The node branch adds
the compositor toggles, a 1-3 row node list, naming mode, resolved label,
warnings, base directory, write-main-output, format, transparency,
`filter_size`, overwrite, name template and conflicts.

Path Preview is a checkbox with a file count. It draws a 1-4 row list only when
the checkbox is on and files are planned. The panel mixes file settings, File
Output node settings and the general render setting `render.filter_size`.

### Problems, Presets and Log

Problems groups messages by ERROR, WARNING and INFO. Every message, collection
and fix hint is drawn in full, wrapped at 48 characters at 0.9 scale.

Presets is closed by default and uses one built-in preset menu with per-item
tooltips. Log is always open and contains only its two buttons.

### Lists and actions

Main uses four action rows. Analyze appears in Main and Problems; Copy appears
in Problems and Log. Secondary actions such as Preview Camera, Cleanup and
Restore each have a full row.

### Known gaps

- One sidebar category holds all eight panels.
- A running job has no progress bar.
- `render.filter_size` is duplicated outside the Render properties.
- Collapsed override groups show only their label and checkbox, not the values
  they contain. Animation controls arrive with 3.3.0.

## Layout rules

### Property rows

- Property-heavy panels start with `layout.use_property_split = True` and
  `layout.use_property_decorate = False`.
- Use `_left_checkbox` when a checkbox label must stay on the left.
- Do not add persistent help labels. Put the text in the property description.
- Use `separator(factor=0.5)` for a visual break; avoid full-height separators
  between related rows.
- Use a box for an alert, a warning group or a short job-status block. Do not
  wrap ordinary settings in boxes.
- Use `scale_y` 0.85-0.9 only for secondary text such as problem entries.

### Lists

- Wrap every `template_list` in a layout with
  `use_property_split = False` and `use_property_decorate = False`.
  Otherwise rows inherit property-split layout and appear centred.
- Draw a compact header above the list when the list has two columns.
- Target rows use the fixed `Collection` / `Canvas / status` table.
- A skipped target shows the short `skipped` marker and stays compact.
- Path Preview and File Output node information are compact lists, not boxes
  that grow with the data.
- List heights follow their content: target `max(3, min(8, visible))`,
  Always Include 1-3, Path Preview 1-4, File Output nodes 1-3. All lists
  scroll. Draw one info row instead of an empty `template_list`.
- Keep `filter_items` and the export-mode filter intact when changing heights.
- `template_list(type='COMPACT')` disables `filter_items`. The target list must
  stay `DEFAULT`, because search and export-mode filtering depend on it.

### Collapsible sections

- Use `layout.panel(idname, default_closed=...)` for a section inside a panel.
  It returns `(header, body)`; draw a `body` only when it is not `None`.
- `layout.panel` only works at full panel width. It cannot be used inside
  `box`, `row`, `column`, `split` or another constrained layout.
- The header may contain a checkbox, an operator or a right-aligned summary.
  This is the preferred place for a group toggle.
- An override group is a plain checkbox row while off and becomes a panel only
  when checked. This avoids an empty body under an unchecked group.
- Use a stable `idname`. The open state is stored per region, not per scene.
- Use `layout.panel_prop(data, prop)` only when the bool genuinely means
  "this section is open". Never use it for `override_*` toggles: collapsing
  the section would silently disable the override.
- Do not nest collapsible sections deeper than needed. One level inside a
  panel is the normal case.

### Menus and popovers

- Group rare actions in a menu (`layout.menu`, `operator_menu_enum`). Built-in
  presets already use an enum menu with per-item tooltips.
- Use a popover (`layout.popover(panel=...)`) or `wm.call_panel` only for
  secondary content such as Path Preview, node details or the full problem
  list. Primary settings stay in the panel.
- A popover needs a registered panel class. Check where that class appears
  before adding it; a panel in the UI region without a parent can also show in
  the sidebar.
- `prop_with_popover` and `prop_with_menu` are not generic "field plus button"
  widgets. They only work on property widgets that support a popover or menu.

### Density

- Every row added to the default open state must remove or relocate another
  row. A new setting goes into a collapsed section unless it is used daily.
- Density target: the default open state fits roughly one sidebar screen at
  1080p, about 30-35 rows at 100% UI scale. Use it when deciding whether a row
  belongs in the open state. The 2.3.0 subset (P1.1, P1.2 and P1.7) is a
  partial step; the rest of P1 is unscheduled.
- Prefer icon buttons with tooltips for secondary actions: refresh, open
  folder, make active, copy, cancel. Keep text on primary actions.
- Pair short numeric fields such as Min and Max in one row. Use `grid_flow`
  for two to four short checkboxes; use `prop_tabs_enum` for two to four
  modes. Do not compress longer enums.
- Use `layout.progress(factor=..., type='BAR')` for a running job instead of a
  multi-line status box.

## Anti-patterns

- Persistent hint labels that repeat what a tooltip can say.
- Tooltips on plain labels or UIList rows. Blender does not support them; use
  a property description or a menu item description instead.
- `template_list(type='COMPACT')` for the target list.
- `panel_prop` keyed to an `override_*` property.
- `layout.panel` inside a box, row or column.
- A collapse or popover that hides state without showing it in the header.
- Drawing the full export report in the UI. `Log` exposes `Copy Log` and
  `Open Log` only.
- A global `scale_y` shrink for the whole panel.
- New operators for pure UI actions in v3. Reuse existing operator IDs.

## Compatibility

- Preserve every existing panel ID. `BTS_PT_report` keeps its ID even though
  its label is `Log`.
- Preserve operator `bl_idname` values and `scene.bts_settings` property names
  and enum identifiers.
- New panels and `UIList` classes must be registered in `__init__.py` and
  added to the expected sets in `tests/test_package_contract.py`.
- New UI that can change output stays opt-in. With new toggles off, existing
  scenes keep their output.

## Verification

Run the focused checks after a UI change:

```powershell
python -m unittest discover -s tests -p "test_package_contract.py"
python -m unittest discover -s tests -p "test_docs.py"
python -m unittest discover -s tests -p "test_*.py"
```

Then run the Blender smoke suite as described in
[docs/agent/smoke.md](smoke.md). It covers the panel draw path, known icon
names, tooltip strings, the 50-collection scene, the target table, output
lists, the three Override groups and the view grid.

If a panel starts using `layout.panel` or `layout.panel_prop`, update
`_FakeLayout` in `tests/smoke_blender.py` so both methods return
`(self, self)`. The default fake returns `self`, which cannot be unpacked.

Visual checks are mandatory for layout changes. Run Blender at 100% and 150%
UI scale with an empty scene and with 50 collections. Check that labels are
not clipped, columns stay aligned, the list does not jump when the selection
changes and the panel scroll position is stable. Widen the sidebar at 150%:
the six view buttons expand to fill the panel, and `Margin` / `Remove Camera`
keep the camera panel readable.

Do not claim a UI change is complete from the draw probe alone.

## Improvement proposals

P1.1, P1.2 and P1.7 are implemented in 2.3.0 as V5b and V5. The detailed
catalog, estimates and variants are in [ui-proposals.md](ui-proposals.md); the
rest is unscheduled.

## Related documents

- Scope and rationale: `IMPROVEMENT_PLAN.md` sections 4-6.
- Tasks and checks: `IMPLEMENTATION_SEQUENCE.md` stages U, O, V and A.
- Smoke procedure: [docs/agent/smoke.md](smoke.md).
- Historical 2.0.0 interface report: `reports/STAGE_05_REPORT.md`.
- Blender layout API: https://docs.blender.org/api/current/bpy.types.UILayout.html
