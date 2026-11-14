"""#4272: N2's #525 resume says what it does with a recovered draft it cannot use.

On a first pass with no draft in state, ``generate_spec`` resumes from the
newest ``*-spec-draft.md`` in the lineage instead of paying for a new draft
(#525). It read that file with no handler, so a draft that could not be read
raised out of N2; and an empty draft was skipped without a word before N2 drafted
again. An unreadable draft now halts N2 through ``route_after_generate_spec``,
naming the path and the cause; an empty one is reported in one line, then N2
drafts.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from assemblyzero.workflows.implementation_spec.graph import route_after_generate_spec

# `nodes/__init__` re-exports the FUNCTION generate_spec, which shadows the
# module of the same name, so the module is imported by its dotted path.
gs = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.generate_spec"
)

DRAFT = "# Implementation Spec\n\n" + "A line of the spec.\n" * 20
RECOVERED = "# Implementation Spec (recovered)\n\n" + "A recovered line.\n" * 20

needs_posix_permissions = pytest.mark.skipif(
    sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="a mode-000 file refuses reads only on POSIX, and not to root",
)


def _drafter(response: str = DRAFT) -> Mock:
    drafter = Mock()
    drafter.invoke.return_value = Mock(
        success=True, response=response, error_message=None,
        input_tokens=0, output_tokens=0,
    )
    return drafter


def _state(tmp_path: Path) -> dict:
    lineage = tmp_path / "lineage"
    lineage.mkdir(exist_ok=True)
    return {
        "config_mock_mode": True,
        "lld_content": "# LLD\n\ncontent\n",
        "current_state_snapshots": {},
        "pattern_references": [],
        "assemblyzero_root": "",
        "repo_root": "",
        "issue_number": 42,
        "audit_dir": str(lineage),
        "review_iteration": 0,
    }


def _run(state: dict, drafter: Mock | None = None):
    drafter = drafter or _drafter()
    with patch.object(gs, "get_provider", return_value=drafter), \
            patch.object(gs, "load_template", return_value="# Template"):
        return gs.generate_spec(state), drafter


def _halts(result: dict, *needles: str) -> None:
    message = result["error_message"]
    assert message, "N2 must return an error_message"
    assert route_after_generate_spec(result) == "HALT"
    assert "[N2]" in message and "#42" in message
    for needle in needles:
        assert needle in message, f"{needle!r} not in {message!r}"
    assert "spec_draft" not in result


class TestAnUnreadableDraftHalts:
    def test_t1_a_draft_that_is_not_utf8_halts_n2_with_the_path_named(self, tmp_path):
        state = _state(tmp_path)
        draft = Path(state["audit_dir"]) / "003-spec-draft.md"
        draft.write_bytes(b"# Spec\n\xff\xfe not utf-8\n")
        result, drafter = _run(state)
        _halts(result, str(draft), "UnicodeDecodeError", "recovered draft")
        drafter.invoke.assert_not_called()

    @needs_posix_permissions
    def test_t1_a_draft_that_cannot_be_opened_halts_n2_with_the_path_named(self, tmp_path):
        state = _state(tmp_path)
        draft = Path(state["audit_dir"]) / "003-spec-draft.md"
        draft.write_text(RECOVERED, encoding="utf-8")
        draft.chmod(0o000)
        try:
            result, drafter = _run(state)
        finally:
            draft.chmod(0o600)
        _halts(result, str(draft), "PermissionError")
        drafter.invoke.assert_not_called()

    def test_the_halt_is_loud_on_stderr(self, tmp_path, capsys):
        state = _state(tmp_path)
        draft = Path(state["audit_dir"]) / "003-spec-draft.md"
        draft.write_bytes(b"\xff\xfe")
        _run(state)
        assert str(draft) in capsys.readouterr().err


class TestAnEmptyDraftIsReported:
    def test_t2_an_empty_draft_is_reported_then_n2_drafts(self, tmp_path, capsys):
        state = _state(tmp_path)
        draft = Path(state["audit_dir"]) / "003-spec-draft.md"
        draft.write_text("  \n\n", encoding="utf-8")
        result, drafter = _run(state)

        out = capsys.readouterr().out
        said = [line for line in out.splitlines() if str(draft) in line]
        assert len(said) == 1, out
        assert "empty" in said[0]
        drafter.invoke.assert_called_once()
        assert result["error_message"] == ""
        assert result["spec_draft"].startswith("# Implementation Spec")
        assert out.index(said[0]) < out.index("Generating initial Implementation Spec draft")


class TestAGoodDraftStillResumes:
    def test_a_readable_draft_is_recovered_without_a_drafter_call(self, tmp_path):
        state = _state(tmp_path)
        draft = Path(state["audit_dir"]) / "003-spec-draft.md"
        draft.write_text(RECOVERED, encoding="utf-8")
        result, drafter = _run(state)
        drafter.invoke.assert_not_called()
        assert result["error_message"] == ""
        assert result["spec_draft"] == RECOVERED
        assert result["spec_draft_path"] == str(draft)
