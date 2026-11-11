"""Target collection lists, migration, auto-sync and always-include helpers."""

from types import SimpleNamespace

import bpy

from .scene import gather_source_collections


# Collections are synced from a debounced timer, outside the depsgraph callback.
_SYNC_SUPPRESSED = 0
_SYNC_PENDING = set()
_SYNC_LAST = {}
_SYNC_TIMER_REGISTERED = False


def target_fingerprint(context, settings):
    """Cheap description of the available source collections."""
    names = tuple(
        collection.name for collection in gather_source_collections(context, settings)
    )
    return (
        str(getattr(settings, "export_source", "")),
        bool(getattr(settings, "skip_empty", True)),
        names,
    )


def push_target_sync_suppression():
    """Stop auto-sync while preflight or a job changes visibility."""
    global _SYNC_SUPPRESSED
    _SYNC_SUPPRESSED += 1


def pop_target_sync_suppression():
    global _SYNC_SUPPRESSED
    if _SYNC_SUPPRESSED > 0:
        _SYNC_SUPPRESSED -= 1


def target_sync_suppressed():
    return _SYNC_SUPPRESSED > 0


def _timer_api():
    app = getattr(bpy, "app", None)
    return getattr(app, "timers", None)


def request_target_sync(context=None, scene=None):
    """Mark a scene for a debounced target-list sync."""
    if _SYNC_SUPPRESSED:
        return False
    context = context if context is not None else getattr(bpy, "context", None)
    scene = scene if scene is not None else getattr(context, "scene", None)
    settings = getattr(scene, "bts_settings", None)
    if scene is None or settings is None:
        return False
    _SYNC_PENDING.add(scene.as_pointer())
    timers = _timer_api()
    if timers is None:
        return False
    try:
        if not timers.is_registered(apply_pending_target_sync):
            timers.register(apply_pending_target_sync, first_interval=0.2)
            global _SYNC_TIMER_REGISTERED
            _SYNC_TIMER_REGISTERED = True
    except Exception:  # noqa: BLE001 - the manual refresh button still works
        return False
    return True


def _scene_context(scene):
    view_layers = getattr(scene, "view_layers", None) or ()
    view_layer = view_layers[0] if view_layers else None
    if view_layer is None:
        return None
    return SimpleNamespace(scene=scene, view_layer=view_layer)


def apply_pending_target_sync():
    """Apply queued syncs now. Used by the timer and by tests."""
    global _SYNC_TIMER_REGISTERED
    _SYNC_TIMER_REGISTERED = False
    if _SYNC_SUPPRESSED:
        _SYNC_PENDING.clear()
        return None
    scenes = {
        scene.as_pointer(): scene
        for scene in (getattr(bpy.data, "scenes", None) or ())
    }
    for key in list(_SYNC_PENDING):
        _SYNC_PENDING.discard(key)
        scene = scenes.get(key)
        if scene is None:
            continue
        settings = getattr(scene, "bts_settings", None)
        context = _scene_context(scene)
        if settings is None or context is None:
            continue
        try:
            fingerprint = target_fingerprint(context, settings)
        except Exception:  # noqa: BLE001 - never break the UI timer
            continue
        if _SYNC_LAST.get(key) == fingerprint:
            continue
        try:
            migrate_settings(context, settings)
            sync_target_items(context, settings)
            _SYNC_LAST[key] = target_fingerprint(context, settings)
        except Exception:  # noqa: BLE001 - keep Blender running
            pass
    return None


def sync_depsgraph_handler(scene=None, *_args):
    """Queue a target sync when source collections change."""
    if _SYNC_SUPPRESSED:
        return
    if scene is None:
        scene = getattr(getattr(bpy, "context", None), "scene", None)
    settings = getattr(scene, "bts_settings", None)
    context = _scene_context(scene) if scene is not None else None
    if settings is None or context is None:
        return
    try:
        fingerprint = target_fingerprint(context, settings)
    except Exception:  # noqa: BLE001
        return
    if _SYNC_LAST.get(scene.as_pointer()) == fingerprint:
        return
    request_target_sync(scene=scene)


def unregister_target_sync():
    """Remove the timer and forget pending sync state."""
    global _SYNC_TIMER_REGISTERED, _SYNC_SUPPRESSED
    timers = _timer_api()
    if timers is not None:
        try:
            if timers.is_registered(apply_pending_target_sync):
                timers.unregister(apply_pending_target_sync)
        except Exception:  # noqa: BLE001
            pass
    _SYNC_TIMER_REGISTERED = False
    _SYNC_SUPPRESSED = 0
    _SYNC_PENDING.clear()
    _SYNC_LAST.clear()


def _target_add(settings, name, enabled=True):
    item = settings.target_items.add()
    item.name = name
    item.enabled = enabled
    return item


def _target_clear(settings):
    while len(settings.target_items):
        settings.target_items.remove(0)


def _include_add(settings, name):
    if any(item.name == name for item in settings.always_include_items):
        return
    item = settings.always_include_items.add()
    item.name = name


def _include_clear(settings):
    while len(settings.always_include_items):
        settings.always_include_items.remove(0)


