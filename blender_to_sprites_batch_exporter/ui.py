"""Sidebar panels."""

from bpy.types import Panel

from .logic import (
    DEPTH_CAPABLE,
    collect_file_outputs,
    get_cached_analysis,
    is_relative_unsaved,
    normalize_image_settings,
)


# ============================================================
# UI
# ============================================================

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
        if is_relative_unsaved(context.scene.bts_settings.output_dir):
            box = layout.box()
            box.alert = True
            box.label(text="Unsaved file + relative '//' path", icon='ERROR')
        analysis = get_cached_analysis(context, context.scene.bts_settings)
        if analysis is not None:
            counts = analysis.counts
            box = layout.box()
            box.label(
                text="Analysis: "
                f"{len(analysis.targets)} target(s), "
                f"{counts['ERROR']} error(s), "
                f"{counts['WARNING']} warning(s)",
                icon='ERROR' if counts['ERROR'] else 'INFO',
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
        s = context.scene.bts_settings
        layout.prop(s, "export_source")
        layout.prop(s, "skip_empty")
        layout.separator()
        layout.prop(s, "isolation_mode")
        layout.prop(s, "keep_collections", icon='OUTLINER_COLLECTION')
        layout.prop(s, "keep_lights")
        if s.isolation_mode == 'EXCLUDE' and s.keep_lights:
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
        s = context.scene.bts_settings
        layout.prop(s, "camera_axis")
        layout.prop(s, "camera_margin")
        layout.prop(s, "auto_cleanup_camera")
        layout.separator()
        layout.prop(s, "padding_mode", expand=True)
        layout.prop(s, "padding_pixels" if s.padding_mode == 'PIXELS' else "padding_units")


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
        s = context.scene.bts_settings
        layout.prop(s, "pixels_per_unit")
        layout.prop(s, "resolution_multiple")
        layout.prop(s, "square_output")
        col = layout.column(align=True)
        col.prop(s, "min_resolution")
        col.prop(s, "max_resolution")


class BTS_PT_Output(Panel):
    bl_label = "Output"
    bl_idname = "BTS_PT_output"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        scene = context.scene
        s = scene.bts_settings
        rd = scene.render
        node_map = collect_file_outputs(
            scene, reachable_only=bool(getattr(s, "nodes_connected_only", True))
        )
        nodes = list(node_map.values())

        if nodes:
            layout.prop(s, "use_compositor_nodes")
            if s.use_compositor_nodes:
                layout.prop(s, "nodes_connected_only")

        if nodes and s.use_compositor_nodes:
            compositing_off = not getattr(rd, "use_compositing", True)
            if compositing_off:
                warn = layout.box()
                warn.alert = True
                warn.label(text="Compositing is disabled!", icon='ERROR')
                warn.label(text="It will be force-enabled during export.")

            layout.prop(s, "node_naming")
            layout.prop(s, "node_override_base")
            layout.prop(s, "output_dir", text="Base Dir" if s.node_override_base else "Fallback Dir")
            if s.node_override_base and not s.output_dir:
                e = layout.box()
                e.alert = True
                e.label(text="Base Dir is empty!", icon='ERROR')
            layout.prop(s, "write_main_output")
            layout.prop(s, "use_transparent")
            if s.node_naming == 'PREFIX':
                info = layout.box()
                info.label(text="Prefix mode updates node item names natively.", icon='INFO')
                info.label(text="No post-rename is performed, preserving Unity .meta files.")
            layout.prop(s, "use_prefix_fallback")
            if s.write_main_output:
                self._draw_format(layout, s)
            layout.prop(s, "overwrite_policy")
            layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = s.output_dir
            layout.separator()
            layout.label(text=f"{len(nodes)} File Output node(s) active", icon='NODE_COMPOSITING')
        else:
            layout.prop(s, "output_dir")
            self._draw_format(layout, s)
            layout.prop(s, "overwrite_policy")
            layout.prop(s, "use_transparent")
            layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = s.output_dir
            if nodes:
                box = layout.box()
                box.label(text="File Output nodes found but disabled.", icon='INFO')
                box.label(text="Compositing will be disabled during export.")

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
