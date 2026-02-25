

```python
"""Unit tests for cascade detection engine.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution
Tests: T010, T030, T040, T050, T060, T080, T110, T120, T200, T210
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

from assemblyzero.hooks.cascade_detector import (
    MAX_INPUT_LENGTH,
    CascadeDetectionResult,
    CascadeRiskLevel,
    compute_risk_score,
    detect_cascade_risk,
    is_permission_prompt,
)
from assemblyzero.hooks.cascade_patterns import (
    CascadePattern,
    load_default_patterns,
    load_user_patterns,
    merge_patterns,
)


# ── Fixture loading ──

FIXTURES_PATH = Path("tests/fixtures/cascade_samples.json")


@pytest.fixture
def fixtures() -> dict:
    """Load test fixtures from cascade_samples.json."""
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def cascade_samples(fixtures: dict) -> list[dict]:
    return fixtures["cascade_samples"]


@pytest.fixture
def permission_samples(fixtures: dict) -> list[dict]:
    return fixtures["permission_prompt_samples"]


@pytest.fixture
def non_cascade_samples(fixtures: dict) -> list[dict]:
    return fixtures["non_cascade_samples"]


@pytest.fixture
def edge_case_samples(fixtures: dict) -> list[dict]:
    return fixtures["edge_case_samples"]


# ── T010: Continuation offer detection ──


class TestContinuationOfferDetection:
    """T010: Detect 'Should I continue with the next issue?' (REQ-1)."""

    def test_should_i_continue(self) -> None:
        result = detect_cascade_risk(
            "Great, issue #42 is fixed! Should I continue with issue #43?"
        )
        assert result["detected"] is True
        assert result["risk_level"] in (
            CascadeRiskLevel.MEDIUM,
            CascadeRiskLevel.HIGH,
            CascadeRiskLevel.CRITICAL,
        )
        assert result["recommended_action"] != "allow"
        assert len(result["matched_patterns"]) > 0

    def test_do_you_want_me_to_proceed(self) -> None:
        result = detect_cascade_risk("Do you want me to proceed with the next task?")
        assert result["matched_patterns"]  # At least one pattern matches
        assert "CP-002" in result["matched_patterns"]


# ── T020: Numbered choice with completion ──


class TestNumberedChoiceDetection:
    """T020: Detect '1. Yes 2. No' numbered choice after task completion (REQ-1)."""

    def test_numbered_yes_no_with_completion(self) -> None:
        result = detect_cascade_risk(
            "Done! What's next?\n1. Yes, start issue #44\n2. No, stop here"
        )
        assert result["detected"] is True
        assert result["risk_level"] == CascadeRiskLevel.CRITICAL
        assert result["recommended_action"] == "block_and_alert"


# ── T030: Permission prompt passthrough ──


class TestPermissionPromptPassthrough:
    """T030: Allow legitimate permission prompt (REQ-3)."""

    def test_bash_permission_prompt(self) -> None:
        result = detect_cascade_risk(
            "Allow bash command: git push origin main? (y/n)"
        )
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE
        assert result["recommended_action"] == "allow"

    def test_file_write_permission_prompt(self) -> None:
        result = detect_cascade_risk("Allow file write: /src/main.py? (y/n)")
        assert result["detected"] is False
        assert result["recommended_action"] == "allow"

    def test_is_permission_prompt_bash(self) -> None:
        assert is_permission_prompt("Allow bash command: git push origin main? (y/n)") is True

    def test_is_permission_prompt_file_write(self) -> None:
        assert is_permission_prompt("Allow file write: /src/main.py? (y/n)") is True

    def test_is_permission_prompt_read_tool(self) -> None:
        assert is_permission_prompt("Allow Read tool to read file: src/config.json?") is True

    def test_is_not_permission_prompt(self) -> None:
        assert is_permission_prompt("Should I continue with the next issue?") is False

    def test_is_permission_prompt_empty(self) -> None:
        assert is_permission_prompt("") is False


# ── T040: Task completion pivot ──


class TestTaskCompletionPivot:
    """T040: Detect 'I finished X. Should I do Y?' pivot (REQ-1)."""

    def test_completion_pivot(self) -> None:
        result = detect_cascade_risk(
            "I've completed the refactor. Now let me also update the tests for the new module."
        )
        assert result["detected"] is True
        assert result["risk_level"] in (
            CascadeRiskLevel.MEDIUM,
            CascadeRiskLevel.HIGH,
            CascadeRiskLevel.CRITICAL,
        )


# ── T050: Scope expansion ──


class TestScopeExpansion:
    """T050: Detect 'While I'm at it, I could also...' (REQ-1)."""

    def test_scope_expansion(self) -> None:
        result = detect_cascade_risk(
            "While I'm at it, I could also fix the related CSS issue in the sidebar."
        )
        assert result["detected"] is True
        assert result["risk_level"] in (
            CascadeRiskLevel.MEDIUM,
            CascadeRiskLevel.HIGH,
            CascadeRiskLevel.CRITICAL,
        )


# ── T060: Empty input ──


class TestEmptyInput:
    """T060: Handle empty/None model output gracefully (REQ-1)."""

    def test_empty_string(self) -> None:
        result = detect_cascade_risk("")
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE
        assert result["recommended_action"] == "allow"

    def test_none_input(self) -> None:
        # Type ignore since we're testing robustness
        result = detect_cascade_risk(None)  # type: ignore[arg-type]
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE


# ── T080: ReDoS resistance ──


class TestReDoSResistance:
    """T080: Pathological input completes fast (REQ-6)."""

    def test_redos_resistance(self) -> None:
        # Pathological input: lots of repetitive characters
        adversarial = "a" * 10000 + " Should I " + "b" * 10000
        adversarial = adversarial[:MAX_INPUT_LENGTH]  # Respect cap

        start = time.perf_counter()
        result = detect_cascade_risk(adversarial)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"ReDoS: detection took {elapsed:.3f}s (limit: 0.1s)"

    def test_redos_with_nested_quantifiers(self) -> None:
        """Ensure patterns don't cause catastrophic backtracking."""
        adversarial = "Should I " * 500 + "continue"
        adversarial = adversarial[:MAX_INPUT_LENGTH]

        start = time.perf_counter()
        _ = detect_cascade_risk(adversarial)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"ReDoS: detection took {elapsed:.3f}s (limit: 0.1s)"


# ── T110: Below threshold allow ──


class TestBelowThresholdAllow:
    """T110: Below-threshold score results in allow (REQ-1)."""

    def test_single_weak_match_below_threshold(self) -> None:
        # "Should I format this differently?" — matches CP-001 "should I" but
        # as a legitimate question. However, our regex checks "should I (continue|proceed|start|begin|move on)"
        # so this should NOT match at all.
        result = detect_cascade_risk("Should I format this differently?")
        assert result["recommended_action"] == "allow"

    def test_low_risk_single_category(self) -> None:
        # A single continuation_offer match with weight 0.5
        # Score = 0.5, which is below default threshold 0.6
        result = detect_cascade_risk("Ready to move on?")
        assert result["risk_level"] in (CascadeRiskLevel.NONE, CascadeRiskLevel.LOW)
        assert result["recommended_action"] == "allow"


# ── T120: Multi-category compounding ──


class TestMultiCategoryCompounding:
    """T120: Multi-category match produces higher score (REQ-1)."""

    def test_multi_category_higher_than_single(self) -> None:
        # Single category match
        single_result = detect_cascade_risk("Should I continue?")
        single_score = single_result["confidence"]

        # Multi-category match: continuation + task completion pivot + numbered
        multi_text = (
            "I've fixed issue #42. Should I start on issue #43?\n"
            "1. Yes, proceed\n"
            "2. No, stop here"
        )
        multi_result = detect_cascade_risk(multi_text)
        multi_score = multi_result["confidence"]

        assert multi_score > single_score, (
            f"Multi-category score ({multi_score}) should exceed "
            f"single-category score ({single_score})"
        )


# ── T200/T210: Performance latency ──


class TestDetectionLatency:
    """T200/T210: Detection completes under 5ms (REQ-6)."""

    def test_typical_input_latency(self) -> None:
        """T200: 2000-char model output."""
        text = "Here is a summary of the changes I made. " * 50  # ~2050 chars
        text = text[:2000]

        total = 0.0
        runs = 100
        for _ in range(runs):
            start = time.perf_counter()
            detect_cascade_risk(text)
            total += time.perf_counter() - start

        avg = total / runs
        assert avg < 0.005, f"Average detection time {avg*1000:.2f}ms exceeds 5ms limit"

    def test_max_input_latency(self) -> None:
        """T210: 10000-char model output (max cap)."""
        text = "Model output content with various words. " * 250  # ~10000 chars
        text = text[:10000]

        total = 0.0
        runs = 100
        for _ in range(runs):
            start = time.perf_counter()
            detect_cascade_risk(text)
            total += time.perf_counter() - start

        avg = total / runs
        assert avg < 0.005, f"Average detection time {avg*1000:.2f}ms exceeds 5ms limit"


# ── T220: Gemini-style cascade ──


class TestGeminiStyleCascade:
    """T220: Detects Gemini-style cascade output (REQ-1)."""

    def test_gemini_cascade(self) -> None:
        result = detect_cascade_risk(
            "I solved issue 1. Should I do issue 2?\n1. Yes\n2. No"
        )
        assert result["detected"] is True
        assert result["risk_level"] == CascadeRiskLevel.CRITICAL


# ── T230: Code output passthrough ──


class TestCodeOutputPassthrough:
    """T230: Code containing pattern keywords is NOT flagged (REQ-3)."""

    def test_code_not_flagged(self) -> None:
        result = detect_cascade_risk("def should_i_continue(): return True")
        assert result["detected"] is False


# ── T240: Legitimate question passthrough ──


class TestLegitimateQuestionPassthrough:
    """T240: Technical questions not flagged (REQ-3)."""

    def test_technical_question_not_flagged(self) -> None:
        result = detect_cascade_risk(
            "Should I use async or sync for this function?"
        )
        assert result["detected"] is False
        assert result["risk_level"] == CascadeRiskLevel.NONE


# ── T250: File write permission passthrough ──


class TestFileWritePermission:
    """T250: File write permission prompt not flagged (REQ-3)."""

    def test_file_write_not_flagged(self) -> None:
        result = detect_cascade_risk("Allow file write: /src/main.py? (y/n)")
        assert result["detected"] is False
        assert is_permission_prompt("Allow file write: /src/main.py? (y/n)") is True


# ── Compute risk score direct tests ──


class TestComputeRiskScore:
    """Direct tests for compute_risk_score function."""

    def test_empty_matches(self) -> None:
        score, level = compute_risk_score([])
        assert score == 0.0
        assert level == CascadeRiskLevel.NONE

    def test_single_category_max(self) -> None:
        """Same category, different weights -> takes max."""
        match = re.search(r"test", "test")
        assert match is not None
        patterns_matches = [
            (
                {"id": "CP-001", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.7, "examples": []},
                match,
            ),
            (
                {"id": "CP-002", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.5, "examples": []},
                match,
            ),
        ]
        score, _level = compute_risk_score(patterns_matches)  # type: ignore[arg-type]
        assert score == pytest.approx(0.7, abs=0.01)

    def test_multi_category_sum(self) -> None:
        """Different categories sum their max weights."""
        match = re.search(r"test", "test")
        assert match is not None
        patterns_matches = [
            (
                {"id": "CP-001", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.7, "examples": []},
                match,
            ),
            (
                {"id": "CP-020", "category": "task_completion_pivot", "regex": "test", "description": "", "risk_weight": 0.8, "examples": []},
                match,
            ),
        ]
        score, _level = compute_risk_score(patterns_matches)  # type: ignore[arg-type]
        assert score == pytest.approx(1.0, abs=0.01)  # 0.7 + 0.8 = 1.5 -> capped at 1.0

    def test_score_capped_at_one(self) -> None:
        match = re.search(r"test", "test")
        assert match is not None
        patterns_matches = [
            ({"id": "CP-001", "category": "continuation_offer", "regex": "test", "description": "", "risk_weight": 0.7, "examples": []}, match),
            ({"id": "CP-020", "category": "task_completion_pivot", "regex": "test", "description": "", "risk_weight": 0.8, "examples": []}, match),
            ({"id": "CP-010", "category": "numbered_choice", "regex": "test", "description": "", "risk_weight": 0.5, "examples": []}, match),
        ]
        score, level = compute_risk_score(patterns_matches)  # type: ignore[arg-type]
        assert score == 1.0
        assert level == CascadeRiskLevel.CRITICAL


# ── Pattern loading tests ──


class TestPatternLoading:
    """T070, T100, T180, T190: Pattern loading and merging."""

    def test_default_patterns_count(self) -> None:
        """Default patterns should have at least 15 entries."""
        patterns = load_default_patterns()
        assert len(patterns) >= 15

    def test_default_patterns_have_required_fields(self) -> None:
        patterns = load_default_patterns()
        for p in patterns:
            assert "id" in p
            assert "category" in p
            assert "regex" in p
            assert "description" in p
            assert "risk_weight" in p

    def test_default_patterns_compile(self) -> None:
        """All default patterns must compile without error."""
        patterns = load_default_patterns()
        for p in patterns:
            try:
                re.compile(p["regex"])
            except re.error as exc:
                pytest.fail(f"Pattern {p['id']} has invalid regex: {exc}")

    def test_corrupt_config_fallback(self, tmp_path: Path) -> None:
        """T070: Corrupt config falls back gracefully (REQ-8)."""
        corrupt_file = tmp_path / "cascade_block_patterns.json"
        corrupt_file.write_text("{invalid json!!!", encoding="utf-8")

        user_patterns = load_user_patterns(config_path=corrupt_file)
        assert user_patterns == []

        # Verify defaults still work
        defaults = load_default_patterns()
        assert len(defaults) >= 15

    def test_merge_override_by_id(self) -> None:
        """T100/T190: User pattern overrides default by ID (REQ-5)."""
        defaults: list[CascadePattern] = [
            {"id": "CP-001", "category": "continuation_offer", "regex": r"regex_a", "description": "default", "risk_weight": 0.7, "examples": []},
            {"id": "CP-010", "category": "numbered_choice", "regex": r"regex_b", "description": "default", "risk_weight": 0.5, "examples": []},
        ]
        overrides: list[CascadePattern] = [
            {"id": "CP-001", "category": "continuation_offer", "regex": r"regex_override", "description": "user override", "risk_weight": 0.8, "examples": []},
            {"id": "CP-100", "category": "scope_expansion", "regex": r"regex_new", "description": "new user", "risk_weight": 0.6, "examples": []},
        ]
        merged = merge_patterns(defaults, overrides)

        merged_map = {p["id"]: p for p in merged}
        assert merged_map["CP-001"]["regex"] == r"regex_override"
        assert merged_map["CP-001"]["risk_weight"] == 0.8
        assert merged_map["CP-010"]["regex"] == r"regex_b"
        assert "CP-100" in merged_map
        assert len(merged) == 3

    def test_user_patterns_from_json(self, tmp_path: Path) -> None:
        """T180: User patterns loaded from JSON config (REQ-5)."""
        config = {
            "version": "1.0",
            "enabled": True,
            "patterns": [
                {
                    "id": "CP-100",
                    "category": "continuation_offer",
                    "regex": r"(?i)want me to tackle the next",
                    "description": "Custom pattern",
                    "risk_weight": 0.7,
                    "examples": ["Want me to tackle the next issue?"],
                },
                {
                    "id": "CP-101",
                    "category": "scope_expansion",
                    "regex": r"(?i)I could additionally",
                    "description": "Custom expansion",
                    "risk_weight": 0.5,
                    "examples": [],
                },
            ],
            "risk_threshold": 0.6,
            "alert_on_block": True,
            "log_all_checks": False,
        }
        config_path = tmp_path / "cascade_block_patterns.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        user = load_user_patterns(config_path=config_path)
        assert len(user) == 2
        user_ids = {p["id"] for p in user}
        assert "CP-100" in user_ids
        assert "CP-101" in user_ids

    def test_disabled_config_returns_empty(self, tmp_path: Path) -> None:
        config = {"version": "1.0", "enabled": False, "patterns": [{"id": "CP-100", "category": "continuation_offer", "regex": "test", "description": "test", "risk_weight": 0.5}]}
        config_path = tmp_path / "cascade_block_patterns.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        user = load_user_patterns(config_path=config_path)
        assert user == []

    def test_missing_config_returns_empty(self, tmp_path: Path) -> None:
        user = load_user_patterns(config_path=tmp_path / "nonexistent.json")
        assert user == []


# ── Fixture-driven comprehensive tests ──


class TestFixtureSamples:
    """Run detection against all fixture samples."""

    def test_all_cascade_samples_detected(self, cascade_samples: list[dict]) -> None:
        for sample in cascade_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] is True, (
                f"Sample {sample['id']} ({sample['category']}) should be detected as cascade "
                f"but got detected={result['detected']}, risk={result['risk_level']}"
            )

    def test_all_permission_prompts_allowed(self, permission_samples: list[dict]) -> None:
        for sample in permission_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] is False, (
                f"Permission prompt {sample['id']} ({sample['category']}) should NOT be detected "
                f"but got detected={result['detected']}, patterns={result['matched_patterns']}"
            )

    def test_all_non_cascade_samples_allowed(self, non_cascade_samples: list[dict]) -> None:
        for sample in non_cascade_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] is False, (
                f"Non-cascade sample {sample['id']} ({sample['category']}) should NOT be detected "
                f"but got detected={result['detected']}, patterns={result['matched_patterns']}"
            )

    def test_edge_cases_detected(self, edge_case_samples: list[dict]) -> None:
        for sample in edge_case_samples:
            result = detect_cascade_risk(sample["text"])
            assert result["detected"] == sample["expected_detected"], (
                f"Edge case {sample['id']} ({sample['category']}) expected "
                f"detected={sample['expected_detected']} but got {result['detected']}"
            )
```
