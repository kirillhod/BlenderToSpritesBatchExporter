"""Operators exposed by the add-on."""

import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from .logic import (
    BatchJob,
    analyze_scene,
    clear_analysis_cache,
    configure_camera,
    ensure_camera,
    get_collection_bounds,
    include_all,
    is_background,
    is_owned_camera,
    is_relative_unsaved,
    remove_camera,
    request_cancel,
)


class BTS_OT_BatchExport(Operator):
    bl_idname = "bts.batch_export"
    bl_label = "Batch Export Collections"
    bl_description = "Render every target collection in isolation with an auto-fitted orthographic camera"
    bl_options = {'REGISTER'}

    overwrite_confirmed: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    confirm_message: StringProperty(default="", options={'HIDDEN', 'SKIP_SAVE'})

    _job = None
    _timer = None

    def invoke(self, context, event):
        settings = context.scene.bts_settings
        analysis, _ = analyze_scene(
            context,
            settings,
            use_cache=False,
            allow_existing=bool(self.overwrite_confirmed),
        )
        if analysis.errors:
            self._report_analysis(analysis)
            return {'CANCELLED'}

        if analysis.conflicts and not self.overwrite_confirmed:
            if is_background():
                for plan in analysis.conflicts:
                    self.report({'ERROR'}, f"File already exists: {plan.path}")
                return {'CANCELLED'}
            lines = [
                f"{plan.collection}: {plan.path}" for plan in analysis.conflicts[:8]
            ]
            if len(analysis.conflicts) > 8:
                lines.append(f"... and {len(analysis.conflicts) - 8} more")
            self.confirm_message = "Overwrite existing files?\n" + "\n".join(lines)
            self.overwrite_confirmed = True
            return context.window_manager.invoke_confirm(self, event)

        if context.window is None or is_background():
            return self.execute(context)
        return self._start_modal(context, analysis)

    def _start_modal(self, context, analysis):
        self._job = BatchJob(
            context, context.scene.bts_settings, analysis, operator=self
        )
        if not self._job.start():
            result = self._job.finish()
            self._report_result(result)
            return {'FINISHED'} if not result.cancelled else {'CANCELLED'}
        self._timer = context.window_manager.event_timer_add(
            0.01, window=context.window
        )
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC':
            if self._job is not None:
                self._job.request_cancel()
            return self._finish_modal(context)
        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}

        if self._job is None or self._job.cancelled or self._job.done:
            return self._finish_modal(context)

        try:
            self._job.step()
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, f"Batch export failed: {exc}")
            self._job.request_cancel()
        if self._job.cancelled or self._job.done:
            return self._finish_modal(context)
        return {'RUNNING_MODAL'}

    def _finish_modal(self, context):
        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        result = self._job.finish() if self._job is not None else None
        self._job = None
        if result is not None:
            self._report_result(result)
        return {'FINISHED'} if (result is None or not result.cancelled) else {'CANCELLED'}

    def execute(self, context):
        settings = context.scene.bts_settings
        analysis, _ = analyze_scene(
            context,
            settings,
            use_cache=False,
            allow_existing=bool(self.overwrite_confirmed),
        )
        if analysis.errors:
            self._report_analysis(analysis)
            return {'CANCELLED'}
        if analysis.conflicts and not self.overwrite_confirmed:
            self.report(
                {'ERROR'},
                "Existing output files require confirmation. Use the button in "
                "the 3D View or change the overwrite policy.",
            )
            return {'CANCELLED'}

        if context.window is not None and not is_background():
            return self._start_modal(context, analysis)

        job = BatchJob(context, settings, analysis, operator=self)
        result = job.run()
        self._report_result(result)
        return {'FINISHED'} if not result.cancelled else {'CANCELLED'}

    def draw(self, context):
        layout = self.layout
        for line in self.confirm_message.splitlines():
            layout.label(text=line)

    def _report_analysis(self, analysis, include_info=False):
        for problem in analysis.problems:
            if problem.severity == 'INFO' and not include_info:
                continue
            self.report({problem.severity}, problem.as_text())

    def _report_result(self, result):
        for problem in result.problems:
            if problem.severity == 'INFO':
                continue
            self.report({problem.severity}, problem.as_text())
        if result.cancelled:
            self.report(
                {'WARNING'},
                f"Batch export cancelled - {result.rendered} rendered, "
                f"{result.skipped} skipped, {result.failed} failed.",
            )
        else:
            self.report(
                {'INFO'},
                f"Batch export done - {result.rendered} rendered, "
                f"{result.skipped} skipped, {result.failed} failed.",
            )


