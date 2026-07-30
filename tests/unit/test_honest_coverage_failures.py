"""Coverage failures are honest and terminal (#1938, #1939, #1940).

Reference incident: run11b-issue4-234552 (2026-07-30). The N5 loop printed
'50 passed, 0 failed | Exit: 1 (some tests failed)' — the coverage gate
wearing a test-failure label — then the stagnation guard's correct halt
was retried as if transient, and the stage retry resumed the identical
worktree ('Skipped (already exists)') to reproduce the identical 86%.
Meanwhile the LLD had invented a 95% target against the repo's declared
fail_under of 89, with no tests planned for the 12 defensive-concurrency
lines that made the number unreachable.
"""

from assemblyzero.core.halt_node import classify_error
from assemblyzero.workflows.orchestrator.stages import _classify_halt_transience
from assemblyzero.workflows.requirements.nodes import generate_draft
from assemblyzero.workflows.testing.exit_code_router import (
    describe_exit_code,
    describe_run_outcome,
)

LIVE_STAGNATION_MESSAGE = (
    "Coverage stagnant: 87.0% -> 86.0% (< 1% improvement). "
    "Halting to prevent token waste."
)


class TestHonestExitLabel:
    def test_exit_1_with_zero_failures_names_the_coverage_gate(self):
        label = describe_run_outcome(1, failed_count=0)
        assert "coverage" in label
        assert "tests failed" not in label

    def test_exit_1_with_real_failures_keeps_the_test_label(self):
        assert describe_run_outcome(1, failed_count=3) == "some tests failed"

    def test_unknown_failed_count_defers_to_plain_description(self):
        assert describe_run_outcome(1, failed_count=None) == "some tests failed"

    def test_other_exit_codes_pass_through(self):
        for code in (0, 2, 3, 4, 5):
            assert describe_run_outcome(code, failed_count=0) == describe_exit_code(code)


class TestStagnationIsTerminal:
    def test_live_message_classifies_stagnation(self):
        """The old 'stagnation'-only pattern never matched what the guard
        actually prints."""
        assert classify_error(LIVE_STAGNATION_MESSAGE) == "stagnation"

    def test_planless_stagnation_halt_is_non_transient(self):
        sub_result = {"error_message": LIVE_STAGNATION_MESSAGE}
        assert _classify_halt_transience(sub_result) is False

    def test_planless_non_stagnation_failure_keeps_default(self):
        """gh flakes and friends keep their retry budget (the #1463
        contract): no plan + no stagnation marker -> None -> retry-default."""
        sub_result = {"error_message": "gh CLI flake: connection reset"}
        assert _classify_halt_transience(sub_result) is None

    def test_empty_sub_result_keeps_default(self):
        assert _classify_halt_transience({}) is None


class TestDrafterCoverageGuidance:
    def test_prompt_pins_target_to_repo_gate(self):
        src = generate_draft.__dict__.get("__doc__") or ""
        import inspect

        source = inspect.getsource(generate_draft)
        assert "fail_under" in source
        assert "Issue #1940" in source

    def test_prompt_demands_reachable_targets(self):
        import inspect

        source = inspect.getsource(generate_draft)
        assert "arithmetically reachable" in source
        assert "defensive branches" in source
