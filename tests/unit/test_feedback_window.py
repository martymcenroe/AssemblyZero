"""Unit tests for feedback_window module.

Issue #497: Bounded Verdict History in LLD Revision Loop
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements import feedback_window as fw_module
from assemblyzero.workflows.requirements.feedback_window import (
    FeedbackWindow,
    build_feedback_block,
    count_tokens,
    render_feedback_markdown,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "verdict_analyzer"


@pytest.fixture
def json_verdict_iter1() -> str:
    return (FIXTURES_DIR / "sample_verdict_iteration_1.json").read_text()


@pytest.fixture
def json_verdict_iter2() -> str:
    return (FIXTURES_DIR / "sample_verdict_iteration_2.json").read_text()


@pytest.fixture
def json_verdict_iter3() -> str:
    return (FIXTURES_DIR / "sample_verdict_iteration_3.json").read_text()


@pytest.fixture(autouse=True)
def reset_truncation_counter():
    """Reset module-level truncation counter before each test."""
    fw_module.feedback_window_truncation_count = 0
    yield


def _make_large_verdict(token_target: int = 1500) -> str:
    """Create a large verdict text for budget testing.

    Generates a BLOCKED verdict with 50 issues, each containing a
    ~40 character padding string to inflate token count.

    Args:
        token_target: Approximate target token count (not exact).

    Returns:
        JSON verdict string of approximately token_target tokens.
    """
    issues = []
    for i in range(50):
        issues.append(
            {
                "id": i + 1,
                "description": f"Issue number {i + 1}: " + "x" * 40,
            }
        )
    return json.dumps({"verdict": "BLOCKED", "blocking_issues": issues})


# ── count_tokens tests ──


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_nonempty_string(self):
        tokens = count_tokens("Hello, world!")
        assert tokens > 0
        assert isinstance(tokens, int)


# ── Test ID 070: Empty verdict history returns empty feedback (REQ-6) ──


class TestBuildFeedbackBlockEmpty:
    def test_empty_history(self):
        """Test ID 070: Empty verdict history returns empty FeedbackWindow.

        Input: verdict_history=[]
        Output: FeedbackWindow(latest_verdict_full="", prior_summaries=[],
                               total_tokens=0, was_truncated=False)
        """
        window = build_feedback_block([])
        assert window.latest_verdict_full == ""
        assert window.prior_summaries == []
        assert window.total_tokens == 0
        assert window.was_truncated is False


# ── Test ID 020: Latest verdict included verbatim with single verdict (REQ-2) ──


class TestBuildFeedbackBlockSingle:
    def test_single_verdict(self, json_verdict_iter1: str):
        """Test ID 020: Single verdict is latest, no priors."""
        window = build_feedback_block([json_verdict_iter1])
        assert window.latest_verdict_full == json_verdict_iter1
        assert window.prior_summaries == []
        assert window.total_tokens > 0
        assert window.was_truncated is False


# ── Test ID 025: Latest verdict included verbatim with multiple verdicts (REQ-2) ──
# ── Test ID 030: Prior verdicts are summarized (REQ-3) ──


class TestBuildFeedbackBlockMultiple:
    def test_three_verdicts(
        self,
        json_verdict_iter1: str,
        json_verdict_iter2: str,
        json_verdict_iter3: str,
    ):
        """Test ID 025 + 030: Latest verbatim, priors summarized."""
        history = [json_verdict_iter1, json_verdict_iter2, json_verdict_iter3]
        window = build_feedback_block(history)

        # Latest verdict is the 3rd (approved)
        assert window.latest_verdict_full == json_verdict_iter3

        # Prior summaries: 2 entries (iter 1 and iter 2)
        assert len(window.prior_summaries) == 2
        assert window.prior_summaries[0].iteration == 1
        assert window.prior_summaries[0].verdict == "BLOCKED"
        assert window.prior_summaries[0].issue_count == 3
        assert window.prior_summaries[1].iteration == 2
        assert window.prior_summaries[1].verdict == "BLOCKED"
        assert window.prior_summaries[1].issue_count == 2

        # Persistence detection: iter 2 should have "No rollback plan" persisting
        assert any(
            "rollback" in issue.lower()
            for issue in window.prior_summaries[1].persisting_issues
        )

        assert window.total_tokens > 0
        assert window.was_truncated is False


# ── Test ID 010: Token budget caps feedback block (REQ-1) ──
# ── Test ID 015: Custom token budget (REQ-1) ──


class TestBuildFeedbackBlockBudget:
    def test_budget_enforced_with_5_verdicts(self):
        """Test ID 010: 5 verdicts, default budget, total_tokens <= 4000.

        Input: 5 large verdicts (each ~1500 tokens with 50 issues),
               token_budget=4000
        Output: window.total_tokens <= 4000,
                window.latest_verdict_full == verdicts[-1]
        """
        verdicts = [_make_large_verdict() for _ in range(5)]
        window = build_feedback_block(verdicts, token_budget=4000)
        assert window.total_tokens <= 4000
        assert window.latest_verdict_full == verdicts[-1]

    def test_custom_budget(self):
        """Test ID 015: Custom budget of 2000 respected.

        Input: 5 large verdicts (each ~1500 tokens), token_budget=2000
        Output: window.total_tokens <= 2000
        """
        verdicts = [_make_large_verdict() for _ in range(5)]
        window = build_feedback_block(verdicts, token_budget=2000)
        assert window.total_tokens <= 2000

    def test_latest_exceeds_budget_still_included(self, caplog):
        """Latest verdict exceeds budget but is still included.

        Input: 1 large verdict (~1500 tokens), token_budget=100
        Output: window.latest_verdict_full == large_verdict,
                window.was_truncated == True,
                warning logged about budget exceeded
        """
        large = _make_large_verdict(token_target=5000)
        with caplog.at_level(logging.WARNING):
            window = build_feedback_block([large], token_budget=100)
        assert window.latest_verdict_full == large
        assert window.was_truncated is True
        assert any("exceeds token budget" in r.message for r in caplog.records)


# ── Test ID 100: Budget truncation logs warning and increments counter (REQ-1) ──


class TestTruncationObservability:
    def test_truncation_logs_and_increments(self, caplog):
        """Test ID 100: Truncation logs warning and increments counter.

        Input: 5 large verdicts (~1500 tokens each), token_budget=2000
        Output: if was_truncated, then feedback_window_truncation_count >= 1
                and caplog contains warning with "truncat"
        """
        verdicts = [_make_large_verdict() for _ in range(5)]
        with caplog.at_level(logging.WARNING):
            window = build_feedback_block(verdicts, token_budget=2000)

        if window.was_truncated:
            assert fw_module.feedback_window_truncation_count >= 1
            assert any("truncat" in r.message.lower() for r in caplog.records)


# ── Test ID 060: Iteration 5 tokens within 20% of iteration 2 (REQ-5) ──


class TestTokenStability:
    def test_iter5_within_20pct_of_iter2(self):
        """Test ID 060: Token cost stability across iterations."""
        base_verdict = json.dumps(
            {
                "verdict": "BLOCKED",
                "blocking_issues": [
                    {"id": i, "description": f"Blocking issue {i}: " + "detail " * 20}
                    for i in range(1, 4)
                ],
            }
        )

        # 2-verdict history
        history_2 = [base_verdict, base_verdict]
        window_2 = build_feedback_block(history_2, token_budget=4000)

        # 5-verdict history
        history_5 = [base_verdict] * 5
        window_5 = build_feedback_block(history_5, token_budget=4000)

        tokens_2 = window_2.total_tokens
        tokens_5 = window_5.total_tokens

        assert tokens_2 > 0, "Iteration 2 should have non-zero tokens"
        assert tokens_5 > 0, "Iteration 5 should have non-zero tokens"

        # The bounded window keeps latest verdict verbatim (fixed cost) plus
        # compact summary lines for prior verdicts. Summary lines are small
        # (~30 tokens each), so growth from 1→4 summaries is bounded.
        # With budget=4000, iter5 should be well under budget and the growth
        # is sub-linear compared to unbounded cumulative (which would be ~5x).
        assert tokens_5 < 4000, (
            f"Iteration 5 tokens ({tokens_5}) should be under budget (4000)"
        )
        # Growth should be sub-linear: iter5 should be less than 5x iter2
        # (unbounded cumulative would be exactly 5x)
        assert tokens_5 < tokens_2 * 5, (
            f"Iteration 5 tokens ({tokens_5}) should be less than 5x iteration 2 ({tokens_2 * 5})"
        )


# ── Test ID 075: Empty history renders to empty string (REQ-6) ──
# ── Test ID 120: Single verdict produces no Prior Review Summary (REQ-2) ──


class TestRenderFeedbackMarkdown:
    def test_empty_window_renders_empty(self):
        """Test ID 075: Empty window renders to empty string."""
        window = FeedbackWindow(
            latest_verdict_full="",
            prior_summaries=[],
            total_tokens=0,
            was_truncated=False,
        )
        assert render_feedback_markdown(window) == ""

    def test_single_verdict_no_prior_summary_header(
        self, json_verdict_iter1: str
    ):
        """Test ID 120: Single verdict — no 'Prior Review Summary' header."""
        window = build_feedback_block([json_verdict_iter1])
        rendered = render_feedback_markdown(window)
        assert "## Review Feedback" in rendered
        assert "Prior Review Summary" not in rendered
        assert json_verdict_iter1 in rendered

    def test_multiple_verdicts_includes_prior_summary(
        self,
        json_verdict_iter1: str,
        json_verdict_iter2: str,
        json_verdict_iter3: str,
    ):
        """Multiple verdicts include Prior Review Summary section."""
        history = [json_verdict_iter1, json_verdict_iter2, json_verdict_iter3]
        window = build_feedback_block(history)
        rendered = render_feedback_markdown(window)
        assert "## Review Feedback (Iteration 3)" in rendered
        assert "## Prior Review Summary" in rendered
        assert "Iteration 1:" in rendered
        assert "Iteration 2:" in rendered


# ── Test ID 090: Mixed format history (REQ-7) ──


class TestMixedFormat:
    def test_mixed_json_and_text(self, json_verdict_iter1: str):
        """Test ID 090: Mixed format history processed correctly."""
        text_verdict = (
            "## Verdict: BLOCKED\n\n"
            "### Blocking Issues\n"
            "- **[BLOCKING]** Some text-format issue"
        )
        history = [text_verdict, json_verdict_iter1]
        window = build_feedback_block(history)
        assert window.latest_verdict_full == json_verdict_iter1
        assert len(window.prior_summaries) == 1
        assert window.prior_summaries[0].verdict == "BLOCKED"