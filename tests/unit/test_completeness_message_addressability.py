"""Can pinning read each completeness complaint? (#2557, swept under #2576.)

Registry class 3 — **the demanded change is never refusable**
(`docs/standards/0029-defect-class-registry.md`).

The repaired invariant from #2555 holds mechanically only for complaints the
enforcement can READ. This suite drives every real check with a fixture that
genuinely fails it, takes the REAL emitted message, and classifies it. No
message text is hardcoded: a rewording that drops an address changes the
verdict and fails the suite the day it is written, which is the whole point.

The taxonomy is three-way and the middle case matters:

* **addressed** — the message cites a line of the draft. Enforcement unlocks
  it; the drafter's mandated edit lands.
* **demands-addition** — the message demands NEW content. There is no line to
  cite by construction and #2560's exemption carries it. Correct, not a defect.
* **unaddressable** — the message targets EXISTING content in a scheme the
  vocabulary cannot read. **This is the deadlock class**: the drafter makes the
  change, pinning reverts it, the loop burns its cap on byte-identical drafts.

Four checks are currently unaddressable. Each is pinned below against its filed
issue, so the gap is a failing-in-waiting rather than a comment. When one is
repaired, its test here flips and must be moved to the addressable set.
"""
from __future__ import annotations

import importlib

import pytest

from assemblyzero.workflows.implementation_spec.message_addressability import (
    ADDRESSED,
    DEMANDS_ADDITION,
    UNADDRESSABLE,
    addresses_draft,
)

#: `nodes/__init__.py` re-exports the FUNCTION `validate_completeness`, which
#: shadows the module of the same name. Importing the module by path is the
#: only way to reach the individual checks.
vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)


# ---------------------------------------------------------------------------
# The classifier itself
# ---------------------------------------------------------------------------


class TestClassifier:
    def test_a_backticked_span_present_in_the_draft_addresses_it(self):
        draft = "line one\nclass RenderValues:\n    pass\n"
        verdict = addresses_draft("Missing example for `RenderValues`", draft)
        assert verdict.verdict == ADDRESSED
        assert verdict.matched_lines == (2,)

    def test_a_token_absent_from_the_draft_addresses_nothing(self):
        """Parsing is not addressing. A backticked name the draft does not
        contain reads like an address and unlocks nothing."""
        draft = "line one\nclass RenderValues:\n    pass\n"
        verdict = addresses_draft("Missing file `src/absent.py`", draft)
        assert verdict.tokens == ("src/absent.py",)
        assert verdict.verdict == UNADDRESSABLE

    def test_a_dashed_line_range_inside_the_draft_addresses_it(self):
        draft = "\n".join(f"line {n}" for n in range(1, 21))
        verdict = addresses_draft("Retag the fence at lines 3-5", draft)
        assert verdict.verdict == ADDRESSED
        assert verdict.matched_lines == (3, 4, 5)

    def test_an_out_of_bounds_range_is_reported_not_counted(self):
        """Worse than no citation: it reads as an address and unlocks
        nothing."""
        draft = "one\ntwo\n"
        verdict = addresses_draft("see lines 80-90", draft)
        assert verdict.out_of_bounds == ((80, 90),)
        assert verdict.verdict == UNADDRESSABLE

    def test_a_bare_line_number_is_not_an_address(self):
        """#2555: the fence complaint carried 'line 1' from a quoted
        SyntaxError -- a position inside a snippet, not a draft address."""
        draft = "one\ntwo\nthree\n"
        verdict = addresses_draft(
            "SyntaxError: invalid decimal literal (<unknown>, line 1)", draft
        )
        assert verdict.ranges == ()
        assert verdict.verdict == UNADDRESSABLE

    def test_an_addition_demand_is_its_own_verdict(self):
        draft = "## Section 10 Tests\n"
        verdict = addresses_draft(
            "2 LLD pass criterion(s) have no test in the spec. Add a test "
            "for each.",
            draft,
        )
        assert verdict.verdict == DEMANDS_ADDITION

    def test_addressed_beats_demands_addition(self):
        """A citable line is the stronger guarantee; the exemption is a
        fallback, not an equal alternative."""
        draft = "one\ntwo\nthree\nfour\nfive\n"
        verdict = addresses_draft(
            "lines 2-3 have no test in the spec", draft
        )
        assert verdict.demands_addition is True
        assert verdict.verdict == ADDRESSED


