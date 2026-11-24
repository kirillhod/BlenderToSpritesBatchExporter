# UI improvement proposals

Status: proposals and decisions. P1.1, P1.2 and P1.7 are implemented in 2.3.0
(V5b and V5); the rest is not approved. P4 records the Outliner and hierarchy
options from the later review; it is not scheduled. The current rules and
current state are in [ui.md](ui.md); read that before changing `ui.py`.

Recorded after 2.2.0 during the UI density review.

## Goal

Reduce the default open state from about 55-80 rows to about 30-35 without
hiding daily controls, changing the target model or adding operator IDs.

The full P1 target is 30-35 rows. The adopted 2.3.0 subset (P1.1, P1.2 and
P1.7) is expected to land around 40-50 rows; it removes the largest empty rows
without touching Main, Output or Always Include.

Constraints:

- preserve panel IDs, UIList IDs and `scene.bts_settings` names;
- no new operator IDs in v3;
- keep Export and Analyze visible;
- use Blender layout primitives only;
- verify every layout change in Blender, not only in the draw probe.

## Where the space goes

- Fixed-height lists reserve 18 rows; a small scene leaves about 13 empty.
- Overrides take 5 rows when both groups are off and 11 when both are on.
- Main uses four action rows plus a two-row status box.
- Output mixes file settings, node settings, a render setting, Path Preview
  and conflicts; in node mode it reaches about 25 rows.
- Problems can add many wrapped lines; full messages are required.

## P1. Low-risk packing

| ID | Proposal | Where | Saving | Risk |
|---|---|---|---:|---|
| P1.1 | Dynamic list heights | all lists | 5-12 rows | low |
| P1.2 | Collapsible Overrides groups | Collections | 4 rows off, 1 on; up to 14 collapsed | low |
| P1.3 | Collapse Always Include and isolation | Collections | 4-6 rows | low |
| P1.4 | Sections in Node Output | Output | 5-10 rows | low |
| P1.5 | Path Preview as a section | Output | 0 rows, consistency | low |
| P1.6 | Compress Main actions and status | Main | 3-4 rows | low |
| P1.7 | Pair short fields | Resolution, Output | 0-1 vs 2.2.0; avoids +5 | low |
| P1.8 | Icon-only secondary actions | all panels | 1-3 rows | low |
| P1.9 | Override marker in target rows | Collections | 0 rows | low |
| P1.10 | Remove or relocate `filter_size` | Output | 1 row | medium |
| P1.11 | Remove duplicated Analyze or Copy | Main, Problems, Log | 0-1 row | low |

Status after the 2.3.0 decision:

- P1.1 is implemented as V5b.
- P1.2 and P1.7 are implemented in V5.
- P1.3-P1.6 and P1.8-P1.11 are not scheduled.
- P2 and P3 are not scheduled; do not put P2 into 3.0.0.

### P1.1. Dynamic list heights (implemented as V5b)

`template_list(rows=...)` is the actual height, not a maximum. Compute it from
the visible count:

```python
visible = _target_counts(context, settings)[1]
rows = max(3, min(8, visible))
layout.template_list(
    "BTS_UL_Targets", "", settings, "target_items",
    settings, "active_target_index", rows=rows,
)
```

Use the same rule for Always Include (1-3), Path Preview (1-4) and node output
(1-3). Draw one info row instead of an empty list.

This changes the current density contract: update the Current state and Layout
rules sections of `ui.md` in the same change. Check whether the panel jump when
the count changes is acceptable.

Do not use `template_list(type='COMPACT')` for the target list: it disables
`filter_items`, so search and export-mode filtering stop working.

### P1.2. Collapsible Overrides groups (implemented in V5)

Replace the always-open `layout.box()` with two full-width sections. Put the
group checkbox in the header:

```python
header, body = layout.panel("bts_override_framing", default_closed=False)
header.use_property_split = False
header.prop(item, "override_framing", text="Framing")
if body and item.override_framing:
    body.prop(item, "camera_margin")
    body.prop(item, "padding_mode", expand=True)
```

Do the same for Resolution. When a group is off, only its header row remains;
the `Using global` row disappears. The header checkbox is visible whether the
section is open or closed.

Do not use `panel_prop(item, "override_framing")`: the open state would be
stored in the override bool, so collapsing the section would silently disable
the override.

`layout.panel` only works at full panel width; remove the box and call it from
the panel body, not from a row or column.

Estimate: with two groups in 2.2.0, 5 rows off to 2 and 11 on to 10. If V5
added View to the old box, three groups would be 7 rows off and 17 on. With
collapsible groups they are 3 and 16. A closed group hides its fields, so the
saving can reach 14 rows when all are closed.

### P1.3. Collapse Always Include and isolation

Put the Always Include list, Add/Remove, isolation mode and Keep Lights in one
section:

```python
header, body = layout.panel("bts_include", default_closed=True)
header.label(text=f"Always Include: {len(settings.always_include_items)}")
if body:
    ...
```

