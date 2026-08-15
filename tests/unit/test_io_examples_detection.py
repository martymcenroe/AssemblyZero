"""functions_have_io_examples: judged at the definition site (#2302, #2303).

The fixtures are the real drafts from the 2026-08-13 boostgauge #7 roll, the
first spec-stage failure in campaign history with its drafts on disk (#2250):

* ``boostgauge-7-spec-draft-008.md`` -- the draft the stage died on. 29 public
  functions, 22 of them per-criterion test stubs the drafter added to satisfy
  ``criteria_have_tests``. Every stub carries a concrete input and an expected
  output inline; the check failed them anyway.
* ``boostgauge-7-spec-draft-006.md`` -- the revision before it. 7 functions,
  no test stubs, and it PASSED this check. Kept so a repair cannot be shown
  green merely by passing everything.
* ``boostgauge-7-run2-spec-draft-008.md`` and ``...-run2-final-spec.md`` --
  the SECOND 2026-08-13 run (lineage ``done/7-implspec/2026-08-13T20-44-22Z/``),
  added while settling #2300. A different document of the same class: 845 lines
  against 805, a different objective and LLD, and 23 exempt test stubs rather
  than 22. The repair holds on both, which the single-document fixture could
  not show. The final spec is included because it is the artifact the stage
  ships, and nothing else pinned it.

Two defects are pinned here. The detection was forward-only from every textual
occurrence of a name, so a function inside a long fenced block could not see
the fence it was inside, and a name repeated often got more chances than a name
written once (#2302). And test stubs were graded by the rule template 0701
writes for API functions, which it never asks of a test (#2303).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_functions_have_io_examples as check,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "io_examples"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestTheDraftTheStageDiedOn:
    """Draft 008 is the regression fixture. It was correct; the check was not."""

    @pytest.fixture
    def draft008(self):
        return _fixture("boostgauge-7-spec-draft-008.md")

    def test_it_passes(self, draft008):
        result = check(draft008)
        assert result["passed"], result["details"]

    def test_the_named_stubs_are_no_longer_reported(self, draft008):
        details = check(draft008)["details"]
        for stub in ("test_req_3", "test_req_10", "test_req_11", "test_req_12"):
            assert stub not in details, (
                f"{stub} is still reported missing. It carries a concrete input "
                f"and an expected output on its own signature line."
            )

    def test_the_skipped_tests_are_reported_not_silent(self, draft008):
        """A silent exemption is indistinguishable from a check that ran."""
        details = check(draft008)["details"]
        assert "22 test function(s) were NOT checked" in details

    def test_the_earlier_draft_still_passes(self):
        """006 passed before this repair and must still pass -- otherwise the
        change is a rewrite whose agreement with the old behaviour is unknown."""
        assert check(_fixture("boostgauge-7-spec-draft-006.md"))["passed"]


class TestTheSecondRunOfTheSameStage:
    """#2300's evidence: the repair holds on a DIFFERENT document.

    The 2026-08-13 #7 spec stage ran twice. The fixture above is the 805-line
    draft the issue cites; lineage `done/7-implspec/2026-08-13T20-44-22Z/` holds
    a second, later run whose draft 008 is 845 lines with a different objective,
    a different LLD, and 23 exempt stubs instead of 22.

    One document passing is a weaker claim than it reads as -- it can be
    satisfied by an exemption that happens to cover that document's shape. Two
    independent documents of the same class is the claim #2300 actually needs.
    """

    def test_the_second_runs_draft_passes(self):
        result = check(_fixture("boostgauge-7-run2-spec-draft-008.md"))
        assert result["passed"], result["details"]

    def test_the_second_runs_final_spec_passes(self):
        """The artifact the stage ships, which nothing else pinned."""
        result = check(_fixture("boostgauge-7-run2-final-spec.md"))
        assert result["passed"], result["details"]

    def test_its_exempt_count_differs_from_the_other_run(self):
        """Proves these are genuinely different documents rather than a copy --
        a duplicated fixture would prove nothing twice."""
        details = check(_fixture("boostgauge-7-run2-spec-draft-008.md"))["details"]
        assert "23 test function(s) were NOT checked" in details

    def test_the_graded_functions_are_still_graded(self):
        """The exemption must not have swallowed the real API surface: ten
        non-test functions are checked and pass on their own merits."""
        details = check(_fixture("boostgauge-7-run2-spec-draft-008.md"))["details"]
        assert "All 10 public non-test functions have I/O examples" in details


class TestItStillFailsUndocumentedFunctions:
    """A repair that passes everything is worse than the defect it replaced."""

    def test_bare_signature_in_prose_fails(self):
        spec = "# Spec\n\nThe module exposes a helper.\n\ndef compute_ratio(n, d):\n    ...\n"
        result = check(spec)
        assert not result["passed"]
        assert "compute_ratio" in result["details"]

    def test_signature_in_a_fence_without_concrete_values_fails(self):
        spec = "# Spec\n\n```python\ndef compute_ratio(n, d):\n    ...\n```\n"
        assert not check(spec)["passed"]

    def test_the_test_exemption_does_not_cover_neighbours(self):
        """An exempt test in the file must not launder the API function beside it."""
        spec = (
            "# Spec\n\ndef test_req_1(tmp_path):\n    pass\n\n"
            "def compute_ratio(n, d):\n    ...\n"
        )
        result = check(spec)
        assert not result["passed"]
        assert "compute_ratio" in result["details"]


class TestTheDetectionItself:
    """The two mechanical defects, isolated from the fixtures."""

    def test_an_example_above_the_signature_counts(self):
        """The old window started AT the name and ran forward, so anything
        documented above it was unreachable."""
        spec = (
            "# Spec\n\n**Input Example:** n=3, d=4\n**Output Example:** 0.75\n\n"
            "def compute_ratio(n, d):\n    ...\n"
        )
        assert check(spec)["passed"]

    def test_a_function_deep_inside_a_long_fence_counts(self):
        """The #2302 case. The opening fence is behind the definition and the
        closing fence is far ahead, so a forward search for a fence found
        neither -- while the function sat inside one the whole time."""
        spec = (
            "# Spec\n\n```python\n"
            + "# filler\n" * 400
            + "def compute_ratio(n, d):\n"
            "    # -- expected: 0.75 for n=3, d=4\n"
            "    return n / d\n"
            + "# filler\n" * 400
            + "```\n"
        )
        assert check(spec)["passed"]

    def test_the_verdict_does_not_depend_on_repetition(self):
        """Two functions documented identically must get the same verdict, no
        matter how often one of their names appears elsewhere.

        This is the `save_on_exit` asymmetry from draft 008: it occurred 34
        times and passed on a few lucky windows, while each test stub occurred
        once and failed on the same evidence.
        """
        documented = (
            "```python\ndef {name}(a):\n    # -- expected: 4 for a=2\n"
            "    return a * 2\n```\n"
        )
        once = "# Spec\n\n" + documented.format(name="alpha")
        many = (
            "# Spec\n\n"
            + documented.format(name="beta")
            + "\n".join(f"See beta for detail {i}." for i in range(30))
        )

        assert check(once)["passed"] == check(many)["passed"]

    def test_expected_is_recognised_as_an_io_word(self):
        """The drafter's own idiom. Without it, `-- expected: ...` beside a
        signature reads as no documentation at all."""
        spec = "# Spec\n\ndef compute_ratio(n, d):\n\nexpected: 0.75 when n=3 and d=4\n"
        assert check(spec)["passed"]


class TestTestFunctionsAreExempt:
    """#2303: required by one check, graded by another's rule, described by
    neither section of the template until now."""

    @pytest.mark.parametrize("name", ["test_req_1", "test_position_resets", "roundtrip_test"])
    def test_test_functions_are_not_graded(self, name):
        spec = f"# Spec\n\ndef {name}(tmp_path):\n    pass\n"
        result = check(spec)
        assert result["passed"]
        assert "NOT checked" in result["details"]

    def test_a_spec_of_only_tests_is_not_applicable_and_says_so(self):
        spec = "# Spec\n\ndef test_a():\n    pass\n\ndef test_b():\n    pass\n"
        result = check(spec)
        assert result["passed"]
        assert "not applicable" in result["details"].lower()
        assert "2 test function(s) were NOT checked" in result["details"]

    def test_private_and_dunder_are_still_skipped(self):
        spec = "# Spec\n\ndef _helper(a):\n    ...\n\ndef __init__(self):\n    ...\n"
        assert check(spec)["passed"]
