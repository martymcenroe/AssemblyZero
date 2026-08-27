"""Zero requirements is a named event, and no gate goes vacuously green (#2552).

The near-miss of 2026-08-27: the leavings sweep had cleared the LLD working
copy, and a resumed impl stage would have fallen back to the spec — whose
Section 3 is "Current State", so every extraction pattern returns empty —
with only a WARN line saying so. Verification against the code sharpened
the filed diagnosis: the N1 fast path has refused a zero denominator since
2026-02-01 (`728f0116`) and #496's Gate 2 blocks empty requirements before
the fast path is consulted — both now PINNED here, since nothing tested
them — while the N4b completeness gate's verdict was genuinely
requirement-blind (its own #2024 comment records a prior zero-requirements
verdict) and load_lld's WARN scrolled past unnamed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from assemblyzero.workflows.testing.nodes.completeness_gate import (
    completeness_gate,
)
from assemblyzero.workflows.testing.nodes.load_lld import (
    describe_zero_requirements,
)
from assemblyzero.workflows.testing.nodes.review_test_plan import (
    _run_mechanical_gates,
    check_requirement_coverage,
)


class TestTheEmptySetIsNamed:
    def test_a_missing_lld_reads_as_unreadable_and_names_the_search(self):
        reason = describe_zero_requirements(
            331, Path("C:/repo"), "C:/repo/spec.md", None, False
        )
        assert reason.startswith("requirements unreadable")
        assert "LLD-331.md" in reason
        assert "docs" in reason and "lld" in reason
        assert "searched:" in reason

    def test_an_unreadable_lld_names_its_path(self):
        reason = describe_zero_requirements(
            331, Path("C:/repo"), "C:/repo/spec.md",
            Path("C:/repo/docs/lld/active/LLD-331.md"), False,
        )
        assert reason.startswith("requirements unreadable")
        assert "LLD-331.md" in reason
        assert "could not be read" in reason

    def test_a_readable_pair_with_nothing_to_extract_reads_as_declared_none(self):
        reason = describe_zero_requirements(
            331, Path("C:/repo"), "C:/repo/spec.md",
            Path("C:/repo/docs/lld/active/LLD-331.md"), True,
        )
        assert reason.startswith("no requirements declared")
        assert "LLD-331.md" in reason
        assert "spec.md" in reason


class TestN1RefusesTheZeroDenominator:
    """The two guards the filed diagnosis missed, pinned so a refactor
    cannot silently drop them."""

    def test_zero_zero_is_never_full_coverage(self):
        """The 2026-02-01 guard: 0/0 reads as passed=False, so the
        fast path can never skip the reviewer on an empty set."""
        result = check_requirement_coverage([], [])
        assert result["passed"] is False
        assert result["total"] == 0

    def test_gate_two_blocks_empty_requirements(self):
        errors = _run_mechanical_gates({
            "test_scenarios": [{"name": "test_x", "type": "unit"}],
            "requirements": [],
            "lld_content": "word " * 60,
        })
        assert any("No requirements" in e for e in errors)

    def test_gate_two_quotes_the_recorded_reason(self):
        """#2552: the block names WHY — declared-none vs unreadable, with
        the searched path — instead of leaving the operator to hunt."""
        errors = _run_mechanical_gates({
            "test_scenarios": [{"name": "test_x", "type": "unit"}],
            "requirements": [],
            "requirements_empty_reason": (
                "requirements unreadable: no LLD found for issue #331 "
                "under C:/repo/docs/lld/active"
            ),
            "lld_content": "word " * 60,
        })
        gate_two = next(e for e in errors if "No requirements" in e)
        assert "requirements unreadable" in gate_two
        assert "LLD" in gate_two


class TestN4bRefusesTheEmptySet:
    def _state(self, tmp_path: Path, requirements, reason=""):
        return {
            "repo_root": str(tmp_path),
            "issue_number": 331,
            "implementation_files": [str(tmp_path / "impl.py")],
            "test_files": [],
            "requirements": requirements,
            "requirements_empty_reason": reason,
            "iteration_count": 0,
        }

    def test_zero_requirements_is_never_a_pass(self, tmp_path, capsys):
        out = completeness_gate(self._state(
            tmp_path, [],
            reason="requirements unreadable: no LLD found for issue #331",
        ))
        capsys.readouterr()
        assert out["completeness_verdict"] == "BLOCK"
        assert "zero requirements" in out["error_message"]
        assert "requirements unreadable" in out["error_message"]
        assert "#2552" in out["error_message"]

    def test_a_zero_with_no_recorded_reason_still_refuses_and_says_so(
        self, tmp_path, capsys
    ):
        out = completeness_gate(self._state(tmp_path, []))
        capsys.readouterr()
        assert out["completeness_verdict"] == "BLOCK"
        assert "no recorded reason" in out["error_message"]

    def test_a_populated_set_still_passes_layer_one(self, tmp_path, capsys):
        """The inverse: the gate's ordinary verdict is untouched when a
        real requirement set is present."""
        (tmp_path / "impl.py").write_text("x = 1\n", encoding="utf-8")
        with patch(
            "assemblyzero.workflows.testing.nodes.completeness_gate."
            "run_ast_analysis",
            return_value={
                "verdict": "PASS",
                "issues": [],
                "ast_analysis_ms": 1,
                "gemini_review_ms": None,
            },
        ):
            out = completeness_gate(self._state(tmp_path, ["REQ-1: exists"]))
        capsys.readouterr()
        assert out["completeness_verdict"] == "PASS"
        assert out["error_message"] == ""
