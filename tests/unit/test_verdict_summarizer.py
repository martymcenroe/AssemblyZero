"""Unit tests for verdict_summarizer module.

Issue #497: Bounded Verdict History in LLD Revision Loop
"""

import json
import logging
from pathlib import Path

import pytest

from assemblyzero.workflows.requirements.verdict_summarizer import (
    VerdictSummary,
    extract_blocking_issues,
    format_summary_line,
    identify_persisting_issues,
    summarize_verdict,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "verdict_analyzer"


@pytest.fixture
def json_verdict_iter1() -> str:
    """Load iteration 1 JSON verdict fixture."""
    return (FIXTURES_DIR / "sample_verdict_iteration_1.json").read_text()


@pytest.fixture
def json_verdict_iter2() -> str:
    """Load iteration 2 JSON verdict fixture."""
    return (FIXTURES_DIR / "sample_verdict_iteration_2.json").read_text()


@pytest.fixture
def json_verdict_iter3() -> str:
    """Load iteration 3 JSON verdict fixture."""
    return (FIXTURES_DIR / "sample_verdict_iteration_3.json").read_text()


@pytest.fixture
def text_verdict_blocked() -> str:
    """Text-format blocked verdict."""
    return (
        "## Verdict: BLOCKED\n\n"
        "### Blocking Issues\n"
        "- **[BLOCKING]** Missing error handling for API timeout\n"
        "- **[BLOCKING]** No rollback plan for database migration\n"
        "- **[BLOCKING]** Security section omits OWASP references"
    )


# ── Test ID 080: JSON-format verdict correctly parsed (REQ-7) ──


class TestExtractBlockingIssuesJSON:
    def test_json_format_extracts_issues(self, json_verdict_iter1: str):
        """Test ID 080: JSON-format verdict correctly parsed."""
        issues = extract_blocking_issues(json_verdict_iter1)
        assert len(issues) == 3
        assert "Missing error handling for API timeout" in issues
        assert "No rollback plan for database migration" in issues
        assert "Security section omits OWASP references" in issues

    def test_json_approved_returns_empty(self, json_verdict_iter3: str):
        """Approved JSON verdict returns empty list."""
        issues = extract_blocking_issues(json_verdict_iter3)
        assert issues == []

    def test_json_iter2_extracts_two_issues(self, json_verdict_iter2: str):
        """JSON verdict iteration 2 returns 2 issues."""
        issues = extract_blocking_issues(json_verdict_iter2)
        assert len(issues) == 2
        assert "No rollback plan for database migration" in issues
        assert "Test coverage section missing edge cases" in issues


# ── Test ID 085: Text-format verdict correctly parsed (REQ-7) ──


class TestExtractBlockingIssuesText:
    def test_text_format_extracts_issues(self, text_verdict_blocked: str):
        """Test ID 085: Text-format verdict correctly parsed."""
        issues = extract_blocking_issues(text_verdict_blocked)
        assert len(issues) == 3
        assert "Missing error handling for API timeout" in issues
        assert "No rollback plan for database migration" in issues
        assert "Security section omits OWASP references" in issues

    def test_text_alternative_blocking_format(self):
        """Text verdict with **BLOCKING** (no brackets) variant."""
        text = "- **BLOCKING** Some issue description"
        issues = extract_blocking_issues(text)
        assert len(issues) == 1
        assert "Some issue description" in issues

    def test_empty_string_returns_empty(self):
        """Empty verdict text returns empty list."""
        assert extract_blocking_issues("") == []
        assert extract_blocking_issues("   ") == []


# ── Test ID 095: Malformed JSON falls back to text parsing with warning (REQ-7) ──


class TestExtractBlockingIssuesFallback:
    def test_malformed_json_falls_back_with_warning(self, caplog):
        """Test ID 095: Malformed JSON falls back to text parsing."""
        malformed = '{invalid json\n- **[BLOCKING]** Fallback issue found'
        with caplog.at_level(logging.WARNING):
            issues = extract_blocking_issues(malformed)
        assert "Fallback issue found" in issues
        assert any("falling back to text extraction" in r.message for r in caplog.records)


# ── Test ID 040: Persisting issue flagged across consecutive iterations (REQ-4) ──


class TestIdentifyPersistingIssues:
    def test_exact_match_is_persisting(self):
        """Test ID 040: Exact match detected as persisting."""
        current = ["No rollback plan for database migration"]
        prior = [
            "Missing error handling for API timeout",
            "No rollback plan for database migration",
        ]
        persisting, new = identify_persisting_issues(current, prior)
        assert persisting == ["No rollback plan for database migration"]
        assert new == []

    # ── Test ID 045: Persisting issue detected with minor rephrasing (REQ-4) ──

    def test_rephrased_issue_detected_as_persisting(self):
        """Test ID 045: Minor rephrasing still detected as persisting."""
        current = ["Missing rollback plan for database migration"]
        prior = ["No rollback plan for database migration"]
        persisting, new = identify_persisting_issues(current, prior)
        assert len(persisting) == 1
        assert "Missing rollback plan for database migration" in persisting
        assert new == []

    # ── Test ID 050: Non-persisting issues classified as new (REQ-4) ──

    def test_different_issue_is_new(self):
        """Test ID 050: Completely different issue classified as new."""
        current = ["Test coverage section missing edge cases"]
        prior = ["Missing error handling for API timeout"]
        persisting, new = identify_persisting_issues(current, prior)
        assert persisting == []
        assert new == ["Test coverage section missing edge cases"]

    def test_empty_current_returns_empty(self):
        """Empty current issues returns empty tuples."""
        persisting, new = identify_persisting_issues([], ["some issue"])
        assert persisting == []
        assert new == []

    def test_empty_prior_all_new(self):
        """Empty prior issues means all current are new.

        Input: current_issues=["issue1", "issue2"], prior_issues=[]
        Output: persisting=[], new=["issue1", "issue2"]
        """
        current = ["issue1", "issue2"]
        persisting, new = identify_persisting_issues(current, [])
        assert persisting == []
        assert new == ["issue1", "issue2"]

    def test_mixed_persisting_and_new(self):
        """Mixed: one persists, one new.

        Input: current=["No rollback plan for database migration",
                        "Test coverage section missing edge cases"],
               prior=["Missing error handling for API timeout",
                      "No rollback plan for database migration",
                      "Security section omits OWASP references"]
        Output: persisting=["No rollback plan for database migration"],
                new=["Test coverage section missing edge cases"]
        """
        current = [
            "No rollback plan for database migration",
            "Test coverage section missing edge cases",
        ]
        prior = [
            "Missing error handling for API timeout",
            "No rollback plan for database migration",
            "Security section omits OWASP references",
        ]
        persisting, new = identify_persisting_issues(current, prior)
        assert persisting == ["No rollback plan for database migration"]
        assert new == ["Test coverage section missing edge cases"]


# ── Tests for summarize_verdict ──


class TestSummarizeVerdict:
    def test_iteration_1_all_new(self, json_verdict_iter1: str):
        """Iteration 1 with no prior: all issues are new."""
        summary = summarize_verdict(json_verdict_iter1, iteration=1, prior_issues=None)
        assert summary.iteration == 1
        assert summary.verdict == "BLOCKED"
        assert summary.issue_count == 3
        assert summary.persisting_issues == []
        assert len(summary.new_issues) == 3

    def test_iteration_2_with_persistence(self, json_verdict_iter2: str):
        """Iteration 2 with prior issues: detects persistence."""
        prior = [
            "Missing error handling for API timeout",
            "No rollback plan for database migration",
            "Security section omits OWASP references",
        ]
        summary = summarize_verdict(json_verdict_iter2, iteration=2, prior_issues=prior)
        assert summary.iteration == 2
        assert summary.verdict == "BLOCKED"
        assert summary.issue_count == 2
        assert "No rollback plan for database migration" in summary.persisting_issues
        assert "Test coverage section missing edge cases" in summary.new_issues

    def test_approved_verdict(self, json_verdict_iter3: str):
        """Approved verdict has zero issues."""
        summary = summarize_verdict(json_verdict_iter3, iteration=3, prior_issues=[])
        assert summary.iteration == 3
        assert summary.verdict == "APPROVED"
        assert summary.issue_count == 0
        assert summary.persisting_issues == []
        assert summary.new_issues == []


# ── Test ID 035: Summary line format includes all required fields (REQ-3) ──


class TestFormatSummaryLine:
    def test_blocked_with_persisting(self):
        """Test ID 035: Summary line with persisting issues."""
        summary = VerdictSummary(
            iteration=2,
            verdict="BLOCKED",
            issue_count=2,
            persisting_issues=["No rollback plan for database migration"],
            new_issues=["Test coverage section missing edge cases"],
        )
        line = format_summary_line(summary)
        assert "Iteration 2" in line
        assert "BLOCKED" in line
        assert "2 issues" in line
        assert '1 persists: "No rollback plan for database migration"' in line
        assert "1 new" in line

    def test_blocked_all_new(self):
        """Summary line iteration 1, all new."""
        summary = VerdictSummary(
            iteration=1,
            verdict="BLOCKED",
            issue_count=3,
            persisting_issues=[],
            new_issues=["a", "b", "c"],
        )
        line = format_summary_line(summary)
        assert "Iteration 1" in line
        assert "BLOCKED" in line
        assert "3 issues" in line
        assert "0 persists" in line
        assert "3 new" in line

    def test_approved(self):
        """Approved verdict summary line."""
        summary = VerdictSummary(
            iteration=3,
            verdict="APPROVED",
            issue_count=0,
            persisting_issues=[],
            new_issues=[],
        )
        line = format_summary_line(summary)
        assert "Iteration 3" in line
        assert "APPROVED" in line
        assert "0 issues" in line

    def test_multiple_persisting(self):
        """Multiple persisting issues listed."""
        summary = VerdictSummary(
            iteration=3,
            verdict="BLOCKED",
            issue_count=3,
            persisting_issues=["issue1", "issue2"],
            new_issues=["issue3"],
        )
        line = format_summary_line(summary)
        assert '2 persists: "issue1", "issue2"' in line
        assert "1 new" in line