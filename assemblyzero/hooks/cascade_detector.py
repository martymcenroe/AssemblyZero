"""Core cascade detection engine.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Analyzes model output text for cascade-risk patterns using multi-category
weighted regex scoring.
"""

from __future__ import annotations

import re
from typing import Literal

from assemblyzero.hooks.cascade_patterns import (
    CascadePattern,
    load_default_patterns,
    load_user_patterns,
    merge_patterns,
)
from assemblyzero.hooks.types import CascadeDetectionResult, CascadeRiskLevel

# Maximum input length to prevent performance issues
MAX_INPUT_LENGTH = 10_000


# Pre-compiled permission prompt patterns
_PERMISSION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)^allow (bash|file write|read|write|edit|listdirectory|grep|websearch)\b"),
    re.compile(r"(?i)^allow \w+ tool\b"),
    re.compile(r"(?i)allow (bash command|file write|file read):"),
    re.compile(r"(?i)\(y/n\)\s*$"),
]


def detect_cascade_risk(
    model_output: str,
    patterns: list[CascadePattern] | None = None,
    risk_threshold: float = 0.6,
) -> CascadeDetectionResult:
    """Analyze model output text for cascade-risk patterns.

    Scans the output against all registered patterns, calculates a
    composite risk score, and returns a detection result with
    recommended action.

    Args:
        model_output: The raw text output from the AI model.
        patterns: Optional override patterns. If None, loads from
                  default pattern set merged with user patterns.
        risk_threshold: Minimum composite score (0.0-1.0) to
                       trigger a block recommendation.

    Returns:
        CascadeDetectionResult with detection status and recommended action.
    """
    # Guard: empty/None input
    if not model_output:
        return _make_allow_result()

    # Truncate to max length for performance
    text = model_output[:MAX_INPUT_LENGTH]

    # Short-circuit: don't block permission prompts
    if is_permission_prompt(text):
        return _make_allow_result()

    # Load patterns
    if patterns is None:
        defaults = load_default_patterns()
        user = load_user_patterns()
        patterns = merge_patterns(defaults, user)

    # Compile and match patterns
    matched: list[tuple[CascadePattern, re.Match[str]]] = []
    for pattern in patterns:
        try:
            compiled = re.compile(pattern["regex"])
            match = compiled.search(text)
            if match:
                matched.append((pattern, match))
        except re.error:
            # Skip invalid patterns silently
            continue

    # Compute risk score
    score, risk_level = compute_risk_score(matched)

    # Determine action based on risk level
    if risk_level in (CascadeRiskLevel.NONE, CascadeRiskLevel.LOW):
        recommended_action: Literal["allow", "block_and_prompt", "block_and_alert"] = "allow"
    elif risk_level == CascadeRiskLevel.MEDIUM:
        recommended_action = "block_and_prompt"
    else:  # HIGH or CRITICAL
        recommended_action = "block_and_alert"

    # Apply threshold override: if score is below threshold, allow
    if score < risk_threshold and recommended_action != "allow":
        recommended_action = "allow"
        risk_level = CascadeRiskLevel.LOW if score >= 0.3 else CascadeRiskLevel.NONE

    detected = recommended_action != "allow"

    # Build matched text (first match text for display)
    matched_text = ""
    if matched:
        # Use the match with the highest risk weight for display
        best_match = max(matched, key=lambda m: m[0]["risk_weight"])
        matched_text = best_match[1].group(0)

    return {
        "detected": detected,
        "risk_level": risk_level,
        "matched_patterns": [p["id"] for p, _ in matched],
        "matched_text": matched_text,
        "recommended_action": recommended_action,
        "confidence": min(score, 1.0),
    }


def compute_risk_score(
    matched_patterns: list[tuple[CascadePattern, re.Match[str]]],
) -> tuple[float, CascadeRiskLevel]:
    """Compute composite risk score from matched patterns.

    Uses weighted scoring: each matched pattern contributes its
    risk_weight. Multiple matches in different categories compound.
    Same-category matches don't double-count (max weight per category).

    Args:
        matched_patterns: List of (pattern, match) tuples from scanning.

    Returns:
        Tuple of (score: 0.0-1.0, risk_level: CascadeRiskLevel).
    """
    if not matched_patterns:
        return 0.0, CascadeRiskLevel.NONE

    # Group by category, take max weight per category
    category_max: dict[str, float] = {}
    for pattern, _ in matched_patterns:
        cat = pattern["category"]
        weight = pattern["risk_weight"]
        if cat not in category_max or weight > category_max[cat]:
            category_max[cat] = weight

    # Sum max weights across categories
    raw_score = sum(category_max.values())

    # Cap at 1.0
    score = min(raw_score, 1.0)

    # Map to risk level
    if score < 0.3:
        risk_level = CascadeRiskLevel.NONE
    elif score < 0.5:
        risk_level = CascadeRiskLevel.LOW
    elif score < 0.7:
        risk_level = CascadeRiskLevel.MEDIUM
    elif score < 0.9:
        risk_level = CascadeRiskLevel.HIGH
    else:
        risk_level = CascadeRiskLevel.CRITICAL

    return score, risk_level


def is_permission_prompt(text: str) -> bool:
    """Distinguish genuine permission prompts from cascade offers.

    Permission prompts (e.g., "Allow bash command: git push?") should
    NOT be blocked. This function detects the permission prompt format
    to avoid false positives.

    Args:
        text: Text to check.

    Returns:
        True if this looks like a genuine permission/tool approval prompt.
    """
    if not text:
        return False

    # Check against all permission patterns
    # Strip leading/trailing whitespace for matching
    stripped = text.strip()
    for pattern in _PERMISSION_PATTERNS:
        if pattern.search(stripped):
            return True

    return False


def _make_allow_result() -> CascadeDetectionResult:
    """Create a default 'allow' result (no cascade detected)."""
    return {
        "detected": False,
        "risk_level": CascadeRiskLevel.NONE,
        "matched_patterns": [],
        "matched_text": "",
        "recommended_action": "allow",
        "confidence": 0.0,
    }