"""review_test_plan.py under standard 0034, one test per sweep site.

N1 reviews the test plan. Its review prompt was read from the TARGET
repository, where AssemblyZero's prompt never is, and a missing file became a
built-in default without a word. Its failures were printed on stdout, and a
BLOCKED verdict that named no required change sent "See full verdict for
details." to the reviser. No test makes a model call: the provider and the
retry wrapper are stand-ins. Line numbers in the names are ledger 0908's, at
its base ``79e18ad1``.

The router half of lines 428, 489, 553, 579 and 609 (``route_after_review``
ignores ``error_message`` under ``auto_mode``) is ``graph.py``'s, which this
batch does not edit; these tests pin the node half: every one of them
returns ``error_message`` and says so at ERROR on stderr.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from assemblyzero.core.llm_provider import GeminiProvider
from assemblyzero.core.projects_root import REPO_ROOT
from assemblyzero.workflows.testing.nodes.review_test_plan import (
    REVIEW_PROMPT_PATH,
    _extract_feedback,
    load_review_prompt,
    review_test_plan,
)

# The nodes package re-exports the node FUNCTION under the module's name, so
# the module is imported by its path for monkeypatching.
rtp = importlib.import_module("assemblyzero.workflows.testing.nodes.review_test_plan")

LLD = "This is a detailed low-level design with enough words to pass the gate. " * 6


def _state(tmp_path: Path, **overrides) -> dict:
    audit = tmp_path / "audit"
    audit.mkdir(exist_ok=True)
    state = {
        # Under 100% coverage, so the fast path is skipped and the model is asked.
        "test_scenarios": [
            {"name": "test_a", "test_type": "unit", "requirement_ref": "REQ-1"},
            {"name": "test_b", "test_type": "unit", "requirement_ref": "REQ-1"},
        ],
        "requirements": ["REQ-1: A", "REQ-2: B"],
        "lld_content": LLD,
        "issue_number": 42,
        "repo_root": str(tmp_path),
        "audit_dir": str(audit),
        "file_counter": 0,
        "node_costs": {},
        "node_tokens": {},
        "config_reviewer": "gemini:3.8-flash-high",
    }
    state.update(overrides)
    return state


def _result(content: str, *, success: bool = True, error: str | None = None) -> MagicMock:
    result = MagicMock()
    result.success = success
    result.error_message = error
    result.content = content
    result.response = ""
    result.input_tokens = 10
    result.output_tokens = 5
    return result


@pytest.fixture
def reviewer(monkeypatch):
    """Stand-ins for the provider and the retry wrapper: no model is called.
    Set ``.returns`` to the result the review gets, or ``.raises`` to an
    exception the call raises."""
    box = MagicMock()
    box.returns = _result(json.dumps({"verdict": "APPROVED", "rationale": "fine"}))
    box.raises = None
    box.prompts = []

    def with_retry(fn, policy=None, **kwargs):
        if box.raises is not None:
            raise box.raises
        return box.returns

    provider = MagicMock(spec=GeminiProvider)

    def invoke(**kwargs):
        box.prompts.append(kwargs.get("content", ""))
        return box.returns

    provider.invoke.side_effect = invoke
    monkeypatch.setattr(rtp, "get_provider", lambda *a, **k: provider)
    monkeypatch.setattr("assemblyzero.utils.retry.with_retry", with_retry)
    monkeypatch.setattr(rtp, "log_workflow_execution", lambda **kwargs: None)
    return box


# --- line 156: the review prompt template is missing --------------------------


def test_156_a_missing_prompt_file_raises_naming_it(tmp_path):
    with pytest.raises(FileNotFoundError) as raised:
        load_review_prompt(tmp_path)
    assert str(tmp_path / REVIEW_PROMPT_PATH) in str(raised.value)


def test_156_the_prompt_is_assemblyzeros_own_not_the_targets(tmp_path, reviewer):
    """The target repository holds no AssemblyZero prompt; the review reads
    the one in this checkout, never a built-in default."""
    own = (REPO_ROOT / REVIEW_PROMPT_PATH).read_text(encoding="utf-8")
    assert load_review_prompt() == own

    review_test_plan(_state(tmp_path))
    saved = sorted((tmp_path / "audit").glob("*-review-prompt.md"))
    assert saved, "the prompt is saved to the audit trail"
    assert saved[0].read_text(encoding="utf-8").startswith(own)


# --- line 428: the mechanical gates fail -------------------------------------


def test_428_a_failed_mechanical_gate_is_an_error_on_stderr(tmp_path, reviewer, capsys):
    result = review_test_plan(_state(tmp_path, test_scenarios=[]))

    assert result["error_message"].startswith("GUARD: Mechanical pre-checks failed")
    assert result["test_plan_status"] == "BLOCKED"
    assert "ERROR [N1]" in capsys.readouterr().err


# --- line 489: the reviewer cannot be resolved -------------------------------


def test_489_an_unresolvable_reviewer_is_an_error_on_stderr(tmp_path, reviewer, capsys, monkeypatch):
    def refuse(state, seat):
        raise ValueError("no such seat spec: nonsense")

    monkeypatch.setattr("assemblyzero.core.seats.resolve", refuse)
    result = review_test_plan(_state(tmp_path))

    assert result["error_message"] == "Invalid reviewer: no such seat spec: nonsense"
    err = capsys.readouterr().err
    assert "ERROR [N1]" in err and "nonsense" in err


# --- line 553: the reviewer call fails ---------------------------------------


def test_553_a_failed_review_call_is_an_error_on_stderr(tmp_path, reviewer, capsys):
    reviewer.returns = _result("", success=False, error="agy exited 1: quota")
    result = review_test_plan(_state(tmp_path))

    assert result["error_message"].startswith("Reviewer failed after up to")
    assert "quota" in result["error_message"]
    err = capsys.readouterr().err
    assert "ERROR [N1]" in err and "quota" in err


# --- line 579: an unexpected error during the review -------------------------


def test_579_an_unexpected_error_is_named_with_its_type_on_stderr(tmp_path, reviewer, capsys):
    reviewer.raises = RuntimeError("provider fault")
    result = review_test_plan(_state(tmp_path))

    assert result["error_message"] == "Review error: RuntimeError: provider fault"
    err = capsys.readouterr().err
    assert "ERROR [N1]" in err and "RuntimeError" in err


# --- line 609: no schema-valid verdict ---------------------------------------


def test_609_an_unreadable_verdict_is_an_error_on_stderr(tmp_path, reviewer, capsys):
    reviewer.returns = _result("APPROVED, ship it")
    result = review_test_plan(_state(tmp_path))

    assert result["error_message"].startswith(
        "Test-plan reviewer response rejected: no schema-valid verdict found"
    )
    assert "ERROR [N1]" in capsys.readouterr().err


# --- line 710: a BLOCKED verdict whose feedback cannot be extracted ----------


def test_710_extract_feedback_finds_nothing_rather_than_a_placeholder():
    assert _extract_feedback("No headings and no list here.") == ""


def test_710_a_blocked_verdict_with_only_a_rationale_sends_the_rationale(tmp_path, reviewer):
    reviewer.returns = _result(json.dumps({
        "verdict": "BLOCKED", "rationale": "REQ-2 has no scenario at all.",
    }))
    result = review_test_plan(_state(tmp_path))

    assert result["test_plan_status"] == "BLOCKED"
    assert result["gemini_feedback"] == "REQ-2 has no scenario at all."
    assert not result["error_message"], "BLOCKED is a verdict, not an error (#1490)"


def test_710_a_blocked_verdict_naming_no_change_is_rejected(tmp_path, reviewer, capsys):
    reviewer.returns = _result(json.dumps({"verdict": "BLOCKED", "rationale": ""}))
    result = review_test_plan(_state(tmp_path))

    assert result["error_message"].startswith("Test-plan reviewer response rejected")
    assert "names no required change" in result["error_message"]
    assert "gemini_feedback" not in result
    assert "ERROR [N1]" in capsys.readouterr().err


def test_a_blocked_verdict_with_blocking_issues_sends_them(tmp_path, reviewer):
    """Kept: the structured issues are the feedback."""
    reviewer.returns = _result(json.dumps({
        "verdict": "BLOCKED", "rationale": "see issues",
        "blocking_issues": [
            {"section": "10", "issue": "REQ-2 untested", "severity": "BLOCKING"},
        ],
    }))
    result = review_test_plan(_state(tmp_path))
    assert result["gemini_feedback"] == "[BLOCKING] 10: REQ-2 untested"
