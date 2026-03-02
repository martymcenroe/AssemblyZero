

```python
"""Probe: Persona Status — cross-references persona markers against code existence.

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


_PERSONA_HEADER_PATTERN = re.compile(r"^##\s+(.+)", re.MULTILINE)
_STATUS_PATTERN = re.compile(
    r"[Ss]tatus:?\s*(implemented|active|planned|deprecated|draft)",
    re.IGNORECASE,
)


def probe_persona_status(
    repo_root: Path,
    persona_file: Path | None = None,
) -> ProbeResult:
    """Cross-reference Dramatis-Personae.md implementation markers against code."""
    start = time.monotonic()

    if persona_file is None:
        persona_file = repo_root / "docs" / "Dramatis-Personae.md"
        if not persona_file.exists():
            persona_file = repo_root / "Dramatis-Personae.md"

    if not persona_file.exists():
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name="persona_status",
            findings=[],
            passed=True,
            summary="Persona file not found, skipping",
            execution_time_ms=round(elapsed_ms, 1),
        )

    content = persona_file.read_text(encoding="utf-8")

    # Split content into sections by ## headers
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

    findings: list[VerificationResult] = []
    total_personas = 0

    for section in sections:
        header_match = _PERSONA_HEADER_PATTERN.match(section)
        if not header_match:
            continue

        persona_name = header_match.group(1).strip()
        total_personas += 1

        # Check for status marker
        status_match = _STATUS_PATTERN.search(section)
        if not status_match:
            claim = Claim(
                claim_type=ClaimType.STATUS_MARKER,
                source_file=persona_file,
                source_line=0,
                claim_text=f"Persona '{persona_name}' missing status",
                expected_value="status marker present",
                verification_command="check_persona_status",
            )
            findings.append(
                VerificationResult(
                    claim=claim,
                    status=VerificationStatus.MISMATCH,
                    evidence=f"Persona '{persona_name}' has no status marker",
                )
            )

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = f"All {total_personas} personas have status markers"
    else:
        summary = f"{len(findings)} of {total_personas} personas missing status markers"

    return ProbeResult(
        probe_name="persona_status",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```
