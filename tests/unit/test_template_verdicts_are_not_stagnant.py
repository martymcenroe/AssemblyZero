"""Two different template verdicts are not "the same issues" (#2872), and the
halt counts reviews, not node visits (#2873).

boostgauge #4, `run-issue4-184136` (2026-09-05), design stage. Review 1 raised
three Tier 1 issues (loop bounds on the NextEntryOffset walk; segfault
prevention in the ctypes parse; NULL ImageName on PIDs 0 and 4). The drafter
fixed all three. Review 2 raised one new Tier 1 issue (a bounded queue blocks
on put()). The stage halted: "Two consecutive BLOCKED verdicts with same
issues." The halt message said "Halted after 6 round(s) ... no recorded
reason."

Both reviews were read from the 0702c template (#2835). On that path
`response` is "" and `structured` is a shell with no items, so
`_extract_actionable_feedback` -- which never learned the template source --
returned the bare `Verdict: BLOCKED` for both. The two-strike compared two
identical one-liners. The fixtures below are the two verdicts reduced to
what the template reader reads: the Verdict box and the Tier sections, with
the real issue titles.
"""

from __future__ import annotations

import importlib

from assemblyzero.core.halt_node import describe_halt_from_state
from assemblyzero.core.verdict_schema import parse_markdown_feedback, same_blocking_issues

review = importlib.import_module("assemblyzero.workflows.requirements.nodes.review")


def _template(tier1: list[str], tier2: list[str], summary: str) -> str:
    t1 = "\n".join(f"- [ ] **{t}:** detail." for t in tier1) or "- [ ] No issues found."
    t2 = "\n".join(f"- [ ] **{t}:** detail." for t in tier2) or "- [ ] No issues found."
    return f"""# LLD Review: #4-Windows data collector

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
{summary}

## Open Questions Resolved
None.

## Tier 1: BLOCKING Issues

### Cost
- [ ] No issues found.

### Safety
{t1}

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
{t2}

### Observability
- [ ] No issues found.

### Quality
- [ ] No issues found.

## Tier 3: SUGGESTIONS
- Consider a default maxsize on the queue.

## Questions for Orchestrator
None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision
"""


REVIEW_1 = _template(
    tier1=[
        "Loop bounds undefined for memory parsing",
        "Fail-Safe Strategy (Segfault Prevention)",
        "Fail-Safe Strategy (System Process Names)",
    ],
    tier2=[],
    summary="Solid approach; three memory-safety gaps in the sweep.",
)

REVIEW_2 = _template(
    tier1=["Fail-Safe Strategy (Queue Blocking)"],
    tier2=[
        "Interface Correctness (`composite` missing argument)",
        "Interface Correctness (Data Structure Fields)",
    ],
    summary="Memory safety addressed; one thread-blocking risk and two signature slips.",
)


def _stored_feedback(raw: str) -> str:
    """Exactly what review.py stores in `current_verdict` on the template path."""
    fr = parse_markdown_feedback(raw)
    assert fr is not None and fr["source"] == "markdown_template"
    structured = {"verdict": fr["verdict"], "rationale": fr["rationale"]}
    return review._extract_actionable_feedback("", "BLOCKED", structured, feedback_result=fr)


class TestTheStoredFeedbackCarriesTheIssues:
    def test_review_one_stores_its_three_blocking_issues(self):
        stored = _stored_feedback(REVIEW_1)

        assert stored != "Verdict: BLOCKED"
        assert "Loop bounds undefined" in stored
        assert "Segfault Prevention" in stored
        assert "System Process Names" in stored

    def test_review_two_stores_its_one_blocking_issue_and_its_tier_two(self):
        stored = _stored_feedback(REVIEW_2)

        assert "Queue Blocking" in stored
        assert "composite" in stored

    def test_a_template_with_no_items_still_stores_more_than_the_status(self):
        raw = _template(tier1=[], tier2=[], summary="Nothing blocking; see suggestions.")

        stored = _stored_feedback(raw)

        assert stored != "Verdict: BLOCKED"
        assert "Nothing blocking" in stored or "SUGGESTIONS" in stored


class TestTheTwoStrikeReadsIssuesNotStatus:
    def test_run_24s_two_reviews_are_not_the_same_issues(self):
        first = _stored_feedback(REVIEW_1)
        second = _stored_feedback(REVIEW_2)

        assert not same_blocking_issues(second, first)

    def test_a_genuinely_repeated_review_is_still_stagnation(self):
        first = _stored_feedback(REVIEW_1)
        again = _stored_feedback(REVIEW_1)

        assert same_blocking_issues(again, first)

    def test_the_bare_status_was_the_defect(self):
        """The shape the code produced before #2872: identical by construction."""
        assert same_blocking_issues("Verdict: BLOCKED", "Verdict: BLOCKED")


class TestTheHaltCountsReviews:
    def test_round_count_reads_verdict_count_before_iteration_count(self):
        state = {
            "lld_status": "BLOCKED",
            "verdict_count": 2,
            "iteration_count": 6,
            "max_iterations": 3,
        }

        message = describe_halt_from_state(state, "requirements")

        assert "2 round(s)" in message, message
        assert "6 round(s)" not in message

    def test_workflows_without_verdict_count_are_unchanged(self):
        state = {"lld_status": "BLOCKED", "iteration_count": 4, "max_iterations": 9}

        assert "4 round(s)" in describe_halt_from_state(state, "testing")
