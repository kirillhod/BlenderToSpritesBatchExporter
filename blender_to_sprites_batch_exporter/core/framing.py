"""Camera framing, resolution and temporary camera ownership."""

from math import radians

import mathutils

from .common import *  # noqa: F401,F403


# ============================================================
# CAMERA MATH
# ============================================================

def axis_params(axis_enum):
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


def constrain_resolution(res_x, res_y, settings):
    """Apply square, minimum, multiple and maximum constraints once."""
    res_x = max(int(res_x), 1)
    res_y = max(int(res_y), 1)
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
    return res_x, res_y


def _axis_extents(bounds_min, bounds_max, axis, settings):
    _, _, (ax_w, ax_h) = axis_params(axis)
    pad = padding_in_units(settings)
    width = max((bounds_max[ax_w] - bounds_min[ax_w]) + pad * 2.0, 1e-6)
    height = max((bounds_max[ax_h] - bounds_min[ax_h]) + pad * 2.0, 1e-6)
    return width, height


def _frame_from_resolution(res_x, res_y, bounds_min, bounds_max, settings):
    ppu = max(settings.pixels_per_unit, 1e-6)
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


def compute_axis_frame(bounds_min, bounds_max, axis, settings):
    """Compute one axis at its own resolution."""
    width, height = _axis_extents(bounds_min, bounds_max, axis, settings)
    ppu = max(settings.pixels_per_unit, 1e-6)
    res_x = max(int(round(width * ppu)), 1)
    res_y = max(int(round(height * ppu)), 1)
    res_x, res_y = constrain_resolution(res_x, res_y, settings)
    return _frame_from_resolution(
        res_x, res_y, bounds_min, bounds_max, settings
    )


def compute_collection_frame(bounds_min, bounds_max, axes, settings):
    """Compute one canvas that fits every selected axis.

    The maximum raw resolution is taken first, then the square, minimum,
    multiple and maximum constraints are applied once. This is equivalent to
    constraining each axis and taking the maximum, but avoids rounding twice.
    """
    axes = tuple(axes)
    if not axes:
        return None
    ppu = max(settings.pixels_per_unit, 1e-6)
    raw_x = 0
    raw_y = 0
    for axis in axes:
        width, height = _axis_extents(bounds_min, bounds_max, axis, settings)
        raw_x = max(raw_x, max(int(round(width * ppu)), 1))
        raw_y = max(raw_y, max(int(round(height * ppu)), 1))
    res_x, res_y = constrain_resolution(raw_x, raw_y, settings)
    return _frame_from_resolution(
        res_x, res_y, bounds_min, bounds_max, settings
    )


def compute_frame(bounds_min, bounds_max, settings):
    """Single-axis frame for the legacy camera_axis value."""
    return compute_axis_frame(
        bounds_min, bounds_max, settings.camera_axis, settings
    )


def configure_camera_for_axis(cam_obj, bounds_min, bounds_max, axis, frame, settings):
    """Place the camera for one axis using a shared collection canvas."""
    if frame is None:
        raise ValueError("A camera frame is required")
    offset_dir, rotation, (ax_w, ax_h) = axis_params(axis)
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


def configure_camera(cam_obj, bounds_min, bounds_max, settings):
    frame = compute_frame(bounds_min, bounds_max, settings)
    return configure_camera_for_axis(
        cam_obj,
        bounds_min,
        bounds_max,
        settings.camera_axis,
        frame,
        settings,
    )


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
