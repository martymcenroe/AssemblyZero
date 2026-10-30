"""Node narration fails loudly (ADR 0236, #3585).

``narrated()`` wraps every node of all three graphs. It used to degrade every
failure to silence: a node with no atlas entry printed a plain line once and the
run went on, a narration line that could not be built or printed was dropped
with a bare ``pass``, a convergence record that could not be written was lost,
and a call-recording context that could not be set left the node's model calls
filed under whichever node ran before it. Now a node with no atlas entry fails
the graph build, and each runtime failure alerts the operator and raises before
the node runs.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows import narration
from assemblyzero.workflows.narration import _gate_is_off, narrated

ATLAS = {
    "A_first": {
        "title": "first step",
        "ordinal": 1,
        "goal": "Do the first thing.",
        "successors": {"END": "always"},
    },
}


def test_55_a_state_that_does_not_support_in_is_an_unknown_gate(operator_alerts):
    """Compliant per the ledger: the documented 'unknown' answer, kept."""
    assert _gate_is_off("N4_human_gate_verdict", 0) is False
    assert operator_alerts == []


def test_64_a_node_with_no_atlas_entry_fails_the_graph_build(operator_alerts):
    with pytest.raises(ValueError) as excinfo:
        narrated("Z_unmapped", lambda state: state, ATLAS, 1, stage="lld")

    assert "Z_unmapped" in str(excinfo.value)
    assert "atlas" in str(excinfo.value)


def test_114_a_narration_line_that_cannot_be_built_alerts_and_raises(operator_alerts, capsys):
    broken = {"A_first": {"title": "t", "ordinal": 1}}  # no goal: KeyError
    ran = []
    wrapped = narrated("A_first", lambda state: ran.append(state), broken, 1)

    with pytest.raises(KeyError):
        wrapped({})

    assert ran == [], "the node must not run past a failed narration"
    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert "A_first" in alert["what"]
    assert "narrated" in alert["where"]
    assert "KeyError" in alert["cause"]


def test_114_a_state_that_explodes_alerts_and_raises(operator_alerts, capsys):
    class _Exploding:
        def __contains__(self, _key):
            raise RuntimeError("state is on fire")

    wrapped = narrated(
        "N4_human_gate_verdict", lambda state: state,
        {"N4_human_gate_verdict": {"title": "gate", "ordinal": 0, "goal": "g"}}, 1,
    )

    with pytest.raises(RuntimeError):
        wrapped(_Exploding())

    assert len(operator_alerts) == 1
    assert "state is on fire" in operator_alerts[0]["cause"]


def test_160_a_record_that_cannot_be_written_stops_the_node(tmp_path, operator_alerts, capsys):
    (tmp_path / "data").write_text("not a directory", encoding="utf-8")
    ran = []
    wrapped = narrated("A_first", lambda state: ran.append(state), ATLAS, 1, stage="lld")

    with pytest.raises(OSError):
        wrapped({"repo_root": str(tmp_path)})

    assert ran == []
    assert len(operator_alerts) == 1, "the convergence store alerts once; narration adds none"
    assert "convergence record" in operator_alerts[0]["what"]


def test_160_the_withdrawn_tag_is_gone():
    source = narration.__loader__.get_source(narration.__name__)
    assert "fail-open" not in source


def test_181_a_call_context_that_cannot_be_set_alerts_and_raises(monkeypatch, operator_alerts, capsys):
    from assemblyzero.core import call_recording

    def _refuse(*_args, **_kwargs):
        raise RuntimeError("recorder is broken")

    monkeypatch.setattr(call_recording, "set_context", _refuse)
    ran = []
    wrapped = narrated("A_first", lambda state: ran.append(state), ATLAS, 1, stage="lld")

    with pytest.raises(RuntimeError):
        wrapped({"audit_dir": "x"})

    assert ran == []
    assert len(operator_alerts) == 1
    alert = operator_alerts[0]
    assert "call-recording context" in alert["what"]
    assert "A_first" in alert["what"]
    assert "recorder is broken" in alert["cause"]


def test_a_healthy_node_narrates_records_and_runs(tmp_path, operator_alerts, capsys):
    wrapped = narrated("A_first", lambda state: {"ok": True}, ATLAS, 1, stage="lld")

    assert wrapped({"repo_root": str(tmp_path)}) == {"ok": True}

    assert "NODE [1/1] first step" in capsys.readouterr().out
    assert operator_alerts == []


def test_a_state_with_no_repo_root_records_nothing_and_runs(operator_alerts, capsys):
    """Kept: there is no repository to put the record in. See the docstring."""
    wrapped = narrated("A_first", lambda state: "ran", ATLAS, 1, stage="lld")

    assert wrapped({}) == "ran"
    assert operator_alerts == []
