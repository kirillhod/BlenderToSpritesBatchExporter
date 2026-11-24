"""Viewport preview for the active collection.

The preview reuses the export framing math, switches the 3D View to camera view
and hides the other collections in the viewport. It is a UI mode, not a render:
the visible shading (Solid, Material Preview or Rendered) is left to the user.
"""

import bpy

from .common import is_background
from .framing import (
    compute_collection_frame,
    configure_camera_for_axis,
    ensure_camera,
    is_owned_camera,
)
from .overrides import resolve_target_settings, view_axes_for
from .scene import (
    collections_with_lights,
    get_collection_bounds,
    iter_layer_collections,
    objects_in_collection,
    resolve_lc,
)
from .targets import find_layer_collection, get_target_item

_PREVIEWS = {}
_DIRTY = set()
_TIMER_RUNNING = False
_TIMER_INTERVAL = 0.25


def preview_active(scene=None):
    scene = scene if scene is not None else getattr(bpy.context, "scene", None)
    return scene is not None and scene.as_pointer() in _PREVIEWS


def preview_message(scene=None):
    scene = scene if scene is not None else getattr(bpy.context, "scene", None)
    state = _PREVIEWS.get(scene.as_pointer()) if scene is not None else None
    return str(state.get("message", "")) if state else ""


def mark_preview_dirty(scene=None):
    scene = scene if scene is not None else getattr(bpy.context, "scene", None)
    if scene is not None and scene.as_pointer() in _PREVIEWS:
        _DIRTY.add(scene.as_pointer())
        _request_update()


def preview_depsgraph_handler(scene=None, *_args):
    scene = scene if scene is not None else getattr(bpy.context, "scene", None)
    if scene is not None and scene.as_pointer() in _PREVIEWS:
        _DIRTY.add(scene.as_pointer())
        _request_update()


def _request_update():
    """Apply pending preview changes as soon as Blender is idle.

    The polling timer alone caps the preview at four updates per second, which
    makes value drags look stepped. A zero interval one-shot timer costs
    nothing while idle and keeps drags close to the screen refresh rate.
    """
    if is_background() or not _DIRTY:
        return
    timers = getattr(bpy.app, "timers", None)
    if timers is None:
        return
    try:
        if not timers.is_registered(_update_now):
            timers.register(_update_now, first_interval=0.0)
    except Exception:  # noqa: BLE001 - the polling timer still refreshes
        pass


def _update_now():
    for state in list(_PREVIEWS.values()):
        refresh_preview(state["scene"])
    return None


def _active_layer(view_layer):
    layer_collection = getattr(view_layer, "active_layer_collection", None)
    if layer_collection is None:
        return None
    if layer_collection == view_layer.layer_collection:
        return None
    return layer_collection


def _row_layer(settings, view_layer):
    """Layer collection of the active target row, if it exists."""
    items = getattr(settings, "target_items", None) or ()
    index = int(getattr(settings, "active_target_index", 0) or 0)
    if not 0 <= index < len(items):
        return None
    name = str(getattr(items[index], "name", "") or "")
    if not name:
        return None
    return find_layer_collection(view_layer, name)


def _target_layer(settings, view_layer):
    """Resolve the preview target. The selected row wins over the Outliner.

    Hiding collections resets the Outliner active collection to the root or to
    an ancestor. Reading the row first keeps the preview on the collection the
    user picked while the list stays the source of truth.
    """
    candidates = (_row_layer(settings, view_layer), _active_layer(view_layer))
    for layer_collection in candidates:
        if layer_collection is None:
            continue
        collection = getattr(layer_collection, "collection", None)
        if collection is not None:
            return collection, layer_collection
    return None, None


def _keep_active(view_layer, layer_collection):
    """Put the Outliner active collection back on the preview target."""
    if layer_collection is None:
        return
    try:
        if view_layer.active_layer_collection != layer_collection:
            view_layer.active_layer_collection = layer_collection
    except Exception:  # noqa: BLE001 - selection is best effort
        pass


def _find_view3d(context):
    space = getattr(context, "space_data", None)
    if space is not None and getattr(space, "type", "") == 'VIEW_3D':
        return space
    window = getattr(context, "window", None)
    screen = getattr(window, "screen", None) if window is not None else None
    if screen is None:
        return None
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            return area.spaces.active
    return None


def _snapshot_visibility(view_layer):
    layers = {}
    for path, layer_collection in iter_layer_collections(view_layer.layer_collection):
        if path:
            layers[path] = bool(layer_collection.hide_viewport)
    objects = {}
    for obj in view_layer.objects:
        try:
            objects[obj.name] = bool(obj.hide_get())
        except Exception:  # noqa: BLE001 - visibility is best effort
            pass
    return layers, objects


