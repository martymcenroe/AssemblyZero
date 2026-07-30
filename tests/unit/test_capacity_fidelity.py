"""The capacity signature survives the budget wall and the '≥' sign (#1943, #1944).

Reference: run11b-issue4-001307 attempts 2-3 (2026-07-30 ~00:40). Gemini
served 503s; the #1874 wall correctly halted at 600s — and the surfaced
error 'call budget of 600s exhausted' erased the storm: the stage retried
flat (no #1909 escalation) and the halt classifier's bare-'budget' pattern
would have called it a non-transient COST problem. Separately, the fresh
LLD's repo-pinned '≥89%' target was unparseable (the comparator broke
every regex) and silently ran as the hardcoded 95.
"""

from assemblyzero.core.errors import is_capacity_message
from assemblyzero.core.halt_node import classify_error
from assemblyzero.workflows.testing.nodes.load_lld import extract_coverage_target

FLAVORED_WALL = (
    "All credentials failed:\n"
    "  - oauth-primary: call budget of 600s exhausted riding 503/529 capacity storms"
)
BARE_WALL = (
    "All credentials failed:\n"
    "  - oauth-primary: call budget of 600s exhausted"
)
COST_HALT = "[BUDGET] $5.20 exceeds $5.00 budget. Halting."
LEGACY_COST_HALT = "Cost budget exceeded: $5.20 spent of $5.00 budget"


class TestBudgetWallCarriesTheStorm:
    def test_flavored_wall_is_a_capacity_signature(self):
        assert is_capacity_message(FLAVORED_WALL) is True

    def test_flavored_wall_classifies_capacity_not_budget(self):
        assert classify_error(FLAVORED_WALL) == "capacity_exhausted"

    def test_cost_halts_still_classify_budget(self):
        assert classify_error(COST_HALT) == "budget"
        assert classify_error(LEGACY_COST_HALT) == "budget"

    def test_bare_wall_no_longer_false_matches_cost_budget(self):
        """A budget-wall message with no flavor (e.g. the wall fired before
        any attempt ran) must not classify as a COST problem. It is not
        capacity either — it falls through to the generic bucket, which
        retries by default rather than telling the operator to raise
        --budget for provider weather."""
        assert classify_error(BARE_WALL) != "budget"


class TestCoverageTargetParsesComparators:
    def test_the_live_lld_line_parses(self):
        lld = (
            "**Coverage Target:** ≥89% for all new code "
            "(matching `pyproject.toml` `fail_under = 89`)"
        )
        assert extract_coverage_target(lld) == 89

    def test_ascii_ge_parses(self):
        assert extract_coverage_target("Code coverage >= 80% required") == 80

    def test_plain_forms_still_parse(self):
        assert extract_coverage_target("Coverage: 90%") == 90
        assert extract_coverage_target("Target coverage: 85%") == 85
        assert extract_coverage_target("Achieve 92% coverage overall") == 92

    def test_no_declaration_falls_to_default(self):
        assert extract_coverage_target("No numbers here.") == 95
