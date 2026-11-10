"""Pure scene, path and rendering logic.

This module must not import :mod:`ui` or :mod:`operators`.
"""

import os
import time
from math import radians

import bpy
import mathutils


ADDON_CAM_NAME = "_BTS_OrthoCamera"
ADDON_CAM_OWNED = "bts_owned_camera"

GEOMETRY_TYPES = {
    'MESH', 'CURVE', 'SURFACE', 'META', 'FONT',
    'CURVES', 'POINTCLOUD', 'VOLUME', 'GREASEPENCIL', 'GPENCIL',
}

MAX_INSTANCE_DEPTH = 8
DEPTH_CAPABLE = {'PNG', 'TIFF', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}

EXT_BY_FORMAT = {
    'PNG': '.png',
    'JPEG': '.jpg',
    'JPEG2000': '.jp2',
    'OPEN_EXR': '.exr',
    'OPEN_EXR_MULTILAYER': '.exr',
    'TIFF': '.tif',
    'BMP': '.bmp',
    'WEBP': '.webp',
    'TARGA': '.tga',
    'TARGA_RAW': '.tga',
}


# ============================================================
# PATH HELPERS
# ============================================================

def sanitize_filename(name):
    s = str(name)
    s = s.replace("/", "_").replace("\\", "_")
    invalid_chars = '<>:"|?*\0'
    s = "".join(c for c in s if c >= " " and c not in invalid_chars)
    s = s.strip(" .")
    return s or "untitled"


def safe_join(*parts):
    parts = [str(p).replace("\\", "/") for p in parts if p]
    if not parts:
        return ""
    result = parts[0]
    for p in parts[1:]:
        p = p.strip("/")
        if not p:
            continue
        if result.endswith("/"):
            result += p
        else:
            result += "/" + p
    return result


def ensure_slash(path):
    if not path:
        return "//"
    p = str(path).replace("\\", "/")
    return p if p.endswith("/") else p + "/"


def split_base(path):
    p = str(path or "").replace("\\", "/")
    if p in ("", "/", "//"):
        return (p or "//"), ""
    if p.endswith("/"):
        return p[:-1], ""
    idx = p.rfind("/")
    if idx == -1:
        return "", p
    head, tail = p[:idx], p[idx + 1:]
    if p.startswith("//") and idx <= 1:
        head = "//"
    elif head == "":
        head = "/"
    return head, tail


def make_relative_slot(slot_path):
    s = str(slot_path or "").replace("\\", "/")
    while s.startswith("//"):
        s = s[2:]
    if len(s) >= 2 and s[1] == ":":
        s = s[2:]
    s = s.lstrip("/")
    while s.startswith("./"):
        s = s[2:]
    s = s.replace("../", "")
    return s


def slot_path_is_absolute(slot_path):
    s = str(slot_path or "").replace("\\", "/")
    if not s:
        return False
    return (
            s.startswith("//")
            or s.startswith("/")
            or (len(s) >= 2 and s[1] == ":")
    )


def ensure_dir(blender_path):
    if not blender_path:
        return False
    try:
        abs_path = bpy.path.abspath(blender_path)
        if not abs_path:
            return False
        os.makedirs(abs_path, exist_ok=True)
        return True
    except Exception:
        return False


def is_relative_unsaved(path):
    return bool(path) and str(path).startswith("//") and not bpy.data.is_saved


