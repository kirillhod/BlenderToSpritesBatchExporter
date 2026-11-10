"""Preflight analysis, the batch job and cancellation support."""

import os
import tempfile
import time
from dataclasses import dataclass, field

import bpy
import mathutils

from .common import *  # noqa: F401,F403
from .output import *  # noqa: F401,F403
from .scene import *  # noqa: F401,F403
from .framing import *  # noqa: F401,F403
from .targets import *  # noqa: F401,F403


SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}

# Settings that define the result of an analysis. Changing any of them
# invalidates the cached result.
ANALYSIS_SETTING_ATTRS = (
    "output_dir",
    "file_format",
    "color_mode",
    "color_depth",
    "use_transparent",
    "use_compositor_nodes",
    "node_naming",
    "node_override_base",
    "write_main_output",
    "nodes_connected_only",
    "overwrite_policy",
    "camera_axis",
    "camera_margin",
    "auto_cleanup_camera",
    "padding_mode",
    "padding_pixels",
    "padding_units",
    "pixels_per_unit",
    "resolution_multiple",
    "square_output",
    "min_resolution",
    "max_resolution",
    "isolation_mode",
    "keep_collections",
    "keep_lights",
    "export_source",
    "skip_empty",
    "name_template",
)


@dataclass
class Problem:
    """One actionable preflight or job message."""

    severity: str
    code: str
    message: str
    collection: str | None = None
    fix_hint: str | None = None

    def as_text(self):
        prefix = f"[{self.severity}] {self.code}"
        if self.collection:
            prefix += f" ({self.collection})"
        text = f"{prefix}: {self.message}"
        if self.fix_hint:
            text += f" Hint: {self.fix_hint}"
        return text


class ProblemCollector:
    """Deduplicating, severity-sorted problem store."""

    def __init__(self):
        self._items = []
        self._seen = set()

    def add(self, severity, code, message, collection=None, fix_hint=None):
        problem = Problem(
            severity=severity.upper(),
            code=code,
            message=message,
            collection=collection,
            fix_hint=fix_hint,
        )
        key = (problem.severity, problem.code, problem.message, problem.collection)
        if key not in self._seen:
            self._seen.add(key)
            self._items.append(problem)
        return problem

    def extend(self, problems):
        for problem in problems:
            if isinstance(problem, Problem):
                self.add(
                    problem.severity,
                    problem.code,
                    problem.message,
                    problem.collection,
                    problem.fix_hint,
                )
            else:
                self.add(*problem)
        return self

    def items(self):
        return sorted(
            self._items,
            key=lambda problem: (
                SEVERITY_ORDER.get(problem.severity, 9),
                problem.collection or "",
                problem.code,
                problem.message,
            ),
        )

    def by_severity(self, severity):
        severity = severity.upper()
        return [problem for problem in self.items() if problem.severity == severity]

    @property
    def errors(self):
        return self.by_severity("ERROR")

    @property
    def warnings(self):
        return self.by_severity("WARNING")

    @property
    def infos(self):
        return self.by_severity("INFO")

    def counts(self):
        items = self.items()
        return {
            "ERROR": sum(1 for problem in items if problem.severity == "ERROR"),
            "WARNING": sum(1 for problem in items if problem.severity == "WARNING"),
            "INFO": sum(1 for problem in items if problem.severity == "INFO"),
        }

    def __bool__(self):
        return bool(self._items)

    def __len__(self):
        return len(self._items)


@dataclass
class Bounds:
    minimum: object
    maximum: object
    valid: bool = True


@dataclass
class FrameSpec:
    res_x: int
    res_y: int
    ortho_scale: float
    width: float
    height: float
    center: object


@dataclass
class Target:
    collection: object
    bounds: object = None
    frame: dict | None = None
    output_plan: object = None
    node_plans: list = field(default_factory=list)
    skip_reason: str = ""

    @property
    def name(self):
        return self.collection.name

    @property
    def skipped(self):
        return bool(self.skip_reason)


@dataclass
class JobConfig:
    settings: object
    resolved_layout: str = ""
    using_nodes: bool = False
    node_only: bool = False
    reachable_only: bool = True


