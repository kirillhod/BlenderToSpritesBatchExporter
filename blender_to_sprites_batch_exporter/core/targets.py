"""Target collection lists, migration, auto-sync and always-include helpers."""

from types import SimpleNamespace

import bpy

from .output import node_output_format_label
from .scene import gather_source_collections


VIEW_AXES = ("TOP", "BOTTOM", "FRONT", "BACK", "RIGHT", "LEFT")
VIEW_FIELDS = {
    "TOP": "view_top",
    "BOTTOM": "view_bottom",
    "FRONT": "view_front",
    "BACK": "view_back",
    "RIGHT": "view_right",
    "LEFT": "view_left",
}


# Collections are synced from a debounced timer, outside the depsgraph callback.
_SYNC_SUPPRESSED = 0
_SYNC_PENDING = set()
_SYNC_LAST = {}
_SYNC_TIMER_REGISTERED = False
_ACTIVE_INDEX_SUPPRESSED = 0
_LEGACY_AXIS_SUPPRESSED = 0


def _active_collection_name(context):
    """Name of the Outliner collection, or an empty string for the scene root."""
    view_layer = getattr(context, "view_layer", None)
    active = getattr(view_layer, "active_layer_collection", None)
    root = getattr(view_layer, "layer_collection", None)
    if active is None or active == root:
        return ""
    collection = getattr(active, "collection", None)
    return str(getattr(collection, "name", "") or "")


def active_target_update_suppressed():
    """True while sync writes the active row without touching the Outliner."""
    return _ACTIVE_INDEX_SUPPRESSED > 0


def legacy_axis_update_suppressed():
    """True while the view set writes camera_axis on purpose."""
    return _LEGACY_AXIS_SUPPRESSED > 0


def set_active_target_index(settings, index):
    """Set the active target row without echoing the change back to Outliner."""
    global _ACTIVE_INDEX_SUPPRESSED
    value = int(index)
    if int(getattr(settings, "active_target_index", 0)) == value:
        return
    _ACTIVE_INDEX_SUPPRESSED += 1
    try:
        settings.active_target_index = value
    finally:
        _ACTIVE_INDEX_SUPPRESSED -= 1


