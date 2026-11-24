"""Sidebar panels and collection lists."""

from bpy.types import Panel, UIList

from .logic import (
    DEPTH_CAPABLE,
    active_override_groups,
    gather_source_collections,
    get_job_status,
    is_relative_unsaved,
    normalize_image_settings,
    peek_cached_analysis,
    preview_active,
    preview_message,
    resolve_node_layout,
    target_view_count,
)


# Share of the row left for the collection name; the rest is the status column.
_TARGET_NAME_FACTOR = 0.55
_PREVIEW_NAME_FACTOR = 0.42
_NODE_NAME_FACTOR = 0.42
_VIEW_TOGGLES = (
    ("view_top", "Top"),
    ("view_bottom", "Bottom"),
    ("view_front", "Front"),
    ("view_back", "Back"),
    ("view_right", "Right"),
    ("view_left", "Left"),
)


def _left_checkbox(layout, owner, prop, text=None):
    """Draw a checkbox with its label on the left side."""
    row = layout.row()
    row.use_property_split = False
    if text is None:
        row.prop(owner, prop)
    else:
        row.prop(owner, prop, text=text)


def _wrap_text(text, width=48):
    """Split one long string into readable panel lines without losing text."""
    value = " ".join(str(text or "").split())
    if not value:
        return []
    lines = []
    while len(value) > width:
        cut = value.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width
        lines.append(value[:cut])
        value = value[cut:].lstrip()
    if value:
        lines.append(value)
    return lines


def _target_status_text(status, compact=False):
    """Explain the value shown to the right of a target name."""
    value = str(status or "").strip()
    if not value:
        return ""
    if value[0].isdigit():
        return value if compact else f"Canvas {value}"
    if compact:
        return "skipped"
    return f"Skipped: {value}"


def _target_counts(context, settings):
    """Enabled and visible target counts for the current export mode."""
    try:
        names = {
            collection.name
            for collection in gather_source_collections(context, settings)
        }
        items = [item for item in settings.target_items if item.name in names]
    except Exception:  # noqa: BLE001
        items = list(settings.target_items)
    return sum(1 for item in items if item.enabled), len(items)


def _list_rows(count, minimum, maximum):
    """Content-sized list height, clamped to a stable range."""
    return max(int(minimum), min(int(maximum), int(count)))


def _target_row_count(context, settings):
    """Rows visible after the export-mode and search filters."""
    try:
        names = {
            collection.name
            for collection in gather_source_collections(context, settings)
        }
        items = [item for item in settings.target_items if item.name in names]
    except Exception:  # noqa: BLE001
        items = list(settings.target_items)
    search = str(getattr(settings, "target_search", "") or "").strip().casefold()
    if search:
        items = [item for item in items if search in item.name.casefold()]
    return len(items)


def _active_target_item(context, settings):
    """Selected target row, or None when it is not visible right now."""
    try:
        items = settings.target_items
        index = int(getattr(settings, "active_target_index", 0) or 0)
        if not 0 <= index < len(items):
            return None
        item = items[index]
        names = {
            collection.name
            for collection in gather_source_collections(context, settings)
        }
        if item.name not in names:
            return None
        search = str(getattr(settings, "target_search", "") or "").strip().casefold()
        if search and search not in item.name.casefold():
            return None
        return item
    except Exception:  # noqa: BLE001
        return None


def _draw_view_grid(layout, owner):
    for start in range(0, len(_VIEW_TOGGLES), 3):
        row = layout.row(align=True)
        for field, label in _VIEW_TOGGLES[start:start + 3]:
            row.prop(owner, field, text=label, toggle=True, expand=True)


def _draw_framing_override(layout, item):
    col = layout.column(align=True)
    col.prop(item, "camera_margin", text="Margin")
    col.prop(item, "padding_mode", expand=True)
    col.prop(
        item,
        "padding_pixels" if item.padding_mode == 'PIXELS' else "padding_units",
    )


def _draw_resolution_override(layout, item):
    col = layout.column(align=True)
    col.prop(item, "pixels_per_unit")
    col.prop(item, "resolution_multiple", text="Round To")
    col.prop(item, "square_output")
    col.prop(item, "min_resolution")
    col.prop(item, "max_resolution")


