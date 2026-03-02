"""Janitor probe: factual accuracy drift detection.

Issue #535: Feeds the Hourglass Protocol.
Runs drift analysis and returns probe-compatible result.
"""

from __future__ import annotations

import logging

from assemblyzero.workflows.death.drift_scorer import build_drift_report
from assemblyzero.workflows.janitor.state import Finding, ProbeResult

logger = logging.getLogger(__name__)


def probe_drift(codebase_root: str) -> ProbeResult:
    """Janitor probe that runs drift analysis.

    Compatible with the ProbeFunction signature: (str) -> ProbeResult.
    """
    try:
        report = build_drift_report(codebase_root)

        findings: list[Finding] = []
        severity_map = {"critical": "critical", "major": "warning", "minor": "info"}

        for f in report["findings"]:
            findings.append(
                Finding(
                    probe="drift",
                    category=f["category"],
                    message=f"{f['doc_claim']} — reality: {f['code_reality']}",
                    severity=severity_map.get(f["severity"], "info"),
                    fixable=False,
                    file_path=f["doc_file"],
                )
            )

        if findings:
            status = "findings"
        else:
            status = "ok"

        return ProbeResult(
            probe="drift",
            status=status,
            findings=findings,
        )
    except Exception as exc:
        logger.error("Drift probe failed: %s", exc)
        return ProbeResult(
            probe="drift",
            status="error",
            findings=[],
            error_message=f"{type(exc).__name__}: {exc}",
        )