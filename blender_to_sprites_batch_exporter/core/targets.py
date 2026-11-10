"""Target collection lists, migration and always-include helpers."""

import bpy

from .scene import gather_source_collections


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


def sync_target_items(context, settings):
    """Add newly available source collections and drop deleted ones."""
    migrate_settings(context, settings)
    source = gather_source_collections(context, settings)
    source_names = [collection.name for collection in source]
    existing = {item.name: item for item in settings.target_items}

    for item in list(settings.target_items):
        if item.name not in bpy.data.collections:
            settings.target_items.remove(
                list(settings.target_items).index(item)
            )
            existing.pop(item.name, None)

    for name in source_names:
        if name not in existing:
            _target_add(settings, name, True)


def rebuild_target_items(context, settings):
    """Replace the list with the current source filter."""
    migrate_settings(context, settings)
    existing = {item.name: item.enabled for item in settings.target_items}
    _target_clear(settings)
    for collection in gather_source_collections(context, settings):
        _target_add(settings, collection.name, existing.get(collection.name, True))
    settings.target_items_migrated = True


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


def update_target_status(settings, analysis):
    """Store a short size/status string for the collection UIList."""
    if analysis is None:
        return
    for target in analysis.targets:
        item = get_target_item(settings, target.name)
        if item is None:
            continue
        if target.skip_reason:
            item.size_status = target.skip_reason
        elif target.frame is not None:
            item.size_status = (
                f"{target.frame.res_x}x{target.frame.res_y}"
            )
        elif target.bounds is not None:
            width = target.bounds.maximum.x - target.bounds.minimum.x
            height = target.bounds.maximum.y - target.bounds.minimum.y
            item.size_status = f"{width:.2f} x {height:.2f}"
        else:
            item.size_status = ""
