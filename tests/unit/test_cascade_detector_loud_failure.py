"""A cascade pattern that does not compile stops detection (ADR 0236, #3585).

The detector skipped a pattern whose regex did not compile, "silently", so
detection ran with fewer patterns and could answer "allow" for output the
missing pattern would have blocked. It now raises naming the pattern and the
regex error.

The patterns are passed explicitly here: the detector's per-call config read
and its config path are open issues of their own and are not exercised.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import pytest

from assemblyzero.hooks.cascade_detector import detect_cascade_risk


def _pattern(pattern_id: str, regex: str, weight: float = 0.9) -> dict:
    return {
        "id": pattern_id,
        "category": "continuation_offer",
        "regex": regex,
        "description": "test pattern",
        "risk_weight": weight,
        "examples": [],
    }


def test_81_a_pattern_that_does_not_compile_raises_naming_it():
    patterns = [_pattern("OK-1", r"(?i)\bshould I continue\b"), _pattern("BAD-1", "(unclosed")]

    with pytest.raises(ValueError) as raised:
        detect_cascade_risk("Should I continue with the next issue?", patterns=patterns)

    assert "BAD-1" in str(raised.value)
    assert "(unclosed" in str(raised.value)


def test_81_valid_patterns_still_match():
    result = detect_cascade_risk(
        "Should I continue with the next issue?",
        patterns=[_pattern("OK-1", r"(?i)\bshould I continue\b")],
    )

    assert result["detected"] is True
    assert result["matched_patterns"] == ["OK-1"]
