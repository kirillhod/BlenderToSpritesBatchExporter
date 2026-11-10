"""Pure scene, path and rendering logic.

This module must not import :mod:`ui` or :mod:`operators`.
"""

import os
import time
from dataclasses import dataclass, field
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

# Names that Windows refuses to use as a file or folder name, even with an
# extension. They are prefixed with an underscore during sanitization.
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}

# Conservative limit that keeps room for Blender's frame suffix and the
# extension on all supported platforms.
MAX_OUTPUT_PATH = 255

OVERWRITE_POLICIES = ('ASK', 'ERROR', 'SKIP', 'OVERWRITE', 'SUFFIX')

# Valid color modes and depths for each image format supported by the add-on.
IMAGE_FORMAT_RULES = {
    'PNG': {'color_modes': ('BW', 'RGB', 'RGBA'), 'depths': ('8', '16')},
    'JPEG': {'color_modes': ('BW', 'RGB'), 'depths': ('8',)},
    'JPEG2000': {'color_modes': ('BW', 'RGB', 'RGBA'), 'depths': ('8', '16')},
    'OPEN_EXR': {'color_modes': ('BW', 'RGB', 'RGBA'), 'depths': ('16', '32')},
    'OPEN_EXR_MULTILAYER': {'color_modes': ('BW', 'RGB', 'RGBA'), 'depths': ('16', '32')},
    'TIFF': {'color_modes': ('BW', 'RGB', 'RGBA'), 'depths': ('8', '16', '32')},
    'BMP': {'color_modes': ('BW', 'RGB'), 'depths': ('8',)},
    'WEBP': {'color_modes': ('RGB', 'RGBA'), 'depths': ('8',)},
    'TARGA': {'color_modes': ('BW', 'RGB', 'RGBA'), 'depths': ('8',)},
}

# Render settings that must not leak into an export and must always be restored.
RENDER_STATE_ATTRS = (
    'resolution_x',
    'resolution_y',
    'resolution_percentage',
    'filepath',
    'film_transparent',
    'use_compositing',
    'use_border',
    'use_crop_to_border',
    'use_stamp',
    'use_file_extension',
    'use_stamp_note',
    'use_stamp_date',
    'use_stamp_time',
    'use_stamp_render_time',
    'use_stamp_frame',
    'use_stamp_frame_range',
    'use_stamp_frame_step',
    'use_stamp_camera',
    'use_stamp_lens',
    'use_stamp_scene',
    'use_stamp_strip_name',
    'use_stamp_marker',
    'use_stamp_filename',
    'use_stamp_sequencer_strip',
    'use_stamp_memory',
    'use_stamp_hostname',
    'use_stamp_strip_meta',
)


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


def is_background():
    """True when Blender runs without a UI (``blender -b``)."""
    app = getattr(bpy, "app", None)
    return bool(getattr(app, "background", False))



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
# OUTPUT PATH PLANNING
# ============================================================

@dataclass
class OutputPlan:
    """Resolved output path for one collection."""

    collection: str
    safe_name: str
    base_path: str
    path: str
    abs_path: str
    exists: bool = False
    skip_reason: str = ""
    collision_with: str = ""
    notes: list = field(default_factory=list)

    @property
    def skipped(self):
        return bool(self.skip_reason)


def format_extension(file_format):
    """Return the file extension (with dot) for a Blender file format."""
    return EXT_BY_FORMAT.get(file_format, '')


def sanitize_path_component(name):
    """Sanitize one path component, including Windows reserved names."""
    result = sanitize_filename(name)
    stem, dot, _ = result.rpartition('.')
    check = stem if dot else result
    if check.upper() in WINDOWS_RESERVED_NAMES:
        result = "_" + result
    result = result.rstrip(' .')
    return result or "untitled"


