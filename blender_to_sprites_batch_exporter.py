bl_info = {
    "name": "Blender To Sprites Batch Exporter",
    "author": "kirillhod",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar (N) > Batch Export",
    "description": (
        "Batch render collections to sprites with an auto-fitted orthographic camera, "
        "constant pixels-per-unit resolution and compositor File Output support"
    ),
    "category": "Import-Export",
}

import bpy
import os
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
#  CONSTANTS
# ============================================================

ADDON_NAME = "Blender To Sprites Batch Exporter"
ADDON_TAG = "BTS"
ADDON_CAM_NAME = "_BTS_OrthoCamera"

GEOMETRY_TYPES = {
    'MESH', 'CURVE', 'SURFACE', 'META', 'FONT',
    'CURVES', 'POINTCLOUD', 'VOLUME', 'GREASEPENCIL', 'GPENCIL',
}

MAX_INSTANCE_DEPTH = 8                  # guard against recursive collection instances
DEPTH_CAPABLE = {'PNG', 'TIFF', 'OPEN_EXR', 'OPEN_EXR_MULTILAYER'}

# Names Blender has used for the File Output node's root path.
# Probed by reading, never by hasattr - see _find_base_path_attr().
BASE_PATH_CANDIDATES = ("base_path", "directory", "filepath", "output_path")

EXT_BY_FORMAT = {
    'PNG': '.png', 'JPEG': '.jpg', 'JPEG2000': '.jp2',
    'OPEN_EXR': '.exr', 'OPEN_EXR_MULTILAYER': '.exr',
    'TIFF': '.tif', 'BMP': '.bmp', 'WEBP': '.webp',
    'TARGA': '.tga', 'TARGA_RAW': '.tga',
}

DEBUG = True


def log(msg):
    if DEBUG:
        print(f"[{ADDON_TAG}] {msg}")


# ============================================================
#  PATH HELPERS
# ============================================================

def sanitize_filename(name):
    s = "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()
    return s or "untitled"


def safe_join(*parts):
    """Join path parts with '/', preserving Blender's '//' relative prefix."""
    parts = [p for p in parts if p]
    if not parts:
        return ""
    result = parts[0]
    for p in parts[1:]:
        p = p.strip("\\/")
        if not p:
            continue
        result = result + p if result.endswith(("/", "\\")) else result + "/" + p
    return result


def ensure_slash(path):
    """Guarantee a trailing '/' so Blender treats the path as a directory."""
    if not path:
        return "//"
    return path if path.endswith(("/", "\\")) else path + "/"


def split_base(path):
    """
    Split a Blender path into (directory, filename-stem).

    '//'           -> ('//',    '')
    '//out/'       -> ('//out', '')
    '//out/beauty' -> ('//out', 'beauty')
    """
    p = (path or "").replace("\\", "/")
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
    Force a File Output slot path to be RELATIVE to the node's base path.

    Blender joins base + slot, and a slot starting with '//', '/' or a drive
    letter resolves back to its own absolute location, silently bypassing the
    base path. That makes an overridden base path look like it did nothing.
    """
    s = (slot_path or "").replace("\\", "/")
    while s.startswith("//"):
        s = s[2:]
    if len(s) >= 2 and s[1] == ":":          # 'C:/foo'
        s = s[2:]
    s = s.lstrip("/")
    while s.startswith("./"):
        s = s[2:]
    s = s.replace("../", "")                 # no escaping the base dir
    return s


def prefix_basename(slot_path, prefix):
    """Prefix only the file part of a slot path, keeping any sub-folders intact."""
    s = (slot_path or "").replace("\\", "/")
    if "/" in s:
        d, n = s.rsplit("/", 1)
        return f"{d}/{prefix}_{n}" if n else f"{d}/{prefix}"
    return f"{prefix}_{s}" if s else prefix


def ensure_dir(blender_path):
    """Create the directory for a (possibly relative '//') Blender path."""
    if not blender_path:
        return False
    try:
        abs_path = bpy.path.abspath(blender_path)
        if not abs_path:
            return False
        os.makedirs(abs_path, exist_ok=True)
        return True
    except Exception as e:
        log(f"could not create dir '{blender_path}': {e}")
        return False


def is_relative_unsaved(path):
    """True if the path needs the .blend location but the file was never saved."""
    return bool(path) and path.startswith("//") and not bpy.data.is_saved


# ============================================================
#  COMPOSITOR DISCOVERY
#  Nothing is cached: nodes are re-resolved from the scene on every use,
#  because Python references to node trees can go stale across a render.
# ============================================================

def get_compositor_tree(scene):
    """
    Returns (tree, is_legacy).

    Blender 5.x : scene.compositing_node_group
    Legacy      : scene.node_tree

    The legacy tree is returned even when use_nodes is off, so the exporter
    can switch it on for the duration of the export - but ONLY when the
    legacy tree is the one actually holding the nodes.
    """
    tree = getattr(scene, "compositing_node_group", None)
    if tree is not None:
        return tree, False
    return getattr(scene, "node_tree", None), True


def collect_file_outputs(scene):
    """
    Every File Output node in the scene compositor, recursing into node groups.

    Returns an ordered dict {key: node} where key is a stable tuple of
    (group node names..., node name). The key survives re-walks and render
    calls, unlike a raw NodeTree/Node Python reference.
    """
    root, _ = get_compositor_tree(scene)
    out = {}
    if root is None:
        return out

    visited_trees = set()

    def walk(nt, prefix):
        if nt is None:
            return
        tkey = nt.as_pointer()
        if tkey in visited_trees:
            return                       # recursive group - bail
        visited_trees.add(tkey)
        for n in nt.nodes:
            if n.bl_idname == 'CompositorNodeOutputFile':
                out[prefix + (n.name,)] = n
            elif getattr(n, "type", "") == 'GROUP':
                walk(getattr(n, "node_tree", None), prefix + (n.name,))
        visited_trees.discard(tkey)

    walk(root, tuple())
    return out


# ------------------------------------------------------------
#  Base-path attribute resolution
#  hasattr() cannot be trusted here: on some Blender 5.x builds it returns
#  False for File Output properties that are in fact present and writable.
#  We probe by reading instead.
# ------------------------------------------------------------

def _find_base_path_attr(node):
    """Name of the string attribute holding the node's base path, or None."""
    for name in BASE_PATH_CANDIDATES:
        try:
            value = getattr(node, name)
        except Exception:
            continue
        if isinstance(value, str):
            return name
    return None


