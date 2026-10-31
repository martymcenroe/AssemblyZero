"""N1b compile_assertion_manifest and N1c manifest_gate under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md, at ``79e18ad1``. What N1b needs
and cannot get (a repo root, a declared contract, a lineage directory) halts
through one return that names the cause; the router sends it to HALT, which
alerts. A must-resolve filing that fails alerts, and the halt it reports still
stands. N1c passes through only on an absence N1b recorded.

The abstain rows (89, and the abstain half of 230) are WON'T DO: every LLD in
this repository abstains (110 of 110, counted 2026-10-30), because only the
visual-criteria shape carries a binding column. An alert or a halt there would
fire on every non-visual run. The tags are gone and the pass-through is pinned.
"""
from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    compile_manifest,
    rows_as_dicts,
)
from assemblyzero.workflows.implementation_spec.graph import (
    route_after_compile_manifest,
)

cm = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.compile_manifest"
)

GOOD_LLD = """# LLD

## Decision table — needle criteria

| ID | Criterion | Binding value (quoted) | Assertion method |
|---|---|---|---|
| N1 | Axis at value 0 | 225.0° | tip pixel classifies `#F73923` at (0.86 R, 225°); face-black at (0.86 R, 90°) |
| T1 | None-not-drawn | a None peak renders nothing | recording of samples: no telltale-family pixel present |
"""

NO_LITERAL_LLD = """# LLD

## Decision table

| ID | Criterion | Binding value (quoted) | Assertion method |
|---|---|---|---|
| B1 | Needle look | luminescent candy-apple | verify the needle looks luminescent |
"""

#: An ordinary LLD: tables, none in the criteria shape (no binding column).
ORDINARY_LLD = """# LLD

## 2. Files Changed

| File | Change Type | Description |
|---|---|---|
| src/app.py | Modify | add a flag |
"""


def _repo(tmp_path: Path, *, gate: dict | str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    if gate is not None:
        design = repo / "docs" / "design"
        design.mkdir(parents=True)
        text = gate if isinstance(gate, str) else json.dumps(gate)
        (design / "visual-gate.json").write_text(text, encoding="utf-8")
    return repo


def _state(tmp_path: Path, lld: str, **kw) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        "lld_content": lld,
        "issue_number": 332,
        "config_mock_mode": False,
        "audit_dir": str(audit),
    }
    if "repo_root" not in kw:
        state["repo_root"] = str(_repo(tmp_path))
    state.update(kw)
    return state


def _cannot_run(out: dict, capsys) -> str:
    message = out["error_message"]
    assert message.startswith("N1b assertion manifest cannot run:")
    assert "ERROR [N1b]" in capsys.readouterr().err
    assert route_after_compile_manifest(out) == "HALT"
    return message


def _recording_filer(calls: list):
    def filer(repo_root, issue, conflict, **kwargs):
        calls.append((repo_root, issue, conflict))
    return filer


# ---------------------------------------------------------------------------
# N1b: what it needs to compile
# ---------------------------------------------------------------------------