@dataclass
class JobResult:
    rendered: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: bool = False
    duration: float = 0.0
    files: list = field(default_factory=list)
    problems: list = field(default_factory=list)

    @property
    def total(self):
        return self.rendered + self.skipped + self.failed


@dataclass
class AnalysisResult:
    targets: list
    problems: list
    main_plans: list
    node_plans: list
    main_plan_by_name: dict
    node_plans_by_collection: dict
    using_nodes: bool
    node_only: bool
    resolved_layout: str
    all_file_outputs: dict
    node_snapshots: list
    conflicts: list
    skipped: int
    token: tuple = ()

    @property
    def errors(self):
        return [problem for problem in self.problems if problem.severity == "ERROR"]

    @property
    def warnings(self):
        return [problem for problem in self.problems if problem.severity == "WARNING"]

    @property
    def infos(self):
        return [problem for problem in self.problems if problem.severity == "INFO"]

    @property
    def counts(self):
        return {
            "ERROR": len(self.errors),
            "WARNING": len(self.warnings),
            "INFO": len(self.infos),
        }


# ============================================================
# ANALYSIS CACHE
# ============================================================

_ANALYSIS_CACHE = {}


def _node_token(node):
    fmt = getattr(node, "format", None)
    items = getattr(node, "file_output_items", None) or ()
    return (
        getattr(node, "name", ""),
        getattr(node, "directory", ""),
        getattr(node, "file_name", ""),
        getattr(fmt, "file_format", "") if fmt is not None else "",
        tuple(getattr(item, "name", "") for item in items),
        node_is_linked(node),
    )


def analysis_token(context, settings, targets=None, nodes=None):
    """Return a stable tuple describing the analysis inputs."""
    scene = context.scene
    if targets is None:
        targets = gather_target_collections(context, settings)
    if nodes is None:
        nodes = collect_file_outputs(
            scene,
            reachable_only=bool(getattr(settings, "nodes_connected_only", True)),
        )
    settings_state = tuple(
        (attr, getattr(settings, attr, None)) for attr in ANALYSIS_SETTING_ATTRS
    )
    settings_state += (
        ("always_include_items",
         tuple(item.name for item in getattr(settings, "always_include_items", ()))),
    )
    node_state = tuple(
        (key, _node_token(node)) for key, node in sorted(nodes.items(), key=lambda item: item[0])
    )
    rd = scene.render
    return (
        scene.as_pointer(),
        settings_state,
        tuple(target.name for target in targets),
        node_state,
        getattr(rd, "engine", ""),
        getattr(rd, "use_compositing", None),
        getattr(scene, "frame_current", None),
        getattr(bpy.data, "filepath", ""),
    )


def clear_analysis_cache(scene=None):
    global _ANALYSIS_CACHE
    if scene is None:
        _ANALYSIS_CACHE = {}
        return
    _ANALYSIS_CACHE.pop(scene.as_pointer(), None)


def peek_cached_analysis(scene):
    """Return the cached result without scanning the scene (UI use)."""
    cached = _ANALYSIS_CACHE.get(scene.as_pointer())
    return cached[1] if cached else None


def get_cached_analysis(context, settings):
    key = context.scene.as_pointer()
    cached = _ANALYSIS_CACHE.get(key)
    if not cached:
        return None
    token, result = cached
    current = analysis_token(context, settings)
    if token != current:
        _ANALYSIS_CACHE.pop(key, None)
        return None
    return result


def analyze_scene(context, settings, use_cache=False, allow_existing=False):
    """Run preflight and optionally reuse or refresh the analysis cache."""
    migrate_settings(context, settings)
    sync_target_items(context, settings)
    if use_cache:
        cached = get_cached_analysis(context, settings)
        if cached is not None:
            return cached, True

    result = _run_preflight(context, settings, allow_existing=allow_existing)
    _ANALYSIS_CACHE[context.scene.as_pointer()] = (result.token, result)
    return result, False


# ============================================================
# PREFLIGHT
# ============================================================

def _policy_settings(settings):
    return (
        getattr(settings, "overwrite_policy", "ASK") or "ASK",
        is_background(),
    )


def preflight(context, settings, allow_existing=False):
    """Public preflight entry point."""
    return _run_preflight(context, settings, allow_existing=allow_existing)


