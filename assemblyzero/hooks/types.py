"""Shared type definitions for cascade detection.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Contains CascadeRiskLevel and CascadeDetectionResult so that hooks and
telemetry modules can import them without circular dependencies.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, TypedDict


class CascadeRiskLevel(Enum):
    """Severity of detected cascade risk."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CascadeDetectionResult(TypedDict):
    """Result from analyzing a model output block."""

    detected: bool
    risk_level: CascadeRiskLevel
    matched_patterns: list[str]
    matched_text: str
    recommended_action: Literal["allow", "block_and_prompt", "block_and_alert"]
    confidence: float