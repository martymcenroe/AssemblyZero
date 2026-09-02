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
rp = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.revision_pinning"
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

    def test_spec_test_functions_have_assertions_addresses_each_stub(self):
        """#2706, swept BEFORE its first live roll. The complaint backticks
        the function and cites its `lines N-M` span -- both halves of the
        vocabulary -- so the drafter's rewrite of the stub body lands."""
        draft = (
            "# Spec\n\n## 10. Test Mapping\n\n### 10.1 Per-criterion test "
            "functions\n\n```python\nimport pytest\n\n\n"
            "def test_req_1_value():\n    # expected: value == 1\n    pass\n```\n"
        )
        verdict = _classify(
            vc.check_spec_test_functions_have_assertions(draft, 1, []), draft
        )
        assert "test_req_1_value" in verdict.tokens
        assert verdict.verdict == ADDRESSED

    def test_spec_test_fixtures_resolvable_addresses_the_function(self):
        """#2707. The complaint names the function and the parameter, and
        cites the function's span, so both the signature and the body that
        uses the phantom fixture are open to the drafter."""
        draft = (
            "# Spec\n\n## 10. Test Mapping\n\n### 10.1 Per-criterion test "
            "functions\n\n```python\n"
            "def test_req_1_value(mocker):\n    assert mocker is not None\n```\n"
        )
        verdict = _classify(
            vc.check_spec_test_fixtures_resolvable(draft, "", ""), draft
        )
        assert {"test_req_1_value", "mocker"} <= set(verdict.tokens)
        assert verdict.verdict == ADDRESSED

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

    def test_manifest_traceability_names_the_rows_it_holds(self):
        """#2593, repaired. The no-tests branch reported a COUNT ("binds 2
        row(s)") while holding the ids, and a count addresses nothing --
        `_ROW_ID_RE` reads `N4.1` exactly, so the one vocabulary pinning has
        for this artifact was being withheld by the only check that has the
        artifact.

        **The fixture's key is corrected here, and that matters.** #2593 was
        filed with `{"id": "N4.1"}`, but `check_manifest_traceability` reads
        `row_id` -- the key `assertion_manifest.to_dicts` actually emits. With
        the wrong key the row list came out EMPTY, which is why the issue
        quotes "binds 0 row(s)" and frames the zero-bound branch as the
        notable one. Measured against the real shape the message said "binds
        2 row(s)" and still named neither id, so the defect was real and the
        framing was an artifact of the fixture. A test carrying the wrong key
        would have gone green on a message that names nothing.
        """
        rows = [
            {"row_id": "N4.1", "criterion": "needle within arc"},
            {"row_id": "N4.2", "criterion": "band background"},
        ]
        result = vc.check_manifest_traceability(NO_CITING_TESTS, rows)
        verdict = _classify(result, NO_CITING_TESTS)

        assert "N4.1" in result["details"]
        assert "N4.2" in result["details"]
        assert verdict.tokens == ("n4.1", "n4.2", "section 10")
        assert verdict.verdict == ADDRESSED

    def test_modify_files_have_excerpts_demands_an_addition(self):
        """#2591, repaired. The complaint backticks a file path that is absent
        from the draft BY DEFINITION -- absence is what it is complaining
        about -- so the named-content vocabulary can never address it. It is
        the addition exemption's business, and `MUST include a code block` is
        now in the addition vocabulary.

        The fixture is unchanged from when this test lived in
        `TestUnaddressableToday`; only the expected verdict moved.
        """
        verdict = _classify(
            vc.check_modify_files_have_excerpts(NO_CITING_TESTS, MODIFY_FILES),
            NO_CITING_TESTS,
        )

        assert "src/render.py" in verdict.tokens
        assert verdict.demands_addition is True
        assert verdict.verdict == DEMANDS_ADDITION

    def test_a_complaint_about_existing_content_still_demands_nothing(self):
        """The safety half of #2591's ruling, and the reason the vocabulary is
        a closed enumeration rather than a general notion of "add".

        A wider addition vocabulary frees more locked regions, so a complaint
        about content that ALREADY EXISTS must not trip it. The density
        heuristic (#2592) is the sharpest case: it names no target at all, so
        if anything were going to over-match it would.

        Note which checks are deliberately NOT in this list.
        `functions_have_io_examples` and `data_structures_have_examples` read
        like complaints about existing content and are not -- both say "MUST
        have at least one example", which is a demand to ADD one. They are in
        the vocabulary on purpose. Writing this test the other way round is
        what surfaced that: the first draft asserted
        `functions_have_io_examples` demands nothing, and it was wrong.
        """
        existing_content_complaints = [
            vc.check_change_instructions_specific(SPARSE_SPEC),
            vc.check_manifest_traceability(
                NO_CITING_TESTS, [], lld_content=""
            ),
        ]
        for check_result in existing_content_complaints:
            assert rp.demands_additions([check_result["details"]]) is False, (
                f"{check_result['check_name']}: {check_result['details']}"
            )

    def test_the_vocabulary_is_a_closed_set(self):
        """Six phrasings, enumerated from the checks' own `details=` strings.

        The rule that makes this regex legitimate is that its members can be
        written down (`voice-analysis.md` §28a's closed-set test). If a new
        demand phrasing appears, it is added here deliberately rather than
        matched by a general notion of "add", which would free locked regions
        nobody demanded.
        """
        import re as _re

        members = rp._ADDITION_DEMAND_RE.pattern.split("|")

        assert len(members) == 6
        for phrase, should_match in (
            ("3 criteria have no test in the spec", True),
            ("Each Modify file MUST include a code block showing", True),
            ("Each function MUST have at least one example", True),
            ("Add the block inside that subsection", True),
            ("Change instructions lack diff-level specificity", False),
            ("test(s) tracing to nothing: test_a, test_b", False),
        ):
            assert bool(_re.search(rp._ADDITION_DEMAND_RE, phrase)) is should_match, (
                phrase
            )

    def test_the_demand_to_add_tests_is_exempt_under_2560(self):
        """Naming the rows is necessary and not sufficient.

        This branch demands NEW tests, and #2560's rule is that a locked
        region introducing one passes only when the round's failures carry
        the addition vocabulary. Without it, pinning would refuse the very
        tests the complaint asks for -- the #2686 deadlock shape, one check
        over.
        """
        rows = [{"row_id": "N4.1", "criterion": "needle within arc"}]
        details = vc.check_manifest_traceability(NO_CITING_TESTS, rows)["details"]

        assert rp.demands_additions([details]) is True


class TestUnaddressableToday:
    """The deadlock class, pinned. Each test asserts the CURRENT broken state
    against its filed issue. Repairing one flips its test, which is the
    signal to move it into TestAddressableToday."""

    def test_change_instructions_specific_parses_nothing_at_all(self):
        """#2592. A density heuristic about EXISTING content that names no
        target whatsoever -- the purest form of the class."""
        verdict = _classify(
            vc.check_change_instructions_specific(SPARSE_SPEC), SPARSE_SPEC
        )
        assert verdict.tokens == ()
        assert verdict.ranges == ()
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
            "check_spec_test_functions_have_assertions",
            "check_spec_test_fixtures_resolvable",
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