The header carries the count. Closed, the block takes one row instead of five
to seven.

### P1.4. Sections in Node Output

Split the node branch into full-width sections with summary headers:

- `Nodes: 2 outputs`
- `Naming: Collection + Socket`
- `Base Directory: <output folder>`
- `Main Output: PNG / RGBA`
- `Conflicts: 3 files`

Collapsed sections show state; expanded sections show fields. The node list can
stay inside the Nodes section. This is the largest Output saving in node mode.

### P1.5. Path Preview as a section

Replace the checkbox row with a section:

```python
header, body = layout.panel("bts_preview", default_closed=True)
header.label(text=f"Path Preview: {len(settings.preview_items)} file(s)")
if body:
    ...
```

This does not reduce rows by itself: the closed state is one row today and
stays one row. It makes Path Preview consistent with the other sections and
puts the count in the header.

### P1.6. Compress Main actions and status

Proposed layout:

```text
[ Export ] [ Analyze ]
[ Preview Camera ] [ More v ]   More: Cleanup, Restore
[ Cancel ] [ progress bar ]     only while a job runs
```

Keep Export and Analyze as text buttons. Show Cancel next to the progress bar
while a job runs; do not hide it in a menu. Use `layout.progress(factor=...,
type='BAR')` for the job instead of the two-row status box. Keep the summary
label and the analysis warning row.

### P1.7. Pair short fields (implemented in V5)

- Min and Max resolution in one row with short labels.
- Use `grid_flow(columns=2)` for adjacent short checkboxes in the same panel.
- In V5, six view toggles in a 3x2 grid instead of six checkboxes.

The Min/Max pair saves one row. The view grid does not save rows against
`camera_axis`; it avoids the five extra rows that six checkboxes would add.

Do not pair long labels or enums with more than four options.

### P1.8. Icon-only secondary actions

Refresh, Open Output Folder, Make Active, Copy and Cancel can be icon buttons
with tooltips. Keep text on Export and Analyze. The open-folder button can sit
in the same row as the path.

### P1.9. Override marker in target rows

Draw a small marker in a target row when `override_framing` or
`override_resolution` is on. The values already exist; no new property or
operator is needed. This makes overrides visible without opening the block.

### P1.10. Remove or relocate `filter_size`

`render.filter_size` is a general render setting, not an add-on setting. Remove
it from the panel or move it into an advanced section. This is a product
decision because it is convenient for pixel art.

### P1.11. Remove duplicated actions

Analyze appears in Main and Problems; Copy appears in Problems and Log. Keep
Analyze in Main and Problems. Keep Copy in Log only and remove it from
Problems.

## P2. Structural changes

| ID | Proposal | Where | Saving | Risk |
|---|---|---|---:|---|
| P2.1 | Second sidebar tab | panel categories | moves 4 panels off the main tab | medium |
| P2.2 | Summary headers across Output | Output | 10-15 rows | medium |
| P2.3 | Problems details in a popover | Problems | 3-20 rows | medium |
| P2.4 | Presets in a popover | Main or Presets | 1 row | low |
| P2.5 | Compact and Detailed preference | add-on preferences | 5-10 rows | medium |

### P2.1. Second sidebar tab

Move Output & Naming, Problems, Presets and Log to a second `bl_category`, for
example `BTS Output`, and keep Main, Collections, Camera & Framing and
Resolution in `Batch Export`.

Panel IDs stay the same. The cost is one more tab in the global sidebar and a
new navigation habit. Update README, CHANGELOG and the panel map in `ui.md`.

### P2.2. Summary headers across Output

Use the P1.4 section pattern for both main and node output. A collapsed section
must show its value, not just its title. This is what makes the structural
version usable rather than merely hidden.

### P2.3. Problems details in a popover

Keep a one-line count in Main or in the Problems header and open the full list
in a popover or a `wm.call_panel` popup. The full messages must stay available;
the plan does not allow truncating them.

Do not hide errors by default. If the popover is the only place with details,
the summary row must be alert-colored and must show the error count.

### P2.4. Presets in a popover

Presets is already closed. It could become a popover from Main, saving one
header row. This is a minor gain and not worth doing alone.

### P2.5. Compact and Detailed preference

Add an `AddonPreferences` bool that hides advanced sections. The scene
properties do not change. Both modes need draw tests and a visual check; this
doubles the UI states to maintain.

## P3. Workflow-first changes

| ID | Proposal | Saving | Risk |
|---|---|---:|---|
| P3.1 | Shift+click Export opens an options dialog | 0-5 rows | high |
| P3.2 | Batch Export menu in the 3D View header | 2-4 rows | medium |
| P3.3 | Pie menu for quick actions | 0 rows | medium |

### P3.1. Export dialog

Use the existing `bts.batch_export` operator: plain click exports as today,
Shift+click calls `invoke_props_dialog` with a custom `draw`. No new operator
ID is needed. This changes a primary action and needs documentation, tests and
a decision about whether the dialog replaces or complements the sidebar.

