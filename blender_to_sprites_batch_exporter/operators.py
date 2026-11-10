"""Operators exposed by the add-on."""

import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from .logic import (
    BatchJob,
    BUILTIN_PRESETS,
    add_always_include,
    analyze_scene,
    apply_preset,
    clear_analysis_cache,
    configure_camera,
    default_preset_dir,
    ensure_camera,
    export_preset,
    find_layer_collection,
    format_job_report,
    get_collection_bounds,
    include_all,
    is_background,
    is_owned_camera,
    is_relative_unsaved,
    load_preset,
    migrate_settings,
    preset_path,
    rebuild_target_items,
    remove_always_include,
    remove_camera,
    request_cancel,
    set_active_target,
    set_all_targets,
    sync_target_items,
    write_job_log,
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
            self._report_result(result, context)
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
            self._report_result(result, context)
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
        self._report_result(result, context)
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

    def _report_result(self, result, context):
        for problem in result.problems:
            if problem.severity == 'INFO':
                continue
            self.report({problem.severity}, problem.as_text())
        settings = context.scene.bts_settings
        report_text = settings.last_report or format_job_report(result)
        settings.last_report = report_text
        settings.last_log_path = write_job_log(settings, report_text)
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


class BTS_OT_RefreshTargets(Operator):
    bl_idname = "bts.refresh_targets"
    bl_label = "Refresh Targets"
    bl_description = "Rebuild the target list from the current collection filter"
    bl_options = {'REGISTER', 'UNDO'}

    replace: BoolProperty(default=True, options={'HIDDEN'})

    def execute(self, context):
        settings = context.scene.bts_settings
        if self.replace:
            rebuild_target_items(context, settings)
        else:
            sync_target_items(context, settings)
        clear_analysis_cache(context.scene)
        self.report({'INFO'}, f"{len(settings.target_items)} target(s).")
        return {'FINISHED'}


class BTS_OT_TargetsAll(Operator):
    bl_idname = "bts.targets_all"
    bl_label = "Enable All"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.bts_settings
        sync_target_items(context, settings)
        set_all_targets(settings, True)
        clear_analysis_cache(context.scene)
        return {'FINISHED'}


class BTS_OT_TargetsNone(Operator):
    bl_idname = "bts.targets_none"
    bl_label = "Disable All"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.bts_settings
        sync_target_items(context, settings)
        set_all_targets(settings, False)
        clear_analysis_cache(context.scene)
        return {'FINISHED'}


class BTS_OT_TargetsActive(Operator):
    bl_idname = "bts.targets_active"
    bl_label = "Only Active"
    bl_description = "Enable only the active collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.bts_settings
        sync_target_items(context, settings)
        if not set_active_target(context, settings):
            self.report({'WARNING'}, "No active collection in the Outliner.")
            return {'CANCELLED'}
        clear_analysis_cache(context.scene)
        return {'FINISHED'}


class BTS_OT_ActivateTarget(Operator):
    bl_idname = "bts.activate_target"
    bl_label = "Make Active"
    bl_options = {'REGISTER'}

    collection: StringProperty(default="")

    def execute(self, context):
        name = self.collection
        if not name:
            settings = context.scene.bts_settings
            index = int(getattr(settings, "active_target_index", 0))
            if 0 <= index < len(settings.target_items):
                name = settings.target_items[index].name
        layer = find_layer_collection(context.view_layer, name)
        if layer is None:
            self.report({'WARNING'}, f"Collection not found: {name}")
            return {'CANCELLED'}
        context.view_layer.active_layer_collection = layer
        return {'FINISHED'}


class BTS_OT_AddAlwaysInclude(Operator):
    bl_idname = "bts.add_always_include"
    bl_label = "Add Active"
    bl_description = "Add the active collection to Always Include"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active = context.view_layer.active_layer_collection
        if active is None or active.collection is None:
            self.report({'WARNING'}, "No active collection.")
            return {'CANCELLED'}
        migrate_settings(context, context.scene.bts_settings)
        add_always_include(context.scene.bts_settings, active.collection.name)
        clear_analysis_cache(context.scene)
        return {'FINISHED'}


class BTS_OT_RemoveAlwaysInclude(Operator):
    bl_idname = "bts.remove_always_include"
    bl_label = "Remove"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        settings = context.scene.bts_settings
        migrate_settings(context, settings)
        index = int(getattr(settings, "active_include_index", 0))
        remove_always_include(settings, index)
        clear_analysis_cache(context.scene)
        return {'FINISHED'}


class BTS_OT_CopyReport(Operator):
    bl_idname = "bts.copy_report"
    bl_label = "Copy Report"
    bl_description = "Copy the last export report to the clipboard"
    bl_options = {'REGISTER'}

    def execute(self, context):
        report_text = context.scene.bts_settings.last_report
        if not report_text:
            self.report({'WARNING'}, "No report yet. Run Analyze or Batch Export.")
            return {'CANCELLED'}
        context.window_manager.clipboard = report_text
        self.report({'INFO'}, "Report copied to the clipboard.")
        return {'FINISHED'}


class BTS_OT_OpenLog(Operator):
    bl_idname = "bts.open_log"
    bl_label = "Open Log"
    bl_description = "Open the last export log"
    bl_options = {'REGISTER'}

    def execute(self, context):
        path = context.scene.bts_settings.last_log_path
        if not path or not os.path.isfile(path):
            self.report({'WARNING'}, "No export log found.")
            return {'CANCELLED'}
        bpy.ops.wm.path_open(filepath=path)
        return {'FINISHED'}


class BTS_OT_ApplyPreset(Operator):
    bl_idname = "bts.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset: StringProperty(default="")

    def execute(self, context):
        values = BUILTIN_PRESETS.get(self.preset)
        if values is None:
            self.report({'WARNING'}, f"Unknown preset: {self.preset}")
            return {'CANCELLED'}
        apply_preset(context.scene.bts_settings, values)
        clear_analysis_cache(context.scene)
        self.report({'INFO'}, f"Applied preset: {self.preset}")
        return {'FINISHED'}


class BTS_OT_SavePreset(Operator):
    bl_idname = "bts.save_preset"
    bl_label = "Save Preset"
    bl_description = "Save the current export settings as JSON"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH', default="")
    preset_name: StringProperty(default="custom")

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = preset_path(self.preset_name) or "preset.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        filepath = bpy.path.ensure_ext(self.filepath, ".json")
        try:
            export_preset(context.scene.bts_settings, filepath)
        except Exception as exc:  # noqa: BLE001
            self.report({'ERROR'}, f"Could not save preset: {exc}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Preset saved: {filepath}")
        return {'FINISHED'}


class BTS_OT_LoadPreset(Operator):
    bl_idname = "bts.load_preset"
    bl_label = "Load Preset"
    bl_description = "Load export settings from a JSON preset"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH', default="")

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = default_preset_dir() or ""
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        filepath = bpy.path.ensure_ext(self.filepath, ".json")
        try:
            values, ignored, _version = load_preset(filepath)
        except ValueError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        apply_preset(context.scene.bts_settings, values)
        clear_analysis_cache(context.scene)
        if ignored:
            self.report(
                {'WARNING'},
                "Ignored unknown preset fields: " + ", ".join(sorted(ignored)),
            )
        self.report({'INFO'}, f"Preset loaded: {filepath}")
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

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

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

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

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
