

```python
"""Probe: Stale Timestamps — flags documents with old or missing timestamps.

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
from assemblyzero.spelunking.verifiers import verify_timestamp_freshness


_TIMESTAMP_PATTERN = re.compile(
    r"[Ll]ast\s+[Uu]pdated:?\s*(\d{4}-\d{2}-\d{2})"
)


def probe_stale_timestamps(
    repo_root: Path,
    max_age_days: int = 30,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    """Flag documents with 'Last Updated' more than max_age_days old. Reports missing timestamps."""
    start = time.monotonic()

    if doc_dirs is None:
        doc_dirs = [repo_root / "docs", repo_root]

    md_files: list[Path] = []
    for doc_dir in doc_dirs:
        if not doc_dir.exists():
            continue
        if doc_dir == repo_root:
            md_files.extend(doc_dir.glob("*.md"))
        else:
            md_files.extend(doc_dir.rglob("*.md"))

    findings: list[VerificationResult] = []

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        match = _TIMESTAMP_PATTERN.search(content)

        if match is None:
            # Missing timestamp — report as finding
            claim = Claim(
                claim_type=ClaimType.TIMESTAMP,
                source_file=md_file,
                source_line=0,
                claim_text="missing timestamp",
                expected_value="",
                verification_command="check_timestamp_exists",
            )
            findings.append(
                VerificationResult(
                    claim=claim,
                    status=VerificationStatus.MISMATCH,
                    evidence="No 'Last Updated' timestamp found",
                )
            )
        else:
            date_str = match.group(1)
            claim = Claim(
                claim_type=ClaimType.TIMESTAMP,
                source_file=md_file,
                source_line=0,
                claim_text=f"Last Updated: {date_str}",
                expected_value=date_str,
                verification_command=f"check_freshness {date_str}",
            )
            result = verify_timestamp_freshness(date_str, max_age_days, claim)
            if result.status != VerificationStatus.MATCH:
                findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    stale_count = sum(
        1 for f in findings if f.status == VerificationStatus.STALE
    )
    missing_count = sum(
        1 for f in findings
        if f.status == VerificationStatus.MISMATCH
        and f.claim.claim_text == "missing timestamp"
    )

    parts = []
    if stale_count:
        parts.append(f"{stale_count} stale document(s)")
    if missing_count:
        parts.append(f"{missing_count} missing timestamp(s)")
    summary = ", ".join(parts) if parts else "No stale timestamps found"

    return ProbeResult(
        probe_name="stale_timestamps",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )
```