class TestTheContract:
    def test_54_n1b_without_a_repo_root_halts(self, tmp_path, capsys):
        out = cm.compile_assertion_manifest(_state(tmp_path, GOOD_LLD, repo_root=""))
        assert "repo root" in _cannot_run(out, capsys)

    def test_63_a_declared_contract_that_is_missing_halts(self, tmp_path, capsys):
        repo = _repo(tmp_path, gate={"contract": "docs/design/contract.md"})
        out = cm.compile_assertion_manifest(_state(tmp_path, GOOD_LLD, repo_root=str(repo)))
        assert "docs/design/contract.md" in _cannot_run(out, capsys)

    def test_66_a_gate_declaration_that_cannot_be_loaded_halts(self, tmp_path, capsys):
        repo = _repo(tmp_path, gate="{not json")
        out = cm.compile_assertion_manifest(_state(tmp_path, GOOD_LLD, repo_root=str(repo)))
        assert "JSONDecodeError" in _cannot_run(out, capsys)

    def test_66_a_contract_that_cannot_be_read_halts(self, tmp_path, monkeypatch, capsys):
        repo = _repo(tmp_path, gate={"contract": "docs/design/contract.md"})
        contract = repo / "docs" / "design" / "contract.md"
        contract.write_text("# Contract\n", encoding="utf-8")
        real = Path.read_text

        def read_text(self, *a, **kw):
            if self == contract:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *a, **kw)

        monkeypatch.setattr(Path, "read_text", read_text)
        out = cm.compile_assertion_manifest(_state(tmp_path, GOOD_LLD, repo_root=str(repo)))
        assert "PermissionError" in _cannot_run(out, capsys)

    def test_a_repo_that_declares_no_gate_compiles_without_a_contract(self, tmp_path):
        """Kept: no declaration, no contract, and that is an answer."""
        out = cm.compile_assertion_manifest(_state(tmp_path, GOOD_LLD))
        assert out["error_message"] == ""
        assert out["assertion_manifest_rows"]

    def test_67_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(cm._contract_text)


class TestTheLineageArtifact:
    def test_155_a_compiled_manifest_with_no_audit_dir_halts(self, tmp_path, capsys):
        state = _state(tmp_path, GOOD_LLD)
        del state["audit_dir"]
        assert "audit_dir" in _cannot_run(cm.compile_assertion_manifest(state), capsys)

    def test_155_an_audit_dir_that_does_not_exist_halts(self, tmp_path, capsys):
        state = _state(tmp_path, GOOD_LLD, audit_dir=str(tmp_path / "gone"))
        assert "gone" in _cannot_run(cm.compile_assertion_manifest(state), capsys)

    def test_a_compiled_manifest_is_persisted(self, tmp_path):
        """Kept: the manifest is a lineage artifact."""
        out = cm.compile_assertion_manifest(_state(tmp_path, GOOD_LLD))
        assert out["error_message"] == ""
        assert len(list((tmp_path / "audit").glob("*-assertion-manifest.md"))) == 1


class TestTheAbstain:
    def test_89_an_ordinary_lld_still_sits_out_and_records_why(self, tmp_path, operator_alerts):
        """WON'T DO, pinned: every non-visual LLD abstains."""
        out = cm.compile_assertion_manifest(_state(tmp_path, ORDINARY_LLD))
        assert out["error_message"] == ""
        assert out["assertion_manifest_absent"] is True
        assert out["assertion_manifest_abstained"] is True
        assert "0 in the criteria shape" in out["assertion_manifest_absence_reason"]
        assert operator_alerts == []

    def test_89_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(cm.compile_assertion_manifest)


# ---------------------------------------------------------------------------
# N1b: the must-resolve filing
# ---------------------------------------------------------------------------


