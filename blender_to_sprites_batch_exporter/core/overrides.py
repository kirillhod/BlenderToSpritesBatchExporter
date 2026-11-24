"""Resolve global settings and per-collection overrides into one view."""

from dataclasses import dataclass

from .targets import (
    OVERRIDE_GROUP_FIELDS,
    active_view_axes,
    apply_override_toggle,
)


@dataclass(frozen=True)
class TargetSettings:
    """Effective framing and resolution values for one target."""

    camera_axis: str
    camera_margin: float
    padding_mode: str
    padding_pixels: int
    padding_units: float
    pixels_per_unit: float
    resolution_multiple: int
    square_output: bool
    min_resolution: int
    max_resolution: int


def _global_values(settings):
    return {
        "camera_axis": settings.camera_axis,
        "camera_margin": settings.camera_margin,
        "padding_mode": settings.padding_mode,
        "padding_pixels": settings.padding_pixels,
        "padding_units": settings.padding_units,
        "pixels_per_unit": settings.pixels_per_unit,
        "resolution_multiple": settings.resolution_multiple,
        "square_output": settings.square_output,
        "min_resolution": settings.min_resolution,
        "max_resolution": settings.max_resolution,
    }


def resolve_target_settings(settings, item):
    """Return the effective values for one target, group by group.

    An enabled but unseeded group is seeded from the globals first, so a loaded
    file never silently uses stale target values. Validation stays in preflight:
    invalid values are returned unchanged and reported with the collection name.
    """
    values = _global_values(settings)
    if item is None:
        return TargetSettings(**values)
    for group in ("framing", "resolution"):
        fields = OVERRIDE_GROUP_FIELDS[group]
        if not bool(getattr(item, "override_" + group, False)):
            continue
        apply_override_toggle(settings, item, group)
        for field in fields:
            values[field] = getattr(item, field)
    return TargetSettings(**values)


def view_axes_for(settings, item=None):
    """Active axis identifiers for one target in canonical order.

    A per-collection View override seeds from the globals on first use and then
    owns its own set. An enabled but empty override stays empty so preflight can
    report it instead of silently falling back.
    """
    if item is not None and bool(getattr(item, "override_view", False)):
        apply_override_toggle(settings, item, "view")
        return active_view_axes(item)
    return active_view_axes(settings)