def build_output_path(output_dir, collection_name, file_format, template=None):
    """Build ``(base_path, path)`` for one collection.

    ``base_path`` has no extension and is passed to Blender's ``filepath``;
    ``path`` includes the extension and is used for existence checks.
    ``template`` is reserved for the naming templates of a later stage.
    """
    if template:
        component = template.replace("{collection}", str(collection_name))
        component = sanitize_path_component(component)
    else:
        component = sanitize_path_component(collection_name)
    extension = format_extension(file_format)
    base_path = safe_join(output_dir, component)

    if extension and base_path.lower().endswith(extension.lower()):
        base_path = base_path[: -len(extension)]
    path = base_path + extension

    # Keep the full path usable on Windows; shorten only the file component.
    if len(bpy.path.abspath(path)) > MAX_OUTPUT_PATH:
        excess = len(bpy.path.abspath(path)) - MAX_OUTPUT_PATH
        keep = max(8, len(component) - excess)
        component = component[:keep].rstrip(' .') or "untitled"
        base_path = safe_join(output_dir, component)
        if extension and base_path.lower().endswith(extension.lower()):
            base_path = base_path[: -len(extension)]
        path = base_path + extension

    return base_path, path


def _taken_key(path):
    return os.path.normcase(bpy.path.abspath(path))


def unique_output_path(base_path, extension, taken=None):
    """Return the first free ``base_path`` (adding ``_2``, ``_3``...) and its paths."""
    taken = taken or set()
    candidate = base_path
    index = 2
    while True:
        path = candidate + extension
        key = _taken_key(path)
        if key not in taken and not os.path.exists(bpy.path.abspath(path)):
            return candidate, path, bpy.path.abspath(path)
        candidate = f"{base_path}_{index}"
        index += 1


def plan_output_paths(collection_names, settings, taken=None):
    """Plan output paths for all collections and detect collisions.

    The returned list follows ``collection_names`` order. Collisions are
    reported on the plan of the later collection through ``collision_with``.
    """
    plans = []
    owners = {}
    taken = set(taken or ())
    extension = format_extension(settings.file_format)

    for name in collection_names:
        base_path, path = build_output_path(
            settings.output_dir, name, settings.file_format
        )
        abs_path = bpy.path.abspath(path)
        plan = OutputPlan(
            collection=name,
            safe_name=sanitize_path_component(name),
            base_path=base_path,
            path=path,
            abs_path=abs_path,
        )
        key = os.path.normcase(abs_path)
        if key in owners:
            plan.collision_with = owners[key]
        else:
            owners[key] = name
        plan.exists = bool(abs_path) and os.path.exists(abs_path)
        taken.add(key)
        plans.append(plan)
    return plans


def apply_overwrite_policy(plans, policy, headless=False, file_format=None):
    """Apply an overwrite policy to planned paths.

    Returns ``(plans, errors, conflicts, notes)``. ``errors`` is a list of
    messages that must abort the export; ``conflicts`` contains plans that
    already exist and require user confirmation for the ``ASK`` policy.
    """
    policy = (policy or 'ASK').upper()
    if policy not in OVERWRITE_POLICIES:
        policy = 'ASK'
    errors = []
    conflicts = []
    notes = []

    if headless and policy == 'ASK':
        policy = 'ERROR'
        notes.append(
            "Overwrite policy 'Ask' is not available in background mode; "
            "using 'Error'."
        )

    extension = format_extension(file_format or _plan_format(plans))
    taken = set()

    for plan in plans:
        reason = ""
        target_base = plan.base_path
        target_path = plan.path
        target_abs = plan.abs_path
        target_exists = plan.exists

        if plan.collision_with:
            if policy == 'SUFFIX':
                target_base, target_path, target_abs = unique_output_path(
                    plan.base_path, extension, taken
                )
                target_exists = False
                plan.notes.append(
                    f"Renamed to avoid a collision with '{plan.collision_with}'."
                )
            elif policy == 'SKIP':
                reason = f"name collision with '{plan.collision_with}'"
            else:
                reason = f"output path collides with '{plan.collision_with}'"

        if not reason and target_exists:
            if policy == 'ERROR':
                reason = "file already exists"
            elif policy == 'SKIP':
                reason = "file already exists"
            elif policy == 'SUFFIX':
                target_base, target_path, target_abs = unique_output_path(
                    target_base, extension, taken
                )
                target_exists = False
                plan.notes.append("Renamed because the file already exists.")
            elif policy == 'ASK':
                conflicts.append(plan)

        key = os.path.normcase(target_abs)
        if not reason and key in taken:
            reason = "output path is used twice in this export"

        plan.base_path = target_base
        plan.path = target_path
        plan.abs_path = target_abs
        plan.exists = target_exists

        if reason:
            plan.skip_reason = reason
            if policy in ('ERROR', 'ASK'):
                errors.append(f"'{plan.collection}': {reason}")
        else:
            taken.add(key)

    return plans, errors, conflicts, notes


