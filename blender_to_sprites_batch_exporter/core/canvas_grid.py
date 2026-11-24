"""Canvas grid overlay for the 3D View camera view.

The grid is a screen-space guide for the current render resolution. It is not
geometry, so it never reaches a render or an export. Cell lines snap to canvas
pixels and the step grows when the viewport is zoomed out.
"""

import math

import blf
import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

_HANDLE = None
_SHADER = None
_FAILED = False

_MIN_CELL = 12.0
_MAX_STEP = 4096
_CENTER_ARM = 10.0
_GRID_COLOR = (0.55, 0.72, 1.0, 0.28)
_FRAME_COLOR = (0.55, 0.72, 1.0, 0.7)
_CENTER_COLOR = (1.0, 0.7, 0.25, 0.85)
_LABEL_BG = (0.02, 0.03, 0.05, 0.72)
_LABEL_TEXT = (0.92, 0.95, 1.0, 0.95)


def register_canvas_grid():
    global _HANDLE
    if _HANDLE is not None:
        return
    _HANDLE = bpy.types.SpaceView3D.draw_handler_add(
        _draw, (), 'WINDOW', 'POST_PIXEL'
    )


def unregister_canvas_grid():
    global _HANDLE, _SHADER, _FAILED
    if _HANDLE is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE, 'WINDOW')
        except Exception:  # noqa: BLE001 - the session may be shutting down
            pass
        _HANDLE = None
    _SHADER = None
    _FAILED = False


def reset_failure():
    """Allow the overlay to try again after a property change."""
    global _FAILED
    _FAILED = False


def tag_redraw(context=None):
    """Redraw every 3D View after the grid toggle changes."""
    context = context if context is not None else getattr(bpy, "context", None)
    window_manager = getattr(context, "window_manager", None)
    for window in getattr(window_manager, "windows", ()) or ():
        screen = getattr(window, "screen", None)
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _draw():
    global _SHADER, _FAILED
    if _FAILED:
        return
    try:
        _draw_overlay()
    except Exception:  # noqa: BLE001 - never break the viewport
        _FAILED = True


def _draw_overlay():
    context = bpy.context
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "bts_settings", None)
    if settings is None or not bool(getattr(settings, "show_canvas_grid", False)):
        return
    space = getattr(context, "space_data", None)
    if space is None or getattr(space, "type", "") != 'VIEW_3D':
        return
    region = getattr(context, "region", None)
    region_data = getattr(context, "region_data", None)
    if region is None or region_data is None:
        return
    if getattr(region_data, "view_perspective", "") != 'CAMERA':
        return
    camera = getattr(space, "camera", None) or getattr(scene, "camera", None)
    if camera is None or camera.type != 'CAMERA' or camera.data.type != 'ORTHO':
        return
    res_x = int(getattr(scene.render, "resolution_x", 0) or 0)
    res_y = int(getattr(scene.render, "resolution_y", 0) or 0)
    if res_x <= 0 or res_y <= 0:
        return
    frame = _project_frame(region, region_data, camera, res_x, res_y)
    if frame is None:
        return
    x0, y0, x1, y1 = frame
    left = max(x0, 0.0)
    right = min(x1, float(region.width))
    bottom = max(y0, 0.0)
    top = min(y1, float(region.height))
    if right <= left or top <= bottom:
        return
    scale_x = (x1 - x0) / res_x
    scale_y = (y1 - y0) / res_y
    if scale_x <= 0.0 or scale_y <= 0.0:
        return

    step = _grid_step(min(scale_x, scale_y), res_x, res_y)
    grid = []
    _add_vertical_lines(grid, x0, scale_x, step, res_x, left, right, bottom, top)
    _add_horizontal_lines(grid, y0, scale_y, step, res_y, left, right, bottom, top)
    frame_lines = _frame_lines(x0, y0, x1, y1, left, right, bottom, top)
    center = _center_lines(x0, y0, x1, y1, left, right, bottom, top)

    shader = _shader()
    blend = gpu.state.blend_get()
    line_width = gpu.state.line_width_get()
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(1.0)
    try:
        _draw_lines(shader, grid, _GRID_COLOR)
        _draw_lines(shader, frame_lines, _FRAME_COLOR)
        _draw_lines(shader, center, _CENTER_COLOR)
        _draw_resolution(
            shader, region, res_x, res_y, right, bottom, top
        )
    finally:
        gpu.state.line_width_set(line_width)
        gpu.state.blend_set(blend)


def _shader():
    global _SHADER
    if _SHADER is None:
        _SHADER = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _SHADER


