

```python
"""Data models for the spelunking audit system.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ClaimType(Enum):
    """Categories of verifiable claims."""

    FILE_COUNT = "file_count"
    FILE_EXISTS = "file_exists"
    TECHNICAL_FACT = "technical_fact"
    STATUS_MARKER = "status_marker"
    UNIQUE_ID = "unique_id"
    TIMESTAMP = "timestamp"


class VerificationStatus(Enum):
    """Result of verifying a single claim."""

    MATCH = "match"
    MISMATCH = "mismatch"
    STALE = "stale"
    UNVERIFIABLE = "unverifiable"
    ERROR = "error"


@dataclass
class Claim:
    """A single verifiable factual claim extracted from a document."""

    claim_type: ClaimType
    source_file: Path
    source_line: int
    claim_text: str
    expected_value: str
    verification_command: str


@dataclass
class VerificationResult:
    """Result of verifying a single claim against reality."""

    claim: Claim
    status: VerificationStatus
    actual_value: Optional[str] = None
    evidence: str = ""
    verified_at: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


@dataclass
class DriftReport:
    """Aggregated results for a spelunking run."""

    target_document: Path
    results: list[VerificationResult]
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def total_claims(self) -> int:
        """Count of all claims checked."""
        return len(self.results)

    @property
    def matching_claims(self) -> int:
        """Count of claims that match reality."""
        return sum(
            1 for r in self.results if r.status == VerificationStatus.MATCH
        )

    @property
    def drift_score(self) -> float:
        """Percentage of verifiable claims that match reality. Target: >90%."""
        verifiable = [
            r
            for r in self.results
            if r.status != VerificationStatus.UNVERIFIABLE
        ]
        if not verifiable:
            return 100.0
        matching = sum(
            1 for r in verifiable if r.status == VerificationStatus.MATCH
        )
        return round((matching / len(verifiable)) * 100, 1)


@dataclass
class SpelunkingCheckpoint:
    """YAML-serializable checkpoint for existing 08xx audits to declare."""

    claim: str
    verify_command: str
    source_file: str
    last_verified: Optional[datetime] = None
    last_status: Optional[VerificationStatus] = None


@dataclass
class ProbeResult:
    """Result from an automated spelunking probe."""

    probe_name: str
    findings: list[VerificationResult]
    passed: bool
    summary: str
    execution_time_ms: float
```