def _run_preflight(context, settings, allow_existing=False):
    from .scene import (
        extend_keep_with_lights,
        gather_target_collections,
        include_all,
        restore_excludes,
        snapshot_excludes,
    )

    scene = context.scene
    view_layer = context.view_layer
    migrate_settings(context, settings)
    sync_target_items(context, settings)
    problems = ProblemCollector()
    targets = gather_target_collections(context, settings)
    all_file_outputs = collect_file_outputs(
        scene,
        reachable_only=bool(getattr(settings, "nodes_connected_only", True)),
    )
    using_nodes = bool(
        getattr(settings, "use_compositor_nodes", False) and all_file_outputs
    )
    node_only = bool(using_nodes and not getattr(settings, "write_main_output", False))
    active_nodes = list(all_file_outputs.values())
    resolved_layout = (
        resolve_node_layout(getattr(settings, "node_naming", "SUBFOLDER"), active_nodes)
        if using_nodes
        else ""
    )

    token = analysis_token(context, settings, targets=targets, nodes=all_file_outputs)

    if not targets:
        problems.add(
            "WARNING",
            "no_collections",
            "No collections found to export.",
            fix_hint="Change Export or include at least one collection.",
        )

    output_dir = getattr(settings, "output_dir", "")
    if not using_nodes and not output_dir:
        problems.add(
            "ERROR",
            "output_dir_empty",
            "Output Directory is empty.",
            fix_hint="Choose an output folder.",
        )
    if is_relative_unsaved(output_dir) and (not using_nodes or getattr(settings, "node_override_base", False) or getattr(settings, "write_main_output", False)):
        problems.add(
            "ERROR",
            "relative_unsaved",
            "Output path is relative ('//') but the .blend has never been saved.",
            fix_hint="Save the .blend file or use an absolute path.",
        )

    # Node settings and layout compatibility.
    for severity, message in validate_node_settings(
        scene, settings, all_file_outputs, using_nodes
    ):
        problems.add(
            severity,
            "node_settings",
            message,
            fix_hint="Fix the File Output node or disable node output.",
        )

    if using_nodes:
        if resolved_layout == "FILENAME" and len(active_nodes) != 1:
            problems.add(
                "ERROR",
                "node_layout_conflict",
                "Collection Only layout requires exactly one active File Output node.",
                fix_hint="Use Automatic, Collection Folder or Collection + Socket instead.",
            )
        if resolved_layout == "NONE" and len(targets) > 1:
            problems.add(
                "ERROR",
                "node_manual_multi_target",
                "Don't Modify is a manual single-collection mode and cannot be used "
                "for several collections.",
                fix_hint="Use Automatic, Collection Folder or Collection + Socket, "
                "or export one collection.",
            )
        if node_only:
            formats = sorted(
                {
                    node_output_format_label(node)
                    for node in active_nodes
                    if not node_is_linked(node)
                }
            )
            label = ", ".join(formats) or "EXR multilayer"
            problems.add(
                "INFO",
                "node_format",
                f"File Output nodes write {label}; the add-on image format is not used "
                "while 'Also Write Main Render' is off.",
                fix_hint="Enable 'Also Write Main Render' for PNG/JPEG/WebP sprites.",
            )
            if getattr(settings, "file_format", "") not in ("OPEN_EXR", "OPEN_EXR_MULTILAYER"):
                problems.add(
                    "WARNING",
                    "node_format_mismatch",
                    f"Selected format {settings.file_format} will not be used by "
                    "node-only export.",
                )
    elif all_file_outputs and getattr(settings, "use_compositor_nodes", False):
        problems.add(
            "WARNING",
            "nodes_disconnected",
            "File Output nodes exist but none are connected to the compositor "
            "output; the main render path will be used instead.",
            fix_hint="Connect a File Output node or disable node output.",
        )

    if not node_only:
        for severity, message in normalize_image_settings(settings)[3]:
            problems.add(
                severity,
                "image_settings",
                message,
                fix_hint="Choose a color mode and depth supported by the format.",
            )

    rd = scene.render
    disabled_state = [
        name
        for name in ("use_border", "use_crop_to_border", "use_stamp")
        if getattr(rd, name, False)
    ]
    if disabled_state:
        problems.add(
            "INFO",
            "render_state",
            "These scene settings will be disabled during export: "
            + ", ".join(disabled_state)
            + ".",
        )

    if getattr(settings, "isolation_mode", "EXCLUDE") == "HIDE":
        linked_objects = [
            ob.name
            for ob in scene.objects
            if getattr(ob, "library", None) is not None
        ]
        if linked_objects:
            preview = ", ".join(linked_objects[:5])
            if len(linked_objects) > 5:
                preview += ", ..."
            problems.add(
                "WARNING",
                "linked_isolation",
                "Disable in Renders isolation may not be able to hide linked objects: "
                + preview,
                fix_hint="Use Exclude Collections isolation.",
            )

    # Bounds measurement. It temporarily includes collections and restores them.
    exclude_snapshot = snapshot_excludes(view_layer)
    measured = []
    skipped = 0
    was_modified = False
    try:
        include_all(view_layer)
        view_layer.update()
        was_modified = True
        depsgraph = context.evaluated_depsgraph_get()
        zero = mathutils.Vector((0.0, 0.0, 0.0))
        for collection in targets:
            bounds = get_collection_bounds(collection, depsgraph)
            if bounds is None:
                if getattr(settings, "skip_empty", True):
                    skipped += 1
                    measured.append((collection, None))
                    continue
                bounds = (zero.copy(), zero.copy())
            measured.append((collection, bounds))
    except Exception as exc:  # noqa: BLE001
        problems.add(
            "ERROR",
            "bounds_failed",
            f"Could not measure collection bounds: {exc}",
        )
        measured = [(collection, None) for collection in targets]
    finally:
        if was_modified:
            restore_excludes(view_layer, exclude_snapshot)
            view_layer.update()

    policy, headless = _policy_settings(settings)
    safe_names, name_errors, name_skipped = resolve_node_safe_names(
        [collection.name for collection in targets], "OVERWRITE"
    )
    for message in name_errors:
        problems.add("ERROR", "node_name_collision", message)

    main_plans = []
    main_plan_by_name = {}
    conflicts = []
    if not node_only:
        main_plans = plan_output_paths(
            [collection.name for collection in targets], settings
        )
        main_plans, policy_errors, main_conflicts, policy_notes = apply_overwrite_policy(
            main_plans,
            policy,
            headless=headless,
            file_format=getattr(settings, "file_format", "PNG"),
            allow_existing=allow_existing,
        )
        for message in policy_errors:
            problems.add("ERROR", "overwrite", message)
        for message in policy_notes:
            problems.add("WARNING", "overwrite", message)
        conflicts.extend(main_conflicts)
        main_plan_by_name = {plan.collection: plan for plan in main_plans}

    node_plans = []
    node_plans_by_collection = {collection.name: [] for collection in targets}
    if using_nodes:
        (
            node_plans_by_collection,
            node_plans,
            node_errors,
            node_conflicts,
            node_notes,
            node_skipped,
        ) = plan_node_outputs_by_collection(
            [collection.name for collection in targets],
            resolved_layout,
            settings,
            all_file_outputs,
            safe_names=safe_names,
            policy=policy,
            headless=headless,
            allow_existing=allow_existing,
        )
        for message in node_errors:
            problems.add("ERROR", "node_overwrite", message)
        for message in node_notes:
            problems.add("WARNING", "node_overwrite", message)
        conflicts.extend(node_conflicts)
        for plan in node_plans:
            for note in plan.notes:
                if "already contains the collection token" in note:
                    problems.add(
                        "INFO",
                        "node_duplicate_token",
                        f"{plan.collection}: {note}",
                    )
        for collection_name in node_skipped:
            problems.add(
                "WARNING",
                "node_skipped",
                "Collection was skipped because a node output exists or collides.",
                collection=collection_name,
            )

    if conflicts:
        problems.add(
            "INFO",
            "overwrite_conflicts",
            f"{len(conflicts)} existing output file(s) require confirmation.",
            fix_hint="Change the overwrite policy or confirm the overwrite.",
        )

    # Build targets and apply skip reasons from plans.
    targets_by_name = {collection.name: collection for collection in targets}
    built_targets = []
    for collection, bounds in measured:
        collection_name = collection.name
        bounds_value = (
            Bounds(minimum=bounds[0], maximum=bounds[1])
            if bounds is not None
            else None
        )
        target = Target(collection=collection, bounds=bounds_value)
        plan = main_plan_by_name.get(collection_name)
        target.output_plan = plan
        target.node_plans = list(node_plans_by_collection.get(collection_name, []))
        if bounds is None and getattr(settings, "skip_empty", True):
            target.skip_reason = "no renderable geometry"
        elif plan is not None and plan.skipped:
            target.skip_reason = plan.skip_reason
        elif collection_name in (node_skipped if using_nodes else set()):
            target.skip_reason = "node output skipped"
        built_targets.append(target)

    node_snapshots = [
        snapshot_node(node, key)
        for key, node in all_file_outputs.items()
        if not snapshot_node_is_linked(node)
    ]

    # Count skipped targets. The earlier loop already counts empty collections,
    # so rebuild the count from the final targets to avoid double counting.
    skipped = sum(1 for target in built_targets if target.skipped)

    analysis = AnalysisResult(
        targets=built_targets,
        problems=problems.items(),
        main_plans=main_plans,
        node_plans=node_plans,
        main_plan_by_name=main_plan_by_name,
        node_plans_by_collection=node_plans_by_collection,
        using_nodes=using_nodes,
        node_only=node_only,
        resolved_layout=resolved_layout,
        all_file_outputs=all_file_outputs,
        node_snapshots=node_snapshots,
        conflicts=conflicts,
        skipped=skipped,
        token=token,
    )
    update_target_status(settings, analysis)
    return analysis


