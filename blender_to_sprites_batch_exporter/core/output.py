"""Output path planning, File Output nodes and overwrite policies."""

import os
import re
from dataclasses import dataclass, field

import bpy

from .common import *  # noqa: F401,F403


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


@dataclass
class NodeOutputPlan:
    """Resolved output path for one collection and one File Output node."""

    collection: str
    node_key: tuple
    node_name: str
    socket_name: str
    layout: str
    directory: str
    base_path: str
    file_name: str
    path: str
    abs_path: str
    extension: str = ".exr"
    slot_paths: list = field(default_factory=list)
    slot_key: str = "name"
    library: bool = False
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

    template = str(getattr(settings, "name_template", "{collection}") or "{collection}")
    if template.strip() == "{collection}":
        template = None
    for name in collection_names:
        base_path, path = build_output_path(
            settings.output_dir, name, settings.file_format, template=template
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


def apply_overwrite_policy(plans, policy, headless=False, file_format=None,
                           allow_existing=False):
    """Apply an overwrite policy to planned paths.

    Returns ``(plans, errors, conflicts, notes)``. ``errors`` is a list of
    messages that must abort the export; ``conflicts`` contains plans that
    already exist and require user confirmation for the ``ASK`` policy.
    ``allow_existing`` suppresses Ask conflicts after the user confirmed them.
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
            elif policy == 'ASK' and not allow_existing:
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
            elif policy == 'OVERWRITE':
                # Keep the shared candidate. The path planner reports the
                # duplicate final path so the overwrite policy can decide.
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


def node_output_extension(node):
    """Return the extension written by a File Output node."""
    fmt = getattr(node, "format", None)
    file_format = getattr(fmt, "file_format", "") if fmt is not None else ""
    return EXT_BY_FORMAT.get(file_format, ".exr")


def node_output_format_id(node):
    """Return the Blender file-format identifier written by a node."""
    if node_is_multilayer(node):
        return "OPEN_EXR_MULTILAYER"
    fmt = getattr(node, "format", None)
    file_format = getattr(fmt, "file_format", "") if fmt is not None else ""
    return file_format or "OPEN_EXR_MULTILAYER"


def node_output_format_label(node):
    """Human-readable output format of a File Output node."""
    file_format = node_output_format_id(node)
    if file_format == "OPEN_EXR_MULTILAYER":
        return "EXR multilayer"
    return file_format


def format_family(file_format):
    """Group single- and multi-layer EXR for UI comparisons."""
    value = str(file_format or "").upper()
    if value in ("OPEN_EXR", "OPEN_EXR_MULTILAYER"):
        return "EXR"
    return value


def _raw_node_file_stem(node):
    extension = node_output_extension(node).lower()
    raw = str(getattr(node, "file_name", "") or "").replace("\\", "/")
    raw = raw.split("/")[-1].strip()
    stem, ext = os.path.splitext(raw)
    if ext.lower() == extension:
        raw = stem
    if not raw or raw.lower() == "untitled":
        raw = str(getattr(node, "name", "") or "untitled")
    return raw


def _resolve_node_placeholders(name):
    """Resolve the placeholders Blender substitutes in ``node.file_name``."""
    blend_path = getattr(bpy.data, "filepath", "") or ""
    blend_name = os.path.splitext(os.path.basename(blend_path))[0] or "Unsaved"
    resolved = str(name).replace("{blend_name}", blend_name)
    try:
        frame = int(getattr(bpy.context.scene, "frame_current", 1))
    except Exception:
        frame = 1
    return re.sub(
        r"#+",
        lambda match: str(frame).zfill(len(match.group(0))),
        resolved,
    )


def node_raw_file_name(node):
    """Return the sanitized file stem to store in ``node.file_name``."""
    return sanitize_path_component(_raw_node_file_stem(node))


def node_authored_file_name(node):
    """Return the sanitized file stem as it appears on disk."""
    resolved = _resolve_node_placeholders(_raw_node_file_stem(node))
    return sanitize_path_component(resolved)


def node_socket_names(node):
    """Return the File Output socket names, never the node name or label."""
    items = getattr(node, "file_output_items", None) or ()
    names = []
    for item in items:
        name = str(getattr(item, "name", "") or "").strip()
        if name:
            names.append(name)
    return names


def node_socket_stem(node):
    """Return the sanitized socket identity used in generated file names.

    Blender 5.x stores File Output sockets in ``file_output_items``. A node
    writes one file, so several sockets are joined to keep all identities in
    the file name. The node name and label are deliberately ignored.
    """
    stems = [
        sanitize_path_component(_resolve_node_placeholders(name))
        for name in node_socket_names(node)
    ]
    stems = [stem for stem in stems if stem and stem != "untitled"]
    return "_".join(stems)


def compose_collection_socket(collection, socket_name):
    """Return ``<collection>_<socket>`` without duplicating the collection."""
    if not socket_name:
        return collection
    if _collection_token_in_name(socket_name, collection):
        return socket_name
    return f"{collection}_{socket_name}"


def node_base_dir(node, settings):
    """Return the directory a node writes to before the collection layout."""
    fallback = settings.output_dir or "//"
    if settings.node_override_base:
        return ensure_slash(fallback)
    original = str(getattr(node, "directory", "") or "")
    head, _ = split_base(ensure_slash(original or fallback))
    return ensure_slash(head or fallback)


def resolve_node_layout(layout, active_nodes):
    """Resolve ``AUTO`` and reject unknown layout names.

    ``AUTO`` always means ``PREFIX``: the file is named after the collection
    and the File Output socket. Node names and labels never take part.
    """
    layout = str(layout or "PREFIX").upper()
    if layout == "AUTO":
        return "PREFIX"
    if layout not in NODE_LAYOUTS:
        return "PREFIX"
    return layout


def _collection_token_in_name(file_name, collection):
    """True when a file stem already contains the collection identity."""
    stem = str(file_name or "").casefold()
    collection_key = str(collection or "").casefold()
    if not collection_key:
        return False
    return stem == collection_key or stem.startswith(collection_key + "_")


def plan_node_output_paths(collection_names, layout, settings, nodes, safe_names=None):
    """Plan every ``(collection, File Output node)`` output path.

    ``nodes`` is the mapping returned by :func:`collect_file_outputs`.
    In Blender 5.2 ``node.file_name`` is the output file name and
    ``file_output_items`` are the sockets. Generated names use the socket
    names; node names and labels are ignored. Layer names are never changed.
    """
    active = list(nodes.items())
    resolved = resolve_node_layout(layout, active)
    safe_names = safe_names or {}
    plans = []
    owners = {}

    for collection_name in collection_names:
        safe_col = safe_names.get(collection_name) or sanitize_path_component(
            collection_name
        )
        for key, node in active:
            raw_authored = node_raw_file_name(node)
            authored = node_authored_file_name(node)
            socket_raw = node_socket_stem(node)
            socket_count = len(node_socket_names(node))
            base_dir = node_base_dir(node, settings)
            target_dir = base_dir
            raw_name = raw_authored
            authored_name = authored
            notes = []

            if resolved == "FILENAME":
                raw_name = safe_col
                authored_name = safe_col
                notes.append("Socket names are ignored by Collection Only.")
            elif resolved == "SUBFOLDER":
                target_dir = ensure_slash(safe_join(base_dir, safe_col))
                if socket_raw:
                    raw_name = socket_raw
                    authored_name = socket_raw
                    notes.append("File name uses the File Output socket name.")
                else:
                    notes.append(
                        "File Output node has no sockets; using the node file name."
                    )
            elif resolved == "PREFIX":
                if socket_raw:
                    composed = compose_collection_socket(safe_col, socket_raw)
                    if composed == socket_raw:
                        notes.append(
                            "The socket name already contains the collection "
                            "token; it was not duplicated."
                        )
                    else:
                        notes.append("File name uses the collection and socket name.")
                    raw_name = composed
                    authored_name = composed
                else:
                    composed = compose_collection_socket(safe_col, authored)
                    notes.append(
                        "File Output node has no sockets; using the node file name."
                    )
                    raw_name = composed
                    authored_name = composed

            if socket_count > 1 and resolved in ("SUBFOLDER", "PREFIX"):
                notes.append(
                    f"The node has {socket_count} sockets; their names are joined "
                    "in the file name."
                )

            base_path = safe_join(target_dir, authored_name)
            extension = node_output_extension(node)
            path = base_path + extension
            try:
                abs_path = bpy.path.abspath(path)
            except Exception:
                abs_path = path
            try:
                exists = bool(abs_path) and os.path.exists(abs_path)
            except Exception:
                exists = False

            plan = NodeOutputPlan(
                collection=collection_name,
                node_key=key,
                node_name=getattr(node, "name", ""),
                socket_name=socket_raw,
                layout=resolved,
                directory=ensure_slash(target_dir),
                base_path=base_path,
                file_name=raw_name,
                path=path,
                abs_path=abs_path,
                extension=extension,
                slot_paths=list((snapshot_node(node, key)).get("slot_paths", [])),
                slot_key="name",
                library=node_is_linked(node),
                exists=exists,
                notes=notes,
            )
            if plan.library:
                plan.notes.append(
                    "The node lives in a linked library and will not be modified."
                )

            owner_key = os.path.normcase(abs_path)
            owner = f"{collection_name}:{plan.node_name}"
            if owner_key in owners:
                plan.collision_with = owners[owner_key]
                plan.notes.append(
                    f"Output path collides with '{plan.collision_with}'."
                )
            else:
                owners[owner_key] = owner
            plans.append(plan)
    return plans


def apply_node_output_plan(node, plan):
    """Apply a resolved node plan to a File Output node."""
    if plan is None or plan.library:
        return False
    try:
        if getattr(node, "directory", "") != plan.directory:
            node.directory = plan.directory
        if getattr(node, "file_name", "") != plan.file_name:
            node.file_name = plan.file_name
        return True
    except Exception:
        return False


def _unique_plan_path(plan, extension, taken):
    base_path, path, abs_path = unique_output_path(
        plan.base_path, extension, taken
    )
    return base_path, path, abs_path


def apply_node_overwrite_policy(plans, policy, headless=False, allow_existing=False):
    """Apply an overwrite policy to node output plans.

    Returns ``(plans, errors, conflicts, notes, skipped_collections)``.
    """
    policy = (policy or "ASK").upper()
    if policy not in OVERWRITE_POLICIES:
        policy = "ASK"
    errors = []
    conflicts = []
    notes = []
    skipped = set()
    taken = set()

    if headless and policy == "ASK":
        policy = "ERROR"
        notes.append(
            "Overwrite policy 'Ask' is not available in background mode; "
            "using 'Error'."
        )

    for plan in plans:
        reason = ""
        target_base = plan.base_path
        target_path = plan.path
        target_abs = plan.abs_path
        target_exists = plan.exists

        if plan.collision_with:
            if policy == "SUFFIX":
                target_base, target_path, target_abs = _unique_plan_path(
                    plan, plan.extension, taken
                )
                target_exists = False
                plan.notes.append(
                    f"Renamed to avoid a collision with '{plan.collision_with}'."
                )
            elif policy == "SKIP":
                reason = f"name collision with '{plan.collision_with}'"
            else:
                reason = f"output path collides with '{plan.collision_with}'"

        if not reason and target_exists:
            if policy == "ERROR":
                reason = "file already exists"
            elif policy == "SKIP":
                reason = "file already exists"
            elif policy == "SUFFIX":
                target_base, target_path, target_abs = _unique_plan_path(
                    plan, plan.extension, taken
                )
                target_exists = False
                plan.notes.append("Renamed because the file already exists.")
            elif policy == "ASK" and not allow_existing:
                conflicts.append(plan)

        key = os.path.normcase(target_abs)
        if not reason and key in taken:
            reason = "output path is used twice in this export"

        if target_base != plan.base_path:
            plan.file_name = os.path.basename(target_base)
        plan.base_path = target_base
        plan.path = target_path
        plan.abs_path = target_abs
        plan.exists = target_exists

        if reason:
            plan.skip_reason = reason
            skipped.add(plan.collection)
            if policy in ("ERROR", "ASK"):
                errors.append(
                    f"'{plan.collection}' node '{plan.node_name}': {reason}"
                )
        else:
            taken.add(key)

    return plans, errors, conflicts, notes, skipped


def plan_node_outputs_by_collection(collection_names, layout, settings, nodes,
                                    safe_names=None, policy="ASK",
                                    headless=False, allow_existing=False):
    """Plan and policy-check node outputs grouped by collection."""
    plans = plan_node_output_paths(
        collection_names, layout, settings, nodes, safe_names=safe_names
    )
    plans, errors, conflicts, notes, skipped = apply_node_overwrite_policy(
        plans, policy, headless=headless, allow_existing=allow_existing
    )
    grouped = {name: [] for name in collection_names}
    for plan in plans:
        grouped.setdefault(plan.collection, []).append(plan)
    return grouped, plans, errors, conflicts, notes, skipped


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
            "Also Save Main Render is enabled but Output Directory is empty.",
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
    # Blender 5.0+ API: file_output_items are the node sockets.
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
        "library": node_is_linked(node),
    }


def apply_node_paths(node, settings, collection_name, snap, safe_name=None):
    """Compatibility wrapper around :func:`plan_node_output_paths`.

    Updates only ``node.directory`` and ``node.file_name``. Socket names are
    read to build the file name and are never renamed.
    """
    mode = str(getattr(settings, "node_naming", "SUBFOLDER") or "SUBFOLDER")
    override = bool(getattr(settings, "node_override_base", False))
    if mode == "NONE" and not override:
        return None, [], False, []

    safe_col = safe_name or sanitize_path_component(collection_name)
    key = snap.get("key") or ("node", getattr(node, "name", ""))
    plans = plan_node_output_paths(
        [collection_name],
        mode,
        settings,
        {key: node},
        safe_names={collection_name: safe_col},
    )
    if not plans:
        return None, [], False, ["No node output plan could be created."]
    plan = plans[0]
    ok = apply_node_output_plan(node, plan)

    scan_dirs = []
    original_dir = snap.get("base_path", "")
    fallback = getattr(settings, "output_dir", "") or "//"
    if original_dir:
        head, _ = split_base(ensure_slash(original_dir))
        scan_dirs.append(ensure_slash(head or fallback))
    head, _ = split_base(plan.base_path)
    scan_dirs.append(ensure_slash(head or fallback))

    problems = []
    if not ok:
        problems.append(
            f"{plan.node_name}: could not update the File Output node paths."
        )
    return plan.directory, unique_dirs(scan_dirs), not ok, problems


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
