"""`impl.red.import_errors` advises instead of ending the run (#2766).

The red phase runs the generated test suite BEFORE any implementation
exists, to prove the suite actually fails. An `ImportError` on the module
under test is therefore the expected state, not a defect.

This gate drew a line inside that expected state: it separated an import the
LLD's Section 2.1 file plan accounts for from one it does not, and ended the
run on the second. Two things were wrong with that.

**Its own halt was unintended.** The return set `next_node` to
`"N4_implement_code"` alongside `error_message`, and `route_after_red` reads
the error first -- so the route was dead code and the run stopped where #842
had written "route back to N4 with specific feedback".

**Its inference was overturned.** "Unexpected" means "not in the LLD's file
plan", and #2736 ruled that the plan is a plan rather than a contract;
`impl.path_enforcement` became advisory on exactly that reading.

The issue also left a question open -- zero firings in 180 runs, "either
well-targeted or unreachable, and nothing in the record says which".
`TestWhetherTheGateCouldEverHaveFired` answers it by measurement: reachable,
and in one ordinary configuration it fires on the red phase's normal state.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_ADVISE,
    JUDGES_MODEL_OUTPUT,
    advised,
    gate_key_of,
    registry_by_key,
)
from assemblyzero.workflows.testing.graph import route_after_red
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _classify_import_errors,
    verify_red_phase,
)

GATE = "impl.red.import_errors"

#: What pytest prints when a test imports a module that is not there.
MISSING_UNDER_TEST = (
    "ModuleNotFoundError: No module named 'boostgauge.telltale'"
)
MISSING_THIRD_PARTY = "ModuleNotFoundError: No module named 'numpy'"

PLAN = ["boostgauge/telltale.py"]


class TestWhetherTheGateCouldEverHaveFired:
    """The issue's open question, answered by measurement rather than guess."""

    def test_with_a_file_plan_it_separates_the_two_cases(self):
        expected, unexpected, modules = _classify_import_errors(
            f"{MISSING_UNDER_TEST}\n{MISSING_THIRD_PARTY}\n", PLAN
        )
        assert expected == 1, "the module under test is accounted for"
        assert unexpected == 1 and modules == ["numpy"]

    def test_with_no_file_plan_every_red_phase_import_error_is_unexpected(self):
        """Reachable, and this is the shape that makes it dangerous.

        `expected_modules` is derived from the LLD's Section 2.1 rows. An LLD
        whose file table did not parse leaves it empty, and with an empty
        expected set the module under test -- the one the run is about to
        write -- is classified `unexpected`. The gate then ended the run on
        the red phase's textbook normal state.
        """
        expected, unexpected, modules = _classify_import_errors(
            MISSING_UNDER_TEST, []
        )
        assert expected == 0
        assert unexpected == 1 and modules == ["boostgauge.telltale"], (
            "with no plan to compare against, the module under test itself "
            "counts as unexpected"
        )

    def test_so_zero_firings_was_never_evidence_of_being_well_targeted(self):
        """Both branches above are reachable from ordinary inputs. The row's
        `kills on boostgauge: 0` therefore says nothing about aim -- it says
        boostgauge's LLDs happened to parse and its suites happened not to
        import anything absent. That is luck, and it is why the issue asked."""
        _, unexpected_with_plan, _ = _classify_import_errors(
            MISSING_THIRD_PARTY, PLAN
        )
        _, unexpected_without_plan, _ = _classify_import_errors(
            MISSING_UNDER_TEST, []
        )
        assert unexpected_with_plan and unexpected_without_plan


def _red_state(tmp_path) -> dict:
    return {
        "test_files": [str(tmp_path / "test_example.py")],
        "repo_root": str(tmp_path),
        "worktree_path": str(tmp_path),
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 4242,
        "iteration_count": 0,
        "max_iterations": 10,
        "coverage_target": 90,
        "implementation_files": [],
        "files_to_modify": [{"path": p} for p in PLAN],
        "skip_e2e": True,
    }


