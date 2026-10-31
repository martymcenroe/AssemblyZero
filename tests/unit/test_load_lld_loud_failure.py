"""N0 stops on every input it cannot build from, and says why (#3585, ADR 0236).

Ledger 0908 rows for ``assemblyzero/workflows/testing/nodes/load_lld.py``. Each
test is named for the ledger line it settles (line numbers from commit
79e18ad1). Rows the ledger found compliant are pinned so they stay so.

N0 used to carry on past a spec that was not approved, an LLD it could not
read, a test plan it could not find, an empty requirement set and a missing
files table, each with a WARN line or nothing, and the run spent its reviews
and its implementation budget before a later gate (or nothing) stopped it.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest

# The package re-exports the node FUNCTION under the module's name, so the
# module itself is fetched by its dotted path.
mod = importlib.import_module("assemblyzero.workflows.testing.nodes.load_lld")

SPEC = """# 42 - Widget

**Status:** APPROVED

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/widget.py` | Add | The widget |

## 3. Requirements

1. REQ-1: The widget spins when asked to.

## 10. Test Plan

### test_widget_spins
Verify that the widget spins when asked to.
Requirement: REQ-1
"""


def _spec(tmp_path: Path, text: str = SPEC) -> Path:
    path = tmp_path / "spec-42.md"
    path.write_text(text, encoding="utf-8")
    return path


def _state(tmp_path: Path, spec: Path) -> dict:
    return {"issue_number": 42, "repo_root": str(tmp_path), "lld_path": str(spec)}


def _without(text: str, start: str, end: str) -> str:
    """``text`` with the block from ``start`` up to ``end`` removed."""
    head, _, rest = text.partition(start)
    _, _, tail = rest.partition(end)
    return head + end + tail


def test_a_good_spec_loads(tmp_path):
    """The control: everything the tests below remove is present here."""
    result = mod.load_lld(_state(tmp_path, _spec(tmp_path)))
    assert result["error_message"] == ""
    assert result["files_to_modify"][0]["path"] == "src/widget.py"
    assert result["requirements"]
    assert result["test_scenarios"]


# ---------------------------------------------------------------- line 202


def test_202_an_unparseable_section_10_is_marked_not_hidden():
    suite = mod.extract_spec_test_functions("# Spec\n\nno test section here\n" * 5)
    assert suite["functions"] == []
    assert "Expected: ## 10. Test Mapping" in suite["error"]


def test_202_a_legacy_section_9_is_marked():
    suite = mod.extract_spec_test_functions("# Spec\n\n## 9. Test Plan\n\nrows\n")
    assert "Legacy Section 9" in suite["error"]


def test_202_a_section_10_without_functions_is_a_quiet_answer():
    """No executable functions is the table path's signal, not a failure."""
    suite = mod.extract_spec_test_functions(SPEC)
    assert suite["functions"] == []
    assert "error" not in suite


def test_202_the_structure_rule_has_one_reason_source():
    """validate_spec_structure raises exactly what spec_structure_error says."""
    for text in ("no section", "## 9. Test Plan\n", SPEC):
        reason = mod.spec_structure_error(text)
        if reason:
            with pytest.raises(mod.WorkflowParsingError, match=reason[:20]):
                mod.validate_spec_structure(text)
        else:
            mod.validate_spec_structure(text)


# ------------------------------------------------------------ lines 324, 325


def test_324_a_rebuild_that_raises_is_loud_and_raised(tmp_path, monkeypatch, capsys):
    (tmp_path / ".git").mkdir()

    def broken(*args, **kwargs):
        raise OSError("git show exploded")

    monkeypatch.setattr("assemblyzero.speedrun.restore.restore_artifact", broken)
    with pytest.raises(mod.LLDRebuildFailed) as caught:
        mod.find_lld_path(42, tmp_path)
    message = str(caught.value)
    assert "42" in message
    assert "OSError: git show exploded" in message
    assert "ERROR [N0]" in capsys.readouterr().err


def test_324_load_lld_halts_when_the_rebuild_fails(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()

    def broken(*args, **kwargs):
        raise OSError("git show exploded")

    monkeypatch.setattr("assemblyzero.speedrun.restore.restore_artifact", broken)
    result = mod.load_lld(_state(tmp_path, _spec(tmp_path)))
    assert "could not be rebuilt" in result["error_message"]
    assert "git show exploded" in result["error_message"]


def test_324_a_clean_miss_is_still_absence(tmp_path, monkeypatch):
    """Nothing on any ref is a legitimate answer: None, and no noise."""
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        "assemblyzero.speedrun.restore.restore_artifact", lambda *a, **k: False
    )
    assert mod.find_lld_path(42, tmp_path) is None


def test_325_the_fail_open_tag_is_gone():
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "fail-open:" not in source


# ---------------------------------------------------------------- line 835


def test_835_no_declared_target_is_the_adr_0207_default():
    """Pinned: compliant, documented default."""
    assert mod.declared_coverage_target("no target here") is None
    assert mod.extract_coverage_target("no target here") == 95


# ---------------------------------------------------------------- line 896


def test_896_no_files_table_raises():
    with pytest.raises(mod.WorkflowParsingError) as caught:
        mod.extract_files_to_modify("# Spec\n\nnothing to implement\n")
    assert "Files" in str(caught.value)


def test_896_a_table_that_names_no_file_raises():
    text = (
        "## 2. Files to Implement\n\n"
        "| Order | File | Change Type | Description |\n"
        "|-------|------|-------------|-------------|\n"
        "| 1 | `src/` | Add (Directory) | a package |\n"
    )
    with pytest.raises(mod.WorkflowParsingError):
        mod.extract_files_to_modify(text)


def test_896_load_lld_halts_without_a_files_table(tmp_path, capsys):
    spec = _spec(tmp_path, _without(SPEC, "## 2. Files", "## 3. Requirements"))
    result = mod.load_lld(_state(tmp_path, spec))
    assert "Files to Implement" in result["error_message"]
    assert str(spec) in result["error_message"]
    assert "ERROR [N0]" in capsys.readouterr().err


# ------------------------------------------------- lines 969, 972, 977, 983


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(["gh"], returncode, stdout, stderr)


@pytest.mark.parametrize(
    "outcome, expected",
    [
        (subprocess.TimeoutExpired(["gh"], 30), "Failed to fetch issue #42"),
        (_completed(1, stderr="no such issue"), "Issue #42 not found"),
        (_completed(0, stdout="not json"), "Invalid JSON from gh issue view"),
        (_completed(0, stdout='{"title": "t", "body": ""}'), "has no body content"),
    ],
    ids=["969_timeout", "972_nonzero", "977_bad_json", "983_no_body"],
)
def test_969_to_983_issue_only_fetch_failures_halt(tmp_path, monkeypatch, outcome, expected):
    """Pinned: compliant, each an error_message routed to HALT."""

    def run(*args, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(mod, "run_command", run)
    result = mod._load_from_issue({}, 42, tmp_path)
    assert expected in result["error_message"]


# ---------------------------------------------------------------- line 1001


def _issue(body: str) -> str:
    import json

    return json.dumps({"title": "Widget", "body": body})


def test_1001_issue_only_without_section_10_halts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        mod, "run_command", lambda *a, **k: _completed(0, stdout=_issue("Make it spin."))
    )
    result = mod._load_from_issue({}, 42, tmp_path)
    assert "Section 10" in result["error_message"]
    assert "#42" in result["error_message"]
    assert "ERROR [N0]" in capsys.readouterr().err


def test_896_issue_only_without_a_files_table_halts(tmp_path, monkeypatch):
    body = "## 10. Test Plan\n\n### test_spins\nVerify it spins.\n"
    monkeypatch.setattr(
        mod, "run_command", lambda *a, **k: _completed(0, stdout=_issue(body))
    )
    result = mod._load_from_issue({}, 42, tmp_path)
    assert "Files to Implement" in result["error_message"]


# ----------------------------------------------------- lines 1099, 1136, 1142


def test_1099_a_missing_spec_halts(tmp_path):
    """Pinned: compliant."""
    result = mod.load_lld(_state(tmp_path, tmp_path / "absent.md"))
    assert result["error_message"].startswith(mod.MISSING_REQUIRED_INPUT)


def test_1136_an_unreadable_spec_halts(tmp_path):
    """Pinned: compliant. A directory where the spec should be cannot be read."""
    spec = tmp_path / "spec-42.md"
    spec.mkdir()
    result = mod.load_lld(_state(tmp_path, spec))
    assert result["error_message"].startswith("Failed to read LLD")


def test_1142_a_spec_too_short_halts(tmp_path):
    """Pinned: compliant."""
    result = mod.load_lld(_state(tmp_path, _spec(tmp_path, "# tiny\n")))
    assert result["error_message"] == "GUARD: LLD content too short"


# ---------------------------------------------------------------- line 1146


def test_1146_an_unapproved_spec_halts(tmp_path, capsys):
    spec = _spec(tmp_path, SPEC.replace("APPROVED", "DRAFT"))
    result = mod.load_lld(_state(tmp_path, spec))
    assert "APPROVED" in result["error_message"]
    assert str(spec) in result["error_message"]
    assert "ERROR [N0]" in capsys.readouterr().err


# ---------------------------------------------------------------- line 1164


def test_1164_an_unreadable_original_lld_halts(tmp_path, capsys):
    lld = tmp_path / "docs" / "lld" / "active" / "LLD-042.md"
    lld.mkdir(parents=True)  # found, and cannot be read
    result = mod.load_lld(_state(tmp_path, _spec(tmp_path)))
    assert str(lld) in result["error_message"]
    assert "IsADirectoryError" in result["error_message"]
    assert "ERROR [N0]" in capsys.readouterr().err


# ------------------------------------------------------------ lines 1180, 1182


def test_1180_each_source_error_is_recorded(tmp_path, capsys):
    """The LLD's Section 10 fails and the spec's serves: the LLD's error is said."""
    lld = tmp_path / "docs" / "lld" / "active" / "LLD-042.md"
    lld.parent.mkdir(parents=True)
    lld.write_text(
        "# LLD 42\n\n## 3. Requirements\n\n1. REQ-1: It spins.\n\n"
        "## 9. Test Plan\n\nlegacy\n",
        encoding="utf-8",
    )
    result = mod.load_lld(_state(tmp_path, _spec(tmp_path)))
    assert result["error_message"] == ""
    out = capsys.readouterr().out
    assert str(lld) in out
    assert "Legacy Section 9" in out


def test_1182_no_section_10_anywhere_halts(tmp_path, capsys):
    spec = _spec(tmp_path, SPEC.split("## 10. Test Plan")[0] + "\nmore words " * 20)
    result = mod.load_lld(_state(tmp_path, spec))
    message = result["error_message"]
    assert "Section 10" in message
    assert str(spec) in message
    assert "Expected: ## 10. Test Mapping" in message
    assert "ERROR [N0]" in capsys.readouterr().err


# ---------------------------------------------------------------- line 1224


def test_1224_zero_requirements_halts_at_n0(tmp_path, capsys):
    spec = _spec(
        tmp_path, _without(SPEC, "## 3. Requirements", "## 10. Test Plan")
    )
    result = mod.load_lld(_state(tmp_path, spec))
    message = result["error_message"]
    assert "requirements unreadable" in message or "no requirements declared" in message
    assert str(spec) in message
    assert "ERROR [N0]" in capsys.readouterr().err
