"""Portable export presets stored as JSON."""

import json
import os

import bpy

from .targets import VIEW_FIELDS, active_view_axes, apply_view_migration


PRESET_VERSION = 1

PRESET_FIELDS = (
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
    "view_top",
    "view_bottom",
    "view_front",
    "view_back",
    "view_right",
    "view_left",
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
    "keep_lights",
    "export_source",
    "skip_empty",
    "name_template",
)

BUILTIN_PRESETS = {
    "4 Directions": {
        "camera_axis": "FRONT",
        "view_top": False,
        "view_bottom": False,
        "view_front": True,
        "view_back": True,
        "view_right": True,
        "view_left": True,
        "name_template": "{collection}_{axis}",
    },
    "6 Directions": {
        "camera_axis": "TOP",
        "view_top": True,
        "view_bottom": True,
        "view_front": True,
        "view_back": True,
        "view_right": True,
        "view_left": True,
        "name_template": "{collection}_{axis}",
    },
    "Pixel Art Top": {
        "camera_axis": "TOP",
        "padding_mode": "PIXELS",
        "padding_pixels": 1,
        "pixels_per_unit": 32.0,
        "resolution_multiple": 1,
        "square_output": True,
        "min_resolution": 1,
        "max_resolution": 0,
        "use_transparent": True,
    },
    "Platformer Front": {
        "camera_axis": "FRONT",
        "padding_mode": "PIXELS",
        "padding_pixels": 2,
        "pixels_per_unit": 64.0,
        "resolution_multiple": 1,
        "square_output": False,
        "min_resolution": 1,
        "max_resolution": 0,
        "use_transparent": True,
    },
    "High Resolution Top": {
        "camera_axis": "TOP",
        "padding_mode": "PIXELS",
        "padding_pixels": 8,
        "pixels_per_unit": 128.0,
        "resolution_multiple": 1,
        "square_output": False,
        "min_resolution": 1,
        "max_resolution": 0,
        "use_transparent": True,
    },
}

BUILTIN_PRESET_DESCRIPTIONS = {
    "4 Directions": "Front, back, right and left views; names include the axis.",
    "6 Directions": "All six views; names include the axis.",
    "Pixel Art Top": "Top view, 32 px per unit, 1 px padding, square sprites.",
    "Platformer Front": "Front view, 64 px per unit, 2 px padding.",
    "High Resolution Top": "Top view, 128 px per unit, 8 px padding.",
}


def builtin_preset_description(name):
    return BUILTIN_PRESET_DESCRIPTIONS.get(name, "")


def default_preset_dir():
    try:
        return bpy.utils.user_resource('CONFIG') or ""
    except Exception:
        return ""


def preset_path(name):
    directory = default_preset_dir()
    safe = "".join(
        char if char.isalnum() or char in "._- " else "_" for char in name
    ).strip() or "preset"
    return os.path.join(directory, safe + ".json")


def apply_preset(settings, values):
    """Apply known fields; return ignored keys.

    Legacy presets contain camera_axis but no view fields. They are mapped to
    one view. Presets with view fields apply camera_axis first for old readers,
    then overwrite the view set without collapsing it.
    """
    ignored = []
    view_fields = set(VIEW_FIELDS.values())
    has_views = any(key in view_fields for key in values)
    ordered = []
    if "camera_axis" in values:
        ordered.append(("camera_axis", values["camera_axis"]))
    for key, value in values.items():
        if key == "camera_axis":
            continue
        ordered.append((key, value))

    for key, value in ordered:
        if key not in PRESET_FIELDS or not hasattr(settings, key):
            ignored.append(key)
            continue
        try:
            setattr(settings, key, value)
        except (AttributeError, TypeError, ValueError):
            ignored.append(key)

    if "camera_axis" in values and not has_views:
        apply_view_migration(settings)
    return ignored


def export_preset(settings, filepath, description=""):
    description = str(
        description or getattr(settings, "preset_description", "") or ""
    ).strip()
    values = {
        key: getattr(settings, key)
        for key in PRESET_FIELDS
        if hasattr(settings, key)
    }
    views = active_view_axes(settings)
    if views:
        values["camera_axis"] = views[0]
    data = {
        "version": PRESET_VERSION,
        "description": description,
        "values": values,
    }
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    return filepath


def load_preset(filepath):
    """Return ``(values, ignored, version, description)`` or raise ValueError."""
    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Could not read preset: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Preset must contain a JSON object.")
    version = data.get("version", 0)
    if version != PRESET_VERSION:
        raise ValueError(
            f"Unsupported preset version {version}; expected {PRESET_VERSION}."
        )
    values = data.get("values")
    if not isinstance(values, dict):
        raise ValueError("Preset has no 'values' object.")
    description = str(data.get("description", "") or "").strip()
    ignored = [key for key in values if key not in PRESET_FIELDS]
    return values, ignored, version, description