# ---------------------------------------------------------------------------
# Fixtures that genuinely fail a real check
# ---------------------------------------------------------------------------

FUNCTION_WITH_PARAMS = """# Implementation Spec

## Section 6 Signatures

def compute_needle_angle(value, redline):
    pass
"""

FUNCTION_ZERO_ARG = """# Implementation Spec

## Section 6 Signatures

def compute_needle_angle():
    pass
"""

SPARSE_SPEC = """# Implementation Spec

## Section 8 Change Instructions

Update the module to handle the new case appropriately and carefully.
"""

NO_CITING_TESTS = """# Implementation Spec

## Section 10 Tests

def test_req_1_smoke():
    assert True
"""

MODIFY_FILES = [
    {"path": "src/render.py", "change_type": "Modify", "reason": "x"},
    {"path": "src/absent_module.py", "change_type": "Modify", "reason": "y"},
]


def _classify(check_result, draft):
    assert check_result["passed"] is False, (
        f"fixture no longer fails {check_result['check_name']} -- the sweep "
        f"is classifying a PASS message, which proves nothing"
    )
    return addresses_draft(check_result["details"], draft)


class TestAddressableToday:
    """Checks whose failure message the enforcement can read. Each assertion
    is a rewording guard: change the message so it drops its address and this
    fails."""

    def test_function_spec_sections_addresses_its_subsection(self):
        """#2620's new hard gate, swept BEFORE it ships rather than discovered
        to deadlock on a live roll (#2617's discipline).

        The complaint names the subsection heading, which occurs verbatim in
        the draft, and cites its line as a dashed range -- both halves of the
        enforcement vocabulary, so pinning can read the address either way.
        """
        draft = (
            "# Spec\n\n## 5. Function Specifications\n\n"
            "### 5.1 `compute_needle_angle()`\n\n"
            "**Signature:**\n\n```python\ndef compute_needle_angle(v):\n"
            "    ...\n```\n\nNo examples here.\n"
        )
        verdict = _classify(
            vc.check_function_spec_sections_have_examples(draft), draft
        )
        assert verdict.verdict == ADDRESSED

    def test_functions_have_io_examples_addresses_a_zero_arg_function(self):
        verdict = _classify(
            vc.check_functions_have_io_examples(FUNCTION_ZERO_ARG),
            FUNCTION_ZERO_ARG,
        )
        assert verdict.verdict == ADDRESSED

    def test_functions_have_io_examples_addresses_a_parameterised_function(
        self,
    ):
        """#2590, repaired. The message backticked `name()`, and a function
        taking parameters never contains that literal -- so the identical
        complaint addressed the draft only when the arg list happened to be
        empty, and the common case was the broken one.

        The fixture is unchanged from when this test lived in
        TestUnaddressableToday; only the expected verdict moved. The bare
        name is what a `def` line actually contains."""
        verdict = _classify(
            vc.check_functions_have_io_examples(FUNCTION_WITH_PARAMS),
            FUNCTION_WITH_PARAMS,
        )
        assert verdict.tokens == ("compute_needle_angle",)
        assert verdict.matched_lines != ()
        assert verdict.verdict == ADDRESSED


