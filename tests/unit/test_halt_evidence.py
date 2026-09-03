"""The halt emits its own evidence bundle (#2574).

The acceptance is fidelity to the manual digs: the bundle's facts for the
observed run shapes must match what the hand-derived forensics found —
the refusal events quoted, the byte-identical draft group named, the
preserved refs listed — and a bundle failure must never mask the halt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import assemblyzero.core.halt_evidence as he
import assemblyzero.core.resume_contract as rc
import assemblyzero.core.state_persistence as sp
from assemblyzero.core.halt_evidence import (
    build_halt_evidence,
    render_halt_evidence_md,
    write_halt_evidence,
)
from assemblyzero.core.halt_node import create_halt_node

REFUSAL = (
    "[PINNING] refused: 1 line(s) starting '```python' — locked content "
    "the verdict did not name (#2532)"
)


def _lineage(tmp_path: Path) -> Path:
    """The observed shape: four drafts, three byte-identical (#2555's
    load-bearing fact), one different."""
    audit = tmp_path / "lineage"
    audit.mkdir()
    for name in ("001-spec-draft.md", "004-spec-draft.md", "006-spec-draft.md"):
        (audit / name).write_text("# Spec\n\nsame bytes\n", encoding="utf-8")
    (audit / "002-check.json").write_text('{"passed": true}', encoding="utf-8")
    return audit


def _state(tmp_path: Path) -> dict:
    audit = _lineage(tmp_path)
    repo = tmp_path / "repo"
    runs = repo / "data" / "speedrun" / "runs"
    runs.mkdir(parents=True)
    (runs / "preserved-branches.jsonl").write_text(
        '{"at": "2026-08-27 13:01:22", "branch": '
        '"graveyard/leavings-20260827-130120", "detail": "1 file(s)", '
        '"run": "", "source": "leavings"}\n',
        encoding="utf-8",
    )
    return {
        "issue_number": 331,
        "audit_dir": str(audit),
        "repo_root": str(repo),
        "pinning_events": [REFUSAL] * 6,
        "completeness_issues": ["3 LLD pass criterion(s) have no test"],
        "review_iteration": 3,
        "max_iterations": 3,
    }


class TestTheBundle:
    def test_the_facts_match_the_manual_dig(self, tmp_path):
        evidence = build_halt_evidence(
            _state(tmp_path), "implementation_spec",
            stage="N5_review_iter3", error_message="Iteration cap: ...",
        )
        assert len(evidence["events"]["pinning_events"]) == 6
        assert len(evidence["artifacts"]["files"]) == 4
        groups = evidence["artifacts"]["identical_groups"]
        assert groups == [[
            "001-spec-draft.md", "004-spec-draft.md", "006-spec-draft.md",
        ]]
        preserved = evidence["preserved_refs_tail"]
        assert preserved[0]["branch"] == "graveyard/leavings-20260827-130120"

    def test_the_markdown_quotes_events_and_names_the_group(self, tmp_path):
        evidence = build_halt_evidence(
            _state(tmp_path), "implementation_spec",
            stage="N5_review_iter3", error_message="Iteration cap: ...",
        )
        md = render_halt_evidence_md(evidence)
        assert REFUSAL in md
        assert "Byte-identical group:" in md
        assert "3 file(s), one content" in md
        assert "Draft issue body" in md
        assert "never auto-filed" in md
        assert "graveyard/leavings-20260827-130120" in md

    def test_a_bare_state_still_builds_a_bundle(self, tmp_path):
        evidence = build_halt_evidence(
            {"issue_number": 1}, "testing", stage="N0", error_message="x",
        )
        assert evidence["artifacts"]["files"] == []
        assert evidence["preserved_refs_tail"] == []
        assert "What halted" in render_halt_evidence_md(evidence)

    def test_write_emits_both_formats(self, tmp_path):
        evidence = build_halt_evidence(
            _state(tmp_path), "implementation_spec",
            stage="N5", error_message="cap",
        )
        json_path, md_path = write_halt_evidence(evidence, tmp_path / "out")
        assert json.loads(json_path.read_text(encoding="utf-8"))["issue"] == 331
        assert md_path.read_text(encoding="utf-8").startswith("# Halt evidence")


class TestTheHaltEmitsIt:
    @pytest.fixture
    def store(self, tmp_path, monkeypatch):
        directory = tmp_path / "state"
        directory.mkdir()
        monkeypatch.setattr(rc, "STATE_DIR", directory)
        monkeypatch.setattr(sp, "STATE_DIR", directory)
        return directory

    def test_the_bundle_lands_beside_the_plan_and_in_lineage(
        self, store, tmp_path, capsys
    ):
        state = _state(tmp_path)
        state["error_message"] = "Iteration cap: 3 revision(s) ended"
        halt = create_halt_node("implementation_spec")
        result = halt(state)
        out = capsys.readouterr().out

        assert result["workflow_status"] == "halted"
        assert "halt evidence written" in out
        # #2725: the state-side copy is scoped to this halt. The state
        # directory is shared across every repo the fleet rolls, and
        # `write_halt_evidence` writes fixed filenames, so the old unscoped
        # form left ONE bundle on the whole machine -- overwritten by the next
        # halt of any repo, and by the orchestrator's own relay of this one.
        scoped = [p for p in store.iterdir() if p.is_dir()]
        assert len(scoped) == 1, f"expected one scoped bundle dir, got {scoped}"
        assert scoped[0].name.startswith("halt-implementation_spec-331-")
        assert (scoped[0] / "halt-evidence.md").exists()
        assert (scoped[0] / "halt-evidence.json").exists()
        assert not (store / "halt-evidence.json").exists(), (
            "the unscoped path is what every halt of every repo overwrote"
        )
        lineage_md = Path(state["audit_dir"]) / "halt-evidence.md"
        assert lineage_md.exists(), "the lineage carries the bundle"
        assert REFUSAL in lineage_md.read_text(encoding="utf-8")

    def test_two_workflows_halting_in_one_run_do_not_overwrite_each_other(
        self, store, tmp_path, capsys, monkeypatch
    ):
        """The measured case: run-issue4-183941's spec halt wrote a bundle with
        2 artifacts, and the orchestrator's relay of the same halt wrote one
        with 0 artifacts straight over the top of it."""
        monkeypatch.setenv("SPEEDRUN_RUN_TAG", "run-issue4-183941")
        state = _state(tmp_path)
        state["error_message"] = "Iteration cap: 3 revision(s) ended"
        create_halt_node("implementation_spec")(state)
        create_halt_node("orchestrator")(state)
        capsys.readouterr()
        names = sorted(p.name for p in store.iterdir() if p.is_dir())
        assert names == [
            "halt-implementation_spec-331-run-issue4-183941",
            "halt-orchestrator-331-run-issue4-183941",
        ]

    def test_a_bundle_failure_never_masks_the_halt(
        self, store, tmp_path, monkeypatch, capsys
    ):
        state = _state(tmp_path)
        state["error_message"] = "some halt"
        monkeypatch.setattr(
            he, "build_halt_evidence",
            lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
        )
        halt = create_halt_node("implementation_spec")
        result = halt(state)
        out = capsys.readouterr().out
        assert result["workflow_status"] == "halted"
        assert "halt evidence not written" in out
