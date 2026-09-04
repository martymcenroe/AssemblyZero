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

#: Nodes that are a human checkpoint only while their gate is configured on,
#: mapped to the state key that says so. Closes #2188.
#:
#: The campaign runs every roll with these off, and a watching operator read
#: `NEXT human gate: verdict (the verdict gate is on, or a question needs a
#: human)` as "this roll might stop and wait for me". It never will: with the
#: gate off, `human_gate_verdict` auto-routes on the verdict and returns
#: without asking anything. Operator ruling, 2026-08-10: no human gates, ever.
#:
#: The edge is NOT hidden, because it is genuinely reachable -- a reviewer
#: marking a question HUMAN_REQUIRED routes here whatever the config says. What
#: was wrong is calling a pass-through a gate. Hiding a live edge would trade
#: this misreading for a worse one.
GATE_NODES: dict[str, str] = {
    "N2_human_gate_draft": "config_gates_draft",
    "N4_human_gate_verdict": "config_gates_verdict",
    "N4_human_gate": "human_gate_enabled",  # implementation_spec's own gate
}

#: What a config-dead gate actually does, said plainly.
GATE_OFF_NOTE = "GATE OFF -- passes straight through, never waits"


def _gate_is_off(node_id: str, state) -> bool:
    """True only when the state SAYS the gate is off.

    An absent key means unknown, and an unknown gate is left described as the
    atlas describes it -- announcing OFF on a run that might actually stop
    would be the same defect pointed the other way.
    """
    key = GATE_NODES.get(node_id)
    if key is None:
        return False
    try:
        if key not in state:
            return False
        return not state[key]
    except TypeError:  # a state that does not support `in`
        return False


def _line_for(node_id: str, atlas: dict, total: int, state=None) -> list[str]:
    entry = atlas.get(node_id)
    if entry is None:
        if node_id not in _warned:
            _warned.add(node_id)
            return [f"NODE {node_id} (no atlas entry -- see #2157)"]
        return []

    ordinal = entry.get("ordinal")
    position = f"[{ordinal}/{total}] " if ordinal else ""
    node_line = f"NODE {position}{entry['title']} -- {entry['goal']}"
    if state is not None and _gate_is_off(node_id, state):
        node_line += f" [{GATE_OFF_NOTE}]"
    lines = [node_line]

    successors = entry.get("successors") or {}
    parts = []
    for successor, condition in successors.items():
        name = atlas.get(successor, {}).get("title", successor)
        if state is not None and _gate_is_off(successor, state):
            # The atlas condition here reads "the verdict gate is on, or a
            # question needs a human" -- half of which cannot happen. Replace
            # it rather than append to it.
            parts.append(f"{name} ({GATE_OFF_NOTE})")
        else:
            parts.append(f"{name} ({condition})")
    if parts:
        lines.append(f"NEXT {' | '.join(parts)}")
    return lines


def narrated(node_id: str, fn, atlas: dict, total: int, stage: str = ""):
    """Wrap a graph node so entering it narrates and records its position.

    Two outputs from one wrap, deliberately. The printed lines are for a human
    watching the roll; the record is for the report (#2721), which must not have
    to parse those lines back out of a log afterwards. Wrapping here means a
    graph cannot grow a node that forgets to record, because this is already the
    one place every node announces itself.

    ``stage`` names the sub-workflow for the record. A caller that omits it
    still narrates, and the record is skipped rather than filed under a blank
    stage that would make two graphs' nodes indistinguishable.

    #2731 adds a third output from the same wrap: the call context every model
    call made inside this node is recorded against. Here for the same reason
    the position record is -- this is the one place every node announces
    itself, so a graph cannot grow a node whose calls are recorded with no
    stage, no node name and no round.
    """

    def _wrapped(state, *args, **kwargs):
        try:
            for line in _line_for(node_id, atlas, total, state):
                print(line, flush=True)
        except Exception:  # noqa: BLE001 - narration never costs a run
            pass
        if stage:
            _record_entry(node_id, atlas, total, stage, state)
            _set_call_context(node_id, stage, state)
        return fn(state, *args, **kwargs)

    _wrapped.__name__ = getattr(fn, "__name__", node_id)
    return _wrapped


def _record_entry(node_id: str, atlas: dict, total: int, stage: str, state) -> None:
    """Append this node's entry to the convergence record (#2721).

    Silent on every failure, for the same reason narration is: a run must not
    die because a diagnostic could not be written. The absence is visible at the
    other end -- the report says which source it used, so a run with no records
    reads as a run with no records and never as a run that passed.
    """
    try:
        from assemblyzero.speedrun.convergence import record_node_enter

        repo_root = state.get("repo_root", "") if hasattr(state, "get") else ""
        if not repo_root:
            return
        record_node_enter(
            repo_root,
            stage,
            node_id,
            int((atlas.get(node_id) or {}).get("ordinal", 0) or 0),
            total,
        )
    except Exception:  # noqa: BLE001 - the record never costs a run
        # fail-open: a diagnostic that can take a roll down is worse than a
        # missing diagnostic, and the missing one is reported -- the factory
        # report names its source, so a run with no records reads as a run with
        # no records rather than as a run that passed.
        return


def _set_call_context(node_id: str, stage: str, state) -> None:
    """Tell the call recorder which node the next model calls belong to (#2731).

    The audit directory comes from the state key all three workflows already
    carry, so the recording lands beside the lineage the run writes rather than
    in a new store. A node with no audit directory in state records nothing,
    which is the honest outcome: there is no run-scoped place to put it.
    """
    try:
        from assemblyzero.core.call_recording import set_context

        audit_dir = state.get("audit_dir", "") if hasattr(state, "get") else ""
        set_context(stage, node_id, str(audit_dir or ""))
    except Exception:  # noqa: BLE001 - the recording never costs a run
        # fail-open: this runs BEFORE the node does, so an exception here would
        # take down a node that had not started, to protect a diagnostic. The
        # cost of continuing is bounded and visible: calls made in this node
        # are recorded against whichever node was entered last, and the replay
        # reports the recording it read rather than assuming one exists.
        return
