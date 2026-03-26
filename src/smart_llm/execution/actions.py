from __future__ import annotations

from typing import Callable

from smart_llm.models import ActionResult


def execute_action(action_fn: Callable[[], bool], action_name: str) -> ActionResult:
    """Wrap environment actions with normalized success/failure/error shape."""
    try:
        ok = bool(action_fn())
        if ok:
            return ActionResult(success=True, status="success", message=f"{action_name} succeeded", transitions=1)
        return ActionResult(success=False, status="failure", message=f"{action_name} failed", transitions=1)
    except Exception as exc:
        return ActionResult(
            success=False,
            status="error",
            message=f"{action_name} raised exception",
            error=str(exc),
            transitions=1,
        )