class BTS_OT_Analyze(Operator):
    bl_idname = "bts.analyze"
    bl_label = "Analyze Export"
    bl_description = "Run preflight checks without rendering"
    bl_options = {'REGISTER'}

    def execute(self, context):
        settings = context.scene.bts_settings
        analysis, cached = analyze_scene(context, settings, use_cache=True)
        counts = analysis.counts
        self._report_analysis(analysis)
        self.report(
            {'INFO'},
            f"Analysis {'cached' if cached else 'complete'}: "
            f"{len(analysis.targets)} target(s), {counts['ERROR']} error(s), "
            f"{counts['WARNING']} warning(s), {counts['INFO']} info.",
        )
        return {'FINISHED'}

    def _report_analysis(self, analysis):
        for problem in analysis.problems:
            self.report({problem.severity}, problem.as_text())


class BTS_OT_CancelExport(Operator):
    bl_idname = "bts.cancel_export"
    bl_label = "Cancel Export"
    bl_description = "Stop the running batch export after the current collection"
    bl_options = {'REGISTER'}

    def execute(self, context):
        if request_cancel():
            self.report({'WARNING'}, "Cancellation requested.")
        else:
            self.report({'INFO'}, "No batch export is running.")
        return {'FINISHED'}


# ============================================================
# OPERATORS: PREVIEW / CLEANUP / RESTORE
# ============================================================

class BTS_OT_PreviewCamera(Operator):
    bl_idname = "bts.preview_camera"
    bl_label = "Fit Camera to Active"
    bl_description = "Position the orthographic camera over the active collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.bts_settings
        vl = context.view_layer
        alc = vl.active_layer_collection
        if alc is None or alc == vl.layer_collection:
            self.report({'WARNING'}, "Select a collection in the Outliner.")
            return {'CANCELLED'}
        col = alc.collection
        bounds = get_collection_bounds(col, context.evaluated_depsgraph_get())
        if bounds is None:
            self.report({'WARNING'}, f"'{col.name}' has no renderable geometry.")
            return {'CANCELLED'}
        cam_obj = ensure_camera(scene)
        frame = configure_camera(cam_obj, bounds[0], bounds[1], settings)
        scene.camera = cam_obj
        scene.render.resolution_x = frame["res_x"]
        scene.render.resolution_y = frame["res_y"]
        scene.render.resolution_percentage = 100
        clear_analysis_cache(scene)
        self.report({'INFO'}, f"{col.name}: {frame['res_x']}x{frame['res_y']} px, ortho {frame['ortho_scale']:.4f}")
        return {'FINISHED'}


class BTS_OT_Cleanup(Operator):
    bl_idname = "bts.cleanup"
    bl_label = "Remove Camera"
    bl_description = "Delete the temporary orthographic camera"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if is_owned_camera(context.scene.camera):
            context.scene.camera = None
        removed = remove_camera(context.scene)
        clear_analysis_cache(context.scene)
        self.report({'INFO'}, "Camera removed." if removed else "No temporary camera.")
        return {'FINISHED'}


class BTS_OT_RestoreCollections(Operator):
    bl_idname = "bts.restore_collections"
    bl_label = "Unhide Everything"
    bl_description = "Re-enable all collections and clear hide_render on all objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        vl = context.view_layer
        include_all(vl)
        for ob in context.scene.objects:
            ob.hide_render = False
        vl.update()
        clear_analysis_cache(context.scene)
        self.report({'INFO'}, "All collections included, hide_render cleared.")
        return {'FINISHED'}


class BTS_OT_OpenOutputFolder(Operator):
    bl_idname = "bts.open_output_folder"
    bl_label = "Open Output Folder"
    bl_description = "Open the output directory in your file browser"
    path: StringProperty(default="")

    def execute(self, context):
        p = self.path or context.scene.bts_settings.output_dir
        if is_relative_unsaved(p):
            self.report({'WARNING'}, "Relative path - save the .blend file first.")
            return {'CANCELLED'}
        abs_p = bpy.path.abspath(p)
        if not abs_p or not os.path.isdir(abs_p):
            self.report({'WARNING'}, f"Folder does not exist: {abs_p}")
            return {'CANCELLED'}
        bpy.ops.wm.path_open(filepath=abs_p)
        return {'FINISHED'}
