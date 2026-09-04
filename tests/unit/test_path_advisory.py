"""The LLD's file list is a plan, not a contract (#2736).

Operator ruling, 2026-09-04. `impl.path_enforcement` refused four of the
seventeen files boostgauge's hand build shipped for issue #4 -- three of them
tests the design had not thought of -- and every one of those files is correct
code the operator wrote, reviewed and tagged. The gate may now say what it
sees; it may not refuse the file and it may not end the run.

The artifact that showed the problem is the answer-key audit against boostgauge
`main`, which needs that repository on disk and so cannot run here. What CAN be
pinned here is every mechanism the audit's result rests on: the row's action,
the coupling that makes the advisory unprintable while the row halts, and the
sentence itself over the four paths the audit refused.
"""

from __future__ import annotations

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_ADVISE,
    ACTION_HALT,
    ADVISORY_CONTINUES_DEFAULT,
    JUDGES_MODEL_OUTPUT,
    advised,
    gate_key_of,
    registry_by_key,
)
from assemblyzero.hooks.file_write_validator import (
    PATH_GATE_KEY,
    path_advisory,
    validate_file_write,
)

#: The paths LLD-004 named, as `extract_paths_from_lld` reads them off the
#: shipped document. Authored from the audit's own output rather than derived,
#: so this fixture cannot drift into agreeing with whatever the code does.
LLD_004_PLANNED = {
    "src/boostgauge/collector.py",
    "src/boostgauge/collectors/windows.py",
    "tests/unit/test_collector.py",
    "tests/integration/test_windows_collector.py",
    "tests/benchmark/test_windows_sweep.py",
}

#: The four files the hand build shipped that the plan did not name. Every one
#: was refused before this ruling; the audit's `impl.path_enforcement` column
#: read 7 ran / 4 refused, and reads 7 ran / 0 refused after it.
SHIPPED_BUT_UNPLANNED = (
    "src/boostgauge/collectors/__init__.py",
    "tests/benchmark/test_sweep_cost.py",
    "tests/integration/test_windows_sweep_crosscheck.py",
    "tests/unit/test_collector_source_pin.py",
)


class TestTheRow:
    def test_the_gate_advises_rather_than_halting(self):
        assert registry_by_key()[PATH_GATE_KEY].action == ACTION_ADVISE

    def test_it_still_judges_model_output(self):
        """The classification is a fact about the gate and does not change
        because its consequence did. Rewriting `judges` to make the
        model-output halt count fall would be cooking the number the routing
        policy is measured by."""
        assert registry_by_key()[PATH_GATE_KEY].judges == JUDGES_MODEL_OUTPUT

    def test_a_row_with_no_sites_says_where_it_lives(self):
        row = registry_by_key()[PATH_GATE_KEY]
        assert row.sites == ()
        assert row.decided_in, "a row with no sites is otherwise unfindable"


class TestTheAdvisory:
    @pytest.mark.parametrize("rel", SHIPPED_BUT_UNPLANNED)
    def test_every_file_the_audit_refused_now_gets_a_sentence(self, rel):
        notice = path_advisory(rel, LLD_004_PLANNED)
        assert notice, f"{rel} should draw an advisory, not silence"
        assert rel in notice
        assert "Section 2.1" in notice

    @pytest.mark.parametrize("rel", sorted(LLD_004_PLANNED))
    def test_a_planned_path_draws_no_sentence(self, rel):
        assert path_advisory(rel, LLD_004_PLANNED) == ""

    def test_it_carries_the_gate_key(self):
        notice = path_advisory("tests/unit/test_collector_source_pin.py",
                               LLD_004_PLANNED)
        assert gate_key_of(notice) == PATH_GATE_KEY

    def test_it_says_the_file_is_written(self):
        """A reader of the log has seen this sentence end runs for as long as
        the gate has existed, so the advisory has to say what happens now."""
        notice = path_advisory("tests/benchmark/test_sweep_cost.py",
                               LLD_004_PLANNED)
        assert "The file is written" in notice

    def test_it_does_not_borrow_the_stagnation_guards_sentence(self):
        """No budget is involved in writing one file, so "the budget decides"
        would be prose nobody could act on (#2736)."""
        notice = path_advisory("tests/benchmark/test_sweep_cost.py",
                               LLD_004_PLANNED)
        assert ADVISORY_CONTINUES_DEFAULT not in notice

    def test_an_lld_that_names_no_paths_leaves_the_gate_silent(self):
        assert path_advisory("anything/at/all.py", set()) == ""

    def test_it_names_the_closest_planned_path_when_there_is_one(self):
        notice = path_advisory("tests/unit/test_collector_source_pin.py",
                               LLD_004_PLANNED)
        assert "tests/unit/test_collector.py" in notice


class TestTheCouplingToTheRow:
    def test_the_advisory_is_unprintable_while_the_row_halts(self):
        """`path_advisory` reaches the log only through `advised()`, which
        refuses a halting row. So flipping the row back to `halt` without
        restoring the raise cannot leave a run that says it continued and then
        did not -- this test fails first."""
        assert registry_by_key()[PATH_GATE_KEY].action != ACTION_HALT
        with pytest.raises(ValueError, match="halt row"):
            advised("impl.write_failed", "Failed to write file: disk full.")


class TestTraversalIsNotADesignDisagreement:
    def test_a_path_escaping_the_repository_is_still_refused(self):
        """The ruling is about a design document's file list. A path climbing
        out of the tree is an infrastructure fact, and no ruling about plans
        speaks to it -- `validate_file_write` still reports it."""
        result = validate_file_write("../../etc/passwd", LLD_004_PLANNED)
        assert result["allowed"] is False
        assert "traversal" in result["reason"]


class TestAdvisedTakesACustomContinuation:
    def test_the_default_is_the_stagnation_guards_sentence(self):
        message = advised("impl.stagnation.coverage", "Coverage stagnant.")
        assert ADVISORY_CONTINUES_DEFAULT in message

    def test_a_caller_can_say_something_true_of_its_own_gate(self):
        message = advised("impl.stagnation.coverage", "Coverage stagnant.",
                          continues="Something else entirely.")
        assert "Something else entirely." in message
        assert ADVISORY_CONTINUES_DEFAULT not in message
        assert gate_key_of(message) == "impl.stagnation.coverage"