### P3.2. Header menu

Add a menu to `VIEW3D_MT_editor_menus` with Export, Analyze and Preview Camera.
It makes actions reachable without the sidebar. Remove the matching rows from
Main only if the menu is considered discoverable enough.

### P3.3. Pie menu

A radial menu for the same actions is optional. It does not reduce panel
height; it only speeds up repeat use. A keymap entry is required.

## P4. Outliner and hierarchy

Status: recorded after the 2.3.0 scope decision. Not scheduled; do not add it to
2.3.0. Candidate increment of about 2-3 days after that release.

Facts:

- The Outliner takes no custom columns, rows or widgets.
  `SpaceOutliner.draw_handler_add` exists in 5.2 but is a pixel overlay without
  row or scroll data.
- `Collection.hide_render` as the selection store is rejected: it changes F12,
  is inherited by children, and needs a new restore path in the job.
- The target list is an export queue (canvas/status, overrides, enabled,
  search), not a hierarchy browser. Keep it.

| ID | Proposal | Cost |
|---|---|---:|
| P4.1 | `Render Enabled` filter on `hide_render == False`; no writes, overrides persist | 0.5 day |
| P4.2 | Display order follows the collection tree via `filter_items`; registry order unchanged | 0.5 day |
| P4.3 | Registry and export order follow the tree; rebuild items, keep the active index | 1 day |
| P4.4 | Depth indent in target rows | 0.5 day |
| P4.5 | Preflight warning for an enabled parent with an enabled descendant | 0.5 day |
| P4.6 | Hide direct objects of ancestors in EXCLUDE isolation | 1 day |
| P4.7 | Per-target `include_children`, default True | 2 days |

Nested: a parent target includes its subtree, so an enabled parent duplicates
its children; disabling the parent is the current answer. A parent with its own
objects can leak them into a child render in EXCLUDE mode because the ancestor
layer must be included; confirm with smoke, then fix with P4.6.

Order: no drag in the list (new operator IDs are forbidden in v3), no reliable
read of the Outliner's per-editor `use_sort_alpha`, and no reverse write to
`Collection.children`.

Filters: keep `ALL`, `INCLUDED`, `ACTIVE` and `TOPLEVEL`. `INCLUDED` uses the
per-view-layer exclude; P4.1 would use the global render flag. Add smoke for
`INCLUDED` and `TOPLEVEL`, which have none.

Recommended subset after 2.3.0: P4.2, P4.4, P4.5 and P4.6. P4.1 and P4.3 are
optional; P4.7 is a separate data-model decision.

## Variants

| Variant | Contents | Estimated default rows | Risk |
|---|---|---:|---|
| A0. Adopted in 2.3.0 | P1.1 + P1.2 + P1.7 | 40-50 typical | low |
| A. Full packing | P1 | 30-35 | low |
| B. Structural | P1 + P2.1-P2.3 | 25-30 per tab | medium |
| C. Workflow | B + P3 | 20-25 | high |

A0 is adopted for 2.3.0. Measure the real rows after it ships, then decide
whether the rest of A is needed. Do not put B into 3.0.0; treat it as a separate
decision after that release. Adopt C only on request, because it changes muscle
memory and primary actions.

## Suggested order

1. Finish V1-V4 without UI changes.
2. In V5, use the 3x2 view grid and build Overrides with three collapsible
   sections (P1.2, P1.7).
3. In V5b, use content-sized list heights (P1.1).
4. In V6, run the unit suite, smoke, and visual checks at 100% and 150% scale.
5. Update `ui.md` and mark P1.1, P1.2 and P1.7 implemented.
6. After 2.3.0, measure and decide on the rest of P1. Do not add P2 to 3.0.0;
   leave P3 open unless requested. P4 is a separate candidate after 2.3.0.

## Implementation notes

- `layout.panel` and `panel_prop` must be updated in `_FakeLayout` in
  `tests/smoke_blender.py` to return `(self, self)`.
- New popover panels need classes and updates to the pinned panel set in
  `tests/test_package_contract.py`; preserve all existing IDs.
- No new operator IDs in v3.
- Do not compute bounds or scan nodes in `draw()`; use the cached analysis.
- Do not use `COMPACT` for filtered lists.
- Do not use `panel_prop` for override toggles.
- Every layout change needs a visual check in Blender; the draw probe alone is
  not enough.

## Open questions

- Accept a panel jump when dynamic list heights change?
- Is a second sidebar tab acceptable, or must everything stay in one tab?
- Should Shift+click open an export dialog, or is one-click export sacred?
- Is `filter_size` in scope for removal, or is it a pixel-art convenience?
- Should Problems stay open by default when errors exist?
- Which remaining P1 items should be scheduled after 2.3.0?
- Is the 30-35 row target still the goal after the measured A0 result?
- Is P4 worth one hierarchy increment after 2.3.0, or should the list stay
  independent of the Outliner?