class TestUnaddressableToday:
    """The deadlock class, pinned. Each test asserts the CURRENT broken state
    against its filed issue. Repairing one flips its test, which is the
    signal to move it into TestAddressableToday."""

    def test_modify_files_have_excerpts_names_a_path_not_in_the_draft(self):
        """#2591. The complaint backticks a file path that is absent from the
        draft BY DEFINITION -- absence is what it is complaining about -- and
        its 'MUST include a code block' phrasing does not trip the addition
        vocabulary, which only knows three test-specific phrases."""
        verdict = _classify(
            vc.check_modify_files_have_excerpts(NO_CITING_TESTS, MODIFY_FILES),
            NO_CITING_TESTS,
        )
        assert "src/render.py" in verdict.tokens
        assert verdict.demands_addition is False
        assert verdict.verdict == UNADDRESSABLE

    def test_change_instructions_specific_parses_nothing_at_all(self):
        """#2592. A density heuristic about EXISTING content that names no
        target whatsoever -- the purest form of the class."""
        verdict = _classify(
            vc.check_change_instructions_specific(SPARSE_SPEC), SPARSE_SPEC
        )
        assert verdict.tokens == ()
        assert verdict.ranges == ()
        assert verdict.verdict == UNADDRESSABLE

    def test_manifest_traceability_omits_the_row_ids_it_holds(self):
        """#2593. Row ids are exactly what the vocabulary parses (`_ROW_ID_RE`
        reads N4.1), and the check is holding them -- it just does not put
        them in the message on this branch."""
        rows = [
            {"id": "N4.1", "criterion": "needle within arc"},
            {"id": "N4.2", "criterion": "band background"},
        ]
        verdict = _classify(
            vc.check_manifest_traceability(NO_CITING_TESTS, rows),
            NO_CITING_TESTS,
        )
        assert verdict.tokens == ()
        assert verdict.verdict == UNADDRESSABLE


class TestTheSweepIsExhaustive:
    """The registry's claim is about EVERY check, so the set of checks this
    file drives must not drift behind the module."""

    def test_every_check_function_is_either_swept_or_declared_uncovered(self):
        exported = {
            name
            for name in dir(vc)
            if name.startswith("check_") and callable(getattr(vc, name))
        }
        swept = {
            "check_functions_have_io_examples",
            "check_function_spec_sections_have_examples",
            "check_modify_files_have_excerpts",
            "check_change_instructions_specific",
            "check_manifest_traceability",
        }
        #: Checks this sweep does NOT drive, each with the reason. They need
        #: a real repo tree, a populated symbol table, or an LLD whose
        #: pass-criteria table parses -- context a unit fixture cannot supply
        #: honestly. Naming them here is the difference between a known gap
        #: and a silent one; #2594 carries the work.
        uncovered = {
            "check_data_structures_have_examples",
            "check_pattern_references_valid",
            "check_import_targets_exist",
            "check_visual_baselines_not_self_referential",
            "check_criteria_have_tests",
            "check_error_paths_have_tests",
            "check_api_symbols_exist",
        }
        unaccounted = exported - swept - uncovered
        assert not unaccounted, (
            f"new completeness check(s) {sorted(unaccounted)} are neither "
            f"swept nor declared uncovered. Add a failing fixture and "
            f"classify the message, or list it as uncovered with a reason."
        )

    def test_the_uncovered_list_holds_no_phantoms(self):
        exported = {name for name in dir(vc) if name.startswith("check_")}
        uncovered = {
            "check_data_structures_have_examples",
            "check_pattern_references_valid",
            "check_import_targets_exist",
            "check_visual_baselines_not_self_referential",
            "check_criteria_have_tests",
            "check_error_paths_have_tests",
            "check_api_symbols_exist",
        }
        phantom = uncovered - exported
        assert not phantom, (
            f"declared uncovered but no such check exists: {sorted(phantom)}"
        )


@pytest.mark.parametrize(
    "message",
    [
        "Section 10.2 omits the error path",
        "`compute_angle` returns the wrong type",
        'the phrase "band background" is missing',
        "row N4.2 has no citing test",
        "test_req_8_chrome_housing asserts nothing",
    ],
)
def test_the_vocabulary_parses_each_documented_scheme(message):
    """The five schemes the registry claims are readable, each pinned. If a
    vocabulary change drops one, standard 0029's class-3 entry is wrong and
    this says so."""
    verdict = addresses_draft(message, "")
    assert verdict.tokens or verdict.ranges, (
        f"the vocabulary parsed nothing from {message!r}"
    )
