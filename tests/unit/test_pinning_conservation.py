"""Three faces of one death, as fixture (#2559, #2560, #2561).

run-issue331-111729: five healthy review rounds, then iteration 6's
edit-script died on SEARCH-ambiguous duplicates (merge-made at iteration 2
— restore-alongside-moved-copy), the fallback was an eliding rewrite
([UNCHANGED] placeholder headings), and enforcement's all-or-nothing region
rule passed the elisions wholesale: 565 lines / 28 test definitions became
381 / 10 with no refusal and no regression event for the lost tests
(#2559). The #2304 grace revision then added the demanded tests back and
enforcement refused the additions as locked-content replaces — while the
one addition that happened to diff as a pure insert landed and flipped its
check back to PASS (#2560). The halt reported "shown to the drafter and
survived a revision" with the refusal in the same log (#2561).

These tests pin the repairs: the conservation gate never emits a merge that
lost unnamed tests; a demanded addition is never refusable in the round
that demands it; the halt's survival claim requires a clean pinning record.
"""

from __future__ import annotations

from unittest.mock import patch

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    validate_completeness,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    PinningResult,
    _conservation_override,
    _is_expansion,
    demands_additions,
    enforce_pinning,
    named_line_flags,
    named_tokens,
)

# ---------------------------------------------------------------------------
# The observed shapes, miniature
# ---------------------------------------------------------------------------

#: Draft-015 shape: a passed draft whose test fence holds the criterion
#: tests. The round-6 verdict names `render_face`, which appears in §5.1
#: and inside test_req_1_alpha's body — so those blocks are named and the
#: REQ-8/9/10 test blocks are not, exactly the observed asymmetry.
PREVIOUS = """# Implementation Spec: Stingray Face

## 5. Function Specifications

### 5.1 `render_face()`

Renders the face. The cache is bounded at sixteen entries.

## 6. Change Instructions

### 6.3 `tests/visual/test_skin.py` (Add)

```python
def test_req_1_alpha():
    assert render_face(256).mode == "RGBA"

def test_req_8_chrome_housing():
    assert housing_gradient_samples() >= 3

def test_req_9_screws():
    assert screw_count() == 4

def test_req_10_bezel():
    assert bezel_radius() > 0
```

## 10. Test Mapping

Each criterion maps to one test above.

## 11. Implementation Notes

Cache eviction uses least-recently-used order.
"""

VERDICT = "REVISE: `render_face` must bound its cache at thirty-two entries."

#: The iteration-6 shape: an eliding rewrite. Every middle line is reworded
#: (no verbatim anchor survives between the head and the tail), the REQ-8/9/10
#: tests are gone, and elided sections carry [UNCHANGED] placeholders — the
#: markers found verbatim in preserved draft 018.
ELIDED = """# Implementation Spec: Stingray Face

## 5. Function Specifications (revised)

### 5.1 `render_face()` — cache bound raised

Renders the face; the cache is bounded at thirty-two entries per verdict.

## 6. Change Instructions (consolidated)

### 6.3 `tests/visual/test_skin.py` (Add, trimmed)

```python
def test_req_1_alpha():
    assert render_face(256, bound=32).mode == "RGBA"
```

## [UNCHANGED] 10. Test Mapping

## [UNCHANGED] 11. Implementation Notes
"""


