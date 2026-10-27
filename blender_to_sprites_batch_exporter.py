bl_info = {
    "name": "Blender To Sprites Batch Exporter",
    "author": "kirillhod",
    "version": (1, 1, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar (N) > Batch Export",
    "description": "Batch render collections to sprites with an auto-fitted orthographic camera.",
    "category": "Import-Export",
}

import bpy
import os
import time
import mathutils
from math import radians
from bpy.props import (
    StringProperty,
    FloatProperty,
    IntProperty,
    BoolProperty,
    EnumProperty,
    PointerProperty,
)
from bpy.types import Operator, Panel, PropertyGroup


# ============================================================
# CONSTANTS
# ============================================================

ADDON_CAM_NAME = "_BTS_OrthoCamera"

GEOMETRY_TYPES = {
    'MESH', 'CURVE', 'SURFACE', 'META', 'FONT',
    'CURVES', 'POINTCLOUD', 'VOLUME', 'GREASEPENCIL', 'GPENCIL',
}

MAX_INSTANCE_DEPTH = 8
DEPTH_CAPABLE = {'PNG', 'TIFF', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}

BASE_PATH_CANDIDATES = ("base_path", "directory", "filepath", "output_path")
PATH_SLOT_ATTRS = ("path", "filepath", "output_path", "subpath")

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
    """
    Make a string safe for use as a file/folder name while preserving
    underscores, dots, dashes and spaces.
    """
    s = str(name)

    # Path separators should not appear in file names.
    s = s.replace("/", "_").replace("\\", "_")

    # Remove characters that are invalid on Windows/Linux/macOS.
    invalid_chars = '<>:"|?*\0'
    s = "".join(c for c in s if c >= " " and c not in invalid_chars)

    # Windows does not like trailing dots or spaces.
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
    """
    Split a Blender path into directory and file stem.

    '//out/beauty' -> ('//out', 'beauty')
    '//out/'       -> ('//out', '')
    '//'           -> ('//', '')
    """
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
    """
    Force a File Output slot path to be relative to the node base path.

    Absolute slot paths bypass the node base path.
    """
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
# POST-RENAME HELPERS
# ============================================================

def snapshot_files(dirs, extensions=None):
    """
    Return a set of existing files inside the given Blender directories.
    """
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
    """
    Split Blender frame padding from the filename stem.

    Image0001.png -> ('Image', '0001', '.png')
    Image.png     -> ('Image', '',    '.png')
    """
    stem, ext = os.path.splitext(filename)

    i = len(stem)
    while i > 0 and stem[i - 1].isdigit():
        i -= 1

    digits = stem[i:]
    base = stem[:i]

    # Blender normally uses at least 3/4 padded digits.
    if digits and len(digits) >= 3:
        return base, digits, ext

    return stem, "", ext


def prefix_new_files(dirs, prefix, before_files, start_time, extensions=None):
    """
    Rename newly rendered files by adding a filename prefix.

    Special rule:
    - if the original name is empty or 'Untitled', use only the collection name.
    - otherwise prefix the original name.
    """
    if not prefix or before_files is None or start_time is None:
        return 0

    current = snapshot_files(dirs, extensions)
    candidates = set(current) - set(before_files)

    # Also catch overwritten files whose path already existed.
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

        # Already processed / already prefixed.
        if base_clean == prefix or base_clean.startswith(prefix + "_"):
            continue

        # Empty socket name / Blender fallback name:
        # use only collection name, do not append '_Untitled'.
        if base_clean == "" or base_clean.lower() == "untitled":
            new_base = prefix
        else:
            new_base = f"{prefix}_{base_clean}"

        new_filename = new_base + digits + ext
        new_path = os.path.join(directory, new_filename)

        if os.path.normcase(path) == os.path.normcase(new_path):
            continue

        # Avoid overwriting another file that was already renamed during this pass.
        if os.path.normcase(new_path) in written_targets:
            stem_only, ext_only = os.path.splitext(new_filename)
            k = 1

            while True:
                alt = os.path.join(directory, f"{stem_only}_{k}{ext_only}")
                if (
                        os.path.normcase(alt) not in written_targets
                        and not os.path.exists(alt)
                ):
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
# COMPOSITOR HELPERS
# ============================================================

def get_compositor_tree(scene):
    """
    Return (node_tree, is_legacy).

    Blender 5.x usually uses scene.compositing_node_group.
    Older versions use scene.node_tree.
    """
    tree = getattr(scene, "compositing_node_group", None)
    if tree is not None:
        return tree, False

    return getattr(scene, "node_tree", None), True


def collect_file_outputs(scene):
    """
    Find all File Output nodes in the scene compositor, including node groups.
    """
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

            elif node.bl_idname == 'CompositorNodeGroup':
                walk(getattr(node, "node_tree", None), prefix + (node.name,))

            elif getattr(node, "node_tree", None) is not None:
                walk(getattr(node, "node_tree", None), prefix + (node.name,))

        visited_trees.discard(tree_key)

    walk(root, tuple())
    return out


def get_base_path_attr(node):
    for name in BASE_PATH_CANDIDATES:
        try:
            value = getattr(node, name)
        except Exception:
            continue

        if isinstance(value, str):
            return name

    return None


def read_base_path(node):
    attr = get_base_path_attr(node)
    if attr is None:
        return None, ""

    try:
        return attr, getattr(node, attr) or ""
    except Exception:
        return attr, ""


def node_is_multilayer(node):
    fmt = getattr(node, "format", None)
    if fmt is None:
        return False
    return getattr(fmt, "file_format", "") == 'OPEN_EXR_MULTILAYER'


def get_node_slots(node):
    """
    Return (slot_collection, slot_attribute_name).

    Regular image formats:
        file_slots.path

    Multilayer EXR:
        layer_slots.name
    """
    if node_is_multilayer(node):
        slots = getattr(node, "layer_slots", None)
        if slots is not None:
            return slots, "name"

    slots = getattr(node, "file_slots", None)
    if slots is not None:
        return slots, "path"

    slots = getattr(node, "layer_slots", None)
    if slots is not None:
        return slots, "name"

    return None, None


def get_slots_by_key(node, key):
    if key == "name":
        return getattr(node, "layer_slots", None)
    if key == "path":
        return getattr(node, "file_slots", None)
    return None


def snapshot_node(node, key):
    """
    Capture original node state.
    """
    multilayer = node_is_multilayer(node)
    slots, slot_key = get_node_slots(node)
    base_attr, base_path = read_base_path(node)

    slot_paths = []
    if slots is not None and slot_key:
        for slot in slots:
            try:
                slot_paths.append(str(getattr(slot, slot_key, "")))
            except Exception:
                slot_paths.append("")

    return {
        "key": key,
        "name": node.name,
        "base_attr": base_attr,
        "base_path": base_path,
        "multilayer": multilayer,
        "slot_key": slot_key,
        "slot_paths": slot_paths,
        "library": getattr(node.id_data, "library", None) is not None,
    }


def apply_node_paths(node, settings, collection_name, snap):
    """
    Prepare a File Output node for rendering one collection.

    Important new logic:
    - SUBFOLDER mode changes the base path.
    - PREFIX mode does NOT try to force Blender slot/socket names.
      The rendered files are renamed on disk after rendering.

    Returns:
        target_dir, scan_dirs, needs_prefix_rename, problems
    """
    problems = []

    mode = settings.node_naming
    override = settings.node_override_base

    if mode == 'NONE' and not override:
        return None, [], False, problems

    base_attr = get_base_path_attr(node)
    base_writable = base_attr is not None

    fallback = settings.output_dir or "//"
    original_base = snap.get("base_path", "")
    safe_col = sanitize_filename(collection_name)
    multilayer = snap.get("multilayer", False)

    scan_dirs = []

    def add_scan_dir(d):
        if d:
            scan_dirs.append(ensure_slash(d))

    # Original base directory is always a valid rename-scan candidate.
    orig_head, orig_stem = split_base(original_base or fallback)
    add_scan_dir(orig_head or fallback)

    # Absolute slot paths can bypass the base path. Add their directories too.
    for sp in snap.get("slot_paths", []):
        if slot_path_is_absolute(sp):
            try:
                abs_p = bpy.path.abspath(sp)
            except Exception:
                abs_p = ""

            if abs_p:
                if os.path.isdir(abs_p):
                    add_scan_dir(abs_p)
                else:
                    add_scan_dir(os.path.dirname(abs_p) or abs_p)

    needs_prefix_rename = False

    # ------------------------------------------------------------
    # MULTILAYER EXR
    # Base path is a file stem, not only a directory.
    # ------------------------------------------------------------
    if multilayer:
        if not base_writable:
            # Cannot move it, but prefix mode can still rename the written file.
            needs_prefix_rename = mode in {'PREFIX', 'SUBFOLDER'}
            target_dir = ensure_slash(orig_head or fallback)
            add_scan_dir(target_dir)
            return target_dir, unique_dirs(scan_dirs), needs_prefix_rename, problems

        base_dir = fallback if override else (orig_head or fallback)
        stem = orig_stem or "render"

        if mode == 'SUBFOLDER':
            target_dir = ensure_slash(safe_join(base_dir, safe_col))
            new_base = safe_join(target_dir, stem)
            needs_prefix_rename = False

        elif mode == 'PREFIX':
            target_dir = ensure_slash(base_dir)
            new_base = safe_join(target_dir, stem)
            needs_prefix_rename = True

        else:
            target_dir = ensure_slash(base_dir)
            new_base = safe_join(target_dir, stem)
            needs_prefix_rename = False

        try:
            setattr(node, base_attr, new_base)
        except Exception as e:
            problems.append(f"{node.name}: could not write base path ({e})")

        add_scan_dir(target_dir)
        return target_dir, unique_dirs(scan_dirs), needs_prefix_rename, problems

    # ------------------------------------------------------------
    # REGULAR IMAGE OUTPUT
    # ------------------------------------------------------------

    if not base_writable:
        # Cannot change base path. For SUBFOLDER/PREFIX, fall back to prefixing files.
        target_dir = ensure_slash(original_base or fallback)
        add_scan_dir(target_dir)
        needs_prefix_rename = mode in {'PREFIX', 'SUBFOLDER'}
        return target_dir, unique_dirs(scan_dirs), needs_prefix_rename, problems

    base_dir = fallback if override else (original_base or fallback)

    if mode == 'SUBFOLDER':
        target_dir = ensure_slash(safe_join(base_dir, safe_col))
        new_base = target_dir
        needs_prefix_rename = False

    elif mode == 'PREFIX':
        target_dir = ensure_slash(base_dir)
        new_base = target_dir
        needs_prefix_rename = True

    else:
        target_dir = ensure_slash(base_dir)
        new_base = target_dir
        needs_prefix_rename = False

    if new_base != original_base:
        try:
            setattr(node, base_attr, new_base)
        except Exception as e:
            problems.append(f"{node.name}: could not write base path ({e})")

    # Clean slot paths so they cannot bypass the base path.
    # Do NOT add the collection prefix here. PREFIX mode is handled by post-rename.
    slots, slot_key = get_node_slots(node)
    slot_paths = snap.get("slot_paths", [])

    if slots is not None and slot_key in PATH_SLOT_ATTRS and slot_paths:
        limit = min(len(slots), len(slot_paths))

        for i in range(limit):
            cleaned = make_relative_slot(slot_paths[i])
            try:
                setattr(slots[i], slot_key, cleaned)
            except Exception:
                pass

    add_scan_dir(target_dir)
    return target_dir, unique_dirs(scan_dirs), needs_prefix_rename, problems


def restore_node(node, snap):
    """
    Restore original node base path and slot paths.
    """
    base_attr = get_base_path_attr(node)

    if base_attr is not None:
        try:
            setattr(node, base_attr, snap.get("base_path", ""))
        except Exception:
            pass

    key = snap.get("slot_key")
    slot_paths = snap.get("slot_paths", [])

    if key and slot_paths:
        slots = get_slots_by_key(node, key)
        if slots is not None:
            limit = min(len(slots), len(slot_paths))

            for i in range(limit):
                try:
                    setattr(slots[i], key, slot_paths[i])
                except Exception:
                    pass


# ============================================================
# BOUNDS
# ============================================================

def _corners_degenerate(corners):
    first = corners[0]
    return all((c - first).length_squared < 1e-12 for c in corners[1:])


def get_collection_bounds(collection, depsgraph=None, visited=None, depth=0, ignore_hidden=True):
    """
    World-space AABB of a collection, including children and collection instances.
    Objects disabled for render are ignored.
    """
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
        if v.x < min_co.x:
            min_co.x = v.x
        if v.y < min_co.y:
            min_co.y = v.y
        if v.z < min_co.z:
            min_co.z = v.z
        if v.x > max_co.x:
            max_co.x = v.x
        if v.y > max_co.y:
            max_co.y = v.y
        if v.z > max_co.z:
            max_co.z = v.z
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
    """Yield (path_tuple, layer_collection)."""
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
    """
    Isolate a collection by excluding other collections.

    Uses collection pointers instead of names to avoid name-collision bugs.
    """
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

            # Include ancestors.
            for i in range(len(path) + 1):
                include.add(path[:i])

            # Include descendants.
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


def snapshot_hide_render(scene):
    return {ob.name: ob.hide_render for ob in scene.objects}


def restore_hide_render(scene, snapshot):
    for name, state in snapshot.items():
        ob = bpy.data.objects.get(name)
        if ob is not None:
            try:
                ob.hide_render = state
            except Exception:
                pass


def isolate_collection_by_hide(scene, target_collection, keep_collections=(), keep_lights=True):
    keep_objs = objects_in_collection(target_collection)

    for col in keep_collections:
        if col is not None:
            keep_objs |= objects_in_collection(col)

    for ob in scene.objects:
        if ob.type == 'CAMERA':
            ob.hide_render = False
            continue

        if keep_lights and ob.type in {'LIGHT', 'LIGHT_PROBE'}:
            ob.hide_render = False
            continue

        ob.hide_render = ob.name not in keep_objs


# ============================================================
# PROPERTIES
# ============================================================

class BTS_Settings(PropertyGroup):
    output_dir: StringProperty(
        name="Output Directory",
        description="Folder for rendered sprites",
        default="//sprites/",
        subtype='DIR_PATH',
    )

    file_format: EnumProperty(
        name="Format",
        items=[
            ('PNG', "PNG", ""),
            ('JPEG', "JPEG", ""),
            ('OPEN_EXR', "EXR", ""),
            ('TIFF', "TIFF", ""),
            ('WEBP', "WebP", ""),
            ('TARGA', "Targa", ""),
            ('BMP', "BMP", ""),
        ],
        default='PNG',
    )

    color_mode: EnumProperty(
        name="Color",
        items=[
            ('BW', "BW", ""),
            ('RGB', "RGB", ""),
            ('RGBA', "RGBA", ""),
        ],
        default='RGBA',
    )

    color_depth: EnumProperty(
        name="Depth",
        items=[
            ('8', "8", ""),
            ('16', "16", ""),
            ('32', "32", ""),
        ],
        default='8',
    )

    use_transparent: BoolProperty(
        name="Transparent Film",
        default=True,
    )

    # Compositor
    use_compositor_nodes: BoolProperty(
        name="Use File Output Nodes",
        description="Let File Output nodes write the files",
        default=True,
    )

    node_naming: EnumProperty(
        name="Collection Goes To",
        description="How the collection name is applied to File Output nodes",
        items=[
            ('SUBFOLDER', "Subfolder", "base/<Collection>/"),
            ('PREFIX', "Filename Prefix", "base/<Collection>_<file>"),
            ('NONE', "Don't Modify", "Leave node paths alone"),
        ],
        default='SUBFOLDER',
    )

    node_override_base: BoolProperty(
        name="Override Base Paths",
        description=(
            "Replace each node's base path with the Output Directory. "
            "Slot paths are forced relative so they cannot bypass the base path"
        ),
        default=False,
    )

    write_main_output: BoolProperty(
        name="Also Write Main Render",
        description="Also save the Render Result to the Output Directory",
        default=False,
    )

    # Camera
    camera_axis: EnumProperty(
        name="View Axis",
        items=[
            ('TOP', "Top", "Look down -Z"),
            ('BOTTOM', "Bottom", "Look up +Z"),
            ('FRONT', "Front", "Look along +Y"),
            ('BACK', "Back", "Look along -Y"),
            ('RIGHT', "Right", "Look along -X"),
            ('LEFT', "Left", "Look along +X"),
        ],
        default='TOP',
    )

    camera_margin: FloatProperty(
        name="Camera Distance Margin",
        description="Extra distance between camera and bounds",
        default=10.0,
        min=0.01,
        soft_max=1000.0,
    )

    auto_cleanup_camera: BoolProperty(
        name="Remove Camera After Export",
        default=True,
    )

    # Padding
    padding_mode: EnumProperty(
        name="Padding Mode",
        items=[
            ('PIXELS', "Pixels", ""),
            ('UNITS', "Units", ""),
        ],
        default='PIXELS',
    )

    padding_pixels: IntProperty(
        name="Padding",
        default=16,
        min=0,
        soft_max=512,
    )

    padding_units: FloatProperty(
        name="Padding",
        default=0.1,
        min=0.0,
        soft_max=100.0,
    )

    # Resolution
    pixels_per_unit: FloatProperty(
        name="Pixels / Unit",
        default=100.0,
        min=0.001,
        soft_max=2048.0,
    )

    resolution_multiple: IntProperty(
        name="Round To Multiple Of",
        default=1,
        min=1,
        soft_max=64,
    )

    square_output: BoolProperty(
        name="Square Output",
        default=False,
    )

    min_resolution: IntProperty(
        name="Min Res",
        default=1,
        min=1,
        soft_max=8192,
    )

    max_resolution: IntProperty(
        name="Max Res",
        description="0 = unlimited",
        default=0,
        min=0,
        soft_max=16384,
    )

    # Isolation
    isolation_mode: EnumProperty(
        name="Isolation",
        items=[
            ('EXCLUDE', "Exclude Collections", ""),
            ('HIDE', "Disable in Renders", ""),
        ],
        default='EXCLUDE',
    )

    keep_collections: StringProperty(
        name="Always Include",
        description="Comma-separated collection names that stay visible",
        default="",
    )

    keep_lights: BoolProperty(
        name="Always Keep Lights",
        default=True,
    )

    export_source: EnumProperty(
        name="Export",
        items=[
            ('ALL', "All Collections", ""),
            ('INCLUDED', "Only Included", ""),
            ('ACTIVE', "Active Collection", ""),
            ('TOPLEVEL', "Top-Level Only", ""),
        ],
        default='ALL',
    )

    skip_empty: BoolProperty(
        name="Skip Empty Collections",
        description="Skip collections without renderable geometry",
        default=True,
    )


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


def ensure_camera(scene):
    cam_obj = bpy.data.objects.get(ADDON_CAM_NAME)

    if cam_obj is not None and cam_obj.type != 'CAMERA':
        cam_obj = None

    if cam_obj is None:
        cam_data = bpy.data.cameras.get(ADDON_CAM_NAME) or bpy.data.cameras.new(ADDON_CAM_NAME)
        cam_obj = bpy.data.objects.new(ADDON_CAM_NAME, cam_data)

    if cam_obj.name not in scene.collection.objects:
        try:
            scene.collection.objects.link(cam_obj)
        except RuntimeError:
            pass

    cam_obj.hide_render = False
    cam_obj.hide_viewport = False
    return cam_obj


def remove_camera():
    removed = False

    ob = bpy.data.objects.get(ADDON_CAM_NAME)
    if ob is not None:
        bpy.data.objects.remove(ob, do_unlink=True)
        removed = True

    cam = bpy.data.cameras.get(ADDON_CAM_NAME)
    if cam is not None and cam.users == 0:
        bpy.data.cameras.remove(cam)
        removed = True

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

        # ---------------- path sanity ----------------
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
            self.report(
                {'ERROR'},
                "Output path is relative ('//') but the .blend has never been saved. "
                "Save the file or use an absolute path."
            )
            return {'CANCELLED'}

        if settings.output_dir:
            output_dir_abs = bpy.path.abspath(settings.output_dir)
            try:
                os.makedirs(output_dir_abs, exist_ok=True)
            except Exception as e:
                self.report({'ERROR'}, f"Cannot create output directory: {e}")
                return {'CANCELLED'}

        # ---------------- extensions for post-rename ----------------
        render_exts = set()
        render_exts.add(EXT_BY_FORMAT.get(settings.file_format, "").lower())

        for node in all_file_outputs.values():
            fmt = getattr(node, "format", None)
            if fmt is not None:
                render_exts.add(
                    EXT_BY_FORMAT.get(getattr(fmt, "file_format", ""), "").lower()
                )

        render_exts.discard("")

        # ---------------- compositor snapshots ----------------
        comp_tree, comp_is_legacy = get_compositor_tree(scene)
        node_snapshots = [snapshot_node(n, k) for k, n in node_map.items()]

        # ---------------- scene state snapshots ----------------
        exclude_snapshot = snapshot_excludes(vl)
        hide_snapshot = snapshot_hide_render(scene)

        orig = {
            "camera": scene.camera,
            "res_x": rd.resolution_x,
            "res_y": rd.resolution_y,
            "res_pct": rd.resolution_percentage,
            "filepath": rd.filepath,
            "format": rd.image_settings.file_format,
            "color_mode": rd.image_settings.color_mode,
            "color_depth": rd.image_settings.color_depth,
            "transparent": rd.film_transparent,
            "use_compositing": getattr(rd, "use_compositing", True),
            "use_nodes": getattr(scene, "use_nodes", None),
        }

        touched_use_nodes = False

        # ---------------- measure ----------------
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

        # ---------------- global render setup ----------------
        cam_obj = ensure_camera(scene)
        scene.camera = cam_obj

        rd.resolution_percentage = 100
        rd.film_transparent = settings.use_transparent

        if using_nodes:
            try:
                rd.use_compositing = True
            except Exception:
                pass

            if comp_is_legacy and orig["use_nodes"] is False:
                try:
                    scene.use_nodes = True
                    touched_use_nodes = True
                except Exception:
                    pass

        elif all_file_outputs:
            # File Output nodes exist but are disabled in this add-on.
            # Disable compositing so they do not write unmanaged files.
            try:
                rd.use_compositing = False
            except Exception:
                pass

        if (not using_nodes) or settings.write_main_output:
            apply_image_settings(rd.image_settings, settings)

        rendered = 0
        reported_problems = set()

        wm.progress_begin(0, len(measured))

        try:
            for index, (col, (bmin, bmax)) in enumerate(measured):
                wm.progress_update(index)

                safe_name = sanitize_filename(col.name)
                frame = configure_camera(cam_obj, bmin, bmax, settings)

                rd.resolution_x = frame["res_x"]
                rd.resolution_y = frame["res_y"]

                # ---------------- isolate ----------------
                if settings.isolation_mode == 'EXCLUDE':
                    if not isolate_collection_by_exclude(vl, col, keep_collections):
                        skipped += 1
                        continue
                else:
                    include_all(vl)
                    isolate_collection_by_hide(scene, col, keep_collections, settings.keep_lights)

                vl.update()

                # ---------------- File Output nodes ----------------
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

                        target_dir, scan_dirs, needs_prefix, problems = apply_node_paths(
                            node,
                            settings,
                            col.name,
                            snap,
                        )

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

                # ---------------- main render output ----------------
                if using_nodes:
                    write_still = bool(settings.write_main_output and settings.output_dir)
                else:
                    write_still = True

                if write_still:
                    rd.filepath = safe_join(settings.output_dir, safe_name)

                # ---------------- render + prefix rename ----------------
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
                        prefix_new_files(
                            rename_scan_dirs,
                            safe_name,
                            rename_before,
                            render_start,
                            render_exts or None,
                            )

        finally:
            wm.progress_end()

            # Restore File Output nodes
            if node_snapshots:
                live_nodes = collect_file_outputs(scene)
                for snap in node_snapshots:
                    node = live_nodes.get(snap["key"])
                    if node is not None:
                        restore_node(node, snap)

            # Restore visibility
            restore_hide_render(scene, hide_snapshot)
            restore_excludes(vl, exclude_snapshot)
            vl.update()

            # Restore render settings
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

            if touched_use_nodes:
                try:
                    scene.use_nodes = orig["use_nodes"]
                except Exception:
                    pass

            # Restore camera
            if settings.auto_cleanup_camera:
                remove_camera()
                scene.camera = orig["camera"]
            else:
                scene.camera = orig["camera"] if orig["camera"] else cam_obj

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

        self.report(
            {'INFO'},
            f"{col.name}: {frame['res_x']}x{frame['res_y']} px, ortho {frame['ortho_scale']:.4f}"
        )
        return {'FINISHED'}


class BTS_OT_Cleanup(Operator):
    bl_idname = "bts.cleanup"
    bl_label = "Remove Camera"
    bl_description = "Delete the temporary orthographic camera"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.scene.camera and context.scene.camera.name == ADDON_CAM_NAME:
            context.scene.camera = None

        removed = remove_camera()
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


# ============================================================
# UI
# ============================================================

class BTS_PT_MainPanel(Panel):
    bl_label = "Blender To Sprites"
    bl_idname = "BTS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        col.scale_y = 1.6
        col.operator("bts.batch_export", icon='RENDER_ANIMATION')

        row = layout.row(align=True)
        row.operator("bts.preview_camera", icon='CON_CAMERASOLVER')
        row.operator("bts.cleanup", icon='TRASH')

        layout.operator("bts.restore_collections", icon='LOOP_BACK')

        if is_relative_unsaved(context.scene.bts_settings.output_dir):
            box = layout.box()
            box.alert = True
            box.label(text="Unsaved file + relative '//' path", icon='ERROR')


class BTS_PT_Source(Panel):
    bl_label = "Collections"
    bl_idname = "BTS_PT_source"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        s = context.scene.bts_settings

        layout.prop(s, "export_source")
        layout.prop(s, "skip_empty")
        layout.separator()
        layout.prop(s, "isolation_mode")
        layout.prop(s, "keep_collections", icon='OUTLINER_COLLECTION')

        sub = layout.row()
        sub.enabled = (s.isolation_mode == 'HIDE')
        sub.prop(s, "keep_lights")


class BTS_PT_Camera(Panel):
    bl_label = "Camera & Framing"
    bl_idname = "BTS_PT_camera"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        s = context.scene.bts_settings

        layout.prop(s, "camera_axis")
        layout.prop(s, "camera_margin")
        layout.prop(s, "auto_cleanup_camera")
        layout.separator()
        layout.prop(s, "padding_mode", expand=True)
        layout.prop(s, "padding_pixels" if s.padding_mode == 'PIXELS' else "padding_units")


class BTS_PT_Resolution(Panel):
    bl_label = "Resolution"
    bl_idname = "BTS_PT_resolution"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        s = context.scene.bts_settings

        layout.prop(s, "pixels_per_unit")
        layout.prop(s, "resolution_multiple")
        layout.prop(s, "square_output")

        col = layout.column(align=True)
        col.prop(s, "min_resolution")
        col.prop(s, "max_resolution")


class BTS_PT_Output(Panel):
    bl_label = "Output"
    bl_idname = "BTS_PT_output"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        scene = context.scene
        s = scene.bts_settings
        rd = scene.render

        node_map = collect_file_outputs(scene)
        nodes = list(node_map.values())

        if nodes:
            layout.prop(s, "use_compositor_nodes")

        # ------------------------------------------------------------
        # FILE OUTPUT NODE MODE
        # ------------------------------------------------------------
        if nodes and s.use_compositor_nodes:
            _, legacy = get_compositor_tree(scene)

            compositing_off = not getattr(rd, "use_compositing", True)
            nodes_off = legacy and getattr(scene, "use_nodes", True) is False

            if compositing_off or nodes_off:
                warn = layout.box()
                warn.alert = True
                warn.label(text="Compositing is disabled!", icon='ERROR')
                warn.label(text="It will be force-enabled during export.")

            layout.prop(s, "node_naming")
            layout.prop(s, "node_override_base")
            layout.prop(
                s,
                "output_dir",
                text="Base Dir" if s.node_override_base else "Fallback Dir"
            )

            if s.node_override_base and not s.output_dir:
                e = layout.box()
                e.alert = True
                e.label(text="Base Dir is empty!", icon='ERROR')

            layout.prop(s, "write_main_output")
            layout.prop(s, "use_transparent")

            if s.node_naming == 'PREFIX':
                info = layout.box()
                info.label(text="Prefix mode renames rendered files after export.", icon='INFO')
                info.label(text="File Output node socket names may stay unchanged.")

            if s.write_main_output:
                box = layout.column(align=True)
                box.prop(s, "file_format")
                box.prop(s, "color_mode")

                if s.file_format in DEPTH_CAPABLE:
                    box.prop(s, "color_depth")

            layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = s.output_dir
            layout.separator()
            layout.label(text=f"{len(nodes)} File Output node(s) active", icon='NODE_COMPOSITING')

        # ------------------------------------------------------------
        # STANDARD MODE
        # ------------------------------------------------------------
        else:
            layout.prop(s, "output_dir")
            layout.prop(s, "file_format")
            layout.prop(s, "color_mode")

            if s.file_format in DEPTH_CAPABLE:
                layout.prop(s, "color_depth")

            layout.prop(s, "use_transparent")
            layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = s.output_dir

            if nodes:
                box = layout.box()
                box.label(text="File Output nodes found but disabled.", icon='INFO')
                box.label(text="Compositing will be disabled during export.")


# ============================================================
# REGISTER
# ============================================================

classes = (
    BTS_Settings,
    BTS_OT_BatchExport,
    BTS_OT_PreviewCamera,
    BTS_OT_Cleanup,
    BTS_OT_RestoreCollections,
    BTS_OT_OpenOutputFolder,
    BTS_PT_MainPanel,
    BTS_PT_Source,
    BTS_PT_Camera,
    BTS_PT_Resolution,
    BTS_PT_Output,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.bts_settings = PointerProperty(type=BTS_Settings)


def unregister():
    if hasattr(bpy.types.Scene, "bts_settings"):
        del bpy.types.Scene.bts_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()