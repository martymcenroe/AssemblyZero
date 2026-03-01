"""Unit tests for verdict pattern mining tool.

Issue #308: Tests for parse_verdict_file, classify_issue, mine_patterns.
"""

import pytest
from pathlib import Path

from tools.mine_verdict_patterns import (
    VerdictInfo,
    Pattern,
    parse_verdict_file,
    classify_issue,
    mine_patterns,
    format_report,
    main,
)


SAMPLE_BLOCK_VERDICT = """\
# LLD Review: 99-feature

## Identity Confirmation
I am Gemini 3 Pro.

## Pre-Flight Gate
PASSED

## Review Summary
Coverage is below threshold.

## Requirement Coverage Analysis (MANDATORY)

**Coverage Calculation:** 3 requirements covered / 5 total = **60%**

**Verdict:** **BLOCK** (<95%)

### Missing Test Scenarios
1. Test Requirement 4: Verify edge case
2. Test Requirement 5: Verify error handling

## Tier 1: BLOCKING Issues
### Coverage
- [ ] Coverage below 95% threshold (60%)
"""

SAMPLE_PASS_VERDICT = """\
# LLD Review: 100-other

## Pre-Flight Gate
PASSED

## Requirement Coverage Analysis (MANDATORY)

**Coverage Calculation:** 7 requirements covered / 7 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found.
"""


class TestParseVerdictFile:

    def test_parses_block_verdict(self, tmp_path):
        vf = tmp_path / "99-lld" / "003-verdict.md"
        vf.parent.mkdir()
        vf.write_text(SAMPLE_BLOCK_VERDICT, encoding="utf-8")
        info = parse_verdict_file(vf)
        assert info is not None
        assert info.verdict == "BLOCK"
        assert info.issue_id == "99-lld"
        assert info.coverage_pct == 60.0
        assert len(info.missing_tests) == 2

    def test_parses_pass_verdict(self, tmp_path):
        vf = tmp_path / "100-lld" / "003-verdict.md"
        vf.parent.mkdir()
        vf.write_text(SAMPLE_PASS_VERDICT, encoding="utf-8")
        info = parse_verdict_file(vf)
        assert info is not None
        assert info.verdict == "PASS"
        assert info.coverage_pct == 100.0
        assert len(info.blocking_issues) == 0

    def test_handles_missing_file(self, tmp_path):
        info = parse_verdict_file(tmp_path / "nonexistent.md")
        assert info is None


class TestClassifyIssue:

    def test_classifies_coverage(self):
        matches = classify_issue("Coverage below 95% threshold")
        categories = [m[0] for m in matches]
        assert "low_coverage" in categories

    def test_classifies_missing_tests(self):
        matches = classify_issue("Missing test scenarios for requirement 3")
        categories = [m[0] for m in matches]
        assert "missing_test_scenarios" in categories

    def test_classifies_vague_assertions(self):
        matches = classify_issue("Assert that it works correctly is too vague")
        categories = [m[0] for m in matches]
        assert "vague_assertions" in categories

    def test_uncategorized_fallback(self):
        matches = classify_issue("Something completely unique and novel")
        categories = [m[0] for m in matches]
        assert "uncategorized" in categories


class TestMinePatterns:

    def test_finds_recurring_patterns(self):
        verdicts = [
            VerdictInfo(
                path=Path("a"), issue_id="99-lld", verdict="BLOCK",
                blocking_issues=["Coverage below 95%"],
                missing_tests=["Test 1"],
            ),
            VerdictInfo(
                path=Path("b"), issue_id="100-lld", verdict="BLOCK",
                blocking_issues=["Coverage below threshold"],
                missing_tests=["Test 2", "Test 3"],
            ),
            VerdictInfo(
                path=Path("c"), issue_id="101-lld", verdict="PASS",
                blocking_issues=[], missing_tests=[],
            ),
        ]
        patterns = mine_patterns(verdicts, min_occurrences=2)
        categories = [p.category for p in patterns]
        assert "low_coverage" in categories
        assert "missing_test_scenarios" in categories

    def test_respects_min_occurrences(self):
        verdicts = [
            VerdictInfo(
                path=Path("a"), issue_id="99-lld", verdict="BLOCK",
                blocking_issues=["Coverage below 95%"],
                missing_tests=[],
            ),
        ]
        patterns = mine_patterns(verdicts, min_occurrences=3)
        assert len(patterns) == 0

    def test_skips_pass_verdicts(self):
        verdicts = [
            VerdictInfo(
                path=Path("a"), issue_id="99-lld", verdict="PASS",
                blocking_issues=["This shouldn't count"],
                missing_tests=[],
            ),
        ]
        patterns = mine_patterns(verdicts, min_occurrences=1)
        assert len(patterns) == 0


class TestFormatReport:

    def test_produces_markdown(self):
        verdicts = [
            VerdictInfo(
                path=Path("a"), issue_id="99-lld", verdict="BLOCK",
                coverage_pct=60.0,
            ),
            VerdictInfo(
                path=Path("b"), issue_id="100-lld", verdict="PASS",
                coverage_pct=100.0,
            ),
        ]
        report = format_report(verdicts, [])
        assert "# Verdict Pattern Mining Report" in report
        assert "BLOCK verdicts: 1" in report
        assert "PASS verdicts: 1" in report

    def test_includes_patterns(self):
        patterns = [
            Pattern(
                category="low_coverage",
                description="Coverage below threshold",
                occurrences=5,
                example_verdicts=["99-lld: Coverage 60%"],
                suggested_rule="Not auto-fixable",
            ),
        ]
        report = format_report([], patterns)
        assert "low_coverage" in report
        assert "5 occurrences" in report


class TestMain:

    def test_missing_directory(self):
        exit_code = main(["--lineage-dir", "/nonexistent/path"])
        assert exit_code == 1

    def test_runs_on_real_lineage(self):
        """Integration test: runs on actual lineage if available."""
        lineage = Path("docs/lineage/active")
        if not lineage.exists():
            pytest.skip("No lineage directory")
        exit_code = main(["--dry-run"])
        assert exit_code == 0