def snapshot_node_is_linked(node):
    """Small wrapper used by preflight and the operator."""
    return node_is_linked(node)


# ============================================================
# BATCH JOB
# ============================================================

_ACTIVE_JOB = None
_JOB_STATUS = {
    "running": False,
    "text": "",
    "current": 0,
    "total": 0,
    "rendered": 0,
    "skipped": 0,
    "failed": 0,
}


def get_job_status():
    """Return a copy of the current job status for the UI."""
    return dict(_JOB_STATUS)


def _set_job_status(**values):
    _JOB_STATUS.update(values)


def request_cancel():
    """Request cancellation of the currently running job."""
    if _ACTIVE_JOB is None:
        return False
    _ACTIVE_JOB.request_cancel()
    return True


def active_job():
    return _ACTIVE_JOB


class BatchJob:
    """Execute a preflight plan and restore the scene reliably."""

    def __init__(self, context, settings, analysis, operator=None):
        self.context = context
        self.scene = context.scene
        self.settings = settings
        self.analysis = analysis
        self.config = JobConfig(
            settings=settings,
            resolved_layout=analysis.resolved_layout,
            using_nodes=analysis.using_nodes,
            node_only=analysis.node_only,
            reachable_only=bool(getattr(settings, "nodes_connected_only", True)),
        )
        self.operator = operator
        self.cancel_requested = False
        self.result = JobResult()
        self._started = False
        self._finished = False
        self._index = 0
        self._measured = [
            target for target in analysis.targets if target.bounds is not None
        ]
        self._total = len(self._measured)
        self._problems = ProblemCollector()
        self._reported = set()
        self._node_snapshots = list(analysis.node_snapshots)
        self._exclude_snapshot = None
        self._hide_snapshot = None
        self._render_snapshot = None
        self._orig_camera = None
        self._orig_camera_owned = False
        self._cam_obj = None
        self._keep_collections = ()
        self._progress_started = False
        self._start_time = 0.0

    # --------------------------------------------------------
    def _report(self, severity, message):
        if message in self._reported:
            return
        self._reported.add(message)
        if self.operator is not None:
            self.operator.report({severity}, message)

    def request_cancel(self):
        self.cancel_requested = True

    @property
    def total(self):
        return self._total

    @property
    def index(self):
        return self._index

    @property
    def cancelled(self):
        return self.cancel_requested or self.result.cancelled

    @property
    def done(self):
        return self._index >= self._total

    # --------------------------------------------------------
    def start(self):
        """Prepare snapshots, camera and render state. Returns success."""
        global _ACTIVE_JOB
        _ACTIVE_JOB = self
        self._start_time = time.time()
        self._started = True
        _set_job_status(
            running=True,
            text="Preparing export...",
            current=0,
            total=self._total,
            rendered=0,
            skipped=0,
            failed=0,
        )
        self._problems.extend(self.analysis.problems)
        # Targets without bounds are never put into _measured. Targets skipped
        # by an overwrite policy still pass through step() and are counted there.
        self.result.skipped = sum(
            1 for target in self.analysis.targets if target.bounds is None
        )

        if self._total == 0:
            return False

        from .scene import (
            extend_keep_with_lights,
            parse_keep_collections,
            snapshot_excludes,
            snapshot_hide_render,
            snapshot_render_state,
        )

        self._exclude_snapshot = snapshot_excludes(self.context.view_layer)
        self._hide_snapshot = snapshot_hide_render(self.scene)
        self._render_snapshot = snapshot_render_state(self.scene)
        self._orig_camera = self.scene.camera
        self._orig_camera_owned = is_owned_camera(self.scene.camera)

        self._keep_collections = parse_keep_collections(self.settings)
        if (
            getattr(self.settings, "isolation_mode", "EXCLUDE") == "EXCLUDE"
            and getattr(self.settings, "keep_lights", True)
        ):
            self._keep_collections, auto_lights, risky = extend_keep_with_lights(
                self.scene, self._keep_collections
            )
            if auto_lights:
                self._report(
                    "INFO",
                    "Kept light collections: "
                    + ", ".join(collection.name for collection in auto_lights),
                )
            for collection in risky:
                self._report(
                    "WARNING",
                    f"Collection '{collection.name}' is kept for its lights but also "
                    "contains other objects; they may appear in the render.",
                )

        try:
            self._cam_obj = ensure_camera(self.scene)
            self.scene.camera = self._cam_obj
            prepare_render_state(self.scene, self.settings)
            if self.analysis.using_nodes:
                try:
                    self.scene.render.use_compositing = True
                except Exception:
                    pass
            elif self.analysis.all_file_outputs:
                try:
                    self.scene.render.use_compositing = False
                except Exception:
                    pass

            image_problems = []
            if (not self.analysis.using_nodes) or getattr(
                self.settings, "write_main_output", False
            ):
                apply_image_settings(
                    self.scene.render.image_settings, self.settings, image_problems
                )
            for severity, message in image_problems:
                self._report(severity, message)
        except Exception as exc:  # noqa: BLE001
            self._report("ERROR", f"Could not prepare render state: {exc}")
            return False

        self.context.window_manager.progress_begin(0, max(self._total, 1))
        self._progress_started = True
        return True

    # --------------------------------------------------------
    def step(self):
        """Render the next target. Returns False when the job is done."""
        if self._finished:
            return False
        if self.cancel_requested:
            self.result.cancelled = True
            return False
        if self._index >= self._total:
            return False

        target = self._measured[self._index]
        index = self._index
        self._index += 1
        _set_job_status(
            text=f"Rendering {target.name}...",
            current=index,
            total=self._total,
            rendered=self.result.rendered,
            skipped=self.result.skipped,
            failed=self.result.failed,
        )
        try:
            self.context.window_manager.progress_update(index)
            if target.skip_reason:
                self.result.skipped += 1
                return self._index < self._total

            self._render_target(target)
        except Exception as exc:  # noqa: BLE001
            self.result.failed += 1
            self._report("WARNING", f"Render failed for '{target.name}': {exc}")
        return self._index < self._total

    # --------------------------------------------------------
    def _render_target(self, target):
        scene = self.scene
        view_layer = self.context.view_layer
        settings = self.settings
        rd = scene.render
        collection = target.collection
        bounds = target.bounds
        if bounds is None:
            self.result.skipped += 1
            return

        bmin, bmax = bounds.minimum, bounds.maximum
        frame = configure_camera(self._cam_obj, bmin, bmax, settings)
        target.frame = FrameSpec(
            res_x=frame["res_x"],
            res_y=frame["res_y"],
            ortho_scale=frame["ortho_scale"],
            width=frame["width"],
            height=frame["height"],
            center=frame["center"],
        )
        item = get_target_item(settings, collection.name)
        if item is not None:
            item.size_status = f"{target.frame.res_x}x{target.frame.res_y}"
        rd.resolution_x = target.frame.res_x
        rd.resolution_y = target.frame.res_y

        hide_failures = []
        if getattr(settings, "isolation_mode", "EXCLUDE") == "EXCLUDE":
            if not isolate_collection_by_exclude(
                view_layer, collection, self._keep_collections
            ):
                self.result.skipped += 1
                return
            hide_root_objects(
                scene,
                collection,
                self._keep_collections,
                getattr(settings, "keep_lights", True),
                hide_failures,
            )
        else:
            include_all(view_layer)
            isolate_collection_by_hide(
                scene,
                collection,
                self._keep_collections,
                getattr(settings, "keep_lights", True),
                hide_failures,
            )
        for name in sorted(set(hide_failures)):
            self._problems.add(
                "WARNING",
                "hide_render_failed",
                f"Could not change hide_render for object '{name}'.",
                collection=collection.name,
            )
        view_layer.update()

        node_failed = False

        if self.analysis.using_nodes:
            live_nodes = collect_file_outputs(
                scene,
                reachable_only=bool(
                    getattr(settings, "nodes_connected_only", True)
                ),
            )
            for plan in target.node_plans:
                node = live_nodes.get(plan.node_key)
                if node is None:
                    node_failed = True
                    self._report(
                        "WARNING",
                        f"Could not resolve File Output node '{plan.node_name}'",
                    )
                    break
                if plan.library:
                    continue
                if plan.skipped:
                    self.result.skipped += 1
                    return
                ensure_dir(plan.directory)
                if not apply_node_output_plan(node, plan):
                    node_failed = True
                    self._report(
                        "WARNING",
                        f"{plan.node_name}: could not update the File Output node paths.",
                    )
                    break

        if node_failed:
            self.result.skipped += 1
            return

        write_still = (
            bool(getattr(settings, "write_main_output", False) and settings.output_dir)
            if self.analysis.using_nodes
            else True
        )
        plan = target.output_plan
        if write_still:
            if plan is not None and not plan.skipped:
                rd.filepath = plan.base_path
            else:
                rd.filepath = safe_join(
                    settings.output_dir, sanitize_path_component(collection.name)
                )

        try:
            bpy.ops.render.render(write_still=write_still)
            self.result.rendered += 1
        except Exception as exc:  # noqa: BLE001
            self.result.failed += 1
            self._report("WARNING", f"Render failed for '{collection.name}': {exc}")
            return

        if plan is not None and not plan.skipped:
            self.result.files.append(plan.path)
        for node_plan in target.node_plans:
            if not node_plan.skipped:
                self.result.files.append(node_plan.path)

    def _render_extensions(self):
        extensions = {EXT_BY_FORMAT.get(getattr(self.settings, "file_format", ""), "").lower()}
        for node in self.analysis.all_file_outputs.values():
            extensions.add(node_output_extension(node).lower())
        extensions.discard("")
        return extensions

    # --------------------------------------------------------
    def finish(self):
        """Restore all snapshots and build the result. Idempotent."""
        if self._finished:
            return self.result
        self._finished = True
        global _ACTIVE_JOB
        if self.cancel_requested:
            self.result.cancelled = True

        if self._progress_started:
            try:
                self.context.window_manager.progress_end()
            except Exception:
                pass
            self._progress_started = False

        if not self._started:
            return self.result

        restore_failures = []
        try:
            if self.analysis.using_nodes and self._node_snapshots:
                live_nodes = collect_file_outputs(
                    self.scene,
                    reachable_only=bool(
                        getattr(self.settings, "nodes_connected_only", True)
                    ),
                )
                for snap in self._node_snapshots:
                    node = live_nodes.get(snap["key"])
                    if node is not None:
                        restore_node(node, snap)

            if self._hide_snapshot is not None:
                restore_hide_render(self.scene, self._hide_snapshot, restore_failures)
            if self._exclude_snapshot is not None:
                restore_excludes(self.context.view_layer, self._exclude_snapshot)
                self.context.view_layer.update()
            if self._render_snapshot is not None:
                restore_render_state(
                    self.scene, self._render_snapshot, restore_failures
                )

            restore_cam = None if self._orig_camera_owned else self._orig_camera
            if getattr(self.settings, "auto_cleanup_camera", True):
                remove_camera(self.scene)
                try:
                    self.scene.camera = restore_cam
                except (ReferenceError, TypeError):
                    self.scene.camera = None
            else:
                try:
                    self.scene.camera = (
                        restore_cam if restore_cam is not None else self._cam_obj
                    )
                except (ReferenceError, TypeError):
                    self.scene.camera = self._cam_obj

            if getattr(self.settings, "auto_cleanup_camera", True):
                try:
                    expected_camera = (
                        restore_cam.name if restore_cam is not None else None
                    )
                except ReferenceError:
                    expected_camera = None
            else:
                try:
                    if self._orig_camera is not None:
                        expected_camera = self._orig_camera.name
                    elif self._cam_obj is not None:
                        expected_camera = self._cam_obj.name
                    else:
                        expected_camera = None
                except ReferenceError:
                    expected_camera = None

            state_issues = verify_scene_state(
                self.scene,
                self.context.view_layer,
                self._render_snapshot or {},
                self._exclude_snapshot or {},
                self._hide_snapshot or {},
                self._node_snapshots,
                reachable_only=bool(
                    getattr(self.settings, "nodes_connected_only", True)
                ),
                camera_name=expected_camera,
            )
            state_issues.extend(sorted(set(restore_failures)))
            if state_issues:
                preview = "; ".join(state_issues[:5])
                if len(state_issues) > 5:
                    preview += "; ..."
                self._report(
                    "WARNING",
                    f"Scene state verification found {len(state_issues)} mismatch(es): "
                    f"{preview}",
                )
                self._problems.add(
                    "WARNING",
                    "state_verification",
                    f"{len(state_issues)} scene state mismatch(es) after export.",
                    fix_hint=preview,
                )
        except Exception as exc:  # noqa: BLE001
            self._report("WARNING", f"Scene restore failed: {exc}")
            self._problems.add(
                "ERROR",
                "restore_failed",
                f"Scene restore failed: {exc}",
            )
        finally:
            _ACTIVE_JOB = None

        self.result.problems = self._problems.items()
        self.result.duration = time.time() - self._start_time
        report_text = format_job_report(self.result, self.analysis)
        if hasattr(self.settings, "last_report"):
            self.settings.last_report = report_text
        status_label = "Cancelled" if self.result.cancelled else "Done"
        _set_job_status(
            running=False,
            text=(
                f"{status_label}: {self.result.rendered} rendered, "
                f"{self.result.skipped} skipped, {self.result.failed} failed"
            ),
            current=self._total,
            total=self._total,
            rendered=self.result.rendered,
            skipped=self.result.skipped,
            failed=self.result.failed,
        )
        return self.result

    def run(self):
        """Synchronous execution used by background mode and scripts."""
        if self.start():
            try:
                while self.step():
                    pass
            finally:
                self.finish()
        else:
            self.finish()
        return self.result


def format_job_report(result, analysis=None):
    """Build the plain-text export report shown in the UI and log."""
    status = "CANCELLED" if result.cancelled else "FINISHED"
    lines = [
        "Blender To Sprites Batch Exporter",
        f"Status: {status}",
        f"Rendered: {result.rendered}",
        f"Skipped: {result.skipped}",
        f"Failed: {result.failed}",
        f"Duration: {result.duration:.2f} s",
    ]
    if analysis is not None:
        lines.append(f"Node layout: {analysis.resolved_layout or 'main render'}")
    lines.append("")
    lines.append("Files:")
    if result.files:
        lines.extend(f"  {path}" for path in result.files)
    else:
        lines.append("  (none)")
    if result.problems:
        lines.append("")
        lines.append("Problems:")
        lines.extend(
            f"  {problem.as_text()}" for problem in result.problems
        )
    return "\n".join(lines)


def write_job_log(settings, report_text):
    """Write the report to the temporary folder, not the sprite output."""
    directory = tempfile.gettempdir()
    try:
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "bts_export.log")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(report_text)
            handle.write("\n")
        return path
    except Exception:
        return ""
