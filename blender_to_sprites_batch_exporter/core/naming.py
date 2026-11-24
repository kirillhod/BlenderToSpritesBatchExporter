"""Strict file-name templates for collection stems."""

import re
from dataclasses import dataclass

TOKEN_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::([0-9]*)d)?\}")
KNOWN_TOKENS = frozenset({"collection", "axis"})
ACTIVE_ORDER = ("action", "axis", "frame")
SEPARATORS = " _-."


@dataclass
class NameResult:
    """Resolved stem, the template used, and any notes or errors."""

    text: str
    template: str
    notes: tuple = ()
    errors: tuple = ()


def _active(active_dimensions):
    active = set(active_dimensions or ())
    return tuple(name for name in ACTIVE_ORDER if name in active)


def resolve_template(template, active_dimensions):
    """Append missing active tokens in the canonical action, axis, frame order."""
    template = str(template or "{collection}")
    active = _active(active_dimensions)
    present = {match.group(1) for match in TOKEN_RE.finditer(template)}
    missing = [name for name in active if name not in present]
    if not missing:
        return template, ()
    suffix = "".join("_" + "{" + name + "}" for name in missing)
    labels = ", ".join("{" + name + "}" for name in missing)
    return template + suffix, ("Added missing name token(s): %s." % labels,)


def _remove_inactive(template, active):
    """Remove known dimension tokens that are inactive, with nearby separators."""
    text = template
    active_set = set(active)
    matches = list(TOKEN_RE.finditer(template))
    for match in reversed(matches):
        name = match.group(1)
        if (
            name not in KNOWN_TOKENS
            or name not in ACTIVE_ORDER
            or name in active_set
        ):
            continue
        start, end = match.span()
        before = re.search(r"[ _\-.]*$", text[:start])
        if before and before.group(0):
            start -= len(before.group(0))
        else:
            after = re.match(r"[ _\-.]*", text[end:])
            if after:
                end += len(after.group(0))
        text = text[:start] + text[end:]
    return text


def format_name(template, context, active_dimensions):
    """Resolve a template into a stem.

    Inactive known tokens are omitted together with one adjacent separator.
    Unknown tokens and padding on string tokens are reported as errors.
    """
    template = str(template or "{collection}")
    active = _active(active_dimensions)
    resolved, notes = resolve_template(template, active)
    text = _remove_inactive(resolved, active)
    errors = []

    def replace(match):
        name = match.group(1)
        padding = match.group(2)
        if name not in KNOWN_TOKENS:
            errors.append("Unknown naming token '{%s}'." % name)
            return ""
        if padding is not None:
            errors.append(
                "Padding is only supported for integer tokens; remove it from "
                "'{%s}'." % name
            )
        return str(context.get(name, ""))

    text = TOKEN_RE.sub(replace, text)
    if not text.strip(SEPARATORS):
        tokens = sorted({match.group(1) for match in TOKEN_RE.finditer(resolved)})
        labels = ", ".join("{%s}" % name for name in tokens) or "the template"
        errors.append(
            "The name template resolves to an empty file name; check %s."
            % labels
        )
    return NameResult(
        text=text,
        template=resolved,
        notes=tuple(notes),
        errors=tuple(errors),
    )


def format_task_name(collection_name, axis, axis_count, template):
    """Format one collection and axis stem.

    The axis is active only when the collection renders more than one view.
    """
    active = ("axis",) if int(axis_count) > 1 else ()
    return format_name(
        template,
        {
            "collection": str(collection_name),
            "axis": str(axis or "").lower(),
        },
        active,
    )
