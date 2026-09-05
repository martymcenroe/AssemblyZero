"""Test-plan review under standard 0028: structured verdict or loud rejection.

The pre-0028 file pinned _parse_verdict's structured-then-regex behavior;
_parse_verdict is retired. A reviewer response that yields no schema-valid
verdict is now rejected with error_message — the stage retry machinery is
the re-ask — instead of being silently downgraded (UNKNOWN → REVISE →
BLOCKED) by a regex scrape.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def _state_forcing_llm_path() -> dict:
    """<100% coverage so the fast-path is skipped and the LLM review runs."""
    return {
        "test_scenarios": [
            {"name": "test_a", "type": "unit", "requirement_ref": "REQ-1"},
            {"name": "test_b", "type": "unit", "requirement_ref": "REQ-1"},
        ],
        "requirements": ["REQ-1: A", "REQ-2: B"],
        "lld_content": (
            "This is a detailed low-level design document with sufficient "
            "words to pass the mechanical gate minimum threshold. " * 5
        ),
        "issue_number": 42,
        "repo_root": "/tmp/test-repo",
        "audit_dir": "/tmp/nonexistent",
        "mock_mode": False,
        "node_costs": {},
        "node_tokens": {},
        "file_counter": 0,
        "config_reviewer": "gemini:3.1-pro-preview",
    }


def _llm_result(content: str) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.error_message = None
    result.content = content
    result.response = ""
    result.input_tokens = 100
    result.output_tokens = 50
    return result


@patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
@patch("assemblyzero.utils.retry.with_retry")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_provider")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost")
def test_schema_valid_verdict_proceeds(
    mock_cost, mock_provider, mock_with_retry, mock_root, mock_prompt, mock_log,
):
    from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan
    from assemblyzero.core.llm_provider import GeminiProvider

    mock_root.return_value = Path("/tmp/test-repo")
    mock_prompt.return_value = "review prompt"
    mock_cost.return_value = 0.0
    mock_provider.return_value = MagicMock(spec=GeminiProvider)
    mock_with_retry.return_value = _llm_result(
        json.dumps({"verdict": "APPROVED", "rationale": "Coverage acceptable."})
    )

    result = review_test_plan(_state_forcing_llm_path())
    assert result["test_plan_status"] == "APPROVED"
    assert not result.get("error_message")


@patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
@patch("assemblyzero.utils.retry.with_retry")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_provider")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost")
def test_markdown_verdict_is_rejected_loudly(
    mock_cost, mock_provider, mock_with_retry, mock_root, mock_prompt, mock_log,
):
    """The old regex fallback would have scraped APPROVED out of prose like
    this; under standard 0028 a response that is neither the JSON contract
    nor the review's own template (#2837) is rejected with an error the
    stage retry machinery acts on."""
    from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan
    from assemblyzero.core.llm_provider import GeminiProvider

    mock_root.return_value = Path("/tmp/test-repo")
    mock_prompt.return_value = "review prompt"
    mock_cost.return_value = 0.0
    mock_provider.return_value = MagicMock(spec=GeminiProvider)
    mock_with_retry.return_value = _llm_result(
        "APPROVED — all good, ship it."
    )

    result = review_test_plan(_state_forcing_llm_path())
    assert result.get("error_message"), "unparseable verdict must reject, not proceed"
    assert "rejected" in result["error_message"]
    assert "test_plan_status" not in result


@patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
@patch("assemblyzero.utils.retry.with_retry")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_provider")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost")
def test_the_reviews_own_template_is_a_verdict(
    mock_cost, mock_provider, mock_with_retry, mock_root, mock_prompt, mock_log,
):
    """#2837: the prompt's own Output Format is a markdown template with one
    box to mark; a reviewer that follows it has answered, and the node reads
    it as our own format (standard 0028 §3) instead of ending the run."""
    from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan
    from assemblyzero.core.llm_provider import GeminiProvider

    mock_root.return_value = Path("/tmp/test-repo")
    mock_prompt.return_value = "review prompt"
    mock_cost.return_value = 0.0
    mock_provider.return_value = MagicMock(spec=GeminiProvider)
    mock_with_retry.return_value = _llm_result(
        "## Coverage Analysis\n- Requirements covered: 2/2 (100%)\n\n"
        "## Verdict\n[ ] **APPROVED** - Test plan is ready for implementation\n"
        "[X] **BLOCKED** - Test plan needs revision\n\n"
        "## Required Changes (if BLOCKED)\n1. T030 must assert on a mocked virtual_memory().\n"
    )

    result = review_test_plan(_state_forcing_llm_path())
    assert not result.get("error_message")
    assert result["test_plan_status"] == "BLOCKED"


@patch("assemblyzero.workflows.testing.nodes.review_test_plan.log_workflow_execution")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.load_review_prompt")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_repo_root")
@patch("assemblyzero.utils.retry.with_retry")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_provider")
@patch("assemblyzero.workflows.testing.nodes.review_test_plan.get_cumulative_cost")
def test_rejection_message_carries_excerpt(
    mock_cost, mock_provider, mock_with_retry, mock_root, mock_prompt, mock_log,
):
    from assemblyzero.workflows.testing.nodes.review_test_plan import review_test_plan
    from assemblyzero.core.llm_provider import GeminiProvider

    mock_root.return_value = Path("/tmp/test-repo")
    mock_prompt.return_value = "review prompt"
    mock_cost.return_value = 0.0
    mock_provider.return_value = MagicMock(spec=GeminiProvider)
    mock_with_retry.return_value = _llm_result("Plain prose, no verdict anywhere.")

    result = review_test_plan(_state_forcing_llm_path())
    assert "Plain prose" in result.get("error_message", ""), (
        "the halt banner must be legible (#2197): excerpt included"
    )