def target_fingerprint(context, settings):
    """Cheap description of the available source collections and active item."""
    names = tuple(
        collection.name for collection in gather_source_collections(context, settings)
    )
    return (
        str(getattr(settings, "export_source", "")),
        bool(getattr(settings, "skip_empty", True)),
        names,
        _active_collection_name(context),
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


def clear_view_axes(owner, keep=None):
    """Disable every view boolean on a settings or target item."""
    for axis in VIEW_AXES:
        if axis == keep:
            continue
        setattr(owner, VIEW_FIELDS[axis], False)


def active_view_axes(owner):
    """Active axis identifiers in the canonical TOP..LEFT order."""
    if owner is None:
        return []
    return [
        axis
        for axis in VIEW_AXES
        if bool(getattr(owner, VIEW_FIELDS[axis], False))
    ]


def apply_view_migration(settings):
    """Map the legacy single camera_axis to exactly one view boolean."""
    axis = str(getattr(settings, "camera_axis", "TOP") or "TOP").upper()
    if axis not in VIEW_FIELDS:
        axis = "TOP"
    # Enable the target first, then disable the others. Clearing first can leave
    # an old view temporarily alone and let its update callback overwrite
    # camera_axis with the previous axis.
    setattr(settings, VIEW_FIELDS[axis], True)
    clear_view_axes(settings, keep=axis)
    return axis


def sync_legacy_camera_axis(settings, item=None):
    """Mirror a single active view into the legacy camera_axis value.

    A per-collection view override does not write the global legacy value:
    other targets may still follow the global view set.
    """
    global _LEGACY_AXIS_SUPPRESSED
    if item is not None and bool(getattr(item, "override_view", False)):
        return
    axes = active_view_axes(settings)
    if len(axes) != 1:
        return
    if str(getattr(settings, "camera_axis", "")) == axes[0]:
        return
    _LEGACY_AXIS_SUPPRESSED += 1
    try:
        settings.camera_axis = axes[0]
    finally:
        _LEGACY_AXIS_SUPPRESSED -= 1


def migrate_settings(context, settings):
    """One-time migration of legacy string settings and the node layout."""
    if not getattr(settings, "target_items_migrated", False):
        _target_clear(settings)
        for collection in gather_source_collections(context, settings):
            _target_add(settings, collection.name, True)
        settings.target_items_migrated = True

    if not getattr(settings, "views_migrated", False):
        apply_view_migration(settings)
        settings.views_migrated = True

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


def source_collection_names(context, settings):
    """Names currently selected by the ``export_source`` filter."""
    return {
        collection.name
        for collection in gather_source_collections(context, settings)
    }


def _target_index(settings, name):
    for index, item in enumerate(settings.target_items):
        if item.name == name:
            return index
    return None


def _restore_active_index(settings, name):
    items = list(settings.target_items)
    index = _target_index(settings, name) if name else None
    if index is None:
        count = len(items)
        try:
            current = int(getattr(settings, "active_target_index", 0))
        except (TypeError, ValueError):
            current = 0
        index = min(max(0, current), max(0, count - 1))
    set_active_target_index(settings, index)


def sync_target_items(context, settings):
    """Add available source collections, drop deleted ones and follow Outliner."""
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

    outliner_active = _active_collection_name(context)
    if outliner_active:
        index = _target_index(settings, outliner_active)
        if index is not None:
            if getattr(settings, "export_source", "") == 'ACTIVE':
                item = settings.target_items[index]
                if not item.enabled:
                    item.enabled = True
            set_active_target_index(settings, index)
        else:
            _restore_active_index(settings, active_name)
    else:
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


def set_all_targets(settings, enabled, context=None):
    names = None
    if context is not None:
        try:
            names = source_collection_names(context, settings)
        except Exception:  # noqa: BLE001
            names = None
    for item in settings.target_items:
        if names is not None and item.name not in names:
            continue
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


OVERRIDE_VIEW_FIELDS = (
    "view_top",
    "view_bottom",
    "view_front",
    "view_back",
    "view_right",
    "view_left",
)
OVERRIDE_FRAMING_FIELDS = (
    "camera_margin",
    "padding_mode",
    "padding_pixels",
    "padding_units",
)
OVERRIDE_RESOLUTION_FIELDS = (
    "pixels_per_unit",
    "resolution_multiple",
    "square_output",
    "min_resolution",
    "max_resolution",
)
OVERRIDE_GROUP_FIELDS = {
    "view": OVERRIDE_VIEW_FIELDS,
    "framing": OVERRIDE_FRAMING_FIELDS,
    "resolution": OVERRIDE_RESOLUTION_FIELDS,
}
TARGET_OVERRIDE_ATTRS = (
    "override_view",
    *OVERRIDE_VIEW_FIELDS,
    "override_framing",
    *OVERRIDE_FRAMING_FIELDS,
    "override_resolution",
    *OVERRIDE_RESOLUTION_FIELDS,
)


def apply_override_toggle(settings, item, group, enabled=None):
    """Copy global values on first enable and clear the seed when disabled.

    Returns True when the group values were copied. The seeded flag keeps a
    loaded .blend from replacing stored overrides with the current globals.
    """
    try:
        fields = OVERRIDE_GROUP_FIELDS[group]
    except KeyError:
        raise ValueError("Unknown override group: %s" % group)
    toggle = "override_" + group
    seeded = toggle + "_seeded"
    if enabled is None:
        enabled = bool(getattr(item, toggle, False))
    if not enabled:
        setattr(item, seeded, False)
        return False
    if bool(getattr(item, seeded, False)):
        return False
    for field in fields:
        setattr(item, field, getattr(settings, field))
    setattr(item, seeded, True)
    return True


def target_override_state(settings, names):
    """Return the override inputs for each target name, in export order."""
    items = {
        getattr(item, "name", ""): item
        for item in getattr(settings, "target_items", ())
    }
    state = []
    for name in names:
        item = items.get(name)
        if item is None:
            state.append((name, ()))
            continue
        state.append((
            name,
            tuple(getattr(item, attr, None) for attr in TARGET_OVERRIDE_ATTRS),
        ))
    return tuple(state)


def active_override_groups(item):
    """Return the enabled override group names for one target item."""
    if item is None:
        return ()
    return tuple(
        group
        for group in OVERRIDE_GROUP_FIELDS
        if bool(getattr(item, "override_" + group, False))
    )


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
    """Global view count used before per-target axes are resolved."""
    return len(active_view_axes(settings)) or 1


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


def _clear_collection(items):
    """Remove every item from a Blender collection property."""
    if items is None:
        return
    while len(items):
        items.remove(len(items) - 1)


def _preview_display_path(plan, base_dir):
    """Path shown in the compact preview list, relative to the output dir."""
    path = str(
        getattr(plan, "path", "") or getattr(plan, "abs_path", "") or ""
    ).replace("\\", "/")
    if not path:
        return ""
    base = str(base_dir or "").replace("\\", "/").rstrip("/")
    if base:
        prefix = base + "/"
        if path.casefold().startswith(prefix.casefold()):
            return path[len(prefix):]
    return path


def _add_preview_item(settings, collection_name, plan):
    items = getattr(settings, "preview_items", None)
    if items is None or getattr(plan, "skipped", False):
        return
    path = _preview_display_path(plan, getattr(settings, "output_dir", ""))
    if not path:
        return
    item = items.add()
    item.name = str(collection_name)
    item.path = path
    item.exists = bool(getattr(plan, "exists", False))


def _update_output_lists(settings, analysis):
    """Fill the compact Path Preview and File Output node lists."""
    _clear_collection(getattr(settings, "preview_items", None))
    _clear_collection(getattr(settings, "node_items", None))
    if analysis is None:
        return
    for target in analysis.targets:
        if target.skipped:
            continue
        plan = target.output_plan
        if plan is not None:
            _add_preview_item(settings, target.name, plan)
        for plan in target.node_plans:
            _add_preview_item(settings, target.name, plan)
    node_items = getattr(settings, "node_items", None)
    if node_items is None:
        return
    for node in (getattr(analysis, "all_file_outputs", {}) or {}).values():
        item = node_items.add()
        item.name = str(getattr(node, "name", "") or "File Output")
        detail = node_output_format_label(node)
        outputs = len(getattr(node, "file_output_items", ()) or ())
        if outputs:
            detail += f" ({outputs})"
        item.detail = detail


def clear_target_status(scene):
    """Erase stored row status strings and output lists for one scene."""
    settings = getattr(scene, "bts_settings", None)
    if settings is None:
        return
    for item in settings.target_items:
        item.size_status = ""
    _clear_collection(getattr(settings, "preview_items", None))
    _clear_collection(getattr(settings, "node_items", None))


def clear_all_target_statuses():
    """Erase stored row status strings in every loaded scene."""
    for scene in getattr(bpy.data, "scenes", ()) or ():
        clear_target_status(scene)


def update_target_status(settings, analysis):
    """Store compact collection, preview and node-list state."""
    _update_output_lists(settings, analysis)
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
