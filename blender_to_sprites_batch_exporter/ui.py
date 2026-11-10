"""Sidebar panels and collection lists."""

from bpy.types import Panel, UIList

from .logic import (
    BUILTIN_PRESETS,
    DEPTH_CAPABLE,
    get_job_status,
    is_relative_unsaved,
    node_output_format_label,
    normalize_image_settings,
    peek_cached_analysis,
    resolve_node_layout,
)


def _trim(text, limit=150):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _enabled_targets(settings):
    return sum(1 for item in settings.target_items if item.enabled)


def _short_path(path, base):
    value = str(path or "").replace("\\", "/")
    root = str(base or "").replace("\\", "/").rstrip("/")
    if root and value.casefold().startswith(root.casefold() + "/"):
        return value[len(root) + 1:]
    return value


def _preview_plan(analysis):
    if analysis is None:
        return None
    for target in analysis.targets:
        if target.skipped:
            continue
        if target.node_plans:
            return target.node_plans[0]
        if target.output_plan is not None:
            return target.output_plan
    return None


class BTS_UL_Targets(UIList):
    bl_idname = "BTS_UL_Targets"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.name, icon='OUTLINER_COLLECTION')
        if item.size_status:
            row.label(text=item.size_status)
        elif not item.enabled:
            row.label(text="disabled")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        search = str(data.target_search or "").strip().casefold()
        if not search:
            return [], []
        flags = [
            self.bitflag_filter_item
            if search in item.name.casefold()
            else 0
            for item in items
        ]
        return flags, []


