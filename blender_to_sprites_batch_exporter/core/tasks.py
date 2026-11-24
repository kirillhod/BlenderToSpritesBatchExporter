"""Expand target collections and views into render tasks."""

from dataclasses import dataclass


@dataclass
class RenderTask:
    """One render: a collection, an axis and the shared collection canvas.

    Animation fields stay optional so 3.1 can expand the same task object with
    an action and a frame without changing the still-render path.
    """

    collection: object
    axis: str
    action: str | None = None
    frame: int | None = None
    canvas: object | None = None
    output_plan: object | None = None
    node_plans: tuple = ()
    skip_reason: str = ""
    target: object | None = None


def expand_tasks(targets):
    """Return one task per target axis, or one skipped task without axes."""
    tasks = []
    for target in targets:
        collection = getattr(target, "collection", None)
        axes = getattr(target, "axes", ()) or ()
        if isinstance(axes, str):
            axes = (axes,)
        else:
            axes = tuple(axes)
        canvas = getattr(target, "frame", None)
        output_plan = getattr(target, "output_plan", None)
        node_plans = tuple(getattr(target, "node_plans", ()) or ())
        skip_reason = str(getattr(target, "skip_reason", "") or "")
        if not axes:
            tasks.append(
                RenderTask(
                    collection=collection,
                    axis="",
                    canvas=canvas,
                    output_plan=output_plan,
                    node_plans=node_plans,
                    skip_reason=skip_reason or "no views",
                    target=target,
                )
            )
            continue
        for axis in axes:
            tasks.append(
                RenderTask(
                    collection=collection,
                    axis=axis,
                    canvas=canvas,
                    output_plan=output_plan,
                    node_plans=node_plans,
                    skip_reason=skip_reason,
                    target=target,
                )
            )
    return tasks