def _pytest_result(output: str):
    return {
        "returncode": 1,
        "stdout": output,
        "stderr": "",
        "parsed": {"passed": 0, "failed": 0, "errors": 2, "coverage": 0},
    }


class TestItAdvisesInsteadOfHalting:
    @pytest.fixture
    def rolled(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.Path.exists",
            lambda self: True,
        )
        events: list[dict] = []
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases"
            ".log_workflow_execution",
            lambda **kw: events.append(kw),
        )
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.write_red_marker",
            lambda *a, **k: None,
        )
        with patch(
            "assemblyzero.workflows.testing.nodes.verify_phases.run_pytest",
            return_value=_pytest_result(
                f"{MISSING_UNDER_TEST}\n{MISSING_THIRD_PARTY}\n"
            ),
        ):
            result = verify_red_phase(_red_state(tmp_path))
        return result, events, capsys.readouterr().out

    def test_the_run_is_not_stopped(self, rolled):
        result, _, _ = rolled
        assert result.get("error_message", "") == "", result.get("error_message")

    def test_it_goes_where_the_dead_route_pointed(self, rolled):
        result, _, _ = rolled
        assert result["next_node"] == "N4_implement_code"
        assert route_after_red(result) == "N4_implement_code", (
            "and the router agrees, which it could not while an error was set"
        )

    def test_the_advisory_is_printed_and_carries_its_gate_key(self, rolled):
        _, _, out = rolled
        assert "[ADVISORY]" in out, out
        assert "Red phase detected 1 unexpected ImportError(s): numpy" in out, out
        line = next(ln for ln in out.splitlines() if "[ADVISORY]" in ln)
        assert gate_key_of(line) == GATE, line

    def test_it_still_says_the_run_continues_and_where(self, rolled):
        _, _, out = rolled
        assert "continuing to implementation" in out.lower(), out

    def test_the_event_is_still_logged(self, rolled):
        _, events, _ = rolled
        logged = [e for e in events if e.get("event") == "red_phase_unexpected_imports"]
        assert len(logged) == 1, events
        assert logged[0]["details"]["unexpected_modules"] == ["numpy"]

    def test_an_expected_import_error_says_nothing_at_all(
        self, tmp_path, monkeypatch, capsys
    ):
        """The advisory must not become noise on the normal case."""
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.Path.exists",
            lambda self: True,
        )
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases"
            ".log_workflow_execution",
            lambda **kw: None,
        )
        monkeypatch.setattr(
            "assemblyzero.workflows.testing.nodes.verify_phases.write_red_marker",
            lambda *a, **k: None,
        )
        with patch(
            "assemblyzero.workflows.testing.nodes.verify_phases.run_pytest",
            return_value=_pytest_result(MISSING_UNDER_TEST),
        ):
            result = verify_red_phase(_red_state(tmp_path))
        assert "[ADVISORY]" not in capsys.readouterr().out
        assert result["next_node"] == "N4_implement_code"


class TestTheRegistryRowMovedWithTheCode:
    def test_the_row_advises(self):
        row = registry_by_key()[GATE]
        assert row.action == ACTION_ADVISE
        assert row.judges == JUDGES_MODEL_OUTPUT, (
            "it still judges the drafter's output -- what changed is what it "
            "does about it"
        )
        assert row.justified_by == "#2766"

    def test_the_row_has_no_halt_site_left(self):
        assert registry_by_key()[GATE].sites == ()
        assert registry_by_key()[GATE].decided_in.endswith("verify_red_phase")

    def test_advised_would_refuse_the_key_if_the_row_still_halted(self):
        """`advised()` is the interlock: code and row cannot disagree. This
        asserts the interlock is armed for THIS key, so a future PR that
        flips the row back to halt fails here rather than shipping a log line
        that says the run continued and a run that did not."""
        assert advised(GATE, "x").endswith(f"[gate:{GATE}]")