def _draw_overrides(layout, item):
    if item is None:
        row = layout.row()
        row.active = False
        row.label(text="Overrides: no target selected", icon='INFO')
        return
    groups = (
        ("view", "View", _draw_view_grid),
        ("framing", "Framing", _draw_framing_override),
        ("resolution", "Resolution", _draw_resolution_override),
    )
    for group, label, draw in groups:
        enabled = bool(getattr(item, "override_" + group, False))
        if not enabled:
            # Nothing to expand while the override is off: draw a plain
            # checkbox row instead of a panel with an empty body.
            row = layout.row()
            row.use_property_split = False
            row.prop(item, "override_" + group, text=label)
            continue
        header, body = layout.panel(
            "bts_override_" + group, default_closed=False
        )
        header.use_property_split = False
        header.prop(item, "override_" + group, text=label)
        if body is not None:
            draw(body, item)


class BTS_UL_Targets(UIList):
    bl_idname = "BTS_UL_Targets"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        split = row.split(factor=_TARGET_NAME_FACTOR, align=True)
        split.label(text=item.name, icon='OUTLINER_COLLECTION')
        analysis = peek_cached_analysis(context.scene)
        status = ""
        if analysis is not None and item.size_status:
            status = _target_status_text(item.size_status, compact=True)
        elif not item.enabled:
            status = "disabled"
        if active_override_groups(item):
            split.label(text=status, icon='DECORATE_OVERRIDE')
        elif status:
            split.label(text=status)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        search = str(data.target_search or "").strip().casefold()
        source_names = None
        if context is not None:
            try:
                source_names = {
                    collection.name
                    for collection in gather_source_collections(context, data)
                }
            except Exception:  # noqa: BLE001
                source_names = None
        flags = []
        for item in items:
            visible = source_names is None or item.name in source_names
            if visible and search:
                visible = search in item.name.casefold()
            flags.append(self.bitflag_filter_item if visible else 0)
        return flags, []


class BTS_UL_AlwaysInclude(UIList):
    bl_idname = "BTS_UL_AlwaysInclude"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon='OUTLINER_COLLECTION')


class BTS_UL_Preview(UIList):
    bl_idname = "BTS_UL_Preview"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        split = row.split(factor=_PREVIEW_NAME_FACTOR, align=True)
        split.label(text=item.name, icon='OUTLINER_COLLECTION')
        split.label(
            text=item.path,
            icon='ERROR' if item.exists else 'FILE_IMAGE',
        )


class BTS_UL_NodeOutputs(UIList):
    bl_idname = "BTS_UL_NodeOutputs"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        split = row.split(factor=_NODE_NAME_FACTOR, align=True)
        split.label(text=item.name, icon='NODE_COMPOSITING')
        split.label(text=item.detail)


class BTS_PT_MainPanel(Panel):
    bl_label = "Blender To Sprites"
    bl_idname = "BTS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.bts_settings
        enabled, visible = _target_counts(context, settings)
        analysis = peek_cached_analysis(context.scene)
        summary = (
            f"Targets: {enabled}/{visible}   "
            f"Views: {target_view_count(settings)}"
        )
        if analysis is not None:
            tasks = sum(
                1 for task in getattr(analysis, "tasks", ()) if not task.skip_reason
            )
            summary += f"   Tasks: {tasks}"
        layout.label(text=summary, icon='OUTLINER_COLLECTION')
        status = get_job_status()
        if status.get("running"):
            box = layout.box()
            box.label(text=status.get("text", "Exporting..."), icon='TIME')
            box.label(
                text=f"{status.get('current', 0)}/{status.get('total', 0)}  "
                     f"rendered {status.get('rendered', 0)}  "
                     f"skipped {status.get('skipped', 0)}  "
                     f"failed {status.get('failed', 0)}"
            )
        row = layout.row(align=True)
        row.operator("bts.batch_export", icon='RENDER_ANIMATION')
        row = layout.row(align=True)
        row.operator("bts.analyze", icon='VIEWZOOM')
        row.operator("bts.cancel_export", icon='CANCEL')
        row = layout.row(align=True)
        row.operator("bts.preview_camera", text="Fit Camera", icon='CON_CAMERASOLVER')
        row.operator("bts.cleanup", icon='TRASH')
        layout.operator("bts.restore_collections", icon='LOOP_BACK')
        if is_relative_unsaved(settings.output_dir):
            box = layout.box()
            box.alert = True
            box.label(text="Unsaved file + relative '//' path", icon='ERROR')
        if analysis is not None:
            counts = analysis.counts
            if counts['ERROR'] or counts['WARNING']:
                row = layout.row()
                row.alert = bool(counts['ERROR'])
                row.label(
                    text=f"Analysis: {counts['ERROR']} error(s), "
                         f"{counts['WARNING']} warning(s)",
                    icon='ERROR' if counts['ERROR'] else 'STATUS_WARNING',
                )