def migrate_settings(context, settings):
    """One-time migration of legacy string settings and the node layout."""
    if not getattr(settings, "target_items_migrated", False):
        _target_clear(settings)
        for collection in gather_source_collections(context, settings):
            _target_add(settings, collection.name, True)
        settings.target_items_migrated = True

    if not getattr(settings, "always_include_migrated", False):
        if len(settings.always_include_items) == 0:
            for name in str(getattr(settings, "keep_collections", "")).split(","):
                name = name.strip()
                if name:
                    _include_add(settings, name)
        settings.always_include_migrated = True

    if not getattr(settings, "layout_migrated", False):
        # 1.4.0 had SUBFOLDER as the default and did not expose AUTO.
        # A saved legacy file therefore gets the old default back. New unsaved
        # scenes keep the recommended Automatic layout.
        if getattr(bpy.data, "filepath", "") and getattr(settings, "node_naming", "AUTO") == "AUTO":
            settings.node_naming = "SUBFOLDER"
        settings.layout_migrated = True

    if not str(getattr(settings, "name_template", "") or "").strip():
        settings.name_template = "{collection}"


def _restore_active_index(settings, name):
    items = list(settings.target_items)
    if name:
        for index, item in enumerate(items):
            if item.name == name:
                settings.active_target_index = index
                return
    count = len(items)
    try:
        current = int(getattr(settings, "active_target_index", 0))
    except (TypeError, ValueError):
        current = 0
    settings.active_target_index = min(max(0, current), max(0, count - 1))


def sync_target_items(context, settings):
    """Add newly available source collections and drop deleted ones."""
    migrate_settings(context, settings)
    source = gather_source_collections(context, settings)
    source_names = [collection.name for collection in source]
    items = list(settings.target_items)
    active_index = int(getattr(settings, "active_target_index", 0) or 0)
    active_name = items[active_index].name if 0 <= active_index < len(items) else ""
    existing = {item.name: item for item in settings.target_items}

    for item in items:
        if item.name not in bpy.data.collections:
            settings.target_items.remove(list(settings.target_items).index(item))
            existing.pop(item.name, None)

    for name in source_names:
        if name not in existing:
            _target_add(settings, name, True)

    _restore_active_index(settings, active_name)
    scene = getattr(context, "scene", None)
    if scene is not None:
        try:
            _SYNC_LAST[scene.as_pointer()] = target_fingerprint(context, settings)
        except Exception:  # noqa: BLE001
            pass


def rebuild_target_items(context, settings):
    """Compatibility wrapper. Refreshing never discards flags or overrides."""
    sync_target_items(context, settings)


def enabled_target_names(settings):
    return [
        item.name
        for item in settings.target_items
        if getattr(item, "enabled", True) and item.name in bpy.data.collections
    ]


def set_all_targets(settings, enabled):
    for item in settings.target_items:
        item.enabled = bool(enabled)


def set_active_target(context, settings):
    """Enable only the active Outliner collection."""
    active = context.view_layer.active_layer_collection
    collection = active.collection if active is not None else None
    if collection is None:
        return False
    found = False
    for item in settings.target_items:
        item.enabled = item.name == collection.name
        found = found or item.enabled
    return found


def get_target_item(settings, name):
    for item in settings.target_items:
        if item.name == name:
            return item
    return None


def add_always_include(settings, name):
    _include_add(settings, str(name))


def remove_always_include(settings, index):
    if 0 <= index < len(settings.always_include_items):
        settings.always_include_items.remove(index)


def always_include_names(settings):
    return [item.name for item in settings.always_include_items]


def find_layer_collection(view_layer, name):
    root = view_layer.layer_collection
    stack = [root]
    while stack:
        layer = stack.pop()
        if layer.collection is not None and layer.collection.name == name:
            return layer
        stack.extend(layer.children)
    return None


def active_include_name(settings):
    index = int(getattr(settings, "active_include_index", 0))
    if 0 <= index < len(settings.always_include_items):
        return settings.always_include_items[index].name
    return ""


def target_view_count(settings):
    """Views used for one target. Single view until multi-view is enabled."""
    return 1


def format_target_status(res_x, res_y, view_count=1, frame_count=0, skip_reason=""):
    """Short, self-explanatory row text for one target."""
    if skip_reason:
        return str(skip_reason)
    if not res_x or not res_y:
        return ""
    text = f"{int(res_x)}x{int(res_y)}"
    details = []
    if int(view_count or 0) > 1:
        details.append(f"{int(view_count)} views")
    if int(frame_count or 0) > 1:
        details.append(f"{int(frame_count)} frames")
    if details:
        text += ", " + ", ".join(details)
    return text


def clear_target_status(scene):
    """Erase stored row status strings for one scene."""
    settings = getattr(scene, "bts_settings", None)
    if settings is None:
        return
    for item in settings.target_items:
        item.size_status = ""


def clear_all_target_statuses():
    """Erase stored row status strings in every loaded scene."""
    for scene in getattr(bpy.data, "scenes", ()) or ():
        clear_target_status(scene)


def update_target_status(settings, analysis):
    """Store a short canvas/status string for the collection UIList."""
    for item in settings.target_items:
        item.size_status = ""
    if analysis is None:
        return
    views = target_view_count(settings)
    for target in analysis.targets:
        item = get_target_item(settings, target.name)
        if item is None:
            continue
        target_views = len(getattr(target, "axes", ()) or ()) or views
        frames = int(getattr(target, "frame_count", 0) or 0)
        if target.skip_reason:
            item.size_status = format_target_status(
                0, 0, skip_reason=target.skip_reason
            )
        elif target.frame is not None:
            item.size_status = format_target_status(
                target.frame.res_x,
                target.frame.res_y,
                view_count=target_views,
                frame_count=frames,
            )
        else:
            item.size_status = ""
