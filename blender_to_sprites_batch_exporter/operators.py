"""Operators exposed by the add-on."""

import os
import time

import bpy
import mathutils
from bpy.props import StringProperty
from bpy.types import Operator

from .logic import (
    DEPTH_CAPABLE,
    EXT_BY_FORMAT,
    apply_image_settings,
    apply_node_paths,
    collect_file_outputs,
    configure_camera,
    ensure_camera,
    ensure_dir,
    gather_target_collections,
    get_collection_bounds,
    include_all,
    is_owned_camera,
    is_relative_unsaved,
    isolate_collection_by_exclude,
    isolate_collection_by_hide,
    parse_keep_collections,
    prefix_new_files,
    remove_camera,
    restore_excludes,
    restore_hide_render,
    restore_node,
    safe_join,
    sanitize_filename,
    snapshot_excludes,
    snapshot_files,
    snapshot_hide_render,
    snapshot_node,
    unique_dirs,
)


# ============================================================
# OPERATOR: BATCH EXPORT
# ============================================================

class BTS_OT_BatchExport(Operator):
    bl_idname = "bts.batch_export"
    bl_label = "Batch Export Collections"
    bl_description = "Render every target collection in isolation with an auto-fitted orthographic camera"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        vl = context.view_layer
        settings = scene.bts_settings
        rd = scene.render
        wm = context.window_manager

        targets = gather_target_collections(context, settings)
        if not targets:
            self.report({'WARNING'}, "No collections found to export.")
            return {'CANCELLED'}

        keep_collections = parse_keep_collections(settings)
        all_file_outputs = collect_file_outputs(scene)
        using_nodes = bool(settings.use_compositor_nodes and all_file_outputs)
        node_map = all_file_outputs if using_nodes else {}

        if settings.node_override_base and not settings.output_dir:
            self.report({'ERROR'}, "Override Base Paths is enabled but Output Directory is empty.")
            return {'CANCELLED'}
        if settings.write_main_output and not settings.output_dir:
            self.report({'ERROR'}, "Also Write Main Render is enabled but Output Directory is empty.")
            return {'CANCELLED'}
        if not using_nodes and not settings.output_dir:
            self.report({'ERROR'}, "Output Directory is empty.")
            return {'CANCELLED'}
        if is_relative_unsaved(settings.output_dir):
            self.report({'ERROR'}, "Output path is relative ('//') but the .blend has never been saved. Save the file or use an absolute path.")
            return {'CANCELLED'}

        if settings.output_dir:
            output_dir_abs = bpy.path.abspath(settings.output_dir)
            try:
                os.makedirs(output_dir_abs, exist_ok=True)
            except Exception as e:
                self.report({'ERROR'}, f"Cannot create output directory: {e}")
                return {'CANCELLED'}

        render_exts = set()
        render_exts.add(EXT_BY_FORMAT.get(settings.file_format, "").lower())
        for node in all_file_outputs.values():
            fmt = getattr(node, "format", None)
            if fmt is not None:
                render_exts.add(EXT_BY_FORMAT.get(getattr(fmt, "file_format", ""), "").lower())
        render_exts.discard("")

        node_snapshots = [snapshot_node(n, k) for k, n in node_map.items()]
        exclude_snapshot = snapshot_excludes(vl)
        hide_snapshot = snapshot_hide_render(scene)

        orig = {
            "camera": scene.camera,
            "camera_owned": is_owned_camera(scene.camera),
            "res_x": rd.resolution_x,
            "res_y": rd.resolution_y,
            "res_pct": rd.resolution_percentage,
            "filepath": rd.filepath,
            "format": rd.image_settings.file_format,
            "color_mode": rd.image_settings.color_mode,
            "color_depth": rd.image_settings.color_depth,
            "transparent": rd.film_transparent,
            "use_compositing": getattr(rd, "use_compositing", True),
        }

        include_all(vl)
        vl.update()
        depsgraph = context.evaluated_depsgraph_get()
        measured = []
        skipped = 0
        zero = mathutils.Vector((0.0, 0.0, 0.0))

        for col in targets:
            bounds = get_collection_bounds(col, depsgraph)
            if bounds is None:
                if settings.skip_empty:
                    skipped += 1
                    continue
                bounds = (zero.copy(), zero.copy())
            measured.append((col, bounds))

        if not measured:
            restore_excludes(vl, exclude_snapshot)
            vl.update()
            self.report({'WARNING'}, "No collections with renderable geometry.")
            return {'CANCELLED'}

        cam_obj = ensure_camera(scene)
        scene.camera = cam_obj
        rd.resolution_percentage = 100
        rd.film_transparent = settings.use_transparent

        if using_nodes:
            try:
                rd.use_compositing = True
            except Exception:
                pass
        elif all_file_outputs:
            try:
                rd.use_compositing = False
            except Exception:
                pass

        if (not using_nodes) or settings.write_main_output:
            apply_image_settings(rd.image_settings, settings)

        rendered = 0
        reported_problems = set()
        hide_failures = []
        restore_failures = []
        wm.progress_begin(0, len(measured))

        try:
            for index, (col, (bmin, bmax)) in enumerate(measured):
                wm.progress_update(index)
                safe_name = sanitize_filename(col.name)
                frame = configure_camera(cam_obj, bmin, bmax, settings)
                rd.resolution_x = frame["res_x"]
                rd.resolution_y = frame["res_y"]

                if settings.isolation_mode == 'EXCLUDE':
                    if not isolate_collection_by_exclude(vl, col, keep_collections):
                        skipped += 1
                        continue
                else:
                    include_all(vl)
                    isolate_collection_by_hide(scene, col, keep_collections, settings.keep_lights, hide_failures)
                vl.update()

                rename_scan_dirs = []
                do_prefix_rename = False

                if using_nodes:
                    live_nodes = collect_file_outputs(scene)
                    for snap in node_snapshots:
                        node = live_nodes.get(snap["key"])
                        if node is None:
                            msg = f"Could not resolve File Output node '{snap['name']}'"
                            if msg not in reported_problems:
                                reported_problems.add(msg)
                                self.report({'WARNING'}, msg)
                            continue

                        target_dir, scan_dirs, needs_prefix, problems = apply_node_paths(node, settings, col.name, snap)
                        for p in problems:
                            if p not in reported_problems:
                                reported_problems.add(p)
                                self.report({'WARNING'}, p)
                        if target_dir:
                            ensure_dir(target_dir)
                        for d in scan_dirs:
                            ensure_dir(d)
                        if needs_prefix:
                            do_prefix_rename = True
                            rename_scan_dirs.extend(scan_dirs)

                write_still = bool(settings.write_main_output and settings.output_dir) if using_nodes else True
                if write_still:
                    rd.filepath = safe_join(settings.output_dir, safe_name)

                rename_before = None
                render_start = time.time()

                if do_prefix_rename:
                    rename_scan_dirs = unique_dirs(rename_scan_dirs)
                    for d in rename_scan_dirs:
                        ensure_dir(d)
                    rename_before = snapshot_files(rename_scan_dirs, render_exts or None)

                try:
                    bpy.ops.render.render(write_still=write_still)
                    rendered += 1
                except Exception as e:
                    self.report({'WARNING'}, f"Render failed for '{col.name}': {e}")
                else:
                    if do_prefix_rename:
                        prefix_new_files(rename_scan_dirs, safe_name, rename_before, render_start, render_exts or None)
        finally:
            wm.progress_end()
            if node_snapshots:
                live_nodes = collect_file_outputs(scene)
                for snap in node_snapshots:
                    node = live_nodes.get(snap["key"])
                    if node is not None:
                        restore_node(node, snap)

            restore_hide_render(scene, hide_snapshot, restore_failures)
            restore_excludes(vl, exclude_snapshot)
            vl.update()

            rd.resolution_x = orig["res_x"]
            rd.resolution_y = orig["res_y"]
            rd.resolution_percentage = orig["res_pct"]
            rd.filepath = orig["filepath"]
            rd.image_settings.file_format = orig["format"]
            for attr in ("color_mode", "color_depth"):
                try:
                    setattr(rd.image_settings, attr, orig[attr])
                except Exception:
                    pass
            rd.film_transparent = orig["transparent"]
            try:
                rd.use_compositing = orig["use_compositing"]
            except Exception:
                pass

            restore_cam = None if orig["camera_owned"] else orig["camera"]
            if settings.auto_cleanup_camera:
                remove_camera(scene)
                try:
                    scene.camera = restore_cam
                except (ReferenceError, TypeError):
                    scene.camera = None
            else:
                try:
                    scene.camera = restore_cam if restore_cam is not None else cam_obj
                except (ReferenceError, TypeError):
                    scene.camera = cam_obj

            all_hide_failures = sorted(set(hide_failures) | set(restore_failures))
            if all_hide_failures:
                preview = ", ".join(all_hide_failures[:5])
                if len(all_hide_failures) > 5:
                    preview += ", ..."
                self.report(
                    {'WARNING'},
                    f"Could not change hide_render for {len(all_hide_failures)} object(s): {preview}",
                )

        self.report({'INFO'}, f"Batch export done - {rendered} rendered, {skipped} skipped.")
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