class TestTheConservationGate:
    def test_the_eliding_rewrite_is_refused_entire(self):
        """The observed loss: the giant region touches a named line, so the
        walk would pass the elisions through and delete the unnamed tests.
        The gate sees the loss, sees the revision lost them too, and emits
        the previous draft entire — never the stitched result."""
        result = enforce_pinning(
            PREVIOUS, ELIDED, current_tokens=named_tokens(VERDICT),
        )
        assert result.conservation_event, "the gate must fire"
        assert "refused entire" in result.conservation_event
        assert "test_req_8_chrome_housing" in result.conservation_event
        assert result.text == PREVIOUS
        for name in ("test_req_8_chrome_housing", "test_req_9_screws",
                     "test_req_10_bezel"):
            assert name in result.text

    def test_a_targeted_revision_never_trips_the_gate(self):
        """The #2532/#2558 protections stand: a small named fix passes, an
        unnamed tinker is refused per-region, and conservation stays out of
        the way."""
        targeted = PREVIOUS.replace(
            "bounded at sixteen entries", "bounded at thirty-two entries"
        ).replace(
            "least-recently-used order", "first-in-first-out order"
        )
        result = enforce_pinning(
            PREVIOUS, targeted, current_tokens=named_tokens(VERDICT),
        )
        assert result.conservation_event == ""
        assert "thirty-two entries" in result.text, "the named fix lands"
        assert "least-recently-used order" in result.text, (
            "the unnamed tinker is restored"
        )
        assert result.refusals

    def test_a_verdict_named_test_may_be_removed(self):
        """A deletion the verdict names is not a conservation loss — the
        gate protects only what nothing asked to touch."""
        verdict = (
            "REVISE: `render_face` must bound its cache; remove "
            "`test_req_10_bezel`, the bezel is out of scope."
        )
        removed = PREVIOUS.replace(
            "\ndef test_req_10_bezel():\n    assert bezel_radius() > 0\n",
            "\n",
        )
        result = enforce_pinning(
            PREVIOUS, removed, current_tokens=named_tokens(verdict),
        )
        assert result.conservation_event == ""
        assert "test_req_10_bezel" not in result.text

    def test_the_misalignment_tier_emits_the_revision(self):
        """Tier one, at the gate's own seam: the walked output lost a test
        the revision still holds — differ misalignment, not drafter
        deletion — so the revision is emitted unenforced."""
        walked_missing_one = PREVIOUS.replace(
            "\ndef test_req_9_screws():\n    assert screw_count() == 4\n",
            "\n",
        )
        flags = named_line_flags(PREVIOUS, named_tokens(VERDICT))
        override = _conservation_override(
            PREVIOUS, PREVIOUS, walked_missing_one,
            current_tokens=named_tokens(VERDICT),
            current_flags=flags,
        )
        assert isinstance(override, PinningResult)
        assert "emitting the revision unenforced" in override.conservation_event
        assert override.text == PREVIOUS
        assert "test_req_9_screws" in override.text

    def test_a_clean_walk_returns_no_override(self):
        flags = named_line_flags(PREVIOUS, named_tokens(VERDICT))
        assert _conservation_override(
            PREVIOUS, PREVIOUS, PREVIOUS,
            current_tokens=named_tokens(VERDICT),
            current_flags=flags,
        ) is None

    def test_a_merge_minted_duplicate_emits_the_revision(self):
        """The iteration-2 event: the walk restored a superseded copy
        alongside the revision's moved one. A count beyond BOTH inputs was
        minted by the merge, never authored."""
        duplicated_walk = PREVIOUS.replace(
            "## 10. Test Mapping",
            "```python\ndef test_req_9_screws():\n"
            "    assert screw_count() == 4\n```\n\n## 10. Test Mapping",
        )
        flags = named_line_flags(PREVIOUS, named_tokens(VERDICT))
        override = _conservation_override(
            PREVIOUS, PREVIOUS, duplicated_walk,
            current_tokens=named_tokens(VERDICT),
            current_flags=flags,
        )
        assert isinstance(override, PinningResult)
        assert "multiplied" in override.conservation_event
        assert "test_req_9_screws" in override.conservation_event
        assert override.text == PREVIOUS

    def test_an_authored_dual_listing_is_not_the_merges_to_judge(self):
        """The fleet's spec template legitimately lists a test in both its
        change-instruction and test-mapping sections — a count the revision
        itself carries never trips the gate."""
        dual = PREVIOUS.replace(
            "Each criterion maps to one test above.",
            "```python\ndef test_req_1_alpha():\n"
            "    assert render_face(256).mode == \"RGBA\"\n```",
        )
        flags = named_line_flags(PREVIOUS, named_tokens(VERDICT))
        assert _conservation_override(
            PREVIOUS, dual, dual,
            current_tokens=named_tokens(VERDICT),
            current_flags=flags,
        ) is None


