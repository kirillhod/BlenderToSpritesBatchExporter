"""Operators exposed by the add-on."""

import os
import time

import bpy
import mathutils
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator

from .logic import (
    EXT_BY_FORMAT,
    apply_image_settings,
    apply_node_paths,
    apply_overwrite_policy,
    collect_file_outputs,
    configure_camera,
    ensure_camera,
    ensure_dir,
    extend_keep_with_lights,
    gather_target_collections,
    get_collection_bounds,
    hide_root_objects,
    include_all,
    is_background,
    is_owned_camera,
    is_relative_unsaved,
    isolate_collection_by_exclude,
    isolate_collection_by_hide,
    parse_keep_collections,
    plan_output_paths,
    prefix_new_files,
    prepare_render_state,
    remove_camera,
    resolve_node_safe_names,
    restore_excludes,
    restore_hide_render,
    restore_node,
    restore_render_state,
    safe_join,
    sanitize_path_component,
    snapshot_excludes,
    snapshot_files,
    snapshot_hide_render,
    snapshot_node,
    snapshot_render_state,
    unique_dirs,
    validate_node_settings,
    verify_scene_state,
)


# ============================================================
# OPERATOR: BATCH EXPORT
# ============================================================

class BTS_OT_BatchExport(Operator):
    bl_idname = "bts.batch_export"
    bl_label = "Batch Export Collections"
    bl_description = "Render every target collection in isolation with an auto-fitted orthographic camera"
    bl_options = {'REGISTER'}

    overwrite_confirmed: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
    confirm_message: StringProperty(default="", options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        settings = context.scene.bts_settings
        if settings.overwrite_policy != 'ASK':
            return self.execute(context)

        plans = plan_output_paths(
            [col.name for col in gather_target_collections(context, settings)],
            settings,
        )
        _, errors, conflicts, _ = apply_overwrite_policy(
            plans, 'ASK', headless=is_background(), file_format=settings.file_format
        )
        if errors:
            for message in errors:
                self.report({'ERROR'}, message)
            return {'CANCELLED'}
        if not conflicts:
            return self.execute(context)

        if is_background():
            for plan in conflicts:
                self.report({'ERROR'}, f"File already exists: {plan.path}")
            return {'CANCELLED'}

        lines = [f"{plan.collection}: {plan.path}" for plan in conflicts[:8]]
        if len(conflicts) > 8:
            lines.append(f"... and {len(conflicts) - 8} more")
        self.confirm_message = "Overwrite existing files?\n" + "\n".join(lines)
        self.overwrite_confirmed = True
        return context.window_manager.invoke_confirm(self, event)

    def draw(self, context):
        layout = self.layout
        for line in self.confirm_message.splitlines():
            layout.label(text=line)

    def execute(self, context):
        scene = context.scene
        vl = context.view_layer
        settings = scene.bts_settings
        rd = scene.render
        wm = context.window_manager
        headless = is_background()

        targets = gather_target_collections(context, settings)
        if not targets:
            self.report({'WARNING'}, "No collections found to export.")
            return {'CANCELLED'}

        all_file_outputs = collect_file_outputs(
            scene, reachable_only=bool(getattr(settings, "nodes_connected_only", True))
        )
        using_nodes = bool(settings.use_compositor_nodes and all_file_outputs)
        node_only = using_nodes and not settings.write_main_output

        node_problems = validate_node_settings(scene, settings, all_file_outputs, using_nodes)
        warnings = [message for severity, message in node_problems if severity == 'WARNING']
        errors = [message for severity, message in node_problems if severity == 'ERROR']

        if settings.use_compositor_nodes and not using_nodes:
            all_nodes = collect_file_outputs(scene)
            if all_nodes:
                warnings.append(
                    "File Output nodes exist but none are connected to the compositor "
                    "output; the main render path will be used instead."
                )

        if not using_nodes and not settings.output_dir:
            errors.append("Output Directory is empty.")
        if is_relative_unsaved(settings.output_dir):
            errors.append(
                "Output path is relative ('//') but the .blend has never been saved. "
                "Save the file or use an absolute path."
            )
        if (using_nodes and settings.node_naming == 'NONE'
                and not settings.node_override_base and len(targets) > 1):
            errors.append(
                "Don't Modify mode would write every collection to the same File Output "
                "paths. Select Subfolder, Prefix, or Override Base Paths."
            )
        if errors:
            for message in errors:
                self.report({'ERROR'}, message)
            for message in warnings:
                self.report({'WARNING'}, message)
            return {'CANCELLED'}

        for message in warnings:
            self.report({'WARNING'}, message)

        if settings.output_dir:
            output_dir_abs = bpy.path.abspath(settings.output_dir)
            try:
                os.makedirs(output_dir_abs, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                self.report({'ERROR'}, f"Cannot create output directory: {exc}")
                return {'CANCELLED'}

        # Resolve all output names before rendering anything.
        plans = []
        plan_by_name = {}
        if not node_only:
            plans = plan_output_paths([col.name for col in targets], settings)
            plans, policy_errors, conflicts, policy_notes = apply_overwrite_policy(
                plans,
                settings.overwrite_policy,
                headless=headless,
                file_format=settings.file_format,
            )
            for message in policy_notes:
                self.report({'WARNING'}, message)
            if conflicts and not self.overwrite_confirmed:
                preview = ", ".join(plan.path for plan in conflicts[:5])
                errors.append(
                    f"{len(conflicts)} output file(s) already exist ({preview}). "
                    "Confirm the overwrite or change the overwrite policy."
                )
            errors.extend(policy_errors)
            if errors:
                for message in errors:
                    self.report({'ERROR'}, message)
                return {'CANCELLED'}
            plan_by_name = {plan.collection: plan for plan in plans}

        node_safe_names = {}
        node_skipped = set()
        if using_nodes:
            if node_only:
                node_safe_names, node_name_errors, node_skipped = resolve_node_safe_names(
                    [col.name for col in targets], settings.overwrite_policy
                )
                if node_name_errors:
                    for message in node_name_errors:
                        self.report({'ERROR'}, message)
                    return {'CANCELLED'}
            else:
                node_safe_names = {
                    plan.collection: plan.safe_name
                    for plan in plans
                    if not plan.skipped
                }

        render_exts = set()
        render_exts.add(EXT_BY_FORMAT.get(settings.file_format, "").lower())
        for node in all_file_outputs.values():
            fmt = getattr(node, "format", None)
            if fmt is not None:
                render_exts.add(EXT_BY_FORMAT.get(getattr(fmt, "file_format", ""), "").lower())
        render_exts.discard("")

        node_snapshots = [
            snapshot_node(node, key)
            for key, node in all_file_outputs.items()
            if not snapshot_node_is_linked(node)
        ]
        exclude_snapshot = snapshot_excludes(vl)
        hide_snapshot = snapshot_hide_render(scene)
        render_snapshot = snapshot_render_state(scene)
        orig_camera = scene.camera
        orig_camera_owned = is_owned_camera(scene.camera)

        keep_collections = parse_keep_collections(settings)
        if settings.isolation_mode == 'EXCLUDE' and settings.keep_lights:
            keep_collections, auto_lights, risky = extend_keep_with_lights(
                scene, keep_collections
            )
            if auto_lights:
                self.report(
                    {'INFO'},
                    "Kept light collections: " + ", ".join(col.name for col in auto_lights),
                )
            for collection in risky:
                self.report(
                    {'WARNING'},
                    f"Collection '{collection.name}' is kept for its lights but also "
                    "contains other objects; they may appear in the render.",
                )

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
        prepare_render_state(scene, settings)

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

        image_problems = []
        if (not using_nodes) or settings.write_main_output:
            apply_image_settings(rd.image_settings, settings, image_problems)
        for severity, message in image_problems:
            self.report({severity}, message)

        rendered = 0
        reported_problems = set()
        hide_failures = []
        restore_failures = []
        render_failures = []
        wm.progress_begin(0, max(len(measured), 1))

        def report_once(message, severity='WARNING'):
            if message not in reported_problems:
                reported_problems.add(message)
                self.report({severity}, message)

        try:
            for index, (col, (bmin, bmax)) in enumerate(measured):
                wm.progress_update(index)
                plan = plan_by_name.get(col.name)
                if plan is not None and plan.skipped:
                    skipped += 1
                    continue
                if col.name in node_skipped:
                    skipped += 1
                    continue

                frame = configure_camera(cam_obj, bmin, bmax, settings)
                rd.resolution_x = frame["res_x"]
                rd.resolution_y = frame["res_y"]

                if settings.isolation_mode == 'EXCLUDE':
                    if not isolate_collection_by_exclude(vl, col, keep_collections):
                        skipped += 1
                        continue
                    hide_root_objects(
                        scene, col, keep_collections, settings.keep_lights, hide_failures
                    )
                else:
                    include_all(vl)
                    isolate_collection_by_hide(
                        scene, col, keep_collections, settings.keep_lights, hide_failures
                    )
                vl.update()

                rename_scan_dirs = []
                do_prefix_rename = False

                if using_nodes:
                    live_nodes = collect_file_outputs(
                        scene,
                        reachable_only=bool(getattr(settings, "nodes_connected_only", True)),
                    )
                    for snap in node_snapshots:
                        node = live_nodes.get(snap["key"])
                        if node is None:
                            report_once(
                                f"Could not resolve File Output node '{snap['name']}'"
                            )
                            continue
                        if snap.get("library"):
                            continue

                        target_dir, scan_dirs, needs_prefix, problems = apply_node_paths(
                            node,
                            settings,
                            col.name,
                            snap,
                            safe_name=node_safe_names.get(col.name),
                        )
                        for problem in problems:
                            report_once(problem)
                        if target_dir:
                            ensure_dir(target_dir)
                        for directory in scan_dirs:
                            ensure_dir(directory)
                        if needs_prefix:
                            if settings.use_prefix_fallback:
                                do_prefix_rename = True
                                rename_scan_dirs.extend(scan_dirs)
                            else:
                                report_once(
                                    f"{node.name}: node paths could not be updated and the "
                                    "emergency prefix rename is disabled."
                                )

                write_still = bool(settings.write_main_output and settings.output_dir) if using_nodes else True
                if write_still:
                    if plan is not None:
                        rd.filepath = plan.base_path
                    else:
                        rd.filepath = safe_join(
                            settings.output_dir, sanitize_path_component(col.name)
                        )

                rename_before = None
                render_start = time.time()

                if do_prefix_rename:
                    rename_scan_dirs = unique_dirs(rename_scan_dirs)
                    for directory in rename_scan_dirs:
                        ensure_dir(directory)
                    rename_before = snapshot_files(rename_scan_dirs, render_exts or None)

                try:
                    bpy.ops.render.render(write_still=write_still)
                    rendered += 1
                except Exception as exc:  # noqa: BLE001
                    self.report({'WARNING'}, f"Render failed for '{col.name}': {exc}")
                else:
                    if do_prefix_rename:
                        prefix_new_files(
                            rename_scan_dirs,
                            plan.safe_name if plan is not None else sanitize_path_component(col.name),
                            rename_before,
                            render_start,
                            render_exts or None,
                        )
        finally:
            wm.progress_end()
            if node_snapshots:
                live_nodes = collect_file_outputs(
                    scene,
                    reachable_only=bool(getattr(settings, "nodes_connected_only", True)),
                )
                for snap in node_snapshots:
                    node = live_nodes.get(snap["key"])
                    if node is not None:
                        restore_node(node, snap)

            restore_hide_render(scene, hide_snapshot, restore_failures)
            restore_excludes(vl, exclude_snapshot)
            vl.update()
            restore_render_state(scene, render_snapshot, render_failures)

            restore_cam = None if orig_camera_owned else orig_camera
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

            if settings.auto_cleanup_camera:
                try:
                    expected_camera = restore_cam.name if restore_cam is not None else None
                except ReferenceError:
                    expected_camera = None
            else:
                try:
                    expected_camera = orig_camera.name if orig_camera is not None else cam_obj.name
                except ReferenceError:
                    expected_camera = cam_obj.name

            state_issues = verify_scene_state(
                scene,
                vl,
                render_snapshot,
                exclude_snapshot,
                hide_snapshot,
                node_snapshots,
                reachable_only=bool(getattr(settings, "nodes_connected_only", True)),
                camera_name=expected_camera,
            )
            state_issues.extend(sorted(set(render_failures)))

            all_hide_failures = sorted(set(hide_failures) | set(restore_failures))
            if all_hide_failures:
                preview = ", ".join(all_hide_failures[:5])
                if len(all_hide_failures) > 5:
                    preview += ", ..."
                self.report(
                    {'WARNING'},
                    f"Could not change hide_render for {len(all_hide_failures)} object(s): {preview}",
                )

            if state_issues:
                preview = "; ".join(state_issues[:5])
                if len(state_issues) > 5:
                    preview += "; ..."
                self.report(
                    {'WARNING'},
                    f"Scene state verification found {len(state_issues)} mismatch(es): {preview}",
                )

        self.report({'INFO'}, f"Batch export done - {rendered} rendered, {skipped} skipped.")
        return {'FINISHED'}


def snapshot_node_is_linked(node):
    """Small local wrapper to keep operator code readable."""
    try:
        return getattr(node.id_data, "library", None) is not None
    except Exception:
        return False



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
