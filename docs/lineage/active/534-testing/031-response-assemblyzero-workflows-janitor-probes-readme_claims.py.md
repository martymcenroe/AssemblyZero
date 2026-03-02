

```python
"""Probe: README Claims — extracts technical claims and verifies against codebase.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path

from assemblyzero.spelunking.extractors import extract_technical_claims
from assemblyzero.spelunking.models import (
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_no_contradiction


def probe_readme_claims(
    repo_root: Path,
    readme_path: Path | None = None,
) -> ProbeResult:
    """Extract technical claims from README and verify against codebase."""
    start = time.monotonic()

    if readme_path is None:
        readme_path = repo_root / "README.md"

    if not readme_path.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="readme_claims",
            findings=[],
            passed=True,
            summary="README not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    content = readme_path.read_text(encoding="utf-8")
    claims = extract_technical_claims(content, readme_path)

    findings: list[VerificationResult] = []

    for claim in claims:
        result = verify_no_contradiction(
            claim.expected_value, repo_root, claim=claim
        )
        if result.status == VerificationStatus.MISMATCH:
            findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No README contradictions found"
    else:
        terms = [f.claim.expected_value for f in findings[:3]]
        summary = f"{len(findings)} README contradiction(s): {', '.join(terms)}"

    return ProbeResult(
        probe_name="readme_claims",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```