def _plan_format(plans):
    for plan in plans:
        extension = os.path.splitext(plan.path)[1]
        for file_format, ext in EXT_BY_FORMAT.items():
            if ext == extension:
                return file_format
    return 'PNG'


def plan_node_name_collisions(collection_names):
    """Return ``(name, other)`` pairs that sanitize to the same component."""
    owners = {}
    collisions = []
    for name in collection_names:
        safe_name = sanitize_path_component(name)
        key = os.path.normcase(safe_name)
        if key in owners:
            collisions.append((name, owners[key]))
        else:
            owners[key] = name
    return collisions


def resolve_node_safe_names(collection_names, policy):
    """Resolve unique sanitized names for node-based output.

    Returns ``(mapping, errors, skipped)``. ``skipped`` contains collection
    names that cannot be written without a collision under the Skip policy.
    """
    errors = []
    skipped = set()
    used = set()
    result = {}
    for name in collection_names:
        base = sanitize_path_component(name)
        candidate = base
        if os.path.normcase(candidate) in used:
            if policy == 'SUFFIX':
                index = 2
                while os.path.normcase(f"{base}_{index}") in used:
                    index += 1
                candidate = f"{base}_{index}"
            elif policy == 'SKIP':
                skipped.add(name)
                result[name] = candidate
                continue
            else:
                errors.append(
                    f"'{name}': sanitized name '{base}' collides with another collection."
                )
                result[name] = candidate
                continue
        used.add(os.path.normcase(candidate))
        result[name] = candidate
    return result, errors, skipped


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


def node_is_linked(node):
    """Return True when the node tree comes from a linked library."""
    try:
        return getattr(node.id_data, "library", None) is not None
    except Exception:
        return False


def _reachable_node_pointers(tree, _seen_trees=None):
    """Collect pointers of nodes reachable upstream from a compositor output."""
    if tree is None:
        return set()
    if _seen_trees is None:
        _seen_trees = set()
    tree_key = tree.as_pointer()
    if tree_key in _seen_trees:
        return set()
    _seen_trees.add(tree_key)

    roots = [
        node for node in tree.nodes
        if node.bl_idname in {'CompositorNodeComposite', 'CompositorNodeViewer'}
    ]
    if not roots:
        roots = [node for node in tree.nodes if node.bl_idname == 'NodeGroupOutput']

    seen = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        key = node.as_pointer()
        if key in seen:
            continue
        seen.add(key)
        for socket in getattr(node, "inputs", ()):
            for link in getattr(socket, "links", ()):
                stack.append(link.from_node)
        sub_tree = getattr(node, "node_tree", None)
        if sub_tree is not None:
            seen |= _reachable_node_pointers(sub_tree, _seen_trees)
    return seen


def _node_has_input_links(node):
    for socket in getattr(node, "inputs", ()):
        if getattr(socket, "links", None):
            return True
    return False


def collect_file_outputs(scene, reachable_only=False):
    """Collect File Output nodes.

    With ``reachable_only`` a File Output node is kept when it is either an
    ancestor of the compositor output or receives data through an input link.
    File Output nodes are normally side branches: they are not part of the
    path to Composite, so the input-link check is what distinguishes a working
    node from a disconnected one.
    """
    root, _ = get_compositor_tree(scene)
    out = {}
    if root is None:
        return out
    reachable = _reachable_node_pointers(root) if reachable_only else None
    visited_trees = set()

    def walk(tree, prefix):
        if tree is None:
            return
        tree_key = tree.as_pointer()
        if tree_key in visited_trees:
            return
        visited_trees.add(tree_key)
        for node in tree.nodes:
            is_file_output = node.bl_idname == 'CompositorNodeOutputFile'
            if reachable is not None:
                active = (
                    node.as_pointer() in reachable
                    or _node_has_input_links(node)
                )
                if not active:
                    continue
            if is_file_output:
                out[prefix + (node.name,)] = node
            elif getattr(node, "node_tree", None) is not None:
                walk(getattr(node, "node_tree", None), prefix + (node.name,))
        visited_trees.discard(tree_key)

    walk(root, tuple())
    return out