class BTS_PT_Source(Panel):
    bl_label = "Collections"
    bl_idname = "BTS_PT_source"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.bts_settings

        layout.prop(settings, "export_source")
        row = layout.row(align=True)
        row.operator("bts.refresh_targets", icon='FILE_REFRESH')
        row.prop(settings, "target_search", text="", icon='VIEWZOOM')
        list_layout = layout.column()
        list_layout.use_property_split = False
        list_layout.use_property_decorate = False
        visible_rows = _target_row_count(context, settings)
        if visible_rows:
            header_row = list_layout.row(align=True)
            header_row.label(icon='BLANK1')
            split = header_row.split(factor=_TARGET_NAME_FACTOR, align=True)
            split.label(text="Collection", icon='OUTLINER_COLLECTION')
            split.label(text="Canvas / status")
            list_layout.template_list(
                "BTS_UL_Targets",
                "",
                settings,
                "target_items",
                settings,
                "active_target_index",
                rows=_list_rows(visible_rows, 3, 8),
            )
        else:
            search = str(getattr(settings, "target_search", "") or "").strip()
            list_layout.label(
                text="No targets match." if search else "No collections found.",
                icon='INFO',
            )
        grid = layout.grid_flow(
            row_major=True, columns=4, even_columns=True, align=True
        )
        grid.operator("bts.targets_all", text="All")
        grid.operator("bts.targets_none", text="None")
        grid.operator("bts.targets_active", text="Active")
        grid.operator("bts.activate_target", text="Activate")
        _left_checkbox(layout, settings, "skip_empty")

        active_preview = preview_active(context.scene)
        preview_row = layout.row(align=True)
        preview_split = preview_row.split(factor=0.55, align=True)
        op = preview_split.operator(
            "bts.preview_camera",
            text="Exit Preview" if active_preview else "Preview",
            icon='VIEW_CAMERA',
        )
        op.preview = True
        _left_checkbox(preview_split, settings, "show_canvas_grid")
        if active_preview:
            message = preview_message(context.scene)
            if message:
                layout.label(text=message, icon='ERROR')

        layout.separator(factor=0.5)
        _draw_overrides(layout, _active_target_item(context, settings))

        layout.separator(factor=0.5)
        layout.label(text="Always Include", icon='OUTLINER_COLLECTION')
        include_items = settings.always_include_items
        if len(include_items) == 0:
            layout.label(text="No collections selected.", icon='INFO')
        else:
            layout.template_list(
                "BTS_UL_AlwaysInclude",
                "",
                settings,
                "always_include_items",
                settings,
                "active_include_index",
                rows=_list_rows(len(include_items), 1, 3),
            )
        row = layout.row(align=True)
        row.operator("bts.add_always_include", text="Add Active", icon='ADD')
        row.operator("bts.remove_always_include", text="Remove", icon='REMOVE')
        layout.prop(settings, "isolation_mode")
        layout.prop(settings, "keep_lights")


class BTS_PT_Camera(Panel):
    bl_label = "Camera & Framing"
    bl_idname = "BTS_PT_camera"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.bts_settings
        _draw_view_grid(layout, settings)
        layout.prop(settings, "camera_margin", text="Margin")
        layout.prop(settings, "auto_cleanup_camera", text="Remove Camera")
        layout.separator(factor=0.5)
        layout.prop(settings, "padding_mode", expand=True)
        layout.prop(
            settings,
            "padding_pixels" if settings.padding_mode == 'PIXELS' else "padding_units",
        )


