"""Probe registry and execution utilities.

Issue #94: Lu-Tze: The Janitor
"""

from __future__ import annotations

from typing import Callable

from assemblyzero.workflows.janitor.state import ProbeResult, ProbeScope

# Type alias for probe callables
ProbeFunction = Callable[[str], ProbeResult]


def _build_registry() -> dict[ProbeScope, ProbeFunction]:
    """Build probe registry lazily to avoid circular imports."""
    from assemblyzero.workflows.janitor.probes.harvest import probe_harvest
    from assemblyzero.workflows.janitor.probes.links import probe_links
    from assemblyzero.workflows.janitor.probes.todo import probe_todo
    from assemblyzero.workflows.janitor.probes.worktrees import probe_worktrees

    return {
        "links": probe_links,
        "worktrees": probe_worktrees,
        "harvest": probe_harvest,
        "todo": probe_todo,
    }


def get_probes(scopes: list[ProbeScope]) -> list[tuple[ProbeScope, ProbeFunction]]:
    """Return probe functions for the requested scopes.

    Raises ValueError if an unknown scope is requested.
    """
    registry = _build_registry()
    result: list[tuple[ProbeScope, ProbeFunction]] = []
    for scope in scopes:
        if scope not in registry:
            raise ValueError(f"Unknown probe scope: {scope}")
        result.append((scope, registry[scope]))
    return result


def run_probe_safe(
    probe_name: ProbeScope, probe_fn: ProbeFunction, repo_root: str
) -> ProbeResult:
    """Execute a probe with crash isolation.

    If the probe raises an exception, returns a ProbeResult with
    status='error' instead of propagating the exception.
    """
    try:
        return probe_fn(repo_root)
    except Exception as e:
        return ProbeResult(
            probe=probe_name,
            status="error",
            findings=[],
            error_message=f"{type(e).__name__}: {e}",
        )