def validate_node_settings(scene, settings, all_file_outputs, using_nodes):
    """Return ``(severity, message)`` problems for the current node setup."""
    problems = []
    if using_nodes and settings.node_override_base and not settings.output_dir:
        problems.append((
            'ERROR',
            "Override Base Paths is enabled but Output Directory is empty.",
        ))
    if using_nodes and settings.write_main_output and not settings.output_dir:
        problems.append((
            'ERROR',
            "Also Write Main Render is enabled but Output Directory is empty.",
        ))
    if not using_nodes:
        return problems

    for node in all_file_outputs.values():
        directory = getattr(node, "directory", "")
        if node_is_linked(node):
            problems.append((
                'WARNING',
                f"File Output node '{node.name}' is linked; its paths will not be changed.",
            ))
            continue
        if is_relative_unsaved(directory) and not settings.node_override_base:
            problems.append((
                'ERROR',
                f"File Output node '{node.name}' uses the relative path '//' "
                "but the .blend has never been saved.",
            ))
    return problems


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
        "file_name": getattr(node, "file_name", ""),
        "multilayer": node_is_multilayer(node),
        "slot_key": "name",
        "slot_paths": slot_paths,
        "library": getattr(node.id_data, "library", None) is not None,
    }


def apply_node_paths(node, settings, collection_name, snap, safe_name=None):
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
    safe_col = safe_name or sanitize_filename(collection_name)

    scan_dirs = []
    def add_scan_dir(d):
        if d:
            scan_dirs.append(ensure_slash(d))

    orig_head, _ = split_base(ensure_slash(original_dir or fallback))
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

    # Blender 5.2 stores the output file name separately from the directory.
    # PREFIX mode must update it, otherwise every collection writes the same
    # file name inside the shared directory.
    if mode == 'PREFIX':
        original_file = str(snap.get("file_name", "") or "")
        filename = original_file.replace("\\", "/").split("/")[-1]
        stem, ext = os.path.splitext(filename)
        if not stem or stem.lower() == "untitled":
            new_file = safe_col + ext
        else:
            new_file = f"{safe_col}_{sanitize_filename(stem)}{ext}"
        try:
            node.file_name = new_file
        except Exception as e:
            problems.append(f"{node.name}: could not write file name ({e})")
            needs_prefix_rename = True

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
    try:
        node.file_name = snap.get("file_name", "")
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


def normalize_image_settings(settings):
    """Return valid ``(format, color_mode, color_depth, problems)`` values.

    Invalid combinations are corrected instead of being silently swallowed by
    a ``TypeError`` from Blender.
    """
    problems = []
    file_format = settings.file_format
    rules = IMAGE_FORMAT_RULES.get(file_format)
    color_mode = settings.color_mode
    color_depth = settings.color_depth

    if rules is not None:
        if color_mode not in rules["color_modes"]:
            if "RGBA" in rules["color_modes"]:
                fallback = "RGBA"
            elif "RGB" in rules["color_modes"]:
                fallback = "RGB"
            else:
                fallback = rules["color_modes"][0]
            problems.append((
                'WARNING',
                f"{color_mode} is not supported by {file_format}; using {fallback}.",
            ))
            color_mode = fallback
        if color_depth not in rules["depths"]:
            fallback = "16" if "16" in rules["depths"] else rules["depths"][0]
            problems.append((
                'WARNING',
                f"{color_depth}-bit depth is not supported by {file_format}; "
                f"using {fallback}.",
            ))
            color_depth = fallback
    elif file_format not in DEPTH_CAPABLE:
        color_depth = ""

    return file_format, color_mode, color_depth, problems


def apply_image_settings(image_settings, settings, problems=None):
    """Apply validated image settings; collect warnings in ``problems``."""
    file_format, color_mode, color_depth, found = normalize_image_settings(settings)
    if problems is not None:
        problems.extend(found)
    image_settings.file_format = file_format
    try:
        image_settings.color_mode = color_mode
    except (TypeError, ValueError) as exc:
        if problems is not None:
            problems.append(('WARNING', f"Could not set color mode: {exc}"))
    if file_format in DEPTH_CAPABLE and color_depth:
        try:
            image_settings.color_depth = color_depth
        except (TypeError, ValueError) as exc:
            if problems is not None:
                problems.append(('WARNING', f"Could not set color depth: {exc}"))