def _project_frame(region, region_data, camera, res_x, res_y):
    """Return the camera canvas rect in region pixels."""
    data = camera.data
    scale = float(getattr(data, "ortho_scale", 0.0) or 0.0)
    if scale <= 0.0:
        return None
    aspect = res_x / float(res_y)
    fit = str(getattr(data, "sensor_fit", 'AUTO') or 'AUTO')
    if fit == 'HORIZONTAL':
        width = scale
        height = scale / aspect
    elif fit == 'VERTICAL':
        height = scale
        width = scale * aspect
    elif res_x >= res_y:
        width = scale
        height = scale / aspect
    else:
        height = scale
        width = scale * aspect
    half_w = width / 2.0
    half_h = height / 2.0
    center_x = width * float(getattr(data, "shift_x", 0.0) or 0.0)
    center_y = -height * float(getattr(data, "shift_y", 0.0) or 0.0)
    matrix = camera.matrix_world
    corners = (
        matrix @ Vector((center_x - half_w, center_y - half_h, -1.0)),
        matrix @ Vector((center_x + half_w, center_y - half_h, -1.0)),
        matrix @ Vector((center_x + half_w, center_y + half_h, -1.0)),
        matrix @ Vector((center_x - half_w, center_y + half_h, -1.0)),
    )
    points = [
        location_3d_to_region_2d(region, region_data, corner) for corner in corners
    ]
    if any(point is None for point in points):
        return None
    xs = [point.x for point in points]
    ys = [point.y for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _grid_step(scale, res_x, res_y):
    step = 1
    limit = max(res_x, res_y)
    while step * scale < _MIN_CELL and step < limit:
        step *= 2
    return min(step, _MAX_STEP)


def _add_vertical_lines(
    target, x0, scale, step, res_x, left, right, bottom, top
):
    start = max(0, int(math.floor((left - x0) / scale / step)))
    end = min(res_x // step, int(math.ceil((right - x0) / scale / step)))
    for index in range(start, end + 1):
        canvas_x = index * step
        if canvas_x > res_x:
            continue
        screen_x = x0 + canvas_x * scale
        if screen_x < left or screen_x > right:
            continue
        target.extend(((screen_x, bottom), (screen_x, top)))


def _add_horizontal_lines(
    target, y0, scale, step, res_y, left, right, bottom, top
):
    start = max(0, int(math.floor((bottom - y0) / scale / step)))
    end = min(res_y // step, int(math.ceil((top - y0) / scale / step)))
    for index in range(start, end + 1):
        canvas_y = index * step
        if canvas_y > res_y:
            continue
        screen_y = y0 + canvas_y * scale
        if screen_y < bottom or screen_y > top:
            continue
        target.extend(((left, screen_y), (right, screen_y)))


def _frame_lines(x0, y0, x1, y1, left, right, bottom, top):
    lines = []
    if bottom <= y0 <= top:
        lines.extend(((left, y0), (right, y0)))
    if bottom <= y1 <= top:
        lines.extend(((left, y1), (right, y1)))
    if left <= x0 <= right:
        lines.extend(((x0, bottom), (x0, top)))
    if left <= x1 <= right:
        lines.extend(((x1, bottom), (x1, top)))
    return lines


def _center_lines(x0, y0, x1, y1, left, right, bottom, top):
    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    if not (left <= center_x <= right and bottom <= center_y <= top):
        return []
    arm_x = min(_CENTER_ARM, (x1 - x0) / 4.0)
    arm_y = min(_CENTER_ARM, (y1 - y0) / 4.0)
    return [
        (max(left, center_x - arm_x), center_y),
        (min(right, center_x + arm_x), center_y),
        (center_x, max(bottom, center_y - arm_y)),
        (center_x, min(top, center_y + arm_y)),
    ]


def _draw_lines(shader, coords, color):
    if len(coords) < 4:
        return
    batch = batch_for_shader(shader, 'LINES', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_rect(shader, x, y, width, height, color):
    coords = (
        x, y, x + width, y, x + width, y + height,
        x, y, x + width, y + height, x, y + height,
    )
    batch = batch_for_shader(shader, 'TRIS', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_resolution(shader, region, res_x, res_y, right, bottom, top):
    """Draw the canvas resolution inside the frame at its top-right."""
    text = "%dx%d" % (int(res_x), int(res_y))
    blf.size(0, 11)
    text_w, text_h = blf.dimensions(0, text)
    pad = 4.0
    box_w = float(text_w) + pad * 2.0
    box_h = float(text_h) + pad * 2.0
    x = right - box_w - 6.0
    y = top - box_h - 6.0
    x = max(2.0, min(x, float(region.width) - box_w - 2.0))
    y = max(bottom + 2.0, min(y, float(region.height) - box_h - 2.0))
    _draw_rect(shader, x, y, box_w, box_h, _LABEL_BG)
    blf.color(0, *_LABEL_TEXT)
    blf.position(0, x + pad, y + pad, 0)
    blf.draw(0, text)
