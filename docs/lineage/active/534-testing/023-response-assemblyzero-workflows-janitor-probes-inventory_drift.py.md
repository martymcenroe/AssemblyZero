

```python
"""Probe: Inventory Drift — counts files vs. 0003-file-inventory.md claims.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path

from assemblyzero.spelunking.extractors import extract_file_count_claims
from assemblyzero.spelunking.models import (
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_file_count


def probe_inventory_drift(
    repo_root: Path,
    inventory_path: Path | None = None,
) -> ProbeResult:
    """Count files in key directories and compare to 0003-file-inventory.md."""
    start = time.monotonic()

    if inventory_path is None:
        inventory_path = repo_root / "docs" / "standards" / "0003-file-inventory.md"

    if not inventory_path.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="inventory_drift",
            findings=[],
            passed=True,
            summary="Inventory file not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    content = inventory_path.read_text(encoding="utf-8")
    claims = extract_file_count_claims(content, inventory_path)

    findings: list[VerificationResult] = []

    for claim in claims:
        # Parse the verification command to get directory and pattern
        cmd = claim.verification_command.replace(" | count", "").replace("glob ", "")
        directory = repo_root / Path(cmd).parent
        glob_pattern = Path(cmd).name
        expected = int(claim.expected_value)

        result = verify_file_count(directory, expected, glob_pattern, claim)
        if result.status != VerificationStatus.MATCH:
            findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No inventory drift detected"
    else:
        mismatch_details = []
        for f in findings:
            mismatch_details.append(
                f"{f.claim.claim_text}: expected {f.claim.expected_value}, actual {f.actual_value}"
            )
        summary = f"{len(findings)} inventory mismatch(es): {'; '.join(mismatch_details[:3])}"

    return ProbeResult(
        probe_name="inventory_drift",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```
