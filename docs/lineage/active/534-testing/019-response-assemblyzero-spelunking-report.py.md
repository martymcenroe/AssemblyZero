

```python
"""Report generator — produces Markdown and JSON drift reports.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import json
from pathlib import Path

from assemblyzero.spelunking.models import (
    DriftReport,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)


_DRIFT_PASS_THRESHOLD = 90.0
_CLAIM_TEXT_MAX_LEN = 50
_EVIDENCE_MAX_LEN = 100


def generate_drift_report(
    report: DriftReport,
    output_format: str = "markdown",
) -> str:
    """Generate a human-readable drift report from verification results."""
    if output_format == "markdown":
        return _generate_markdown_report(report)
    elif output_format == "json":
        return _generate_json_report(report)
    else:
        raise ValueError(
            f"Unsupported output format: {output_format}. Use 'markdown' or 'json'."
        )


def _generate_markdown_report(report: DriftReport) -> str:
    """Generate Markdown formatted drift report."""
    lines: list[str] = []

    # Header
    lines.append("# Spelunking Drift Report")
    lines.append("")
    lines.append(f"**Target:** {report.target_document}")
    lines.append(f"**Generated:** {report.generated_at.isoformat()}")
    lines.append(f"**Drift Score:** {_format_drift_score_badge(report.drift_score)}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Claims | {report.total_claims} |")
    lines.append(f"| Matching | {report.matching_claims} |")

    mismatch_count = sum(
        1 for r in report.results if r.status == VerificationStatus.MISMATCH
    )
    stale_count = sum(
        1 for r in report.results if r.status == VerificationStatus.STALE
    )
    error_count = sum(
        1 for r in report.results if r.status == VerificationStatus.ERROR
    )

    lines.append(f"| Mismatches | {mismatch_count} |")
    lines.append(f"| Stale | {stale_count} |")
    lines.append(f"| Errors | {error_count} |")
    lines.append("")

    # Detail table
    if report.results:
        lines.append("## Claim Details")
        lines.append("")
        lines.append("| Source | Line | Claim | Status | Expected | Actual | Evidence |")
        lines.append("|--------|------|-------|--------|----------|--------|----------|")
        for result in report.results:
            lines.append(_format_verification_row(result))
        lines.append("")

    return "\n".join(lines)


def _generate_json_report(report: DriftReport) -> str:
    """Generate JSON formatted drift report."""
    data = {
        "target_document": str(report.target_document),
        "generated_at": report.generated_at.isoformat(),
        "drift_score": report.drift_score,
        "total_claims": report.total_claims,
        "matching_claims": report.matching_claims,
        "results": [
            {
                "claim_type": r.claim.claim_type.value,
                "source_file": str(r.claim.source_file),
                "source_line": r.claim.source_line,
                "claim_text": r.claim.claim_text,
                "status": r.status.value,
                "expected_value": r.claim.expected_value,
                "actual_value": r.actual_value,
                "evidence": r.evidence,
                "error_message": r.error_message,
            }
            for r in report.results
        ],
    }
    return json.dumps(data, indent=2)


def generate_probe_summary(
    probe_results: list[ProbeResult],
) -> str:
    """Generate a summary of all probe results in Markdown table format."""
    lines: list[str] = []

    lines.append("# Probe Summary")
    lines.append("")
    lines.append("| Probe | Status | Findings | Time (ms) |")
    lines.append("|-------|--------|----------|-----------|")

    total_findings = 0
    total_time = 0.0
    passed_count = 0
    failed_count = 0

    for result in probe_results:
        status_badge = "[PASS]" if result.passed else "[FAIL]"
        finding_count = len(result.findings)
        total_findings += finding_count
        total_time += result.execution_time_ms

        if result.passed:
            passed_count += 1
        else:
            failed_count += 1

        lines.append(
            f"| {result.probe_name} | {status_badge} | {finding_count} | {result.execution_time_ms} |"
        )

    # Totals row
    lines.append(
        f"| **Totals** | **{passed_count} passed, {failed_count} failed** "
        f"| **{total_findings}** | **{round(total_time, 1)}** |"
    )
    lines.append("")

    return "\n".join(lines)


def _format_verification_row(result: VerificationResult) -> str:
    """Format a single VerificationResult as a Markdown table row."""
    source = str(result.claim.source_file)
    line = str(result.claim.source_line)
    claim_text = result.claim.claim_text
    if len(claim_text) > _CLAIM_TEXT_MAX_LEN:
        claim_text = claim_text[: _CLAIM_TEXT_MAX_LEN - 3] + "..."
    status = result.status.value.upper()
    expected = result.claim.expected_value
    actual = result.actual_value if result.actual_value is not None else "-"
    evidence = result.evidence
    if len(evidence) > _EVIDENCE_MAX_LEN:
        evidence = evidence[: _EVIDENCE_MAX_LEN - 3] + "..."

    return f"| {source} | {line} | {claim_text} | {status} | {expected} | {actual} | {evidence} |"


def _format_drift_score_badge(score: float) -> str:
    """Format drift score with pass/fail indicator."""
    if score >= _DRIFT_PASS_THRESHOLD:
        return f"[PASS] {score}%"
    return f"[FAIL] {score}%"
```
