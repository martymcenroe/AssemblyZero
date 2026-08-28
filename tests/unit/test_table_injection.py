"""The source decision table reaches the LLD by code, not by drafter (#2607).

Literals travelled through a stochastic rewriter and the guard stack existed
to catch what fell out. Three demonstrations in one week; the sharpest is
run-issue331-093613, where -- diagnosed under #2608 -- the drafter asked to
restate a nine-row ruling-dense table emitted **no table at all** in draft 1,
and one round of gate-driven repair restored seven rows as prose bullets,
dropping S7, S9 and every assertion method.

Detection was good. This is prevention: where the transform is "copy these
values verbatim", no LLM is in the path.

Composes with the pinning fixtures rather than rewriting them. The
#2558/#2562/#2606 invariants are untouched: an injected region is
re-asserted mechanically, so pinning is never asked to adjudicate it, and
the tests below assert that separation directly.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec.assertion_manifest import (
    compile_manifest,
)
from assemblyzero.workflows.requirements.table_injection import (
    BEGIN_MARKER,
    END_MARKER,
    apply_injection,
    build_injection,
    has_injection,
    injected_line_span,
    reassert,
    source_criteria_tables,
    source_table_text,
    strip_injection,
)

#: Two rows of the real #331 table, with the padding and the em-dashes the
#: source actually carries -- byte-verbatim means these characters survive.
ISSUE = """# 331 - static face renderer

## Decision table — static elements and their binding values

| ID | Element | Binding value (quoted from the render contract) | Assertion method |
|----|---------|------------------------------------------------|------------------|
| S1 | Dial face | flat `#0A0A0C`, radius R = 0.40 × size | classification at 3 interior points |
| S5 | Numerals | `#FFFFFF`, cap height 0.11 R, centres at 0.72 R | ≥1 white pixel within the cap-height box; the mirror check samples ONLY at 0.12 R–0.25 R off-axis |

## Test plan constraints

Option C only.
"""

#: The lossy shape the drafter actually produced: bullets, no table.
LOSSY_DRAFT = """# 331 - static face renderer

## 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/skins/stingray.py` | Add | The renderer. |

## 3. Requirements

1. The system shall render each static element:
   - S1: R = 0.40
   - S5: 0.11 R

## 4. Alternatives Considered

Vector rendering rejected.
"""

PROSE_ISSUE = """# Make the button blue

## Requirements

1. The button shall be blue.
"""


class TestByteVerbatim:
    """The acceptance: the table appears verbatim, not re-rendered."""

    def test_the_sliced_block_is_the_sources_own_lines(self):
        table = source_criteria_tables(ISSUE)[0]
        block = source_table_text(ISSUE, table)
        source_lines = ISSUE.splitlines()
        for line in block.splitlines():
            assert line in source_lines, (
                f"{line!r} was re-rendered rather than sliced"
            )

    def test_the_slice_spans_header_separator_and_every_row(self):
        table = source_criteria_tables(ISSUE)[0]
        block = source_table_text(ISSUE, table)
        assert len(block.splitlines()) == 2 + len(table.rows)

    def test_padding_and_unicode_survive(self):
        """A round-trip through parsed cells would normalise these. The
        em-dash and en-dash are in the real #331 rows."""
        block = source_table_text(ISSUE, source_criteria_tables(ISSUE)[0])
        assert "0.12 R–0.25 R" in block, "en-dash normalised"
        assert "R = 0.40 × size" in block, "multiplication sign normalised"
        assert "|----|" in block, "separator padding normalised"

    def test_the_table_reaches_the_draft_verbatim(self):
        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        block = source_table_text(ISSUE, source_criteria_tables(ISSUE)[0])
        for line in block.splitlines():
            assert line in injected.splitlines()


