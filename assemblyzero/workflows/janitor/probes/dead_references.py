"""Probe: Dead References — finds file path references pointing to nonexistent files.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path

from assemblyzero.spelunking.extractors import extract_file_reference_claims
from assemblyzero.spelunking.models import (
    ProbeResult,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_file_exists


def probe_dead_references(
    repo_root: Path,
    doc_dirs: list[Path] | None = None,
) -> ProbeResult:
    """Grep all Markdown files for file path references and verify each exists."""
    start = time.monotonic()

    if doc_dirs is None:
        doc_dirs = [repo_root / "docs"]
        # Also check root-level markdown
        doc_dirs.append(repo_root)

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
        claims = extract_file_reference_claims(content, md_file)

        for claim in claims:
            result = verify_file_exists(Path(claim.expected_value), repo_root, claim)
            if result.status == VerificationStatus.MISMATCH:
                findings.append(result)

    elapsed_ms = (time.monotonic() - start) * 1000
    passed = len(findings) == 0

    if passed:
        summary = "No dead references found"
    else:
        dead_paths = [f.claim.expected_value for f in findings[:5]]
        summary = f"{len(findings)} dead reference(s) found: {', '.join(dead_paths)}"

    return ProbeResult(
        probe_name="dead_references",
        findings=findings,
        passed=passed,
        summary=summary,
        execution_time_ms=round(elapsed_ms, 1),
    )