def _restore_visibility(view_layer, layers, objects):
    for path, state in layers.items():
        layer_collection = resolve_lc(view_layer, path)
        if layer_collection is None:
            continue
        if layer_collection.hide_viewport != state:
            try:
                layer_collection.hide_viewport = state
            except Exception:  # noqa: BLE001
                pass
    for name, state in objects.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        try:
            if obj.hide_get() != state:
                obj.hide_set(state)
        except Exception:  # noqa: BLE001
            pass


def _isolate(view_layer, target_collection, keep_collections):
    target_id = target_collection.as_pointer()
    keep_ids = {
        collection.as_pointer()
        for collection in keep_collections
        if collection is not None
    }
    entries = list(iter_layer_collections(view_layer.layer_collection))
    include = set()
    found = False
    for path, layer_collection in entries:
        collection = layer_collection.collection
        if collection is None:
            continue
        key = collection.as_pointer()
        if key != target_id and key not in keep_ids:
            continue
        if key == target_id:
            found = True
        for index in range(len(path) + 1):
            include.add(path[:index])
        for other_path, _ in entries:
            if len(other_path) > len(path) and other_path[:len(path)] == path:
                include.add(other_path)
    if not found:
        return False

    for path, layer_collection in sorted(entries, key=lambda entry: len(entry[0])):
        if not path:
            continue
        hidden = path not in include
        if layer_collection.hide_viewport != hidden:
            try:
                layer_collection.hide_viewport = hidden
            except Exception:  # noqa: BLE001
                pass

    keep_names = objects_in_collection(target_collection)
    for obj in view_layer.objects:
        if obj.name in keep_names or is_owned_camera(obj):
            continue
        if obj.type in {'LIGHT', 'LIGHT_PROBE'}:
            continue
        try:
            obj.hide_set(True)
        except Exception:  # noqa: BLE001
            pass
    return True


def _frame_data(context, settings, collection):
    item = get_target_item(settings, collection.name)
    axes = view_axes_for(settings, item)
    if not axes:
        return None, "No views selected."
    try:
        depsgraph = context.evaluated_depsgraph_get()
    except Exception:  # noqa: BLE001
        depsgraph = None
    bounds = get_collection_bounds(collection, depsgraph)
    if bounds is None:
        return None, "No renderable geometry."
    resolved = resolve_target_settings(settings, item)
    frame = compute_collection_frame(bounds[0], bounds[1], axes, resolved)
    if frame is None:
        return None, "Could not compute a canvas."
    return (item, axes, resolved, bounds, frame), ""


def _apply_frame(state, collection, data):
    _item, axes, resolved, bounds, frame = data
    scene = state["scene"]
    camera = state["camera_obj"]
    if camera is None or camera.name not in bpy.data.objects:
        camera = ensure_camera(scene)
        state["camera_obj"] = camera
        scene.camera = camera
        space = state.get("space")
        if space is not None:
            try:
                space.camera = camera
            except Exception:  # noqa: BLE001
                pass
    configure_camera_for_axis(camera, bounds[0], bounds[1], axes[0], frame, resolved)
    scene.camera = camera
    scene.render.resolution_x = int(frame["res_x"])
    scene.render.resolution_y = int(frame["res_y"])
    scene.render.resolution_percentage = 100
    state["message"] = ""


def enter_preview(context, collection=None):
    scene = context.scene
    settings = scene.bts_settings
    view_layer = context.view_layer
    if collection is not None:
        target = collection
        layer = find_layer_collection(view_layer, target.name)
    else:
        target, layer = _target_layer(settings, view_layer)
    if target is None:
        return False, "Select a collection in the Outliner."
    data, error = _frame_data(context, settings, target)
    if data is None:
        return False, "%s: %s" % (target.name, error)

    layers, objects = _snapshot_visibility(view_layer)
    space = _find_view3d(context)
    region_3d = getattr(space, "region_3d", None) if space is not None else None
    state = {
        "scene": scene,
        "view_layer": view_layer,
        "collection": target.name,
        "camera": scene.camera,
        "res_x": scene.render.resolution_x,
        "res_y": scene.render.resolution_y,
        "res_percentage": scene.render.resolution_percentage,
        "space": space,
        "perspective": getattr(region_3d, "view_perspective", None),
        "space_camera": getattr(space, "camera", None) if space is not None else None,
        "camera_zoom": getattr(region_3d, "view_camera_zoom", None),
        "camera_offset": tuple(getattr(region_3d, "view_camera_offset", (0.0, 0.0))),
        "layers": layers,
        "objects": objects,
        "camera_obj": None,
        "message": "",
    }

    camera = ensure_camera(scene)
    state["camera_obj"] = camera
    _PREVIEWS[scene.as_pointer()] = state
    try:
        _apply_frame(state, target, data)
        keep = list(collections_with_lights(scene))
        if not _isolate(view_layer, target, keep):
            exit_preview(scene=scene)
            return False, "%s is not in the view layer." % target.name
        _keep_active(view_layer, layer)

        if space is not None and region_3d is not None:
            try:
                space.camera = camera
            except Exception:  # noqa: BLE001
                pass
            try:
                region_3d.view_perspective = 'CAMERA'
                region_3d.view_camera_zoom = 0.0
                region_3d.view_camera_offset = (0.0, 0.0)
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        exit_preview(scene=scene)
        return False, str(exc)

    _DIRTY.discard(scene.as_pointer())
    _ensure_timer()
    return True, ""


