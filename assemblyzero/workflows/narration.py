"""Graph-position narration: NODE and NEXT lines at every transition (#2158).

The graph itself reports where the run is -- each node is wrapped at
graph-build time, so the position is authoritative rather than inferred
from log grepping. Lines land on the workflow's stdout, which the roll
redirects to the per-roll log and the follower streams to the operator's
console (standard 0026).

Narration must never cost a run: every failure path here degrades to
silence, and a node missing from the atlas warns once, by name, and the
roll continues.
"""

from __future__ import annotations

_warned: set[str] = set()


def _line_for(node_id: str, atlas: dict, total: int) -> list[str]:
    entry = atlas.get(node_id)
    if entry is None:
        if node_id not in _warned:
            _warned.add(node_id)
            return [f"NODE {node_id} (no atlas entry -- see #2157)"]
        return []

    ordinal = entry.get("ordinal")
    position = f"[{ordinal}/{total}] " if ordinal else ""
    lines = [f"NODE {position}{entry['title']} -- {entry['goal']}"]

    successors = entry.get("successors") or {}
    parts = []
    for successor, condition in successors.items():
        name = atlas.get(successor, {}).get("title", successor)
        parts.append(f"{name} ({condition})")
    if parts:
        lines.append(f"NEXT {' | '.join(parts)}")
    return lines


def narrated(node_id: str, fn, atlas: dict, total: int):
    """Wrap a graph node so entering it narrates its position."""

    def _wrapped(state, *args, **kwargs):
        try:
            for line in _line_for(node_id, atlas, total):
                print(line, flush=True)
        except Exception:  # noqa: BLE001 - narration never costs a run
            pass
        return fn(state, *args, **kwargs)

    _wrapped.__name__ = getattr(fn, "__name__", node_id)
    return _wrapped