class BTS_UL_AlwaysInclude(UIList):
    bl_idname = "BTS_UL_AlwaysInclude"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name, icon='OUTLINER_COLLECTION')


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
        enabled = _enabled_targets(settings)
        layout.label(
            text=f"Targets: {enabled}/{len(settings.target_items)}   "
                 f"Angle: {settings.camera_axis.title()}   Frame: 1",
            icon='OUTLINER_COLLECTION',
        )
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
        col = layout.column(align=True)
        col.scale_y = 1.6
        col.operator("bts.batch_export", icon='RENDER_ANIMATION')
        row = layout.row(align=True)
        row.operator("bts.analyze", icon='VIEWZOOM')
        row.operator("bts.cancel_export", icon='CANCEL')
        row = layout.row(align=True)
        row.operator("bts.preview_camera", icon='CON_CAMERASOLVER')
        row.operator("bts.cleanup", icon='TRASH')
        layout.operator("bts.restore_collections", icon='LOOP_BACK')
        if is_relative_unsaved(settings.output_dir):
            box = layout.box()
            box.alert = True
            box.label(text="Unsaved file + relative '//' path", icon='ERROR')
        analysis = peek_cached_analysis(context.scene)
        if analysis is not None:
            counts = analysis.counts
            box = layout.box()
            box.label(
                text=f"Analysis: {len(analysis.targets)} target(s), "
                     f"{counts['ERROR']} error(s), "
                     f"{counts['WARNING']} warning(s)",
                icon='ERROR' if counts['ERROR'] else 'INFO',
            )
            box.label(text="Details are in the Problems panel.")
        else:
            layout.label(text="Run Analyze to validate settings.", icon='INFO')


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
        layout.template_list(
            "BTS_UL_Targets",
            "",
            settings,
            "target_items",
            settings,
            "active_target_index",
            rows=7,
        )
        row = layout.row(align=True)
        row.operator("bts.targets_all", text="All")
        row.operator("bts.targets_none", text="None")
        row.operator("bts.targets_active", text="Active")
        row.operator("bts.activate_target", text="Make Active", icon='RESTRICT_SELECT_OFF')
        layout.prop(settings, "skip_empty")

        layout.separator()
        layout.label(text="Always Include", icon='OUTLINER_COLLECTION')
        layout.template_list(
            "BTS_UL_AlwaysInclude",
            "",
            settings,
            "always_include_items",
            settings,
            "active_include_index",
            rows=3,
        )
        row = layout.row(align=True)
        row.operator("bts.add_always_include", text="Add Active", icon='ADD')
        row.operator("bts.remove_always_include", text="Remove", icon='REMOVE')
        layout.prop(settings, "isolation_mode")
        layout.prop(settings, "keep_lights")
        if settings.isolation_mode == 'EXCLUDE' and settings.keep_lights:
            info = layout.box()
            info.label(text="Light collections are included automatically.", icon='INFO')
            info.label(text="Other objects in those collections may render too.")


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
        layout.prop(settings, "camera_axis")
        layout.prop(settings, "camera_margin")
        layout.prop(settings, "auto_cleanup_camera")
        layout.separator()
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
        layout.prop(settings, "resolution_multiple")
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

        if analysis is None:
            box = layout.box()
            box.label(text="File Output detection uses the analysis cache.", icon='INFO')
            box.operator("bts.analyze", icon='VIEWZOOM')

        if nodes:
            layout.prop(settings, "use_compositor_nodes")
            if settings.use_compositor_nodes:
                layout.prop(settings, "nodes_connected_only")

        if analysis is not None and nodes and settings.use_compositor_nodes:
            self._draw_node_output(layout, settings, analysis, nodes, context.scene.render)
        else:
            self._draw_main_output(layout, settings)
            if nodes:
                box = layout.box()
                box.label(text="File Output nodes found but disabled.", icon='INFO')
                box.label(text="Compositing will be disabled during export.")

    def _draw_main_output(self, layout, settings):
        layout.prop(settings, "output_dir")
        layout.prop(settings, "name_template")
        layout.label(text="Examples: {collection} -> Body.png", icon='FILE_IMAGE')
        layout.label(text="{collection}_sprite -> Body_sprite.png")
        self._draw_format(layout, settings)
        layout.prop(settings, "overwrite_policy")
        layout.prop(settings, "use_transparent")
        layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = settings.output_dir
        self._draw_preview(layout, settings, None)

    def _draw_node_output(self, layout, settings, analysis, nodes, render):
        compositing_off = not getattr(render, "use_compositing", True)
        if compositing_off:
            warn = layout.box()
            warn.alert = True
            warn.label(text="Compositing is disabled!", icon='ERROR')
            warn.label(text="It will be force-enabled during export.")

        layout.label(text=f"{len(nodes)} active File Output node(s)", icon='NODE_COMPOSITING')
        layout.prop(settings, "node_naming")
        resolved = resolve_node_layout(settings.node_naming, nodes)
        node_only = bool(settings.use_compositor_nodes and not settings.write_main_output)
        if resolved:
            label = {
                "FILENAME": "Collection Name",
                "SUBFOLDER": "Collection Subfolder",
                "PREFIX": "Collection Prefix",
                "NONE": "Don't Modify",
            }.get(resolved, resolved)
            layout.label(text=f"Resolved: {label}", icon='INFO')
        if settings.node_naming == 'PREFIX':
            info = layout.box()
            info.label(text="Prefix is a flat multi-output layout.", icon='INFO')
            info.label(text="An existing collection token is not duplicated.")
        if len(nodes) != 1 and settings.node_naming == 'FILENAME':
            warn = layout.box()
            warn.alert = True
            warn.label(text="Collection Name requires one File Output node.", icon='ERROR')
            warn.label(text="Use Automatic, Subfolder or Prefix.")
        if len(analysis.targets) > 1 and settings.node_naming == 'NONE':
            warn = layout.box()
            warn.alert = True
            warn.label(text="Don't Modify is a single-collection mode.", icon='ERROR')
            warn.label(text="Use Automatic, Subfolder or Prefix.")

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
        if node_only:
            info = layout.box()
            info.label(
                text=f"Node output: {node_output_format_label(nodes[0])}",
                icon='FILE_IMAGE',
            )
            info.label(text="Enable Also Save Main Render for PNG/JPEG.")
        else:
            self._draw_format(layout, settings)
        layout.prop(settings, "use_transparent")
        layout.prop(settings, "overwrite_policy")
        if settings.write_main_output:
            layout.prop(settings, "name_template")
            layout.label(text="Example: {collection} -> Body.png", icon='FILE_IMAGE')
        else:
            layout.label(text="Node layout writes EXR files.", icon='INFO')
        if analysis.conflicts:
            box = layout.box()
            box.alert = True
            box.label(
                text=f"{len(analysis.conflicts)} existing file(s) need confirmation.",
                icon='ERROR',
            )
            for conflict in analysis.conflicts[:3]:
                box.label(
                    text=_trim(
                        f"{conflict.collection}: "
                        f"{_short_path(conflict.path, settings.output_dir)}"
                    )
                )
        self._draw_preview(layout, settings, analysis)
        advanced = layout.box()
        advanced.label(text="Advanced", icon='PREFERENCES')
        advanced.prop(settings, "use_prefix_fallback")
        layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = settings.output_dir

    def _draw_preview(self, layout, settings, analysis):
        if analysis is None:
            return
        plan = _preview_plan(analysis)
        if plan is None:
            return
        box = layout.box()
        box.label(text="Path Preview", icon='FILE_IMAGE')
        box.label(text=_trim(_short_path(getattr(plan, "path", ""), settings.output_dir)))
        if getattr(plan, "exists", False):
            box.label(text="File already exists", icon='ERROR')
        if analysis.node_plans:
            extra = len(analysis.node_plans) - 1
            if extra > 0:
                box.label(text=f"... and {extra} node output(s)")

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
            ("WARNING", 'WARNING'),
            ("INFO", 'INFO'),
        ):
            group = [problem for problem in analysis.problems if problem.severity == severity]
            if not group:
                continue
            box = layout.box()
            box.label(text=f"{severity.title()} ({len(group)})", icon=icon)
            for problem in group[:6]:
                col = box.column(align=True)
                col.label(text=_trim(f"{problem.code}: {problem.message}"))
                if problem.collection:
                    col.label(text=f"Collection: {problem.collection}")
                if problem.fix_hint:
                    col.label(text=_trim(problem.fix_hint))
            if len(group) > 6:
                box.label(text=f"... and {len(group) - 6} more")
        layout.label(text="Warnings do not block export; errors do.", icon='INFO')
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
        for name in BUILTIN_PRESETS:
            layout.operator("bts.apply_preset", text=name, icon='PRESET').preset = name
        layout.separator()
        row = layout.row(align=True)
        row.operator("bts.save_preset", text="Save JSON", icon='FILE_TICK')
        row.operator("bts.load_preset", text="Load JSON", icon='FILEBROWSER')
        layout.label(text="Multi-view presets arrive with 2.1.", icon='INFO')


class BTS_PT_Report(Panel):
    bl_label = "Report"
    bl_idname = "BTS_PT_report"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.bts_settings
        report = settings.last_report
        if report:
            box = layout.box()
            for line in report.splitlines()[:20]:
                box.label(text=line)
            if len(report.splitlines()) > 20:
                box.label(text="... see the log file for the full report")
        else:
            layout.label(text="No export report yet.", icon='INFO')
        row = layout.row(align=True)
        row.operator("bts.copy_report", icon='COPYDOWN')
        row.operator("bts.open_log", icon='TEXT')
        row.operator("bts.open_output_folder", icon='FILE_FOLDER').path = settings.output_dir
