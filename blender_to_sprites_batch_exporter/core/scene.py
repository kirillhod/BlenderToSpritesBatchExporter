"""Collections, bounds, isolation and render state restoration."""

import os

import bpy
import mathutils

from .common import *  # noqa: F401,F403
from .output import collect_file_outputs


# ============================================================
# BOUNDS
# ============================================================

def _corners_degenerate(corners):
    first = corners[0]
    return all((c - first).length_squared < 1e-12 for c in corners[1:])


def get_collection_bounds(collection, depsgraph=None, visited=None, depth=0, ignore_hidden=True):
    if visited is None:
        visited = set()
    key = collection.as_pointer()
    if key in visited:
        return None
    visited.add(key)

    min_co = mathutils.Vector((float('inf'),) * 3)
    max_co = mathutils.Vector((float('-inf'),) * 3)
    found = False

    def expand(v):
        nonlocal found
        if v.x < min_co.x: min_co.x = v.x
        if v.y < min_co.y: min_co.y = v.y
        if v.z < min_co.z: min_co.z = v.z
        if v.x > max_co.x: max_co.x = v.x
        if v.y > max_co.y: max_co.y = v.y
        if v.z > max_co.z: max_co.z = v.z
        found = True

    for obj in collection.objects:
        if ignore_hidden and obj.hide_render:
            continue
        inst = getattr(obj, "instance_collection", None)
        if obj.type == 'EMPTY' and inst is not None and depth < MAX_INSTANCE_DEPTH:
            sub = get_collection_bounds(inst, depsgraph, None, depth + 1, ignore_hidden)
            if sub:
                smin, smax = sub
                off = inst.instance_offset
                mw = obj.matrix_world
                for cx in (smin.x, smax.x):
                    for cy in (smin.y, smax.y):
                        for cz in (smin.z, smax.z):
                            expand(mw @ (mathutils.Vector((cx, cy, cz)) - off))
            continue

        if obj.type not in GEOMETRY_TYPES:
            continue

        obj_eval = obj
        if depsgraph is not None:
            try:
                ev = obj.evaluated_get(depsgraph)
                if ev is not None:
                    obj_eval = ev
            except Exception:
                pass

        try:
            bb = obj_eval.bound_box
        except Exception:
            continue
        if not bb:
            continue

        mw = obj_eval.matrix_world
        corners = [mw @ mathutils.Vector(c) for c in bb]
        if _corners_degenerate(corners):
            continue
        for c in corners:
            expand(c)

    for child in collection.children:
        sub = get_collection_bounds(child, depsgraph, visited, depth, ignore_hidden)
        if sub:
            expand(sub[0])
            expand(sub[1])

    return (min_co, max_co) if found else None


# ============================================================
# LAYER COLLECTION UTILITIES
# ============================================================

def iter_layer_collections(root_lc):
    stack = [(root_lc, ())]
    while stack:
        lc, path = stack.pop()
        yield path, lc
        for child in lc.children:
            stack.append((child, path + (child.name,)))


def resolve_lc(view_layer, path):
    lc = view_layer.layer_collection
    for name in path:
        lc = lc.children.get(name)
        if lc is None:
            return None
    return lc


def snapshot_excludes(view_layer):
    return {
        path: lc.exclude
        for path, lc in iter_layer_collections(view_layer.layer_collection)
        if path
    }


def restore_excludes(view_layer, snapshot):
    for path in sorted(snapshot.keys(), key=len):
        lc = resolve_lc(view_layer, path)
        if lc is None:
            continue
        state = snapshot[path]
        if lc.exclude != state:
            try:
                lc.exclude = state
            except Exception:
                pass


def include_all(view_layer):
    for _, lc in iter_layer_collections(view_layer.layer_collection):
        if lc.exclude:
            try:
                lc.exclude = False
            except Exception:
                pass