def _read_base_path(node):
    attr = _find_base_path_attr(node)
    if attr is None:
        return attr, ""
    try:
        return attr, getattr(node, attr) or ""
    except Exception:
        return attr, ""


def dump_node_strings(node, limit=40):
    """Every string-valued attribute on the node - diagnostics only."""
    out = []
    for a in dir(node):
        if a.startswith("_"):
            continue
        try:
            v = getattr(node, a)
        except Exception:
            continue
        if isinstance(v, str):
            out.append(a)
        if len(out) >= limit:
            break
    return out


def node_is_multilayer(node):
    fmt = getattr(node, "format", None)
    return getattr(fmt, "file_format", "") == 'OPEN_EXR_MULTILAYER' if fmt else False


def slots_attr_for(multilayer):
    """Multilayer EXR writes layer_slots.name, everything else file_slots.path."""
    return ("layer_slots", "name") if multilayer else ("file_slots", "path")


def get_node_slots(node):
    """Return (slot_collection, attribute_name) for the slots Blender writes."""
    attr, key = slots_attr_for(node_is_multilayer(node))
    slots = getattr(node, attr, None)
    if slots is None:
        attr, key = slots_attr_for(not node_is_multilayer(node))
        slots = getattr(node, attr, None)
    return (slots, key) if slots is not None else (None, None)


def get_slots_by_key(node, key):
    """Resolve a slot collection from a stored key, without re-reading format."""
    return getattr(node, "layer_slots" if key == "name" else "file_slots", None)


def get_node_inputs(node):
    inputs = getattr(node, "inputs", None)
    return inputs if inputs is not None and len(inputs) else None


def snapshot_node(node, key):
    """Capture node state. `key` is the stable lookup key from collect_file_outputs."""
    multilayer = node_is_multilayer(node)
    slots, slot_key = get_node_slots(node)
    base_attr, base_val = _read_base_path(node)
    return {
        "key": key,
        "name": node.name,
        "base_attr": base_attr,
        "base_path": base_val,
        "multilayer": multilayer,
        "slot_key": slot_key,
        "slot_names": [getattr(s, slot_key, "") for s in slots] if (slots and slot_key) else [],
        "library": getattr(node.id_data, "library", None) is not None,
    }


# ============================================================
#  PATH SOLVER  (shared by exporter, dry run and UI preview)
# ============================================================

def compute_node_paths(original_base, slot_names, multilayer, settings,
                       collection_name, base_writable=True):
    """
    Pure function - no side effects. Returns:
      base    : new base path value
      slots   : new slot names (same length as slot_names)
      dir     : directory that must exist on disk, or None
      changed : False means "leave the node completely alone"

    When `base_writable` is False the base path cannot be modified, so the
    collection separation is pushed into the SLOT paths instead. Blender
    honours sub-folders inside slot paths, so output still stays separated.
    """
    unchanged = {"base": original_base, "slots": list(slot_names),
                 "dir": None, "changed": False}

    mode = settings.node_naming
    override = settings.node_override_base
    if mode == 'NONE' and not override:
        return unchanged

    fallback = settings.output_dir or "//"
    base = fallback if (override and base_writable) else (original_base or fallback)
    safe_col = sanitize_filename(collection_name)

    # ---------- multilayer EXR: base path is a FILE stem ----------
    if multilayer:
        if not base_writable:
            # Layer names are internal to the file - nothing to separate.
            return unchanged
        head, stem = split_base(base)
        if mode == 'SUBFOLDER':
            new_dir = safe_join(head, safe_col)
            new_base = safe_join(new_dir, stem) if stem else ensure_slash(new_dir)
            target_dir = ensure_slash(new_dir)
        elif mode == 'PREFIX':
            new_base = safe_join(head, f"{safe_col}_{stem}" if stem else safe_col)
            target_dir = ensure_slash(head)
        else:                                   # NONE + override
            new_base = base
            target_dir = ensure_slash(head)
        return {"base": new_base, "slots": list(slot_names),
                "dir": target_dir, "changed": True}

    # ---------- regular output: base path is a DIRECTORY ----------
    # Slot paths must be relative or they bypass the base path entirely.
    cleaned = [make_relative_slot(s) for s in slot_names]

    if not base_writable:
        # Fallback: fold the collection name into the slot paths.
        if mode == 'SUBFOLDER':
            new_slots = [f"{safe_col}/{s}" if s else safe_col for s in cleaned]
            target_dir = ensure_slash(safe_join(original_base or fallback, safe_col))
        elif mode == 'PREFIX':
            new_slots = [prefix_basename(s, safe_col) for s in cleaned]
            target_dir = ensure_slash(original_base or fallback)
        else:                                   # NONE + override, impossible
            return unchanged
        new_slots = [s or "Image" for s in new_slots]
        return {"base": original_base, "slots": new_slots,
                "dir": target_dir, "changed": True}

    if mode == 'SUBFOLDER':
        new_base = ensure_slash(safe_join(base, safe_col))
        new_slots = cleaned
    elif mode == 'PREFIX':
        new_base = ensure_slash(base)
        new_slots = [prefix_basename(s, safe_col) for s in cleaned]
    else:                                       # NONE + override
        new_base = ensure_slash(base)
        new_slots = cleaned

    new_slots = [s or "Image" for s in new_slots]
    return {"base": new_base, "slots": new_slots, "dir": new_base, "changed": True}


