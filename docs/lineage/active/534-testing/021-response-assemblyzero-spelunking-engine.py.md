

```python
"""Core spelunking engine — orchestrates claim extraction, verification, and probe execution.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from assemblyzero.spelunking.extractors import extract_claims_from_markdown
from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    DriftReport,
    ProbeResult,
    SpelunkingCheckpoint,
    VerificationResult,
    VerificationStatus,
)
from assemblyzero.spelunking.verifiers import verify_claim


def run_spelunking(
    target_document: Path,
    repo_root: Path,
    checkpoints: list[SpelunkingCheckpoint] | None = None,
) -> DriftReport:
    """Run full spelunking analysis on a target document."""
    if checkpoints:
        claims = _checkpoints_to_claims(checkpoints)
    else:
        claims = extract_claims_from_markdown(target_document)

    results: list[VerificationResult] = []
    for claim in claims:
        result = verify_claim(claim, repo_root)
        results.append(result)

    return DriftReport(
        target_document=target_document,
        results=results,
    )


def _checkpoints_to_claims(
    checkpoints: list[SpelunkingCheckpoint],
) -> list[Claim]:
    """Convert SpelunkingCheckpoints to Claim objects."""
    claims: list[Claim] = []
    for cp in checkpoints:
        # Determine claim type from verify_command
        if "glob" in cp.verify_command and "count" in cp.verify_command:
            claim_type = ClaimType.FILE_COUNT
        elif "path_exists" in cp.verify_command:
            claim_type = ClaimType.FILE_EXISTS
        elif "grep_absent" in cp.verify_command:
            claim_type = ClaimType.TECHNICAL_FACT
        elif "check_freshness" in cp.verify_command:
            claim_type = ClaimType.TIMESTAMP
        elif "check_unique_prefix" in cp.verify_command:
            claim_type = ClaimType.UNIQUE_ID
        else:
            claim_type = ClaimType.STATUS_MARKER

        # Extract expected value from verify_command
        parts = cp.verify_command.split()
        expected = parts[-1] if len(parts) > 1 else cp.claim

        claims.append(
            Claim(
                claim_type=claim_type,
                source_file=Path(cp.source_file),
                source_line=0,
                claim_text=cp.claim,
                expected_value=expected,
                verification_command=cp.verify_command,
            )
        )
    return claims


def _get_probe_registry() -> dict[str, Callable[[Path], ProbeResult]]:
    """Return mapping of probe names to their functions. Lazy imports."""
    from assemblyzero.workflows.janitor.probes.inventory_drift import (
        probe_inventory_drift,
    )
    from assemblyzero.workflows.janitor.probes.dead_references import (
        probe_dead_references,
    )
    from assemblyzero.workflows.janitor.probes.adr_collision import (
        probe_adr_collision,
    )
    from assemblyzero.workflows.janitor.probes.stale_timestamps import (
        probe_stale_timestamps,
    )
    from assemblyzero.workflows.janitor.probes.readme_claims import (
        probe_readme_claims,
    )
    from assemblyzero.workflows.janitor.probes.persona_status import (
        probe_persona_status,
    )

    return {
        "inventory_drift": probe_inventory_drift,
        "dead_references": probe_dead_references,
        "adr_collision": probe_adr_collision,
        "stale_timestamps": probe_stale_timestamps,
        "readme_claims": probe_readme_claims,
        "persona_status": probe_persona_status,
    }


def run_probe(
    probe_name: str,
    repo_root: Path,
) -> ProbeResult:
    """Run a single named spelunking probe."""
    registry = _get_probe_registry()

    if probe_name not in registry:
        raise ValueError(f"Unknown probe: {probe_name}")

    probe_fn = registry[probe_name]
    start = time.monotonic()

    try:
        result = probe_fn(repo_root)
    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        return ProbeResult(
            probe_name=probe_name,
            findings=[],
            passed=False,
            summary=f"Error: {exc}",
            execution_time_ms=round(elapsed_ms, 1),
        )

    # Update execution time with actual measured time
    elapsed_ms = (time.monotonic() - start) * 1000
    result.execution_time_ms = round(elapsed_ms, 1)
    return result


def run_all_probes(
    repo_root: Path,
) -> list[ProbeResult]:
    """Run all registered spelunking probes and return results."""
    registry = _get_probe_registry()
    results: list[ProbeResult] = []

    for probe_name in registry:
        start = time.monotonic()
        try:
            result = registry[probe_name](repo_root)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = ProbeResult(
                probe_name=probe_name,
                findings=[],
                passed=False,
                summary=f"Error: {exc}",
                execution_time_ms=round(elapsed_ms, 1),
            )
        else:
            elapsed_ms = (time.monotonic() - start) * 1000
            result.execution_time_ms = round(elapsed_ms, 1)

        results.append(result)

    return results
```