class TestTheDefectIsPrevented:
    """The #2608 condition, eliminated at source."""

    def test_the_lossy_draft_compiles_a_manifest_once_injected(self):
        before = compile_manifest(LOSSY_DRAFT, "")
        assert before.applicable is False, "fixture must reproduce the defect"

        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        after = compile_manifest(injected, "")
        assert after.applicable is True
        assert set(after.criteria_ids) == {"S1", "S5"}

    def test_the_conservation_gate_finds_nothing_on_injected_rows(self):
        """#2607's success metric: the #2563 backstop should never fire on
        injected rows, because the literals are the source's own bytes."""
        from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
            validate_assertion_literal_conservation,
        )

        assert validate_assertion_literal_conservation(
            ISSUE, LOSSY_DRAFT
        ), "fixture must reproduce the loss the gate catches today"

        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        assert validate_assertion_literal_conservation(ISSUE, injected) == [], (
            "the gate fired on rows carried verbatim from the source -- "
            "injection did not do its job"
        )

    def test_the_structure_check_passes_once_injected(self):
        """#2608's gate, satisfied by construction rather than by asking the
        drafter again."""
        from assemblyzero.workflows.requirements.nodes.validate_mechanical import (
            validate_decision_table_survives,
        )

        assert validate_decision_table_survives(ISSUE, LOSSY_DRAFT)
        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        assert validate_decision_table_survives(ISSUE, injected) == []


class TestARevisionCannotModifyAnInjectedRow:
    """The third acceptance clause."""

    def _injected(self) -> str:
        return apply_injection(LOSSY_DRAFT, build_injection(ISSUE))

    def test_an_edit_inside_the_block_is_reverted(self):
        injected = self._injected()
        tampered = injected.replace("R = 0.40 × size", "R = 0.99 × size")
        assert tampered != injected

        restored, changed = reassert(tampered, ISSUE)
        assert changed is True
        start, end = injected_line_span(restored)
        block = "\n".join(restored.splitlines()[start - 1 : end])
        assert "R = 0.40 × size" in block
        assert "R = 0.99" not in block

    def test_deleting_the_block_entirely_restores_it(self):
        """The strongest tamper: the drafter removes the markers."""
        gutted = strip_injection(self._injected())
        assert has_injection(gutted) is False

        restored, changed = reassert(gutted, ISSUE)
        assert changed is True
        assert has_injection(restored) is True
        assert "| S1 |" in restored

    def test_reassert_is_idempotent(self):
        injected = self._injected()
        again, changed = reassert(injected, ISSUE)
        assert changed is False
        assert again == injected

    def test_reassert_leaves_the_drafters_own_prose_alone(self):
        """It guards the machine-owned region, not the document. The
        drafter's own sections remain the drafter's."""
        injected = self._injected()
        edited = injected.replace(
            "Vector rendering rejected.", "Vector rendering reconsidered."
        )
        restored, _ = reassert(edited, ISSUE)
        assert "Vector rendering reconsidered." in restored

    def test_repeated_cycles_do_not_accumulate_whitespace(self):
        text = LOSSY_DRAFT
        for _ in range(4):
            text, _ = reassert(text, ISSUE)
        assert "\n\n\n" not in text
        assert text.count(BEGIN_MARKER) == 1
        assert text.count(END_MARKER) == 1


class TestTheControl:
    """Prose-only requirements derive exactly as today."""

    def test_an_issue_with_no_table_injects_nothing(self):
        assert build_injection(PROSE_ISSUE) == ""

    def test_the_draft_is_returned_untouched(self):
        draft = "# LLD\n\n## 3. Requirements\n\n1. Blue.\n"
        assert apply_injection(draft, build_injection(PROSE_ISSUE)) == draft

    def test_reassert_is_a_no_op(self):
        draft = "# LLD\n\n## 3. Requirements\n\n1. Blue.\n"
        restored, changed = reassert(draft, PROSE_ISSUE)
        assert changed is False
        assert restored == draft