def unique_dirs(dirs):
    out = []
    seen = set()
    for d in dirs:
        if not d:
            continue
        d = ensure_slash(d)
        key = os.path.normcase(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


# ============================================================
# POST-RENAME HELPERS (Fallback only)
# ============================================================

def snapshot_files(dirs, extensions=None):
    files = set()
    for d in unique_dirs(dirs):
        try:
            abs_d = bpy.path.abspath(d)
        except Exception:
            continue
        if not abs_d or not os.path.isdir(abs_d):
            continue
        for root, _, names in os.walk(abs_d):
            for name in names:
                if extensions:
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in extensions:
                        continue
                files.add(os.path.join(root, name))
    return files


def _split_frame_suffix(filename):
    stem, ext = os.path.splitext(filename)
    i = len(stem)
    while i > 0 and stem[i - 1].isdigit():
        i -= 1
    digits = stem[i:]
    base = stem[:i]
    if digits and len(digits) >= 3:
        return base, digits, ext
    return stem, "", ext


def prefix_new_files(dirs, prefix, before_files, start_time, extensions=None):
    if not prefix or before_files is None or start_time is None:
        return 0
    current = snapshot_files(dirs, extensions)
    candidates = set(current) - set(before_files)
    for path in current:
        try:
            if os.path.getmtime(path) >= start_time - 2.0:
                candidates.add(path)
        except Exception:
            pass

    renamed = 0
    written_targets = set()
    for path in sorted(candidates):
        directory, filename = os.path.split(path)
        base, digits, ext = _split_frame_suffix(filename)
        base_clean = base.strip()

        if base_clean == prefix or base_clean.startswith(prefix + "_"):
            continue

        if base_clean == "" or base_clean.lower() == "untitled":
            new_base = prefix
        else:
            new_base = f"{prefix}_{base_clean}"

        new_filename = new_base + digits + ext
        new_path = os.path.join(directory, new_filename)

        if os.path.normcase(path) == os.path.normcase(new_path):
            continue

        if os.path.normcase(new_path) in written_targets:
            stem_only, ext_only = os.path.splitext(new_filename)
            k = 1
            while True:
                alt = os.path.join(directory, f"{stem_only}_{k}{ext_only}")
                if os.path.normcase(alt) not in written_targets and not os.path.exists(alt):
                    new_path = alt
                    break
                k += 1

        try:
            os.replace(path, new_path)
            written_targets.add(os.path.normcase(new_path))
            renamed += 1
        except Exception:
            pass
    return renamed


# ============================================================
# COMPOSITOR HELPERS (Blender 5.0+ Optimized)
# ============================================================

def get_compositor_tree(scene):
    # Blender 5.0+ uses compositing_node_group
    tree = getattr(scene, "compositing_node_group", None)
    if tree is not None:
        return tree, False
    # Fallback for edge cases
    return getattr(scene, "node_tree", None), True


def collect_file_outputs(scene):
    root, _ = get_compositor_tree(scene)
    out = {}
    if root is None:
        return out
    visited_trees = set()

    def walk(tree, prefix):
        if tree is None:
            return
        tree_key = tree.as_pointer()
        if tree_key in visited_trees:
            return
        visited_trees.add(tree_key)
        for node in tree.nodes:
            if node.bl_idname == 'CompositorNodeOutputFile':
                out[prefix + (node.name,)] = node
            elif getattr(node, "node_tree", None) is not None:
                walk(getattr(node, "node_tree", None), prefix + (node.name,))
        visited_trees.discard(tree_key)

    walk(root, tuple())
    return out


def node_is_multilayer(node):
    fmt = getattr(node, "format", None)
    if fmt is None:
        return False
    return getattr(fmt, "file_format", "") == 'OPEN_EXR_MULTILAYER'


def snapshot_node(node, key):
    # Blender 5.0+ API: file_output_items
    slots = getattr(node, "file_output_items", None)
    slot_paths = []
    if slots is not None:
        for slot in slots:
            try:
                slot_paths.append(str(slot.name))
            except Exception:
                slot_paths.append("")

    return {
        "key": key,
        "name": node.name,
        "base_path": getattr(node, "directory", ""),
        "multilayer": node_is_multilayer(node),
        "slot_key": "name",
        "slot_paths": slot_paths,
        "library": getattr(node.id_data, "library", None) is not None,
    }


def apply_node_paths(node, settings, collection_name, snap):
    """
    Prepare a File Output node for rendering one collection.
    Blender 5.0+ Native: Modifies node.directory and file_output_items[i].name 
    BEFORE rendering to avoid post-rename os.replace() which breaks Unity .meta files.
    """
    problems = []
    mode = settings.node_naming
    override = settings.node_override_base

    if mode == 'NONE' and not override:
        return None, [], False, problems

    fallback = settings.output_dir or "//"
    original_dir = snap.get("base_path", "")
    safe_col = sanitize_filename(collection_name)

    scan_dirs = []
    def add_scan_dir(d):
        if d:
            scan_dirs.append(ensure_slash(d))

    orig_head, _ = split_base(original_dir or fallback)
    add_scan_dir(orig_head or fallback)

    base_dir = fallback if override else (orig_head or fallback)
    target_dir = base_dir
    needs_prefix_rename = False

    if mode == 'SUBFOLDER':
        target_dir = ensure_slash(safe_join(base_dir, safe_col))
    elif mode == 'PREFIX':
        target_dir = ensure_slash(base_dir)
    else:
        target_dir = ensure_slash(base_dir)

    try:
        node.directory = target_dir
    except Exception as e:
        problems.append(f"{node.name}: could not write directory ({e})")
        needs_prefix_rename = True

    add_scan_dir(target_dir)

    # Update file output items natively
    slots = getattr(node, "file_output_items", None)
    slot_paths = snap.get("slot_paths", [])

    if slots is not None and slot_paths:
        limit = min(len(slots), len(slot_paths))
        for i in range(limit):
            cleaned = make_relative_slot(slot_paths[i])
            # Blender 5.0+ does not allow implicit folder creation via '/' in slot names
            cleaned = cleaned.replace("\\", "_").replace("/", "_")
            try:
                if mode == 'PREFIX':
                    original_name = cleaned.strip()
                    if not original_name or original_name.lower() == "untitled":
                        new_name = safe_col
                    else:
                        new_name = f"{safe_col}_{original_name}"
                    slots[i].name = new_name
                else:
                    slots[i].name = cleaned
            except Exception as e:
                problems.append(f"{node.name}: could not write item name ({e})")
                needs_prefix_rename = True

    return target_dir, unique_dirs(scan_dirs), needs_prefix_rename, problems


def restore_node(node, snap):
    try:
        node.directory = snap.get("base_path", "")
    except Exception:
        pass

    key = snap.get("slot_key")
    slot_paths = snap.get("slot_paths", [])
    slots = getattr(node, "file_output_items", None)

    if key == "name" and slots is not None and slot_paths:
        limit = min(len(slots), len(slot_paths))
        for i in range(limit):
            try:
                slots[i].name = slot_paths[i]
            except Exception:
                pass


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
# CAMERA MATH
# ============================================================

def _axis_params(axis_enum):
    E = mathutils.Euler
    V = mathutils.Vector
    return {
        'TOP':    (V((0, 0, 1)),  E((0.0, 0.0, 0.0)), (0, 1)),
        'BOTTOM': (V((0, 0, -1)), E((radians(180), 0.0, 0.0)), (0, 1)),
        'FRONT':  (V((0, -1, 0)), E((radians(90), 0.0, 0.0)), (0, 2)),
        'BACK':   (V((0, 1, 0)),  E((radians(90), 0.0, radians(180))), (0, 2)),
        'RIGHT':  (V((1, 0, 0)),  E((radians(90), 0.0, radians(90))), (1, 2)),
        'LEFT':   (V((-1, 0, 0)), E((radians(90), 0.0, radians(-90))), (1, 2)),
    }[axis_enum]


def padding_in_units(settings):
    if settings.padding_mode == 'UNITS':
        return settings.padding_units
    return settings.padding_pixels / max(settings.pixels_per_unit, 1e-6)


def _round_up(value, multiple):
    return ((value + multiple - 1) // multiple) * multiple


def compute_frame(bounds_min, bounds_max, settings):
    _, _, (ax_w, ax_h) = _axis_params(settings.camera_axis)
    ppu = max(settings.pixels_per_unit, 1e-6)
    pad = padding_in_units(settings)
    width = max((bounds_max[ax_w] - bounds_min[ax_w]) + pad * 2.0, 1e-6)
    height = max((bounds_max[ax_h] - bounds_min[ax_h]) + pad * 2.0, 1e-6)
    res_x = max(int(round(width * ppu)), 1)
    res_y = max(int(round(height * ppu)), 1)
    if settings.square_output:
        res_x = res_y = max(res_x, res_y)
    res_x = max(res_x, settings.min_resolution)
    res_y = max(res_y, settings.min_resolution)
    m = max(settings.resolution_multiple, 1)
    if m > 1:
        res_x = _round_up(res_x, m)
        res_y = _round_up(res_y, m)
    if settings.max_resolution > 0:
        cap = settings.max_resolution
        if m > 1:
            cap = max(m, (cap // m) * m)
        res_x = min(res_x, cap)
        res_y = min(res_y, cap)
    if settings.square_output:
        res_x = res_y = max(res_x, res_y)
    width = res_x / ppu
    height = res_y / ppu
    return {
        "res_x": res_x,
        "res_y": res_y,
        "ortho_scale": max(width, height),
        "width": width,
        "height": height,
        "center": (bounds_min + bounds_max) / 2.0,
    }


def configure_camera(cam_obj, bounds_min, bounds_max, settings):
    offset_dir, rotation, (ax_w, ax_h) = _axis_params(settings.camera_axis)
    frame = compute_frame(bounds_min, bounds_max, settings)
    depth_axis = ({0, 1, 2} - {ax_w, ax_h}).pop()
    half_depth = (bounds_max[depth_axis] - bounds_min[depth_axis]) / 2.0
    margin = max(settings.camera_margin, 0.01)
    distance = half_depth + margin
    cam_obj.location = frame["center"] + offset_dir * distance
    cam_obj.rotation_euler = rotation
    cam_obj.scale = (1.0, 1.0, 1.0)
    cam = cam_obj.data
    cam.type = 'ORTHO'
    cam.ortho_scale = frame["ortho_scale"]
    cam.shift_x = 0.0
    cam.shift_y = 0.0
    cam.clip_start = 0.001
    cam.clip_end = distance + half_depth * 2.0 + margin
    return frame


def is_owned_camera(ob):
    return ob is not None and ob.type == 'CAMERA' and bool(ob.get(ADDON_CAM_OWNED))


def ensure_camera(scene):
    cam_obj = None
    for ob in scene.objects:
        if is_owned_camera(ob):
            cam_obj = ob
            break
    if cam_obj is None:
        cam_data = bpy.data.cameras.new(ADDON_CAM_NAME)
        cam_obj = bpy.data.objects.new(ADDON_CAM_NAME, cam_data)
        cam_obj[ADDON_CAM_OWNED] = True
    if scene.objects.get(cam_obj.name) is None:
        try:
            scene.collection.objects.link(cam_obj)
        except RuntimeError:
            pass
    cam_obj.hide_render = False
    cam_obj.hide_viewport = False
    return cam_obj


def remove_camera(scene=None):
    removed = False
    if scene is not None:
        candidates = [ob for ob in scene.objects if is_owned_camera(ob)]
    else:
        candidates = [ob for ob in bpy.data.objects if is_owned_camera(ob)]
    camera_data = []
    for ob in candidates:
        data = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        removed = True
        if data is not None:
            camera_data.append(data)
    for cam in camera_data:
        if cam.users == 0:
            try:
                bpy.data.cameras.remove(cam)
                removed = True
            except Exception:
                pass
    return removed


# ============================================================
# COLLECTION GATHERING
# ============================================================

def gather_target_collections(context, settings):
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


def parse_keep_collections(settings):
    cols = []
    for name in settings.keep_collections.split(","):
        name = name.strip()
        if not name:
            continue
        col = bpy.data.collections.get(name)
        if col is not None:
            cols.append(col)
    return cols


def apply_image_settings(image_settings, settings):
    image_settings.file_format = settings.file_format
    try:
        image_settings.color_mode = settings.color_mode
    except TypeError:
        image_settings.color_mode = 'RGB'
    if settings.file_format in DEPTH_CAPABLE:
        depth = settings.color_depth
        if settings.file_format.startswith('OPEN_EXR') and depth == '8':
            depth = '16'
        try:
            image_settings.color_depth = depth
        except TypeError:
            pass