def isolate_collection_by_exclude(view_layer, target_collection, keep_collections=()):
    root = view_layer.layer_collection
    target_id = target_collection.as_pointer()
    keep_ids = {c.as_pointer() for c in keep_collections if c is not None}
    entries = list(iter_layer_collections(root))
    include = set()
    found = False

    for path, lc in entries:
        col = lc.collection
        if col is None:
            continue
        cid = col.as_pointer()
        if cid == target_id or cid in keep_ids:
            if cid == target_id:
                found = True
            for i in range(len(path) + 1):
                include.add(path[:i])
            for q, _ in entries:
                if len(q) > len(path) and q[:len(path)] == path:
                    include.add(q)

    if not found:
        return False

    for path, lc in sorted(entries, key=lambda x: len(x[0])):
        if not path:
            continue
        state = path not in include
        if lc.exclude != state:
            try:
                lc.exclude = state
            except Exception:
                pass
    return True


# ============================================================
# HIDE-RENDER ISOLATION
# ============================================================

def objects_in_collection(collection, out=None, visited=None):
    if out is None:
        out = set()
    if visited is None:
        visited = set()
    key = collection.as_pointer()
    if key in visited:
        return out
    visited.add(key)
    for ob in collection.objects:
        out.add(ob.name)
    for child in collection.children:
        objects_in_collection(child, out, visited)
    return out


def set_hide_render_safe(ob, value, failures=None):
    try:
        if ob.hide_render != value:
            ob.hide_render = value
        return True
    except Exception:
        if failures is not None and ob.name not in failures:
            failures.append(ob.name)
        return False


def snapshot_hide_render(scene):
    return {ob.name: ob.hide_render for ob in scene.objects}


def restore_hide_render(scene, snapshot, failures=None):
    for name, state in snapshot.items():
        ob = bpy.data.objects.get(name)
        if ob is not None:
            set_hide_render_safe(ob, state, failures)


def isolate_collection_by_hide(scene, target_collection, keep_collections=(), keep_lights=True, failures=None):
    if failures is None:
        failures = []
    keep_objs = objects_in_collection(target_collection)
    for col in keep_collections:
        if col is not None:
            keep_objs |= objects_in_collection(col)
    for ob in scene.objects:
        if ob.type == 'CAMERA':
            set_hide_render_safe(ob, False, failures)
            continue
        if keep_lights and ob.type in {'LIGHT', 'LIGHT_PROBE'}:
            set_hide_render_safe(ob, False, failures)
            continue
        set_hide_render_safe(ob, ob.name not in keep_objs, failures)
    return failures


# ============================================================
# SCENE-ROOT AND LIGHT ISOLATION
# ============================================================

def collections_with_lights(scene):
    """Return collections that directly contain lights or light probes."""
    result = []
    seen = set()
    for collection in bpy.data.collections:
        for ob in collection.objects:
            if ob.type in {'LIGHT', 'LIGHT_PROBE'}:
                key = collection.as_pointer()
                if key not in seen:
                    seen.add(key)
                    result.append(collection)
                break
    return result


def collection_has_non_light_objects(collection):
    for ob in collection.objects:
        if ob.type not in {'LIGHT', 'LIGHT_PROBE', 'CAMERA'}:
            return True
    return False


def extend_keep_with_lights(scene, keep_collections):
    """Add collections that hold lights, preserving order and uniqueness.

    Returns ``(keep_collections, added, risky)`` where ``risky`` lists added
    collections that also contain non-light objects.
    """
    result = list(keep_collections)
    seen = {col.as_pointer() for col in result if col is not None}
    added = []
    risky = []
    for collection in collections_with_lights(scene):
        key = collection.as_pointer()
        if key in seen:
            continue
        result.append(collection)
        added.append(collection)
        seen.add(key)
        if collection_has_non_light_objects(collection):
            risky.append(collection)
    return result, added, risky


