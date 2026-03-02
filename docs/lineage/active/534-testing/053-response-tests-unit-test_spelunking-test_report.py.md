

```python
"""Tests for drift report generation.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    DriftReport,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.report import (
    _format_drift_score_badge,
    _format_verification_row,
    generate_drift_report,
    generate_probe_summary,
)


def _make_result(status: VerificationStatus, claim_text: str = "test claim") -> VerificationResult:
    """Helper to create a VerificationResult with minimal boilerplate."""
    return VerificationResult(
        claim=Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=Path("test.md"),
            source_line=1,
            claim_text=claim_text,
            expected_value="5",
            verification_command="test",
        ),
        status=status,
        actual_value="5" if status == VerificationStatus.MATCH else "8",
    )


class TestDriftScore:
    """Tests for drift score calculation."""

    def test_T310_drift_score_calculation(self) -> None:
        """T310: 8 MATCH + 2 MISMATCH -> drift_score == 80.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(8)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 80.0

    def test_T350_unverifiable_excluded(self) -> None:
        """T350: 5 MATCH + 3 UNVERIFIABLE -> drift_score == 100.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]
        results += [_make_result(VerificationStatus.UNVERIFIABLE) for _ in range(3)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 100.0

    def test_all_match(self) -> None:
        """All matching claims -> drift_score == 100.0."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 100.0

    def test_all_mismatch(self) -> None:
        """All mismatched claims -> drift_score == 0.0."""
        results = [_make_result(VerificationStatus.MISMATCH) for _ in range(5)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 0.0

    def test_empty_results(self) -> None:
        """No results -> drift_score == 100.0."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        assert report.drift_score == 100.0

    def test_only_unverifiable(self) -> None:
        """Only UNVERIFIABLE results -> drift_score == 100.0."""
        results = [_make_result(VerificationStatus.UNVERIFIABLE) for _ in range(3)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 100.0

    def test_total_claims(self) -> None:
        """total_claims returns count of all results."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(3)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.total_claims == 5

    def test_matching_claims(self) -> None:
        """matching_claims returns count of MATCH results only."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(3)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.matching_claims == 3

    def test_stale_counted_as_non_match(self) -> None:
        """STALE results count against drift score."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(4)]
        results += [_make_result(VerificationStatus.STALE)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 80.0

    def test_error_counted_as_non_match(self) -> None:
        """ERROR results count against drift score."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(4)]
        results += [_make_result(VerificationStatus.ERROR)]

        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        assert report.drift_score == 80.0


class TestGenerateDriftReport:
    """Tests for drift report generation."""

    def test_T320_markdown_report(self) -> None:
        """T320: Generate valid Markdown with tables."""
        results = [
            _make_result(VerificationStatus.MATCH, "match claim"),
            _make_result(VerificationStatus.MISMATCH, "mismatch claim"),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "# Spelunking Drift Report" in output
        assert "| Metric | Value |" in output
        assert "Total Claims | 2" in output
        assert "[FAIL]" in output or "[PASS]" in output

    def test_T325_json_report(self) -> None:
        """T325: Generate valid JSON with all fields."""
        results = [
            _make_result(VerificationStatus.MATCH),
            _make_result(VerificationStatus.MISMATCH),
            _make_result(VerificationStatus.STALE),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        assert "drift_score" in data
        assert "results" in data
        assert "target_document" in data
        assert len(data["results"]) == 3

    def test_T327_invalid_format_raises(self) -> None:
        """T327: Invalid format raises ValueError."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        with pytest.raises(ValueError, match="Unsupported output format"):
            generate_drift_report(report, output_format="xml")

    def test_markdown_includes_target(self) -> None:
        """Markdown report includes target document path."""
        report = DriftReport(
            target_document=Path("README.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "README.md" in output

    def test_markdown_includes_generated_timestamp(self) -> None:
        """Markdown report includes generated timestamp."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "**Generated:**" in output

    def test_markdown_includes_drift_score(self) -> None:
        """Markdown report includes drift score with badge."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(5)]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "[PASS]" in output
        assert "100.0%" in output

    def test_markdown_fail_badge_for_low_score(self) -> None:
        """Markdown report shows [FAIL] for low drift score."""
        results = [_make_result(VerificationStatus.MATCH)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(9)]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "[FAIL]" in output

    def test_markdown_summary_table_counts(self) -> None:
        """Markdown summary table includes correct counts."""
        results = [
            _make_result(VerificationStatus.MATCH),
            _make_result(VerificationStatus.MISMATCH),
            _make_result(VerificationStatus.STALE),
            _make_result(VerificationStatus.ERROR),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "Matching | 1" in output
        assert "Mismatches | 1" in output
        assert "Stale | 1" in output
        assert "Errors | 1" in output

    def test_markdown_claim_details_section(self) -> None:
        """Markdown report includes Claim Details section with table rows."""
        results = [
            _make_result(VerificationStatus.MATCH, "match claim"),
            _make_result(VerificationStatus.MISMATCH, "mismatch claim"),
        ]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "## Claim Details" in output
        assert "match claim" in output
        assert "mismatch claim" in output

    def test_markdown_empty_results_no_details(self) -> None:
        """Markdown report with empty results has no Claim Details section."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="markdown")

        assert "## Claim Details" not in output
        assert "Total Claims | 0" in output

    def test_json_includes_all_result_fields(self) -> None:
        """JSON report includes all expected fields per result."""
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_EXISTS,
                source_file=Path("README.md"),
                source_line=10,
                claim_text="tools/death.py",
                expected_value="tools/death.py",
                verification_command="path_exists tools/death.py",
            ),
            status=VerificationStatus.MATCH,
            actual_value="tools/death.py",
            evidence="File exists at tools/death.py",
        )
        report = DriftReport(
            target_document=Path("README.md"),
            results=[result],
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        r = data["results"][0]
        assert r["claim_type"] == "file_exists"
        assert r["source_file"] == "README.md"
        assert r["source_line"] == 10
        assert r["claim_text"] == "tools/death.py"
        assert r["status"] == "match"
        assert r["expected_value"] == "tools/death.py"
        assert r["actual_value"] == "tools/death.py"
        assert r["evidence"] == "File exists at tools/death.py"

    def test_json_empty_results(self) -> None:
        """JSON report with no results has empty results array."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[],
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        assert data["results"] == []
        assert data["drift_score"] == 100.0
        assert data["total_claims"] == 0

    def test_json_drift_score_value(self) -> None:
        """JSON report drift_score matches DriftReport property."""
        results = [_make_result(VerificationStatus.MATCH) for _ in range(8)]
        results += [_make_result(VerificationStatus.MISMATCH) for _ in range(2)]
        report = DriftReport(
            target_document=Path("test.md"),
            results=results,
        )

        output = generate_drift_report(report, output_format="json")
        data = json.loads(output)

        assert data["drift_score"] == 80.0

    def test_default_format_is_markdown(self) -> None:
        """Default output format is markdown."""
        report = DriftReport(
            target_document=Path("test.md"),
            results=[_make_result(VerificationStatus.MATCH)],
        )

        output = generate_drift_report(report)

        assert "# Spelunking Drift Report" in output


class TestGenerateProbeSummary:
    """Tests for probe summary generation."""

    def test_T330_probe_summary_table(self) -> None:
        """T330: 3 ProbeResults -> Markdown table with [PASS]/[FAIL]."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[], passed=True, summary="OK", execution_time_ms=10.0),
            ProbeResult(probe_name="probe_b", findings=[_make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=20.0),
            ProbeResult(probe_name="probe_c", findings=[], passed=True, summary="OK", execution_time_ms=15.0),
        ]

        output = generate_probe_summary(probes)

        assert "[PASS]" in output
        assert "[FAIL]" in output
        assert "probe_a" in output
        assert "probe_b" in output
        assert "probe_c" in output

    def test_T335_totals_row(self) -> None:
        """T335: 6 ProbeResults -> totals row with counts."""
        probes = [
            ProbeResult(probe_name=f"probe_{i}", findings=[], passed=(i < 4), summary="", execution_time_ms=10.0 * (i + 1))
            for i in range(6)
        ]

        output = generate_probe_summary(probes)

        assert "**Totals**" in output
        assert "4 passed" in output
        assert "2 failed" in output

    def test_empty_probe_list(self) -> None:
        """Empty list produces header with zero totals."""
        output = generate_probe_summary([])

        assert "# Probe Summary" in output
        assert "0 passed" in output
        assert "0 failed" in output

    def test_all_passed(self) -> None:
        """All probes passed shows correct totals."""
        probes = [
            ProbeResult(probe_name=f"probe_{i}", findings=[], passed=True, summary="OK", execution_time_ms=10.0)
            for i in range(3)
        ]

        output = generate_probe_summary(probes)

        assert "3 passed" in output
        assert "0 failed" in output

    def test_all_failed(self) -> None:
        """All probes failed shows correct totals."""
        probes = [
            ProbeResult(probe_name=f"probe_{i}", findings=[_make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=10.0)
            for i in range(3)
        ]

        output = generate_probe_summary(probes)

        assert "0 passed" in output
        assert "3 failed" in output

    def test_findings_count_in_table(self) -> None:
        """Finding count is shown in the table."""
        findings = [_make_result(VerificationStatus.MISMATCH) for _ in range(3)]
        probes = [
            ProbeResult(probe_name="probe_a", findings=findings, passed=False, summary="Bad", execution_time_ms=20.0),
        ]

        output = generate_probe_summary(probes)

        # The table row should contain "3" as findings count
        lines = output.splitlines()
        probe_line = [l for l in lines if "probe_a" in l]
        assert len(probe_line) == 1
        assert "3" in probe_line[0]

    def test_execution_time_in_table(self) -> None:
        """Execution time is shown in the table."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[], passed=True, summary="OK", execution_time_ms=45.2),
        ]

        output = generate_probe_summary(probes)

        assert "45.2" in output

    def test_total_time_summed(self) -> None:
        """Total execution time is the sum of all probe times."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[], passed=True, summary="OK", execution_time_ms=10.0),
            ProbeResult(probe_name="probe_b", findings=[], passed=True, summary="OK", execution_time_ms=20.0),
            ProbeResult(probe_name="probe_c", findings=[], passed=True, summary="OK", execution_time_ms=30.0),
        ]

        output = generate_probe_summary(probes)

        assert "60.0" in output

    def test_total_findings_summed(self) -> None:
        """Total findings count is sum of all probe findings."""
        probes = [
            ProbeResult(probe_name="probe_a", findings=[_make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=10.0),
            ProbeResult(probe_name="probe_b", findings=[_make_result(VerificationStatus.MISMATCH), _make_result(VerificationStatus.MISMATCH)], passed=False, summary="Bad", execution_time_ms=10.0),
        ]

        output = generate_probe_summary(probes)

        # Totals row should contain total findings of 3
        lines = output.splitlines()
        totals_line = [l for l in lines if "**Totals**" in l]
        assert len(totals_line) == 1
        assert "**3**" in totals_line[0]

    def test_header_present(self) -> None:
        """Output starts with # Probe Summary header."""
        output = generate_probe_summary([])

        assert output.startswith("# Probe Summary")

    def test_table_header_present(self) -> None:
        """Output includes table header row."""
        output = generate_probe_summary([])

        assert "| Probe | Status | Findings | Time (ms) |" in output


class TestFormatVerificationRow:
    """Tests for verification row formatting."""

    def test_basic_row(self) -> None:
        """Basic row formatting includes all fields."""
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("README.md"),
                source_line=5,
                claim_text="11 tools",
                expected_value="11",
                verification_command="glob tools/*.py | count",
            ),
            status=VerificationStatus.MISMATCH,
            actual_value="36",
            evidence="Found 36 .py files",
        )

        row = _format_verification_row(result)

        assert "README.md" in row
        assert "5" in row
        assert "11 tools" in row
        assert "MISMATCH" in row
        assert "11" in row
        assert "36" in row

    def test_long_claim_text_truncated(self) -> None:
        """Claim text longer than 50 chars is truncated with ..."""
        long_text = "a" * 60
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("test.md"),
                source_line=1,
                claim_text=long_text,
                expected_value="5",
                verification_command="test",
            ),
            status=VerificationStatus.MATCH,
            actual_value="5",
        )

        row = _format_verification_row(result)

        assert long_text not in row
        assert "..." in row

    def test_long_evidence_truncated(self) -> None:
        """Evidence longer than 100 chars is truncated with ..."""
        long_evidence = "b" * 120
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("test.md"),
                source_line=1,
                claim_text="test",
                expected_value="5",
                verification_command="test",
            ),
            status=VerificationStatus.MATCH,
            actual_value="5",
            evidence=long_evidence,
        )

        row = _format_verification_row(result)

        assert long_evidence not in row
        assert "..." in row

    def test_none_actual_value_shows_dash(self) -> None:
        """None actual_value displays as '-'."""
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_EXISTS,
                source_file=Path("test.md"),
                source_line=1,
                claim_text="tools/ghost.py",
                expected_value="tools/ghost.py",
                verification_command="path_exists tools/ghost.py",
            ),
            status=VerificationStatus.MISMATCH,
            actual_value=None,
            evidence="File not found",
        )

        row = _format_verification_row(result)

        # Row has pipe-delimited fields; the "actual" field should be "-"
        parts = [p.strip() for p in row.split("|")]
        # Filter out empty strings from leading/trailing pipes
        parts = [p for p in parts if p]
        # parts: [source, line, claim, status, expected, actual, evidence]
        assert parts[5] == "-"

    def test_status_uppercase(self) -> None:
        """Status is displayed in uppercase."""
        result = _make_result(VerificationStatus.MATCH)

        row = _format_verification_row(result)

        assert "MATCH" in row

    def test_short_claim_not_truncated(self) -> None:
        """Claim text shorter than 50 chars is not truncated."""
        short_text = "short claim"
        result = VerificationResult(
            claim=Claim(
                claim_type=ClaimType.FILE_COUNT,
                source_file=Path("test.md"),
                source_line=1,
                claim_text=short_text,
                expected_value="5",
                verification_command="test",
            ),
            status=VerificationStatus.MATCH,
            actual_value="5",
        )

        row = _format_verification_row(result)

        assert short_text in row


class TestFormatDriftScoreBadge:
    """Tests for drift score badge formatting."""

    def test_pass_badge(self) -> None:
        """Score >= 90 gets [PASS] badge."""
        assert _format_drift_score_badge(95.0) == "[PASS] 95.0%"

    def test_fail_badge(self) -> None:
        """Score < 90 gets [FAIL] badge."""
        assert _format_drift_score_badge(75.0) == "[FAIL] 75.0%"

    def test_threshold_boundary(self) -> None:
        """Exactly 90.0 gets [PASS] badge."""
        assert _format_drift_score_badge(90.0) == "[PASS] 90.0%"

    def test_zero_score(self) -> None:
        """Score of 0.0 gets [FAIL] badge."""
        assert _format_drift_score_badge(0.0) == "[FAIL] 0.0%"

    def test_100_score(self) -> None:
        """Score of 100.0 gets [PASS] badge."""
        assert _format_drift_score_badge(100.0) == "[PASS] 100.0%"

    def test_just_below_threshold(self) -> None:
        """Score of 89.9 gets [FAIL] badge."""
        assert _format_drift_score_badge(89.9) == "[FAIL] 89.9%"

    def test_just_above_threshold(self) -> None:
        """Score of 90.1 gets [PASS] badge."""
        assert _format_drift_score_badge(90.1) == "[PASS] 90.1%"
```