class BTS_PT_Resolution(Panel):
    bl_label = "Resolution"
    bl_idname = "BTS_PT_resolution"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.bts_settings
        layout.prop(settings, "pixels_per_unit")
        layout.prop(settings, "resolution_multiple", text="Round To")
        layout.prop(settings, "square_output")
        col = layout.column(align=True)
        col.prop(settings, "min_resolution")
        col.prop(settings, "max_resolution")


class BTS_PT_Output(Panel):
    bl_label = "Output & Naming"
    bl_idname = "BTS_PT_output"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.bts_settings
        analysis = peek_cached_analysis(context.scene)
        nodes = list(analysis.all_file_outputs.values()) if analysis else []

        if nodes:
            _left_checkbox(layout, settings, "use_compositor_nodes")
            if settings.use_compositor_nodes:
                _left_checkbox(layout, settings, "nodes_connected_only")

        if analysis is not None and nodes and settings.use_compositor_nodes:
            self._draw_node_output(layout, settings, analysis, nodes, context.scene.render)
        else:
            self._draw_main_output(layout, settings, context.scene.render)
            if nodes:
                layout.label(text="File Output nodes found but disabled.", icon='INFO')
        self._draw_path_preview(layout, settings)

    def _draw_main_output(self, layout, settings, render):
        layout.prop(settings, "output_dir")
        layout.prop(settings, "name_template")
        self._draw_format(layout, settings)
        layout.prop(settings, "overwrite_policy")
        layout.prop(settings, "use_transparent")
        layout.prop(render, "filter_size")
        layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = settings.output_dir

    def _draw_node_output(self, layout, settings, analysis, nodes, render):
        compositing_off = not getattr(render, "use_compositing", True)
        if compositing_off:
            warn = layout.box()
            warn.alert = True
            warn.label(
                text="Compositing is disabled; it will be force-enabled during export.",
                icon='ERROR',
            )

        self._draw_node_list(layout, settings, nodes)
        layout.prop(settings, "node_naming")
        resolved = resolve_node_layout(settings.node_naming, nodes)
        node_only = bool(settings.use_compositor_nodes and not settings.write_main_output)
        if resolved:
            label = {
                "FILENAME": "Collection Only",
                "SUBFOLDER": "Collection Folder",
                "PREFIX": "Collection + Socket",
                "NONE": "Don't Modify",
            }.get(resolved, resolved)
            layout.label(text=f"Resolved: {label}", icon='INFO')
        if len(nodes) != 1 and settings.node_naming == 'FILENAME':
            warn = layout.box()
            warn.alert = True
            warn.label(text="Collection Only ignores socket names.", icon='ERROR')
            warn.label(text="It requires exactly one File Output node.")
        if len(analysis.targets) > 1 and settings.node_naming == 'NONE':
            warn = layout.box()
            warn.alert = True
            warn.label(text="Don't Modify is a single-collection mode.", icon='ERROR')

        layout.prop(settings, "node_override_base")
        layout.prop(
            settings,
            "output_dir",
            text="Base Directory" if settings.node_override_base else "Fallback Directory",
        )
        if settings.node_override_base and not settings.output_dir:
            error = layout.box()
            error.alert = True
            error.label(text="Base Directory is empty!", icon='ERROR')
        layout.prop(settings, "write_main_output")
        if not node_only:
            self._draw_format(layout, settings)
        layout.prop(settings, "use_transparent")
        layout.prop(render, "filter_size")
        layout.prop(settings, "overwrite_policy")
        if settings.write_main_output:
            layout.prop(settings, "name_template")
        if analysis.conflicts:
            box = layout.box()
            box.alert = True
            box.label(
                text=f"{len(analysis.conflicts)} existing file(s) need confirmation.",
                icon='ERROR',
            )
            for conflict in analysis.conflicts:
                for line in _wrap_text(f"{conflict.collection}: {conflict.path}"):
                    box.label(text=line)
        layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = settings.output_dir

    def _draw_node_list(self, layout, settings, nodes):
        layout.label(
            text=f"File Output Nodes ({len(nodes)})",
            icon='NODE_COMPOSITING',
        )
        list_layout = layout.column()
        list_layout.use_property_split = False
        list_layout.use_property_decorate = False
        header = list_layout.row(align=True)
        split = header.split(factor=_NODE_NAME_FACTOR, align=True)
        split.label(text="Node", icon='NODE_COMPOSITING')
        split.label(text="Format / outputs")
        list_layout.template_list(
            "BTS_UL_NodeOutputs",
            "",
            settings,
            "node_items",
            settings,
            "active_node_index",
            rows=_list_rows(len(nodes), 1, 3),
        )

    def _draw_path_preview(self, layout, settings):
        count = len(settings.preview_items)
        row = layout.row()
        row.use_property_split = False
        row.prop(settings, "show_path_preview", text="Path Preview")
        row.label(text=f"{count} file(s)")
        if not settings.show_path_preview or count == 0:
            return
        list_layout = layout.column()
        list_layout.use_property_split = False
        list_layout.use_property_decorate = False
        header = list_layout.row(align=True)
        split = header.split(factor=_PREVIEW_NAME_FACTOR, align=True)
        split.label(text="Collection", icon='OUTLINER_COLLECTION')
        split.label(text="Path")
        list_layout.template_list(
            "BTS_UL_Preview",
            "",
            settings,
            "preview_items",
            settings,
            "active_preview_index",
            rows=_list_rows(count, 1, 4),
        )

    def _draw_format(self, layout, settings):
        layout.prop(settings, "file_format")
        layout.prop(settings, "color_mode")
        if settings.file_format in DEPTH_CAPABLE:
            layout.prop(settings, "color_depth")
        _, _, _, problems = normalize_image_settings(settings)
        for _, message in problems:
            box = layout.box()
            box.alert = True
            box.label(text=message, icon='ERROR')