def hide_root_objects(scene, target_collection, keep_collections=(), keep_lights=True, failures=None):
    """Hide scene-root objects that are not part of the target or keep sets.

    Exclude isolation cannot hide objects linked directly to the scene
    collection, so they are handled through the safe ``hide_render`` path.
    """
    if failures is None:
        failures = []
    keep_objs = objects_in_collection(target_collection)
    for collection in keep_collections:
        if collection is not None:
            keep_objs |= objects_in_collection(collection)

    hidden = []
    for ob in scene.collection.objects:
        if ob.type == 'CAMERA':
            continue
        if keep_lights and ob.type in {'LIGHT', 'LIGHT_PROBE'}:
            continue
        if ob.name in keep_objs:
            continue
        if set_hide_render_safe(ob, True, failures):
            hidden.append(ob.name)
    return hidden


# ============================================================
# RENDER STATE SNAPSHOT AND VERIFICATION
# ============================================================

def snapshot_render_state(scene):
    """Capture every render setting the export may touch."""
    rd = scene.render
    state = {attr: getattr(rd, attr, None) for attr in RENDER_STATE_ATTRS}
    image_settings = getattr(rd, "image_settings", None)
    if image_settings is not None:
        state["image_settings"] = {
            "file_format": getattr(image_settings, "file_format", None),
            "color_mode": getattr(image_settings, "color_mode", None),
            "color_depth": getattr(image_settings, "color_depth", None),
        }
    state["camera_name"] = scene.camera.name if scene.camera is not None else None
    return state


def restore_render_state(scene, snapshot, failures=None):
    """Restore a snapshot; never raises for a single missing setting."""
    if failures is None:
        failures = []
    rd = scene.render
    for attr in RENDER_STATE_ATTRS:
        expected = snapshot.get(attr)
        if expected is None:
            continue
        try:
            if getattr(rd, attr, None) != expected:
                setattr(rd, attr, expected)
        except (AttributeError, TypeError, ValueError):
            failures.append(attr)
    image_settings = getattr(rd, "image_settings", None)
    saved = snapshot.get("image_settings") or {}
    if image_settings is not None:
        for attr, expected in saved.items():
            if expected is None:
                continue
            try:
                if getattr(image_settings, attr, None) != expected:
                    setattr(image_settings, attr, expected)
            except (AttributeError, TypeError, ValueError):
                failures.append(f"image_settings.{attr}")
    return failures


def prepare_render_state(scene, settings):
    """Apply safe render values for an export."""
    rd = scene.render
    rd.resolution_percentage = 100
    rd.film_transparent = settings.use_transparent
    rd.use_border = False
    rd.use_crop_to_border = False
    rd.use_stamp = False
    rd.use_file_extension = True


def verify_render_state(scene, snapshot):
    """Return readable mismatches between the scene and a snapshot."""
    issues = []
    rd = scene.render
    for attr in RENDER_STATE_ATTRS:
        expected = snapshot.get(attr)
        actual = getattr(rd, attr, None)
        if expected is not None and actual != expected:
            issues.append(f"{attr}: expected {expected!r}, got {actual!r}")
    image_settings = getattr(rd, "image_settings", None)
    saved = snapshot.get("image_settings") or {}
    if image_settings is not None:
        for attr, expected in saved.items():
            actual = getattr(image_settings, attr, None)
            if expected is not None and actual != expected:
                issues.append(f"image_settings.{attr}: expected {expected!r}, got {actual!r}")
    return issues


def verify_excludes(view_layer, snapshot):
    issues = []
    for path, expected in snapshot.items():
        lc = resolve_lc(view_layer, path)
        if lc is None:
            continue
        if lc.exclude != expected:
            issues.append(f"exclude {'/'.join(path)}: expected {expected}, got {lc.exclude}")
    return issues


def verify_hide_render(scene, snapshot):
    issues = []
    for name, expected in snapshot.items():
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        actual = getattr(ob, "hide_render", None)
        if actual is not None and actual != expected:
            issues.append(f"hide_render {name}: expected {expected}, got {actual}")
    return issues