class TestTheFiling:
    def test_186_a_mock_run_files_nothing_and_still_halts(self, tmp_path, capsys, operator_alerts):
        """Kept: a mock run never writes GitHub issues; the halt is unchanged."""
        out = cm.compile_assertion_manifest(
            _state(tmp_path, NO_LITERAL_LLD, config_mock_mode=True)
        )
        assert "UNCOMPILABLE" in out["error_message"]
        assert "mock mode" in capsys.readouterr().out
        assert operator_alerts == []

    def test_188_no_fail_open_tag_remains(self):
        for function in (cm._file_failures, cm.compile_assertion_manifest):
            assert "fail-open" not in inspect.getsource(function)

    def test_198_filing_with_no_repo_root_alerts(self, operator_alerts):
        calls: list = []
        cm._file_failures(
            {"issue_number": 332, "repo_root": ""},
            compile_manifest(NO_LITERAL_LLD),
            filer=_recording_filer(calls),
        )
        assert calls == []
        assert len(operator_alerts) == 1
        assert "repo_root" in operator_alerts[0]["cause"]
        assert "B1" in operator_alerts[0]["consequence"]

    def test_199_filing_with_no_issue_number_alerts(self, tmp_path, operator_alerts):
        calls: list = []
        cm._file_failures(
            {"repo_root": str(tmp_path)},
            compile_manifest(NO_LITERAL_LLD),
            filer=_recording_filer(calls),
        )
        assert calls == []
        assert len(operator_alerts) == 1
        assert "issue_number" in operator_alerts[0]["cause"]

    def test_210_a_filing_failure_alerts_and_the_halt_stands(self, tmp_path, operator_alerts):
        def broken(*_a, **_kw):
            raise OSError("no gh")

        out = cm.compile_assertion_manifest(_state(tmp_path, NO_LITERAL_LLD), filer=broken)
        assert "UNCOMPILABLE" in out["error_message"]
        assert route_after_compile_manifest(out) == "HALT"
        assert len(operator_alerts) == 1
        assert "OSError: no gh" in operator_alerts[0]["cause"]
        assert "B1" in operator_alerts[0]["consequence"]

    def test_a_filing_that_works_files_one_per_criterion(self, tmp_path, operator_alerts):
        """Kept (#2533): one must-resolve per uncompilable criterion."""
        calls: list = []
        state = _state(tmp_path, NO_LITERAL_LLD)
        cm.compile_assertion_manifest(state, filer=_recording_filer(calls))
        assert [(root, issue) for root, issue, _ in calls] == [(state["repo_root"], 332)]
        assert operator_alerts == []

    def test_211_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(cm._file_failures)


# ---------------------------------------------------------------------------
# N1c
# ---------------------------------------------------------------------------


def _compiled_rows() -> list[dict]:
    return rows_as_dicts(compile_manifest(GOOD_LLD))


class TestTheGate:
    def test_230_a_recorded_not_applicable_passes_through(self):
        """Kept: N1b recorded that the LLD has no tables."""
        out = cm.manifest_gate({
            "assertion_manifest": "", "assertion_manifest_rows": [],
            "assertion_manifest_absent": True,
            "assertion_manifest_absence_reason": "0 tables in the document",
        })
        assert out["error_message"] == ""

    def test_230_a_recorded_abstain_passes_through_and_says_so(self, capsys):
        """WON'T DO, pinned: the abstain is every non-visual run."""
        out = cm.manifest_gate({
            "assertion_manifest": "", "assertion_manifest_rows": [],
            "assertion_manifest_absent": True, "assertion_manifest_abstained": True,
            "assertion_manifest_absence_reason": "3 table(s) parsed, 0 in the criteria shape",
        })
        assert out["error_message"] == ""
        assert "ABSTAINED" in capsys.readouterr().out

    def test_230_no_manifest_and_no_recorded_absence_halts(self):
        out = cm.manifest_gate({})
        assert "ASSERTION MANIFEST GATE" in out["error_message"]
        assert "recorded no absence" in out["error_message"]
        assert route_after_compile_manifest(out) == "HALT"

    def test_231_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(cm.manifest_gate)

    def test_256_rows_without_the_criteria_list_halt(self):
        out = cm.manifest_gate({
            "assertion_manifest": "| N1.1 |",
            "assertion_manifest_rows": _compiled_rows(),
        })
        assert "ASSERTION MANIFEST GATE" in out["error_message"]
        assert "assertion_manifest_criteria" in out["error_message"]

    def test_rows_with_their_criteria_list_pass(self):
        """Kept: a clean manifest with N1b's criteria passes the gate."""
        result = compile_manifest(GOOD_LLD)
        out = cm.manifest_gate({
            "assertion_manifest": "| N1.1 |",
            "assertion_manifest_rows": rows_as_dicts(result),
            "assertion_manifest_criteria": list(result.criteria_ids),
        })
        assert out["error_message"] == ""