def exit_preview(context=None, scene=None):
    if scene is None and context is not None:
        scene = context.scene
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return False
    key = scene.as_pointer()
    state = _PREVIEWS.pop(key, None)
    if state is None:
        return False
    _DIRTY.discard(key)

    view_layer = state["view_layer"]
    _restore_visibility(view_layer, state["layers"], state["objects"])
    target_layer = (
        find_layer_collection(view_layer, state["collection"])
        if state.get("collection")
        else None
    )
    _keep_active(view_layer, target_layer)

    try:
        scene.camera = state["camera"]
    except Exception:  # noqa: BLE001
        pass
    scene.render.resolution_x = int(state["res_x"])
    scene.render.resolution_y = int(state["res_y"])
    scene.render.resolution_percentage = int(state["res_percentage"])

    space = state.get("space")
    if space is not None:
        try:
            space.camera = state["space_camera"]
        except Exception:  # noqa: BLE001
            pass
        region_3d = getattr(space, "region_3d", None)
        if region_3d is not None:
            try:
                region_3d.view_perspective = state["perspective"]
            except Exception:  # noqa: BLE001
                pass
            try:
                region_3d.view_camera_zoom = state["camera_zoom"]
                region_3d.view_camera_offset = state["camera_offset"]
            except Exception:  # noqa: BLE001
                pass

    if not _PREVIEWS:
        _stop_timer()
    return True


def toggle_preview(context):
    scene = context.scene
    if preview_active(scene):
        exit_preview(context=context, scene=scene)
        return True, "Preview off."
    return enter_preview(context)


def refresh_preview(scene=None):
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    if scene is None:
        return
    key = scene.as_pointer()
    state = _PREVIEWS.get(key)
    if state is None:
        return

    space = state.get("space")
    if space is not None:
        try:
            perspective = space.region_3d.view_perspective
        except Exception:  # noqa: BLE001
            exit_preview(scene=scene)
            return
        if perspective != 'CAMERA':
            exit_preview(scene=scene)
            return

    view_layer = state["view_layer"]
    settings = scene.bts_settings
    target, layer = _target_layer(settings, view_layer)
    if target is None:
        return

    dirty = key in _DIRTY
    changed = target.name != state["collection"]
    if not dirty and not changed:
        return
    _DIRTY.discard(key)

    context = bpy.context
    if getattr(context, "scene", None) is not scene:
        return
    try:
        data, error = _frame_data(context, settings, target)
    except Exception as exc:  # noqa: BLE001
        state["message"] = str(exc)
        return
    if data is None:
        state["message"] = "%s: %s" % (target.name, error)
        return

    if changed:
        _restore_visibility(view_layer, state["layers"], state["objects"])
        keep = list(collections_with_lights(scene))
        if not _isolate(view_layer, target, keep):
            state["message"] = "%s is not in the view layer." % target.name
            return
        state["collection"] = target.name
        # Hiding collections resets the Outliner active collection; put it back
        # only after our own visibility writes, so an Outliner click survives
        # until the target sync updates the row.
        _keep_active(view_layer, layer)

    _apply_frame(state, target, data)


def exit_all_previews():
    for state in list(_PREVIEWS.values()):
        exit_preview(scene=state["scene"])
    _PREVIEWS.clear()
    _DIRTY.clear()
    _stop_timer()


def clear_previews():
    _PREVIEWS.clear()
    _DIRTY.clear()
    _stop_timer()


def _ensure_timer():
    global _TIMER_RUNNING
    if _TIMER_RUNNING or is_background():
        return
    _TIMER_RUNNING = True
    try:
        bpy.app.timers.register(_preview_timer, first_interval=_TIMER_INTERVAL)
    except Exception:  # noqa: BLE001
        _TIMER_RUNNING = False


def _stop_timer():
    global _TIMER_RUNNING
    _TIMER_RUNNING = False
    try:
        if bpy.app.timers.is_registered(_preview_timer):
            bpy.app.timers.unregister(_preview_timer)
    except Exception:  # noqa: BLE001
        pass


def _preview_timer():
    global _TIMER_RUNNING
    try:
        for state in list(_PREVIEWS.values()):
            refresh_preview(state["scene"])
    finally:
        if not _PREVIEWS:
            _TIMER_RUNNING = False
            return None
    return _TIMER_INTERVAL
