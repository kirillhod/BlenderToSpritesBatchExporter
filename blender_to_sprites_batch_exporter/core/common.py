"""Shared constants, path helpers and image format rules.

This module has no dependencies on other add-on modules.
"""

import os

import bpy


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

# Node output layouts. AUTO and FILENAME are internal in 1.4.0 and become
# user-facing choices in the 2.0.0 interface.
NODE_LAYOUTS = ('AUTO', 'FILENAME', 'SUBFOLDER', 'PREFIX', 'NONE')

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
