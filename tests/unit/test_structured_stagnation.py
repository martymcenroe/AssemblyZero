"""Tests for Issue #503: Structured two-strike stagnation detection.

Validates that same_blocking_issues uses structured JSON comparison
when both verdicts are JSON, falling back to line-overlap heuristic.
"""

import json

import pytest

from assemblyzero.core.verdict_schema import (
    same_blocking_issues,
    _structured_stagnation,
    _line_overlap_stagnation,
)


def _json_verdict(verdict: str, issues: list[dict], rationale: str = "Summary") -> str:
    return json.dumps({
        "verdict": verdict,
        "rationale": rationale,
        "blocking_issues": issues,
    })


class TestStructuredStagnation:
    """Test structured (JSON) stagnation detection."""

    def test_identical_issues_detected(self):
        issues = [
            {"section": "Coverage", "issue": "REQ-3 has no test", "severity": "BLOCKING"},
        ]
        current = _json_verdict("BLOCKED", issues)
        previous = _json_verdict("BLOCKED", issues)
        assert same_blocking_issues(current, previous) is True

    def test_different_issues_not_stagnant(self):
        current = _json_verdict("BLOCKED", [
            {"section": "Coverage", "issue": "REQ-3 has no test", "severity": "BLOCKING"},
        ])
        previous = _json_verdict("BLOCKED", [
            {"section": "Quality", "issue": "Missing edge cases", "severity": "HIGH"},
        ])
        assert same_blocking_issues(current, previous) is False

    def test_similar_issues_detected(self):
        """Fuzzy match should catch slightly reworded issues."""
        current = _json_verdict("BLOCKED", [
            {"section": "Coverage", "issue": "REQ-3 missing test scenario", "severity": "BLOCKING"},
        ])
        previous = _json_verdict("BLOCKED", [
            {"section": "Coverage", "issue": "REQ-3 missing test scenarios", "severity": "BLOCKING"},
        ])
        assert same_blocking_issues(current, previous) is True

    def test_different_sections_not_stagnant(self):
        """Same issue text but different section = not stagnant."""
        current = _json_verdict("BLOCKED", [
            {"section": "Coverage", "issue": "Missing validation", "severity": "BLOCKING"},
        ])
        previous = _json_verdict("BLOCKED", [
            {"section": "Error Handling", "issue": "Missing validation", "severity": "BLOCKING"},
        ])
        assert same_blocking_issues(current, previous) is False

    def test_partial_overlap_not_stagnant(self):
        """<50% overlap should not be considered stagnation."""
        current = _json_verdict("BLOCKED", [
            {"section": "A", "issue": "Issue 1 recurring", "severity": "BLOCKING"},
            {"section": "B", "issue": "New issue 2", "severity": "BLOCKING"},
            {"section": "C", "issue": "New issue 3", "severity": "BLOCKING"},
        ])
        previous = _json_verdict("BLOCKED", [
            {"section": "A", "issue": "Issue 1 recurring", "severity": "BLOCKING"},
        ])
        # 1 out of 3 matches = 33% < 50%
        assert same_blocking_issues(current, previous) is False

    def test_majority_overlap_is_stagnant(self):
        """>50% overlap is stagnation."""
        current = _json_verdict("BLOCKED", [
            {"section": "A", "issue": "Issue 1", "severity": "BLOCKING"},
            {"section": "B", "issue": "Issue 2", "severity": "BLOCKING"},
        ])
        previous = _json_verdict("BLOCKED", [
            {"section": "A", "issue": "Issue 1", "severity": "BLOCKING"},
            {"section": "B", "issue": "Issue 2", "severity": "BLOCKING"},
            {"section": "C", "issue": "Issue 3", "severity": "HIGH"},
        ])
        # 2 out of 2 match = 100% > 50%
        assert same_blocking_issues(current, previous) is True

    def test_no_blocking_issues_not_stagnant(self):
        current = _json_verdict("APPROVED", [])
        previous = _json_verdict("BLOCKED", [
            {"section": "A", "issue": "Issue 1", "severity": "BLOCKING"},
        ])
        assert same_blocking_issues(current, previous) is False

    def test_empty_feedback_not_stagnant(self):
        assert same_blocking_issues("", "some feedback") is False
        assert same_blocking_issues("some feedback", "") is False
        assert same_blocking_issues("", "") is False


class TestLineOverlapFallback:
    """Test that unstructured verdicts use line-overlap."""

    def test_markdown_overlap_detected(self):
        current = "## Issues\n- Missing test for REQ-3\n- No edge cases\n- Incomplete coverage\n"
        previous = "## Issues\n- Missing test for REQ-3\n- No edge cases\n- Incomplete coverage\n"
        assert same_blocking_issues(current, previous) is True

    def test_markdown_different_content(self):
        current = "## Issues\n- Missing test for REQ-3\n"
        previous = "## Issues\n- Great work, all tests pass\n"
        assert same_blocking_issues(current, previous) is False

    def test_mixed_json_and_markdown_uses_fallback(self):
        """When one is JSON and other is markdown, fall back to line overlap."""
        json_verdict = _json_verdict("BLOCKED", [
            {"section": "A", "issue": "Issue 1", "severity": "BLOCKING"},
        ])
        markdown = "## Issues\n- Different format entirely\n- No overlap\n"
        # JSON parses but markdown doesn't, so falls back to line overlap
        # No line overlap between the two, so not stagnant
        assert same_blocking_issues(json_verdict, markdown) is False


class TestStructuredStagnationInternal:
    """Test _structured_stagnation directly."""

    def test_threshold_respected(self):
        current = {
            "blocking_issues": [
                {"section": "Cov", "issue": "missing test XYZ"},
            ]
        }
        previous = {
            "blocking_issues": [
                {"section": "Cov", "issue": "missing test XYZ"},
            ]
        }
        # At threshold 0.8, identical text should match
        assert _structured_stagnation(current, previous, 0.8) is True
        # At threshold 1.0, only exact match (which this is)
        assert _structured_stagnation(current, previous, 1.0) is True

    def test_empty_current_issues(self):
        current = {"blocking_issues": []}
        previous = {"blocking_issues": [{"section": "A", "issue": "B"}]}
        assert _structured_stagnation(current, previous, 0.8) is False