class TestPlacementAndSpan:
    def test_the_block_lands_under_the_requirements_heading(self):
        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        lines = injected.splitlines()
        heading = next(
            i for i, ln in enumerate(lines) if ln.startswith("## 3. Requirements")
        )
        marker = next(i for i, ln in enumerate(lines) if ln == BEGIN_MARKER)
        assert marker > heading

    def test_a_draft_with_no_requirements_heading_still_gets_the_block(self):
        """Placement is for the reader; the compiler finds a criteria table
        anywhere, so appending is correct rather than degraded."""
        injected = apply_injection("# LLD\n\nJust prose.\n", build_injection(ISSUE))
        assert has_injection(injected)
        assert compile_manifest(injected, "").applicable is True

    def test_the_span_is_reported_one_based_and_inclusive(self):
        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        start, end = injected_line_span(injected)
        lines = injected.splitlines()
        assert lines[start - 1] == BEGIN_MARKER
        assert lines[end - 1] == END_MARKER

    def test_no_injection_means_no_span(self):
        assert injected_line_span(LOSSY_DRAFT) is None


class TestPinningNeverAdjudicatesTheBlock:
    """#2607 asks that pinning never have to reason about injected rows.

    Re-assertion is what delivers that, and it is deliberately stronger than
    asking pinning to protect the region: pinning adjudicates a diff and can
    be argued with; re-assertion does not adjudicate. These tests assert the
    separation holds without weakening #2558/#2562/#2606 -- the pinning
    fixtures are untouched and pinning's own behaviour is unchanged.
    """

    def test_pinning_alone_leaves_a_gap_that_reassertion_closes(self):
        """Pinning's protection of the block is CONDITIONAL on the round's
        vocabulary; re-assertion's is not.

        With an empty vocabulary pinning locks everything, so it happens to
        protect the block. But a verdict that names any token occurring
        inside the block unlocks that region -- correctly, by pinning's own
        rule that restructuring around a named item is the named item's
        business. A reviewer writing "the `Dial face` row is wrong" is
        enough. That is the gap, and it is exactly why the injected region
        is re-asserted rather than left to adjudication.
        """
        from assemblyzero.workflows.implementation_spec.revision_pinning import (
            enforce_pinning,
        )

        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        tampered = injected.replace("R = 0.40 × size", "R = 0.99 × size")
        assert tampered != injected

        naming = {"dial face"}
        pinned = enforce_pinning(
            injected, tampered, current_tokens=naming, ever_tokens=naming
        )
        assert "R = 0.99" in pinned.text, (
            "a verdict naming content inside the block should unlock it -- "
            "if this stops being true, pinning changed and this test is the "
            "place to re-derive the claim"
        )

        # Re-assertion does not consult the vocabulary, so it closes the gap.
        restored, changed = reassert(pinned.text, ISSUE)
        assert changed is True
        start, end = injected_line_span(restored)
        assert "R = 0.99" not in "\n".join(
            restored.splitlines()[start - 1 : end]
        )

    def test_pinning_locks_the_block_when_nothing_names_it(self):
        """The complement, recorded because it is the ordinary round: with
        no naming token, pinning already refuses the edit. Re-assertion is
        the belt to that braces, not a replacement for it."""
        from assemblyzero.workflows.implementation_spec.revision_pinning import (
            enforce_pinning,
        )

        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        tampered = injected.replace("R = 0.40 × size", "R = 0.99 × size")
        pinned = enforce_pinning(
            injected, tampered, current_tokens=set(), ever_tokens=set()
        )
        assert "R = 0.99" not in pinned.text
        assert pinned.refusals

    def test_pinning_still_protects_the_drafters_own_content(self):
        """The invariant that must NOT weaken: outside the machine-owned
        block, pinning behaves exactly as before."""
        from assemblyzero.workflows.implementation_spec.revision_pinning import (
            enforce_pinning,
        )

        injected = apply_injection(LOSSY_DRAFT, build_injection(ISSUE))
        meddled = injected.replace(
            "Vector rendering rejected.", "Vector rendering reconsidered."
        )
        result = enforce_pinning(
            injected, meddled,
            current_tokens={"nothing-that-matches"},
            ever_tokens={"nothing-that-matches"},
        )
        assert "Vector rendering rejected." in result.text
        assert result.refusals