def apply_node_paths(node, settings, collection_name, snap):
    """
    Push the solved paths onto a live node and VERIFY they stuck.

    Returns (target_dir_or_None, list_of_problem_strings).
    """
    problems = []

    # Resolve the attribute on the LIVE node - never trust a cached name.
    base_attr = _find_base_path_attr(node)
    base_writable = base_attr is not None

    log(f"  '{node.name}' bl_idname='{node.bl_idname}' base_attr={base_attr!r}")
    if not base_writable:
        problems.append(
            f"{node.name}: no base path attribute found "
            f"(string attrs: {dump_node_strings(node)})"
        )
        if settings.node_override_base:
            problems.append(
                f"{node.name}: cannot override base path - "
                "folding collection name into slot paths instead"
            )

    result = compute_node_paths(
        snap["base_path"], snap["slot_names"], snap["multilayer"],
        settings, collection_name, base_writable=base_writable,
    )
    if not result["changed"]:
        return None, problems

    # ---- base path ----
    if base_writable and result["base"] != snap["base_path"]:
        try:
            setattr(node, base_attr, result["base"])
        except AttributeError as e:
            problems.append(f"{node.name}: '{base_attr}' is read-only ({e})")
        except Exception as e:
            problems.append(f"{node.name}: '{base_attr}' write failed ({e})")
        else:
            try:
                current = getattr(node, base_attr)
            except Exception:
                current = None
            if current is not None and current != result["base"]:
                problems.append(
                    f"{node.name}: '{base_attr}' did not stick "
                    f"(wanted '{result['base']}', got '{current}')"
                )

    # ---- slots ----
    key = snap["slot_key"]
    if key and result["slots"]:
        slots = get_slots_by_key(node, key)
        if slots is None:
            problems.append(f"{node.name}: slot collection '{key}' missing")
        else:
            if len(slots) != len(result["slots"]):
                problems.append(f"{node.name}: slot count changed since export started")
            for slot, new_name in zip(slots, result["slots"]):
                try:
                    setattr(slot, key, new_name)
                except Exception as e:
                    problems.append(f"{node.name}: slot not writable ({e})")
                    break
                try:
                    got = getattr(slot, key)
                except Exception:
                    got = None
                if got is not None and got != new_name:
                    problems.append(
                        f"{node.name}: slot did not stick "
                        f"(wanted '{new_name}', got '{got}')"
                    )
                    break

    return result["dir"], problems


def restore_node(node, snap):
    """Put a node's base path and slot names back the way the user had them."""
    base_attr = _find_base_path_attr(node)
    if base_attr is not None:
        try:
            setattr(node, base_attr, snap["base_path"])
        except Exception as e:
            log(f"restore {base_attr} failed on '{snap['name']}': {e}")

    key = snap["slot_key"]
    if not key or not snap["slot_names"]:
        return
    slots = get_slots_by_key(node, key)
    if slots is None:
        return
    if len(slots) != len(snap["slot_names"]):
        log(f"slot count changed on '{snap['name']}' - partial restore")
    for slot, old in zip(slots, snap["slot_names"]):
        try:
            setattr(slot, key, old)
        except Exception as e:
            log(f"restore slot failed on '{snap['name']}': {e}")


def describe_node_state(node, snap):
    """One-line summary of a node's live path state, for the log."""
    _, base = _read_base_path(node)
    slots = get_slots_by_key(node, snap["slot_key"]) if snap["slot_key"] else None
    names = [getattr(s, snap["slot_key"], "") for s in slots] if slots else []
    return f"base='{base}' slots={names}"


# ============================================================
#  BOUNDS
# ============================================================

def _corners_degenerate(corners):
    """True if every bound_box corner is identical (empty / geometry-less data)."""
    first = corners[0]
    return all((c - first).length_squared < 1e-12 for c in corners[1:])


