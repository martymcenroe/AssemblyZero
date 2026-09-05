"""The non-pytest red phase says its halt is deterministic (#2796).

The red phase runs the generated suite before any implementation exists, to
prove it fails. When tests PASS there instead, something already satisfies
them, and the pytest path has learned to tell three situations apart:

* a red-entry marker, or files this run's own earlier attempt wrote, explain
  the passes (#2337, #2542) -- resume the loop at the green phase;
* the plan says every file is `Modify` and the base ships them (#2670) --
  the passes are base-satisfied regression guards, continue to implementation;
* nothing explains them -- the implementation predates the stage, which is
  deterministic on an unchanged worktree, so halt and say so.

`_verify_red_non_pytest` -- the path Playwright, Jest and Vitest take -- got
none of it, and its halt carried no `DETERMINISTIC FAILURE` token either. The
orchestrator's transience classifier therefore did not know the result was
reproducible, and retried it. That is the twelve-second three-attempt loop
`run-issue7-192332` spent before #2337 landed, still live on this path.

This change gives that site the token and files it under the row that already
owns the conclusion, `impl.red.preexisting_implementation`. It deliberately
does NOT claim the check it does not perform: the message says the path
cannot tell the readings apart, which is true, rather than "neither a marker
nor prior writes explain them", which would describe work never done.

**No recorded run exercises this path** -- boostgauge is a pytest project --
so every assertion here is against a mock roll, and the report says so.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.core.gate_registry import (
    ACTION_HALT,
    JUDGES_INFRASTRUCTURE,
    GATE_REGISTRY,
    registry_by_key,
    scan_halt_sites,
)
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    DETERMINISTIC_FAILURE,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _verify_red_non_pytest,
)

OWNER = "impl.red.preexisting_implementation"
RETIRED = "impl.red_phase_failed"
SITE = (
    "assemblyzero/workflows/testing/nodes/verify_phases.py"
    "::_verify_red_non_pytest::return::2"
)


class _Runner:
    def __init__(self, passed: int, failed: int = 0, errors: int = 0) -> None:
        self._result = {
            "raw_output": f"{passed} passed, {failed} failed",
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "exit_code": 0 if passed and not failed else 1,
        }

    def run_tests(self, test_paths):
        return dict(self._result)


def _state(tmp_path) -> dict:
    return {
        "test_files": [str(tmp_path / "widget.spec.ts")],
        "repo_root": str(tmp_path),
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 4242,
    }


def _roll(tmp_path, runner: _Runner, framework=TestFramework.PLAYWRIGHT):
    with patch(
        "assemblyzero.workflows.testing.nodes.verify_phases.get_runner",
        return_value=runner,
    ):
        return _verify_red_non_pytest(_state(tmp_path), {}, framework)


class TestTheHaltSaysItIsDeterministic:
    def test_it_carries_the_token(self, tmp_path):
        result = _roll(tmp_path, _Runner(passed=3))
        assert result["error_message"].startswith(DETERMINISTIC_FAILURE), (
            "without the token the orchestrator retries a result an "
            "unchanged worktree reproduces exactly"
        )

    def test_it_still_ends_the_run(self, tmp_path):
        result = _roll(tmp_path, _Runner(passed=3))
        assert result["next_node"] == "END"

    def test_it_names_the_count(self, tmp_path):
        message = _roll(tmp_path, _Runner(passed=3))["error_message"]
        assert "3 tests passed unexpectedly" in message, message

    def test_it_now_claims_the_check_because_it_performs_it(self, tmp_path):
        """Superseded by #2805, deliberately rather than deleted.

        This test asserted the opposite: that the message must NOT say
        "neither a red-entry marker ... explain them", because
        `_implementation_already_exists` and `_base_ships_the_implementation`
        were never called on this path and the sentence would have described
        work that did not happen.

        #2805 made the path perform that check, so the sentence became true
        and the old assertion became false. The claim is kept pointing the
        other way, because "the message must not describe a check the code
        skipped" is the rule worth holding either way -- it is only the code
        that moved.
        """
        message = _roll(tmp_path, _Runner(passed=3))["error_message"]
        assert "neither a red-entry marker" in message, message
        assert "cannot tell" not in message, message

    def test_a_properly_red_run_is_untouched(self, tmp_path):
        result = _roll(tmp_path, _Runner(passed=0, failed=4))
        assert result.get("error_message", "") == "", result


class TestTheRowsMovedWithTheCode:
    def test_the_retired_row_is_gone(self):
        assert RETIRED not in registry_by_key(), (
            "its only site moved; a row that names no code is a promise "
            "about nothing"
        )

    def test_the_site_is_owned_by_the_row_that_shares_its_conclusion(self):
        row = registry_by_key()[OWNER]
        assert SITE in row.sites, row.sites
        assert row.judges == JUDGES_INFRASTRUCTURE
        assert row.action == ACTION_HALT, (
            "nothing softened here -- the site still halts, for the same "
            "reason, under a row that reads it correctly"
        )

    def test_the_walker_still_finds_that_site_and_it_is_registered(self):
        """The renumbering guard. Retiring a row is where a site quietly
        becomes unregistered, and the audit's own check is what catches it."""
        from pathlib import Path

        sites, _ = scan_halt_sites(Path(__file__).resolve().parents[2])
        keys = {s.key for s in sites}
        assert SITE in keys, "the walker no longer sees the site at that index"
        owned = {s for gate in GATE_REGISTRY for s in gate.sites}
        assert keys <= owned, sorted(keys - owned)

    def test_no_row_claims_the_retired_key(self):
        for gate in GATE_REGISTRY:
            assert gate.key != RETIRED


class TestTheReportStillClassifiesEveryFormOfThisMessage:
    """Three texts reach this row, and the cause table must claim all three.

    Deleting the generic `impl.red_phase_failed` row is where a historical
    banner silently becomes `unclassified`, which would move the report's
    cause distribution without anyone deciding to.
    """

    @pytest.mark.parametrize("banner", [
        # The pre-#2337 pytest text, as run-issue331's banner carries it.
        "Red phase failed: 23 tests passed unexpectedly. Tests should fail "
        "before implementation exists.",
        # Today's pytest text.
        "DETERMINISTIC FAILURE: Red phase failed: 3 tests passed "
        "unexpectedly, and neither a red-entry marker nor this run's own "
        "prior writes explain them",
        # The non-pytest text this change introduces.
        "DETERMINISTIC FAILURE: Red phase failed: 3 tests passed "
        "unexpectedly. The playwright red phase cannot tell this run's own "
        "prior writes from an implementation that predates the stage",
    ])
    def test_each_form_lands_on_the_owning_row(self, banner):
        from assemblyzero.speedrun.factory_report import classify_cause

        assert classify_cause(banner) == OWNER, banner
