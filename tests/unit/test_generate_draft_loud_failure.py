"""The requirements drafter node (N1) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). A drafter
that cannot draft what it was asked to draft returns ``error_message``, which
``route_after_generate_draft`` sends to HALT, and HALT alerts. Nothing is
spent first: the audit_dir, the prompt size, the prior draft and the
interface refresh are all settled before the drafter is called. Nothing is
dropped to fit: a prompt over the cap halts instead of losing sections.
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.core.seats import resolve
from assemblyzero.workflows.requirements.best_of_n import CandidateScore
from assemblyzero.workflows.requirements.graph import route_after_generate_draft
from assemblyzero.workflows.requirements.state import create_initial_state

gd = importlib.import_module("assemblyzero.workflows.requirements.nodes.generate_draft")


def _result(response: str = "# Draft\n\nBody.\n", success: bool = True, error: str | None = None):
    return LLMCallResult(
        success=success, response=response if success else "", raw_response=response,
        error_message=error, provider="fake", model_used="fake-model",
        duration_ms=1, attempts=1,
    )


class _Drafter:
    def __init__(self, *results):
        self._results = list(results)
        self.calls: list[dict] = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return self._results.pop(0)


def _state(tmp_path: Path, workflow_type: str = "issue", **overrides) -> dict:
    templates = tmp_path / "docs" / "templates"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "0101-issue-template.md").write_text("# Template\n", encoding="utf-8")
    (templates / "0102-feature-lld-template.md").write_text("# Template\n", encoding="utf-8")
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    if workflow_type == "issue":
        state = create_initial_state(
            workflow_type="issue", assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path), brief_file="brief.md",
        )
        state["brief_content"] = "# Brief"
    else:
        state = create_initial_state(
            workflow_type="lld", assemblyzero_root=str(tmp_path),
            target_repo=str(tmp_path), issue_number=42,
        )
        state["issue_title"] = "A widget"
        state["issue_body"] = "Build the widget."
    state = dict(state)
    state["audit_dir"] = str(audit)
    state.update(overrides)
    return state


def _halts(out: dict) -> bool:
    return bool(out.get("error_message")) and route_after_generate_draft(out) == "HALT"


def _said_error(capsys) -> str:
    err = capsys.readouterr().err
    assert "ERROR" in err, f"nothing at ERROR on stderr: {err!r}"
    return err


# --------------------------------------------------------------------------
# Best-of-N (#2573)
# --------------------------------------------------------------------------


class TestBestOfN:
    def test_185_a_failed_candidate_is_said_with_index_spec_and_cause(self, tmp_path, capsys):
        state = _state(tmp_path, "lld", config_draft_candidates=2)
        drafter = _Drafter(_result(success=False, error="rate limited (429)"), _result())

        def clean(index, draft, state, **kwargs):
            return CandidateScore(index=index, draft=draft)

        with patch.object(gd, "get_provider", return_value=drafter), \
             patch.object(gd, "score_candidate", side_effect=clean):
            out = gd.generate_draft(state)

        assert out["error_message"] == ""
        assert len(drafter.calls) == 2
        err = _said_error(capsys)
        assert "candidate 1/2" in err
        assert resolve(state, "requirements.draft").spec in err
        assert "rate limited (429)" in err

    def test_201_no_audit_dir_halts_before_any_candidate_is_drawn(self, tmp_path, capsys):
        state = _state(tmp_path, "lld", config_draft_candidates=2)
        state["audit_dir"] = str(tmp_path / "missing")
        drafter = _Drafter()

        with patch.object(gd, "get_provider", return_value=drafter):
            out = gd.generate_draft(state)

        assert drafter.calls == []
        assert _halts(out)
        assert "missing" in out["error_message"]
        _said_error(capsys)

    def test_233_an_unset_audit_dir_halts_before_any_candidate_is_drawn(self, tmp_path, capsys):
        state = _state(tmp_path, "lld", config_draft_candidates=2, audit_dir="")
        drafter = _Drafter()

        with patch.object(gd, "get_provider", return_value=drafter):
            out = gd.generate_draft(state)

        assert drafter.calls == []
        assert _halts(out)
        assert "audit_dir" in out["error_message"]
        _said_error(capsys)


# --------------------------------------------------------------------------
# The serial drafter
# --------------------------------------------------------------------------


class TestSerialDraft:
    def test_674_no_audit_dir_halts_before_the_drafter_runs(self, tmp_path, capsys):
        state = _state(tmp_path, audit_dir=str(tmp_path / "missing"))
        drafter = _Drafter()

        with patch.object(gd, "get_provider", return_value=drafter):
            out = gd.generate_draft(state)

        assert drafter.calls == []
        assert _halts(out)
        _said_error(capsys)

    def test_674_kept_a_present_audit_dir_records_the_draft(self, tmp_path):
        state = _state(tmp_path)
        drafter = _Drafter(_result())

        with patch.object(gd, "get_provider", return_value=drafter):
            out = gd.generate_draft(state)

        assert out["error_message"] == ""
        assert Path(out["current_draft_path"]).is_file()

    def test_345_the_held_seat_error_halts_as_invalid_drafter_and_the_tag_is_gone(
        self, tmp_path
    ):
        state = _state(tmp_path)

        with patch.object(gd, "resolve", side_effect=ValueError("no seat named requirements.draft")):
            out = gd.generate_draft(state)

        assert _halts(out)
        assert out["error_message"].startswith("Invalid drafter:")
        assert "no seat named requirements.draft" in out["error_message"]
        assert "fail-open" not in inspect.getsource(gd.generate_draft)

    def test_366_a_prompt_over_the_cap_halts_naming_its_size_and_the_cap(self, tmp_path, capsys):
        state = _state(tmp_path)
        size = gd.MAX_TOTAL_PROMPT_CHARS + 1
        drafter = _Drafter()

        with patch.object(gd, "get_provider", return_value=drafter), \
             patch.object(gd, "_build_prompt", return_value="x" * size):
            out = gd.generate_draft(state)

        assert drafter.calls == []
        assert _halts(out)
        assert f"{size:,}" in out["error_message"]
        assert f"{gd.MAX_TOTAL_PROMPT_CHARS:,}" in out["error_message"]
        _said_error(capsys)

    def test_366_kept_a_prompt_at_the_cap_is_sent_whole(self, tmp_path):
        state = _state(tmp_path)
        prompt = "x" * gd.MAX_TOTAL_PROMPT_CHARS
        drafter = _Drafter(_result())

        with patch.object(gd, "get_provider", return_value=drafter), \
             patch.object(gd, "_build_prompt", return_value=prompt):
            out = gd.generate_draft(state)

        assert out["error_message"] == ""
        assert drafter.calls[0]["content"] == prompt

    @pytest.mark.parametrize("kind", ["missing", "directory"])
    def test_480_a_prior_draft_that_cannot_be_read_halts_naming_it(self, tmp_path, capsys, kind):
        prior = tmp_path / "prior" / "LLD-042.md"
        if kind == "directory":
            prior.mkdir(parents=True)
        state = _state(tmp_path, previous_draft_path=str(prior))
        drafter = _Drafter()

        with patch.object(gd, "get_provider", return_value=drafter):
            out = gd.generate_draft(state)

        assert drafter.calls == []
        assert _halts(out)
        assert str(prior) in out["error_message"]
        assert "Error" in out["error_message"]  # the exception type is named
        _said_error(capsys)

    def test_480_kept_a_readable_prior_draft_rides_in_the_system_prompt(self, tmp_path):
        prior = tmp_path / "prior.md"
        prior.write_text("# The prior attempt\n", encoding="utf-8")
        state = _state(tmp_path, previous_draft_path=str(prior))
        drafter = _Drafter(_result())

        with patch.object(gd, "get_provider", return_value=drafter):
            out = gd.generate_draft(state)

        assert out["error_message"] == ""
        assert "# The prior attempt" in drafter.calls[0]["system_prompt"]


# --------------------------------------------------------------------------
# The Tiphys interface refresh on a revision (#1688)
# --------------------------------------------------------------------------


class TestInterfaceRefresh:
    def _revision(self, tmp_path: Path) -> dict:
        return _state(
            tmp_path, "lld",
            current_draft="# 42 - Feature: A widget\n\n## 2.1 Files Changed\n",
            validation_errors=["Section 3 missing"],
        )

    def test_807_a_failing_refresh_halts_the_revision_naming_the_cause(self, tmp_path, capsys):
        state = self._revision(tmp_path)
        drafter = _Drafter()

        with patch.object(gd, "get_provider", return_value=drafter), \
             patch.object(gd, "parse_files_changed_table", return_value=([{"path": "pkg/mod.py"}], [])), \
             patch.object(gd, "build_interface_map_for_paths",
                          side_effect=PermissionError(13, "Permission denied", "pkg/mod.py")):
            out = gd.generate_draft(state)

        assert drafter.calls == []
        assert _halts(out)
        assert "PermissionError" in out["error_message"]
        assert "pkg/mod.py" in out["error_message"]
        _said_error(capsys)

    def test_807_build_revision_context_raises_rather_than_reuse_a_stale_map(self, tmp_path):
        state = self._revision(tmp_path)
        state["interface_map"] = {"pkg/old.py": "def stale(): ..."}

        with patch.object(gd, "parse_files_changed_table", return_value=([{"path": "pkg/mod.py"}], [])), \
             patch.object(gd, "build_interface_map_for_paths", side_effect=SyntaxError("bad file")), \
             pytest.raises(gd.InterfaceRefreshError, match="SyntaxError"):
            gd.build_revision_context(state)

    def test_807_kept_a_draft_naming_no_python_files_uses_the_n0b_map(self, tmp_path):
        state = self._revision(tmp_path)
        state["interface_map"] = {"pkg/old.py": "def kept(): ..."}

        with patch.object(gd, "parse_files_changed_table", return_value=([{"path": "README.md"}], [])), \
             patch.object(gd, "build_interface_map_for_paths") as refresh:
            context = gd.build_revision_context(state)

        refresh.assert_not_called()
        assert "def kept()" in context


# --------------------------------------------------------------------------
# Prompt truncation, retired
# --------------------------------------------------------------------------


def test_1155_no_section_is_dropped_to_fit_the_cap():
    """The section-dropping truncator is gone; an over-cap prompt halts (366)."""
    assert not hasattr(gd, "_truncate_prompt")
    assert "Dropped" not in inspect.getsource(gd)


def test_1160_no_prompt_is_hard_truncated():
    source = inspect.getsource(gd)
    assert "Hard-truncated" not in source
    assert "[:MAX_TOTAL_PROMPT_CHARS]" not in source


# --------------------------------------------------------------------------
# validate_draft_structure (kept for compatibility, #248)
# --------------------------------------------------------------------------


@pytest.mark.parametrize("content", ["", "  \n"])
def test_1186_an_empty_draft_does_not_pass_structure_validation(content):
    message = gd.validate_draft_structure(content)
    assert message and message.startswith("BLOCKED")
    assert "empty" in message


def test_1186_kept_a_draft_with_no_open_questions_section_passes():
    assert gd.validate_draft_structure("# Draft\n\n## Design\n\nText.\n") is None


def test_no_fail_open_tag_remains_in_generate_draft():
    assert "fail-open" not in inspect.getsource(gd)