def verify_nodes(scene, node_snapshots, reachable_only=False):
    issues = []
    live = collect_file_outputs(scene, reachable_only=reachable_only)
    for snap in node_snapshots:
        if snap.get("library"):
            continue
        node = live.get(snap["key"])
        if node is None:
            continue
        expected_dir = snap.get("base_path", "")
        actual_dir = getattr(node, "directory", "")
        if expected_dir != actual_dir:
            issues.append(
                f"node '{snap['name']}' directory: expected {expected_dir!r}, got {actual_dir!r}"
            )
        expected_file = snap.get("file_name", "")
        actual_file = getattr(node, "file_name", "")
        if expected_file and expected_file != actual_file:
            issues.append(
                f"node '{snap['name']}' file name: expected {expected_file!r}, got {actual_file!r}"
            )
        slots = getattr(node, "file_output_items", None)
        expected_slots = snap.get("slot_paths", [])
        if slots is not None and expected_slots:
            limit = min(len(slots), len(expected_slots))
            for index in range(limit):
                if slots[index].name != expected_slots[index]:
                    issues.append(
                        f"node '{snap['name']}' item {index}: "
                        f"expected {expected_slots[index]!r}, got {slots[index].name!r}"
                    )
    return issues


def verify_scene_state(scene, view_layer, snapshot, exclude_snapshot, hide_snapshot,
                       node_snapshots=(), reachable_only=False, camera_name=None):
    """Collect restore warnings without raising from a ``finally`` block."""
    issues = []
    checks = (
        ("render", lambda: verify_render_state(scene, snapshot)),
        ("excludes", lambda: verify_excludes(view_layer, exclude_snapshot)),
        ("hide_render", lambda: verify_hide_render(scene, hide_snapshot)),
        ("nodes", lambda: verify_nodes(scene, node_snapshots, reachable_only)),
    )
    for label, check in checks:
        try:
            issues.extend(check())
        except Exception as exc:  # noqa: BLE001 - verification must not crash export
            issues.append(f"{label} verification failed: {exc}")
    if camera_name is not None:
        actual = scene.camera.name if scene.camera is not None else None
        if actual != camera_name:
            issues.append(f"camera: expected {camera_name!r}, got {actual!r}")
    return issues


# ============================================================
# COLLECTION GATHERING
# ============================================================

def gather_source_collections(context, settings):
    """Collections selected by the legacy ``export_source`` filter."""
    vl = context.view_layer
    root = vl.layer_collection
    result = []
    seen = set()
    def add(lc):
        col = lc.collection
        if col is None:
            return
        key = col.as_pointer()
        if key in seen:
            return
        seen.add(key)
        result.append(col)
    if settings.export_source == 'ACTIVE':
        alc = vl.active_layer_collection
        if alc is not None and alc != root:
            add(alc)
        return result
    if settings.export_source == 'TOPLEVEL':
        for child in root.children:
            add(child)
        return result
    def walk(lc, parent_excluded=False):
        for child in lc.children:
            excluded = parent_excluded or child.exclude
            if settings.export_source == 'INCLUDED' and excluded:
                continue
            add(child)
            walk(child, excluded)
    walk(root)
    return result


def gather_target_collections(context, settings):
    """Return enabled target items, or fall back to the source filter.

    Once ``target_items`` has been populated it is the source of truth. An
    empty list still means "not initialized yet" so old scenes keep working.
    """
    items = getattr(settings, "target_items", None)
    migrated = bool(getattr(settings, "target_items_migrated", False))
    if items is not None and (len(items) > 0 or migrated):
        result = []
        for item in items:
            if not getattr(item, "enabled", True):
                continue
            collection = bpy.data.collections.get(item.name)
            if collection is not None:
                result.append(collection)
        return result
    return gather_source_collections(context, settings)


def parse_keep_collections(settings):
    """Collections that must stay visible during isolation."""
    cols = []
    items = getattr(settings, "always_include_items", None)
    names = []
    migrated = bool(getattr(settings, "always_include_migrated", False))
    if items is not None and (len(items) > 0 or migrated):
        names = [item.name for item in items]
    else:
        names = [name.strip() for name in settings.keep_collections.split(",")]
    for name in names:
        name = str(name).strip()
        if not name:
            continue
        col = bpy.data.collections.get(name)
        if col is not None:
            cols.append(col)
    return cols