class TestDemandedAdditions:
    #: Draft-018 shape at iteration 7: the previous draft carries an unnamed
    #: comment block; the demanded test arrives as a replace over it.
    COMMENT_PREVIOUS = """# Spec

## 6. Change Instructions

```python
def test_alpha():
    assert True

# Baseline-independent geometric assertion:
# - housing horizon samples
# - one dark sample
# - one bright sample
```

## 7. Notes

The notes block stays put.
"""

    ADDED = COMMENT_PREVIOUS.replace(
        """# Baseline-independent geometric assertion:
# - housing horizon samples
# - one dark sample
# - one bright sample""",
        """def test_req_8_chrome_housing():
    assert housing_gradient_samples() >= 3""",
    )

    #: Names §7 only — pinning engaged, the comment block unnamed.
    TOKENS = {"the notes block stays put."}

    def test_the_demanded_addition_lands(self):
        """The observed refusal, repaired: the differ bundles the new test
        as a replace over unnamed old lines, and the round's completeness
        failures demand additions — the compliance passes."""
        result = enforce_pinning(
            self.COMMENT_PREVIOUS, self.ADDED,
            current_tokens=set(self.TOKENS),
            additions_demanded=True,
        )
        assert "def test_req_8_chrome_housing" in result.text
        assert result.refusals == ()
        assert result.additions, "the pass is an event, never silent"

    def test_an_unprompted_addition_is_still_refused(self):
        """The inverse: the same revision in a round demanding no additions
        is judged exactly as before."""
        result = enforce_pinning(
            self.COMMENT_PREVIOUS, self.ADDED,
            current_tokens=set(self.TOKENS),
            additions_demanded=False,
        )
        assert "def test_req_8_chrome_housing" not in result.text
        assert "# Baseline-independent geometric assertion:" in result.text
        assert result.refusals

    def test_a_plain_modification_gains_nothing_from_the_demand(self):
        """additions_demanded frees additions, not modifications: a locked
        rewording with no new test in it is refused either way."""
        reworded = self.COMMENT_PREVIOUS.replace(
            "# - one dark sample", "# - two dark samples"
        )
        result = enforce_pinning(
            self.COMMENT_PREVIOUS, reworded,
            current_tokens=set(self.TOKENS),
            additions_demanded=True,
        )
        assert "# - one dark sample" in result.text
        assert result.refusals

    def test_the_real_check_messages_read_as_demands(self):
        assert demands_additions([
            "3 LLD pass criterion(s) have no test in the spec [join exact "
            "(criterion IDs)]. Add a test for each:\n  - REQ-8 (row 080): "
            "Chrome housing gradients check"
        ])
        assert demands_additions([
            "1 exception type(s) the spec raises have no test asserting "
            "them. Section 10 owes each a test:\n  - ValueError: raised 2 "
            "times"
        ])
        assert not demands_additions([
            "1 code fence(s) tagged as Python do not parse as Python: "
            "lines 81-83"
        ])
        assert not demands_additions([])
        assert not demands_additions(None)


class TestIsExpansion:
    def test_ordered_containment_is_an_expansion(self):
        assert _is_expansion(["a", "b"], ["x", "a", "y", "b", "z"])

    def test_reordering_is_not(self):
        assert not _is_expansion(["a", "b"], ["b", "a"])

    def test_a_dropped_line_is_not(self):
        assert not _is_expansion(["a", "b"], ["a", "z"])


class TestTheHaltsSurvivalClaim:
    """#2561: 'shown to the drafter and survived a revision' asserts the
    drafter's output reached the check intact — provable only against a
    clean pinning record."""

    REFUSAL = (
        "[PINNING] refused: 7 line(s) starting '# Baseline-independent "
        "geometric assertion:' — locked content the verdict did not name "
        "(#2532)"
    )
    CONSERVATION = (
        "[PINNING] CONSERVATION: the revision removed 3 test(s) no verdict "
        "named (test_req_8_chrome_housing, test_req_9_screws, "
        "test_req_10_bezel) -- revision refused entire, previous draft "
        "kept (#2559)"
    )

    def _state(self, iteration=3, shown=(), breakdown=(), pinning_events=()):
        return {
            "spec_draft": "# Spec\n\n" + ("body line\n" * 40),
            "files_to_modify": [],
            "pattern_references": [],
            "repo_root": "",
            "lld_content": "",
            "review_iteration": iteration,
            "max_iterations": 3,
            "checks_shown_to_drafter": list(shown),
            "prior_completeness_breakdown": [dict(e) for e in breakdown],
            "pinning_events": list(pinning_events),
        }

    def _at_cap(self, pinning_events=()):
        """The kept_failing shape: the complaint CHANGED across rounds, so
        neither the identical-complaint nor the complied class claims it."""
        with patch(
            "assemblyzero.workflows.implementation_spec.nodes."
            "validate_completeness.check_modify_files_have_excerpts",
            return_value={
                "check_name": "x", "passed": False,
                "details": "missing excerpt for a.py",
            },
        ):
            first = validate_completeness(self._state())
            return validate_completeness(self._state(
                shown=first["checks_shown_to_drafter"],
                breakdown=[
                    {"iteration": 0, "failures": ["missing excerpt for b.py"]},
                    {"iteration": 1, "failures": ["missing excerpt for c.py"]},
                ],
                pinning_events=pinning_events,
            ))

    def test_refusals_on_the_record_suppress_the_survival_claim(self, capsys):
        out = self._at_cap(pinning_events=[self.REFUSAL])
        capsys.readouterr()
        message = out["error_message"]
        assert "may not have reached the check intact" in message
        assert "survived a revision" not in message

    def test_a_conservation_override_counts_as_enforcement(self, capsys):
        out = self._at_cap(pinning_events=[self.CONSERVATION])
        capsys.readouterr()
        message = out["error_message"]
        assert "may not have reached the check intact" in message
        assert "survived a revision" not in message

    def test_a_clean_record_keeps_the_survival_claim(self, capsys):
        out = self._at_cap(pinning_events=())
        capsys.readouterr()
        message = out["error_message"]
        assert "survived a revision" in message
        assert "may not have reached the check intact" not in message