def get_collection_bounds(collection, depsgraph=None, visited=None, depth=0,
                          ignore_hidden=True):
    """
    World-space AABB of a collection, including children and collection
    instances. Objects with hide_render on are ignored - they will not appear
    in the render, so they must not influence the framing.
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
#  LAYER COLLECTION UTILITIES
# ============================================================

def collect_lc_paths(root_lc):
    paths = []
    stack = [(root_lc, tuple())]
    while stack:
        lc, path = stack.pop()
        for child in lc.children:
            p = path + (child.name,)
            paths.append(p)
            stack.append((child, p))
    return paths


def resolve_lc(view_layer, path):
    lc = view_layer.layer_collection
    for name in path:
        lc = lc.children.get(name)
        if lc is None:
            return None
    return lc


def set_exclude(view_layer, path, state):
    lc = resolve_lc(view_layer, path)
    if lc is not None and lc.exclude != state:
        try:
            lc.exclude = state
        except Exception:
            pass


def snapshot_excludes(view_layer):
    data = {}
    for p in collect_lc_paths(view_layer.layer_collection):
        lc = resolve_lc(view_layer, p)
        if lc is not None:
            data[p] = lc.exclude
    return data


def restore_excludes(view_layer, snapshot):
    # Shallow -> deep: a parent propagates to its children, so children written
    # afterwards always win. One pass is enough.
    for p in sorted(snapshot.keys(), key=len):
        set_exclude(view_layer, p, snapshot[p])


def include_all(view_layer, paths=None):
    vl_paths = paths if paths is not None else collect_lc_paths(view_layer.layer_collection)
    for p in sorted(vl_paths, key=len):
        set_exclude(view_layer, p, False)


def isolate_collection_by_exclude(view_layer, target_name, keep_names=()):
    paths = collect_lc_paths(view_layer.layer_collection)
    wanted = {target_name} | {n for n in keep_names if n}

    include = set()
    target_found = False
    for p in paths:
        if p[-1] not in wanted:
            continue
        if p[-1] == target_name:
            target_found = True
        for i in range(1, len(p) + 1):          # every ancestor
            include.add(p[:i])
        for q in paths:                         # the whole sub-tree
            if len(q) > len(p) and q[:len(p)] == p:
                include.add(q)

    if not target_found:
        return False

    # `include` is prefix-closed, so excluding the rest afterwards is safe.
    for p in sorted(include, key=len):
        set_exclude(view_layer, p, False)
    for p in sorted(paths, key=len):
        if p not in include:
            set_exclude(view_layer, p, True)
    return True


# ============================================================
#  HIDE-RENDER ISOLATION
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
    for ch in collection.children:
        objects_in_collection(ch, out, visited)
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


def isolate_collection_by_hide(scene, target_collection, keep_names=(), keep_lights=True):
    keep_objs = objects_in_collection(target_collection)
    for name in keep_names:
        c = bpy.data.collections.get(name)
        if c:
            keep_objs |= objects_in_collection(c)

    for ob in scene.objects:
        if ob.type == 'CAMERA':
            ob.hide_render = False
            continue
        if keep_lights and ob.type in {'LIGHT', 'LIGHT_PROBE'}:
            ob.hide_render = False
            continue
        ob.hide_render = (ob.name not in keep_objs)


# ============================================================
#  PROPERTIES
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
        items=[('PNG', "PNG", ""), ('JPEG', "JPEG", ""), ('OPEN_EXR', "EXR", ""),
               ('TIFF', "TIFF", ""), ('WEBP', "WebP", ""), ('TARGA', "Targa", ""),
               ('BMP', "BMP", "")],
        default='PNG',
    )
    color_mode: EnumProperty(
        name="Color",
        items=[('BW', "BW", ""), ('RGB', "RGB", ""), ('RGBA', "RGBA", "")],
        default='RGBA',
    )
    color_depth: EnumProperty(
        name="Depth",
        items=[('8', "8", ""), ('16', "16", ""), ('32', "32", "")],
        default='8',
    )
    use_transparent: BoolProperty(name="Transparent Film", default=True)

    # ---- compositor ----
    use_compositor_nodes: BoolProperty(
        name="Use File Output Nodes",
        description="Let File Output nodes write the files. Slot names become the file names",
        default=True,
    )
    node_naming: EnumProperty(
        name="Collection Goes To",
        description="How the collection name is applied to File Output nodes",
        items=[
            ('SUBFOLDER', "Subfolder",
             "base/<Collection>/  -  slot names become the file names inside"),
            ('PREFIX', "Filename Prefix",
             "base/<Collection>_<slot>  -  prepends to each slot name"),
            ('NONE', "Don't Modify",
             "Leave node paths alone (every collection overwrites the same files!)"),
        ],
        default='SUBFOLDER',
    )
    node_override_base: BoolProperty(
        name="Override Base Paths",
        description=("Replace each node's own base path with the Output Directory below. "
                     "Slot paths are also forced to be relative, otherwise an absolute "
                     "slot path would bypass the base path entirely"),
        default=False,
    )
    write_main_output: BoolProperty(
        name="Also Write Main Render",
        description="Save the Render Result to the Output Directory in addition to File Output nodes",
        default=False,
    )

    # ---- camera ----
    camera_axis: EnumProperty(
        name="View Axis",
        items=[
            ('TOP',    "Top",    "Look down -Z"),
            ('BOTTOM', "Bottom", "Look up +Z"),
            ('FRONT',  "Front",  "Look along +Y"),
            ('BACK',   "Back",   "Look along -Y"),
            ('RIGHT',  "Right",  "Look along -X"),
            ('LEFT',   "Left",   "Look along +X"),
        ],
        default='TOP',
    )
    camera_margin: FloatProperty(
        name="Camera Distance Margin",
        description="Extra distance between the camera and the bounds, in units",
        default=10.0, min=0.01, soft_max=1000.0,
    )
    auto_cleanup_camera: BoolProperty(name="Remove Camera After Export", default=True)

    # ---- padding ----
    padding_mode: EnumProperty(
        name="Padding Mode",
        items=[('PIXELS', "Pixels", ""), ('UNITS', "Units", "")],
        default='PIXELS',
    )
    padding_pixels: IntProperty(name="Padding", default=16, min=0, soft_max=512)
    padding_units: FloatProperty(name="Padding", default=0.1, min=0.0, soft_max=100.0)

    # ---- resolution ----
    pixels_per_unit: FloatProperty(
        name="Pixels / Unit", default=100.0, min=0.001, soft_max=2048.0,
    )
    resolution_multiple: IntProperty(
        name="Round To Multiple Of", default=1, min=1, soft_max=64,
    )
    square_output: BoolProperty(name="Square Output", default=False)
    min_resolution: IntProperty(name="Min Res", default=1, min=1, soft_max=8192)
    max_resolution: IntProperty(name="Max Res", description="0 = unlimited",
                                default=0, min=0, soft_max=16384)

    # ---- isolation ----
    isolation_mode: EnumProperty(
        name="Isolation",
        items=[('EXCLUDE', "Exclude Collections", ""),
               ('HIDE',    "Disable in Renders",  "")],
        default='EXCLUDE',
    )
    keep_collections: StringProperty(
        name="Always Include",
        description="Comma-separated collection names that stay visible",
        default="",
    )
    keep_lights: BoolProperty(name="Always Keep Lights", default=True)
    export_source: EnumProperty(
        name="Export",
        items=[('ALL',      "All Collections",   ""),
               ('INCLUDED', "Only Included",     ""),
               ('ACTIVE',   "Active Collection", ""),
               ('TOPLEVEL', "Top-Level Only",    "")],
        default='ALL',
    )
    skip_empty: BoolProperty(
        name="Skip Empty Collections",
        description=("Skip collections without renderable geometry. "
                     "When off they are rendered as an empty frame at the world origin"),
        default=True,
    )


# ============================================================
#  CAMERA MATH
# ============================================================

def _axis_params(axis_enum):
    """-> (offset direction, camera rotation, (horizontal axis, vertical axis))"""
    E = mathutils.Euler
    V = mathutils.Vector
    return {
        'TOP':    (V(( 0,  0,  1)), E((0.0,          0.0, 0.0)),          (0, 1)),
        'BOTTOM': (V(( 0,  0, -1)), E((radians(180), 0.0, 0.0)),          (0, 1)),
        'FRONT':  (V(( 0, -1,  0)), E((radians(90),  0.0, 0.0)),          (0, 2)),
        'BACK':   (V(( 0,  1,  0)), E((radians(90),  0.0, radians(180))), (0, 2)),
        'RIGHT':  (V(( 1,  0,  0)), E((radians(90),  0.0, radians(90))),  (1, 2)),
        'LEFT':   (V((-1,  0,  0)), E((radians(90),  0.0, radians(-90))), (1, 2)),
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

    # Order matters: square -> min -> multiple -> max -> square again, so the
    # result still satisfies every constraint simultaneously.
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
        "ortho_scale": max(width, height),   # Blender applies it to the long edge
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
#  COLLECTION GATHERING
# ============================================================

def gather_target_collections(context, settings):
    vl = context.view_layer
    root = vl.layer_collection
    result = []
    seen = set()

    def add(col):
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
            add(alc.collection)
        return result

    if settings.export_source == 'TOPLEVEL':
        for child in root.children:
            add(child.collection)
        return result

    def walk(lc, depth=0):
        if depth > 0 and not (settings.export_source == 'INCLUDED' and lc.exclude):
            add(lc.collection)
        for ch in lc.children:
            walk(ch, depth + 1)

    walk(root)
    return result


def parse_keep_names(settings):
    return tuple(n.strip() for n in settings.keep_collections.split(",") if n.strip())


def apply_image_settings(image_settings, settings):
    """Set format / colour mode / depth, clamping values the format rejects."""
    image_settings.file_format = settings.file_format
    try:
        image_settings.color_mode = settings.color_mode
    except TypeError:
        image_settings.color_mode = 'RGB'       # JPEG/BMP cannot do RGBA
    if settings.file_format in DEPTH_CAPABLE:
        depth = settings.color_depth
        if settings.file_format.startswith('OPEN_EXR') and depth == '8':
            depth = '16'                        # EXR has no 8-bit mode
        try:
            image_settings.color_depth = depth
        except TypeError:
            pass


# ============================================================
#  OPERATOR: BATCH EXPORT
# ============================================================

class BTS_OT_BatchExport(Operator):
    bl_idname = "bts.batch_export"
    bl_label = "Batch Export Collections"
    bl_description = ("Render every target collection in isolation with an "
                      "auto-fitted orthographic camera")
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        vl = context.view_layer
        settings = scene.bts_settings
        rd = scene.render
        wm = context.window_manager

        keep_names = parse_keep_names(settings)

        # ---------------- path sanity ----------------
        if settings.node_override_base and not settings.output_dir:
            self.report({'ERROR'}, "Override Base Paths is on but Base Dir is empty.")
            return {'CANCELLED'}

        if is_relative_unsaved(settings.output_dir):
            self.report({'ERROR'},
                        "Output path is relative ('//') but the .blend has never "
                        "been saved. Save the file or use an absolute path.")
            return {'CANCELLED'}

        output_dir_abs = bpy.path.abspath(settings.output_dir) if settings.output_dir else ""
        if output_dir_abs:
            try:
                os.makedirs(output_dir_abs, exist_ok=True)
            except Exception as e:
                self.report({'ERROR'}, f"Cannot create output directory: {e}")
                return {'CANCELLED'}

        targets = gather_target_collections(context, settings)
        if not targets:
            self.report({'WARNING'}, "No collections found to export.")
            return {'CANCELLED'}

        # ---------------- compositor discovery ----------------
        comp_tree, comp_is_legacy = get_compositor_tree(scene)
        node_map = collect_file_outputs(scene) if settings.use_compositor_nodes else {}
        using_nodes = bool(node_map)
        log(f"compositor tree: {comp_tree!r} (legacy={comp_is_legacy})")
        log(f"found {len(node_map)} File Output node(s); using_nodes={using_nodes}")

        node_snapshots = [snapshot_node(n, k) for k, n in node_map.items()]
        for snap in node_snapshots:
            log(f"snapshot '{snap['name']}' base_attr={snap['base_attr']!r} "
                f"base='{snap['base_path']}' slots={snap['slot_names']}")
            if snap["library"]:
                self.report({'WARNING'},
                            f"Node '{snap['name']}' lives in a linked library - "
                            "its paths cannot be overridden.")

        # ---------------- snapshots ----------------
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

        # ---------------- measure (everything visible first) ----------------
        include_all(vl, exclude_snapshot.keys())
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
                    log(f"skip (no geometry): {col.name}")
                    continue
                bounds = (zero.copy(), zero.copy())
                log(f"empty collection rendered at origin: {col.name}")
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
            # Only flip use_nodes when the LEGACY tree is the one holding our
            # nodes. Flipping it blindly can spawn a fresh default node tree
            # that replaces the compositor, so the File Output nodes never run
            # and the only files on disk stay at their old locations.
            if comp_is_legacy and orig["use_nodes"] is False:
                try:
                    scene.use_nodes = True
                    touched_use_nodes = True
                    log("legacy scene.use_nodes was OFF - enabled for the export")
                except Exception:
                    pass

        # The main Render Result needs valid image settings whenever it is
        # written to disk - in node mode as well.
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
                    if not isolate_collection_by_exclude(vl, col.name, keep_names):
                        log(f"could not isolate '{col.name}' - skipped")
                        skipped += 1
                        continue
                else:
                    include_all(vl, exclude_snapshot.keys())
                    isolate_collection_by_hide(scene, col, keep_names, settings.keep_lights)

                vl.update()

                # ---------------- File Output nodes ----------------
                if using_nodes:
                    # Re-resolve every iteration: cached node references can be
                    # invalidated by the previous render / depsgraph rebuild.
                    live = collect_file_outputs(scene)
                    for snap in node_snapshots:
                        node = live.get(snap["key"])
                        if node is None:
                            msg = f"Could not resolve File Output node '{snap['name']}'"
                            if msg not in reported_problems:
                                reported_problems.add(msg)
                                self.report({'WARNING'}, msg)
                            log(f"  MISSING node key {snap['key']}")
                            continue

                        target_dir, problems = apply_node_paths(node, settings, col.name, snap)
                        for p in problems:
                            if p not in reported_problems:
                                reported_problems.add(p)
                                self.report({'WARNING'}, p)
                            log(f"  PROBLEM {p}")
                        if target_dir:
                            ensure_dir(target_dir)
                        log(f"  node '{node.name}' {describe_node_state(node, snap)}")

                # ---------------- main render output ----------------
                if using_nodes:
                    write_still = bool(settings.write_main_output and settings.output_dir)
                else:
                    write_still = True
                if write_still:
                    rd.filepath = safe_join(settings.output_dir, safe_name)

                # ---------------- render ----------------
                try:
                    bpy.ops.render.render(write_still=write_still)
                    rendered += 1
                    log(f"{col.name}: {frame['res_x']}x{frame['res_y']} px "
                        f"(ortho {frame['ortho_scale']:.4f})")
                except Exception as e:
                    self.report({'WARNING'}, f"Render failed for '{col.name}': {e}")

        finally:
            wm.progress_end()

            # -------- restore File Output nodes --------
            if node_snapshots:
                live = collect_file_outputs(scene)
                for snap in node_snapshots:
                    node = live.get(snap["key"])
                    if node is not None:
                        restore_node(node, snap)

            # -------- restore visibility --------
            restore_hide_render(scene, hide_snapshot)
            restore_excludes(vl, exclude_snapshot)
            vl.update()

            # -------- restore render settings --------
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

            # -------- camera --------
            if settings.auto_cleanup_camera:
                remove_camera()
                scene.camera = orig["camera"]
            else:
                scene.camera = orig["camera"] if orig["camera"] else cam_obj

        self.report({'INFO'}, f"Batch export done - {rendered} rendered, {skipped} skipped.")
        return {'FINISHED'}


# ============================================================
#  OPERATOR: DRY RUN  (diagnose path problems without rendering)
# ============================================================

class BTS_OT_DryRun(Operator):
    bl_idname = "bts.dry_run"
    bl_label = "Dry Run (Print Paths)"
    bl_description = ("Print every destination path and node property to the "
                      "System Console without rendering anything")
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        settings = scene.bts_settings

        tree, legacy = get_compositor_tree(scene)
        node_map = collect_file_outputs(scene)
        targets = gather_target_collections(context, settings)

        print("=" * 68)
        print(f"[{ADDON_TAG}] DRY RUN   (Blender {bpy.app.version_string})")
        print(f"  compositor tree  : {tree!r} (legacy={legacy})")
        print(f"  use_compositing  : {getattr(scene.render, 'use_compositing', '?')}")
        print(f"  scene.use_nodes  : {getattr(scene, 'use_nodes', 'n/a')}")
        print(f"  File Output nodes: {len(node_map)}")
        print(f"  override base    : {settings.node_override_base}")
        print(f"  naming mode      : {settings.node_naming}")
        print(f"  output dir       : {settings.output_dir}")
        print(f"  collections      : {len(targets)}")

        if not node_map:
            print("  !! No File Output nodes found - standard render path will be used.")

        for key, node in node_map.items():
            multilayer = node_is_multilayer(node)
            slots, slot_key = get_node_slots(node)
            slot_names = [getattr(s, slot_key, "") for s in slots] if (slots and slot_key) else []
            fmt = getattr(node, "format", None)
            ext = EXT_BY_FORMAT.get(getattr(fmt, "file_format", ""), ".png") if fmt else ".png"
            base_attr, base_val = _read_base_path(node)

            print("-" * 68)
            print(f"  NODE {' > '.join(key)}")
            print(f"    bl_idname     : {node.bl_idname}")
            print(f"    base attr     : {base_attr!r}")
            print(f"    base value    : '{base_val}'")
            print(f"    slot attr/key : {slot_key!r}")
            print(f"    slot values   : {slot_names}")

            if base_attr is None:
                print("    !! NO BASE PATH ATTRIBUTE FOUND.")
                print(f"    !! string attrs on this node: {dump_node_strings(node)}")
                print("    !! Collection name will be folded into slot paths instead.")

            for s in slot_names:
                if s and s != make_relative_slot(s):
                    print(f"    !! slot '{s}' is absolute - it bypasses the base path. "
                          f"Will become '{make_relative_slot(s)}'.")

            for col in targets[:3]:
                r = compute_node_paths(base_val, slot_names, multilayer, settings,
                                       col.name, base_writable=base_attr is not None)
                if not r["changed"]:
                    print(f"    [{col.name}] UNCHANGED (collections will overwrite)")
                    continue
                if multilayer:
                    head, stem = split_base(r["base"])
                    print(f"    [{col.name}] -> {ensure_slash(head)}{stem}####{ext}")
                else:
                    for nm in r["slots"][:4]:
                        print(f"    [{col.name}] -> {safe_join(r['base'], nm)}####{ext}")
            if len(targets) > 3:
                print(f"    ... +{len(targets) - 3} more collections")

        print("=" * 68)
        self.report({'INFO'}, "Dry run printed to the System Console.")
        return {'FINISHED'}


# ============================================================
#  OPERATORS: PREVIEW / CLEANUP / RESTORE
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

        self.report({'INFO'},
                    f"{col.name}: {frame['res_x']}x{frame['res_y']} px, "
                    f"ortho {frame['ortho_scale']:.4f}")
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
#  UI
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

        layout.operator("bts.dry_run", icon='CONSOLE')

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

        # ---------- FILE OUTPUT NODE MODE ----------
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
            layout.prop(s, "output_dir",
                        text="Base Dir" if s.node_override_base else "Fallback Dir")

            if s.node_override_base and not s.output_dir:
                e = layout.box()
                e.alert = True
                e.label(text="Base Dir is empty!", icon='ERROR')

            layout.prop(s, "write_main_output")
            layout.prop(s, "use_transparent")

            if s.write_main_output:
                box = layout.column(align=True)
                box.prop(s, "file_format")
                box.prop(s, "color_mode")
                if s.file_format in DEPTH_CAPABLE:
                    box.prop(s, "color_depth")

            layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = s.output_dir

            layout.separator()
            layout.label(text=f"{len(nodes)} File Output node(s):", icon='NODE_COMPOSITING')

            alc = context.view_layer.active_layer_collection
            preview_name = None
            if alc and alc != context.view_layer.layer_collection:
                preview_name = alc.collection.name

            for n in nodes:
                self._draw_node_box(layout, n, s, preview_name)

        # ---------- STANDARD MODE ----------
        else:
            layout.prop(s, "output_dir")
            layout.prop(s, "file_format")
            layout.prop(s, "color_mode")
            if s.file_format in DEPTH_CAPABLE:
                layout.prop(s, "color_depth")
            layout.prop(s, "use_transparent")

            layout.operator("bts.open_output_folder", icon='FILE_FOLDER').path = s.output_dir

            if nodes:
                layout.box().label(text="File Output nodes found but disabled.", icon='INFO')

    # --------------------------------------------------------
    def _draw_node_box(self, layout, node, settings, preview_name):
        box = layout.box()
        box.use_property_split = False
        box.label(text=node.label or node.name, icon='FILE_IMAGE')

        multilayer = node_is_multilayer(node)
        base_attr, base_val = _read_base_path(node)

        if getattr(node.id_data, "library", None) is not None:
            r = box.row()
            r.alert = True
            r.label(text="Linked library node - read only", icon='LIBRARY_DATA_DIRECT')

        if base_attr is not None:
            r = box.row()
            r.enabled = not settings.node_override_base
            r.prop(node, base_attr, text="")
            if settings.node_override_base:
                box.label(text="Overridden by Base Dir above", icon='INFO')
        else:
            w = box.box()
            w.alert = True
            w.label(text="No base path property on this node!", icon='ERROR')
            w.label(text="Collection name goes into slot paths.")
            w.label(text="Run Dry Run for details.")

        fmt = getattr(node, "format", None)
        if fmt is not None:
            r = box.row(align=True)
            r.prop(fmt, "file_format", text="")
            if hasattr(fmt, "color_mode"):
                r.prop(fmt, "color_mode", text="")
            if hasattr(fmt, "color_depth") and fmt.file_format in DEPTH_CAPABLE:
                r.prop(fmt, "color_depth", text="")

        inputs = get_node_inputs(node)
        slots, slot_key = get_node_slots(node)
        slot_names = [getattr(sl, slot_key, "") for sl in slots] if (slots and slot_key) else []

        if slots is not None and slot_key and len(slots):
            box.label(text=("Layers (%d):" if multilayer else "Slots / file names (%d):")
                           % len(slots))
            cl = box.column(align=True)
            for i, slot in enumerate(slots):
                row = cl.row(align=True)
                linked = bool(inputs and i < len(inputs)
                              and getattr(inputs[i], "is_linked", False))
                row.label(text="", icon='LINKED' if linked else 'UNLINKED')
                row.prop(slot, slot_key, text="")

            if not multilayer:
                bad = [s for s in slot_names if s and s != make_relative_slot(s)]
                if bad:
                    w = box.box()
                    w.alert = True
                    w.label(text="Absolute slot path(s) bypass base path!", icon='ERROR')
                    w.label(text="They will be made relative on export.")
        elif inputs is not None:
            box.label(text=f"Inputs ({len(inputs)}):")
            cl = box.column(align=True)
            for i, inp in enumerate(inputs):
                row = cl.row(align=True)
                row.label(text="",
                          icon='LINKED' if getattr(inp, "is_linked", False) else 'UNLINKED')
                row.label(text=inp.name or f"Input {i}")
        else:
            box.label(text="No slots exposed by this node.", icon='INFO')

        # ---- preview (same solver the exporter uses) ----
        if not preview_name:
            return

        result = compute_node_paths(base_val, slot_names, multilayer, settings,
                                    preview_name, base_writable=base_attr is not None)
        ext = EXT_BY_FORMAT.get(getattr(fmt, "file_format", ""), ".png") if fmt else ".png"

        pb = box.box()
        pb.scale_y = 0.85
        pb.label(text=f"Preview - '{preview_name}'", icon='HIDE_OFF')
        if not result["changed"]:
            pb.label(text="Unmodified (collections will overwrite each other!)", icon='ERROR')

        if multilayer:
            head, stem = split_base(result["base"])
            pb.label(text=ensure_slash(head))
            pb.label(text=f"    {stem}####{ext}")
        else:
            pb.label(text=ensure_slash(result["base"] or "//"))
            shown = [n for n in result["slots"] if n]
            for nm in shown[:5]:
                pb.label(text=f"    {nm}####{ext}")
            if len(shown) > 5:
                pb.label(text=f"    ... +{len(shown) - 5} more")


class BTS_PT_Info(Panel):
    bl_label = "Info"
    bl_idname = "BTS_PT_info"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Batch Export"
    bl_parent_id = "BTS_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = context.scene.bts_settings
        vl = context.view_layer

        total = excluded = 0
        stack = [(vl.layer_collection, 0)]
        while stack:
            lc, depth = stack.pop()
            if depth > 0:
                total += 1
                if lc.exclude:
                    excluded += 1
            for ch in lc.children:
                stack.append((ch, depth + 1))

        col = layout.column(align=True)
        col.label(text=f"Collections: {total}   Excluded: {excluded}")

        pad_u = padding_in_units(s)
        col.label(text=f"Padding: {pad_u:.4f} u  /  {pad_u * s.pixels_per_unit:.0f} px")

        alc = vl.active_layer_collection
        if alc and alc != vl.layer_collection:
            box = layout.box()
            box.label(text=alc.collection.name, icon='OUTLINER_COLLECTION')
            box.operator("bts.preview_camera", text="Measure / Fit Camera",
                         icon='FILE_REFRESH')


# ============================================================
#  REGISTER
# ============================================================

classes = (
    BTS_Settings,
    BTS_OT_BatchExport,
    BTS_OT_DryRun,
    BTS_OT_PreviewCamera,
    BTS_OT_Cleanup,
    BTS_OT_RestoreCollections,
    BTS_OT_OpenOutputFolder,
    BTS_PT_MainPanel,
    BTS_PT_Source,
    BTS_PT_Camera,
    BTS_PT_Resolution,
    BTS_PT_Output,
    BTS_PT_Info,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bts_settings = PointerProperty(type=BTS_Settings)
    print(f"[{ADDON_TAG}] {ADDON_NAME} registered.")


def unregister():
    if hasattr(bpy.types.Scene, "bts_settings"):
        del bpy.types.Scene.bts_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print(f"[{ADDON_TAG}] {ADDON_NAME} unregistered.")


if __name__ == "__main__":
    register()