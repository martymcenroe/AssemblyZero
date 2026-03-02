

```python
"""Probe: ADR Collision — detects duplicate numeric prefixes in docs/adrs/.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)


_ADR_PREFIX_PATTERN = re.compile(r"^(\d{4})-")


def probe_adr_collision(
    repo_root: Path,
    adr_dir: Path | None = None,
) -> ProbeResult:
    """Scan docs/adrs/ for duplicate numeric prefixes."""
    start = time.monotonic()

    if adr_dir is None:
        adr_dir = repo_root / "docs" / "adrs"

    if not adr_dir.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="adr_collision",
            findings=[],
            passed=True,
            summary="ADR directory not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    # Group files by prefix
    prefix_map: dict[str, list[str]] = {}
    for file_path in sorted(adr_dir.iterdir()):
        if file_path.is_file() and file_path.suffix == ".md":
            match = _ADR_PREFIX_PATTERN.match(file_path.name)
            if match:
                prefix = match.group(1)
                prefix_map.setdefault(prefix, []).append(file_path.name)

    findings: list[VerificationResult] = []
    for prefix, files in sorted(prefix_map.items()):
        if len(files) > 1:
            claim = Claim(
                claim_type=ClaimType.UNIQUE_ID,
                source_file=adr_dir,
                source_line=0,
                claim_text=f"ADR prefix {prefix} should be unique",
                expected_value="1",
                verification_command=f"check_unique_prefix {adr_dir}",
            )
            findings.append(
                VerificationResult(
                    claim=claim,
                    status=VerificationStatus.MISMATCH,
                    actual_value=str(len(files)),
                    evidence=f"Prefix {prefix} used by: {', '.join(files)}",
                )
            )

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No ADR collisions found"
    else:
        prefixes = [f.claim.claim_text.split()[2] for f in findings]
        summary = f"{len(findings)} ADR prefix collision(s): {', '.join(prefixes)}"

    return ProbeResult(
        probe_name="adr_collision",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```
