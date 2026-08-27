"""The fence-density heuristic advises; it never vetoes (#2539).

run-issue331-200815: five review rounds converging under a certifying
adversarial reviewer, then `change_instructions_specific` failed at "found 8,
expected at least 9" on a 454-line spec — and the threshold is derived from
line count, so the drafter's compliance (adding a snippet, 7→8) grew the spec
and moved the demand with it (8→9). Second instance of the class after
#2526's str.isupper: a cheap proxy vetoing content the judgment layer was
certifying.

Verified while fixing: the fence counter counts EVERY pair regardless of tag
(the "skips non-Python fences" hypothesis belonged to the api-symbols
checker's scan note; the killed draft's 8 blocks were all ```python). Pinned
below anyway, so the property can never silently become false.
"""

from __future__ import annotations

from unittest.mock import patch

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_change_instructions_specific,
    validate_completeness,
)


def _spec_of(lines: int, fenced_blocks: list[str]) -> str:
    """A spec of ~`lines` lines carrying exactly the given fenced blocks."""
    body = list(fenced_blocks)
    prose_needed = max(0, lines - sum(b.count("\n") + 1 for b in body) - 2)
    body.append("\n".join(f"prose line {i}" for i in range(prose_needed)))
    return "# Spec\n\n" + "\n\n".join(body)


def _block(tag: str, i: int = 0) -> str:
    return f"```{tag}\ncontent {i}\n```"


class TestTheObservedCase:
    """454 lines, 8 blocks — the killed draft's exact shape."""

    OBSERVED = _spec_of(454, [_block("python", i) for i in range(8)])

    def test_the_measurement_still_reports_honestly(self):
        result = check_change_instructions_specific(self.OBSERVED)
        assert result["passed"] is False
        assert "found 8" in result["details"]
        assert "by tag: python=8" in result["details"]

    def test_the_node_advisory_flags_and_never_hard_blocks(self):
        """The acceptance: this shape passes-or-advisory-flags, never gates.
        The N5 reviewer judges concreteness directly; the heuristic's veto
        is revoked at the node."""
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={"check_name": "modify_files_have_excerpts",
                          "passed": True, "details": "ok"},
        ):
            out = validate_completeness({
                "spec_draft": self.OBSERVED,
                "files_to_modify": [],
                "pattern_references": [],
                "repo_root": "",
                "lld_content": "",
                "review_iteration": 0,
                "max_iterations": 3,
            })
        assert "change_instructions_specific" not in " ".join(
            out["completeness_issues"]
        ), "the density heuristic must never enter the blocking issue list"
        assert not any(
            "Insufficient code blocks" in issue
            for issue in out["completeness_issues"]
        )

    def test_the_advisory_is_visible_not_silent(self, capsys):
        validate_completeness({
            "spec_draft": self.OBSERVED,
            "files_to_modify": [],
            "pattern_references": [],
            "repo_root": "",
            "lld_content": "",
        })
        printed = capsys.readouterr().out
        assert "[ADVISORY]" in printed
        assert "found 8" in printed


class TestEveryFenceTagCounts:
    """Ask 2, pinned: guidance in diff or text fences satisfies the counter,
    so complying with the check's own advice moves its number."""

    def test_diff_and_text_fences_count_toward_the_threshold(self):
        blocks = (
            [_block("python", i) for i in range(3)]
            + [_block("diff", i) for i in range(3)]
            + [_block("text", i) for i in range(3)]
        )
        spec = _spec_of(440, blocks)  # threshold: 440 // 50 = 8; found 9
        result = check_change_instructions_specific(spec)
        assert "found 8" not in result["details"]
        # The fence count itself is satisfied — if the check reports at all,
        # it is not about block count.
        assert "Insufficient code blocks" not in result["details"]

    def test_the_failure_names_the_per_tag_composition(self):
        spec = _spec_of(454, [_block("python"), _block("diff"), _block("text")])
        result = check_change_instructions_specific(spec)
        assert result["passed"] is False
        assert "diff=1" in result["details"]
        assert "text=1" in result["details"]
        assert "python=1" in result["details"]


class TestCompliedWithoutEffect:
    """Ask 3: a complaint whose shape survives every revision with only its
    counts moving is the drafter complying and the check absorbing it —
    marked at the cap halt as evidence against the check."""

    def _at_cap(self, details_now: str, prior_failures: list[str]):
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={"check_name": "x", "passed": False,
                          "details": details_now},
        ):
            state = {
                "spec_draft": "# Spec\n\n" + ("body line\n" * 40),
                "files_to_modify": [],
                "pattern_references": [],
                "repo_root": "",
                "lld_content": "",
                "review_iteration": 3,
                "max_iterations": 3,
                "checks_shown_to_drafter": [],
                "prior_completeness_breakdown": [],
            }
            first = validate_completeness(state)
            state["checks_shown_to_drafter"] = first["checks_shown_to_drafter"]
            state["prior_completeness_breakdown"] = [
                {"iteration": i, "failures": [
                    f if f != "__NOW__" else details_now
                    for f in prior_failures
                ] + [
                    x for x in first["completeness_issues"] if x != details_now
                ]}
                for i in range(2)
            ]
            return validate_completeness(state)

    def test_counts_moving_under_a_fixed_shape_is_marked(self, capsys):
        out = self._at_cap(
            "Insufficient code blocks: found 8, expected 9 for a 454-line spec.",
            ["Insufficient code blocks: found 7, expected 8 for a 441-line spec."],
        )
        capsys.readouterr()
        assert "COMPLIED WITHOUT EFFECT" in out["error_message"]
        assert "false positive" in out["error_message"]

    def test_byte_identical_is_still_the_declined_class(self, capsys):
        same = "Spec calls methods not found: `isupper`"
        out = self._at_cap(same, [same])
        capsys.readouterr()
        assert "IDENTICAL complaint" in out["error_message"]
        assert "COMPLIED WITHOUT EFFECT" not in out["error_message"]

    def test_a_shape_change_is_still_kept_failing(self, capsys):
        out = self._at_cap(
            "missing excerpt for a.py",
            ["a completely different complaint about b.py"],
        )
        capsys.readouterr()
        assert "shown to the drafter and survived a revision" in out["error_message"]
        assert "COMPLIED WITHOUT EFFECT" not in out["error_message"]
