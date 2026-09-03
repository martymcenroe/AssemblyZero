"""The reviewer's itemized feedback reaches the drafter and the lock (#2715).

boostgauge run-issue4-183941, spec stage, review round 8: the verdict file
quoted three assertions verbatim, named their functions, and cited the LLD
scenario binding each -- and the revision lock refused the drafter's fix to
all three as "locked content the verdict did not name". Rounds 5 through 7
had sent the same three assertions back while the drafter guessed at the
tolerance: 5 %, exact, 10 %, absolute. It was never shown "±1".

`review_feedback` was the rationale paragraph; the items were appended only
when the rationale was empty. The fixtures are that round's verdict and the
draft it judged, verbatim; the control proves the old text left the lines
locked, and the new text opens them and admits the fix.
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
    review_feedback_text,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    enforce_pinning,
    named_line_flags,
    named_tokens,
)

#: `nodes/__init__.py` re-exports the FUNCTION `review_spec`, which shadows
#: the module of the same name; the module is reached by path.
review_spec = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.review_spec"
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "boostgauge4_review_items"
VERDICT = (FIXTURES / "023-readiness-verdict.md").read_text(encoding="utf-8")
DRAFT = (FIXTURES / "021-spec-draft.md").read_text(encoding="utf-8")

#: 1-based lines of the three assertions in the draft the verdict judged.
ASSERTION_LINES = (702, 712, 729)


def _parse_verdict(text: str) -> tuple[str, list[str]]:
    """The verdict file's own rendering: a Rationale paragraph, then
    `## Feedback Items` as `- ` lines. Reading it back is the test's
    business; the pipeline renders it, nothing parses it in production."""
    head, _, items_block = text.partition("## Feedback Items")
    rationale = head.split("Rationale:", 1)[1].strip()
    items = [line[2:].strip() for line in items_block.splitlines() if line.startswith("- ")]
    return rationale, items


RATIONALE, ITEMS = _parse_verdict(VERDICT)


class TestTheFixtureIsWhatTheRunSaw:
    def test_three_items_each_quoting_an_assertion(self) -> None:
        assert len(ITEMS) == 3
        assert "`assert abs(snap.process_count - expected) <= 5`" in ITEMS[0]
        assert "`test_req_090_live_process_count`" in ITEMS[0]

    def test_the_rationale_quotes_nothing(self) -> None:
        """Which is exactly why the lock opened nothing on this round."""
        assert "`" not in RATIONALE

    def test_the_draft_carries_the_three_lines(self) -> None:
        lines = DRAFT.splitlines()
        assert lines[ASSERTION_LINES[0] - 1].strip() == "assert abs(snap.process_count - expected) <= 5"
        assert lines[ASSERTION_LINES[1] - 1].strip() == "assert abs(snap.conpty_count - expected) <= 2"
        assert lines[ASSERTION_LINES[2] - 1].strip() == "assert abs(snap.handle_count - psutil_handles) <= 500"


class TestTheTextCarriesBoth:
    def test_rationale_then_items(self) -> None:
        text = review_feedback_text("Summary.", ["first thing", "second thing"])
        assert text == "Summary.\n\n- first thing\n- second thing"

    def test_rationale_alone(self) -> None:
        assert review_feedback_text("Summary.", []) == "Summary."
        assert review_feedback_text("Summary.", None) == "Summary."

    def test_items_alone_is_unchanged(self) -> None:
        assert review_feedback_text("", ["only item"]) == "- only item"

    def test_nothing_is_nothing(self) -> None:
        assert review_feedback_text("", []) == ""
        assert review_feedback_text("   ", ["  "]) == ""


class TestRunElevensRoundEight:
    """The control and the repair, on the real artifacts."""

    def test_the_old_text_left_the_three_lines_locked(self) -> None:
        old_text = RATIONALE  # what review_feedback used to be
        flags = named_line_flags(DRAFT, named_tokens(old_text, []))
        assert not any(flags[line - 1] for line in ASSERTION_LINES), (
            "the fixture no longer reproduces the refusal"
        )

    def test_the_new_text_names_the_functions_and_the_lines(self) -> None:
        tokens = named_tokens(review_feedback_text(RATIONALE, ITEMS), [])
        assert "test_req_090_live_process_count" in tokens
        assert "assert abs(snap.process_count - expected) <= 5" in tokens

    def test_the_new_text_opens_the_three_lines(self) -> None:
        tokens = named_tokens(review_feedback_text(RATIONALE, ITEMS), [])
        flags = named_line_flags(DRAFT, tokens)
        assert all(flags[line - 1] for line in ASSERTION_LINES)

    def test_the_drafters_fix_is_accepted(self) -> None:
        """The edit the run tried on round 8, with the bounds the items stated."""
        revised = (
            DRAFT.replace("assert abs(snap.process_count - expected) <= 5",
                          "assert abs(snap.process_count - expected) <= 1")
            .replace("assert abs(snap.conpty_count - expected) <= 2",
                     "assert abs(snap.conpty_count - expected) <= 1")
            .replace("assert abs(snap.handle_count - psutil_handles) <= 500",
                     "assert abs(snap.handle_count - psutil_handles) <= psutil_handles * 0.01")
        )
        assert revised != DRAFT
        tokens = named_tokens(review_feedback_text(RATIONALE, ITEMS), [])

        result = enforce_pinning(
            DRAFT, revised, current_tokens=tokens, ever_tokens=tokens,
        )

        assert result.refusals == (), result.refusals
        assert "<= psutil_handles * 0.01" in result.text

    def test_a_line_no_item_named_stays_locked(self) -> None:
        """The control on the repair side: opening the items' lines opens
        nothing else."""
        target = 'logger.debug("Invalid buffer")'
        assert target in DRAFT
        revised = DRAFT.replace(target, 'logger.debug("changed")', 1)
        tokens = named_tokens(review_feedback_text(RATIONALE, ITEMS), [])

        result = enforce_pinning(
            DRAFT, revised, current_tokens=tokens, ever_tokens=tokens,
        )

        assert result.refusals != ()
        assert target in result.text


class TestOneHelperTwoSites:
    def test_both_assembly_sites_use_the_helper(self) -> None:
        source = inspect.getsource(review_spec)
        calls = source.count("review_feedback_text(") - 1  # minus the def
        assert calls == 2, calls
        assert "if not feedback and" not in source, (
            "the rationale-only assembly has reappeared"
        )