class BTS_PT_Problems(Panel):
    bl_label = "Problems"
    bl_idname = "BTS_PT_problems"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        analysis = peek_cached_analysis(context.scene)
        if analysis is None:
            layout.label(text="No analysis yet.", icon='INFO')
            layout.operator("bts.analyze", icon='VIEWZOOM')
            return
        for severity, icon in (
            ("ERROR", 'ERROR'),
            ("WARNING", 'STATUS_WARNING'),
            ("INFO", 'INFO'),
        ):
            group = [problem for problem in analysis.problems if problem.severity == severity]
            if not group:
                continue
            box = layout.box()
            box.label(text=f"{severity.title()} ({len(group)})", icon=icon)
            for problem in group:
                col = box.column(align=True)
                col.scale_y = 0.9
                for line in _wrap_text(f"{problem.code}: {problem.message}"):
                    col.label(text=line)
                if problem.collection:
                    col.label(text=f"Collection: {problem.collection}")
                if problem.fix_hint:
                    for line in _wrap_text(problem.fix_hint):
                        col.label(text=line)
                col.separator(factor=0.25)
        row = layout.row(align=True)
        row.operator("bts.analyze", icon='VIEWZOOM')
        row.operator("bts.copy_report", icon='COPYDOWN')


class BTS_PT_Presets(Panel):
    bl_label = "Presets"
    bl_idname = "BTS_PT_presets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.bts_settings
        layout.operator_menu_enum(
            "bts.apply_preset",
            "preset",
            text="Apply Built-in Preset",
            icon='PRESET',
        )
        layout.separator(factor=0.5)
        layout.prop(settings, "preset_description")
        row = layout.row(align=True)
        row.operator("bts.save_preset", text="Save JSON", icon='FILE_TICK')
        row.operator("bts.load_preset", text="Load JSON", icon='FILEBROWSER')


class BTS_PT_Report(Panel):
    bl_label = "Log"
    bl_idname = "BTS_PT_report"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("bts.copy_report", icon='COPYDOWN')
        row.operator("bts.open_log", icon='TEXT')
