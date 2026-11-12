# Implementation Report: five stale or state-dependent tests (#4528, #4529, #3737, #4733, #3730)

One branch clears four of the five failures named in these issues. The fifth goes green when the operator deploys the law.

## #4528: the auto-reviewer wait-loop tests are retired

`tests/test_auto_reviewer_wait_loop.py` (16 tests) pulled the "Wait for required checks" step out of `.github/workflows/auto-reviewer.yml` and ran it. The step was removed on purpose when the job was retired (#3663, commit `92f0e912`, which also set the job to `if: false`), and the callers are retired by #4719. No workflow holds the step now, so the file is deleted. `tests/unit/test_cerberus_after_auto_review.py::test_the_retired_reusable_workflow_still_reads_them_only_in_a_job_that_never_runs`, in the unit tier CI runs, still fails if the job's `if: false` is removed.

## #4529 and #3737: the orchestrator fixture, and a stage with no runner fails by name

The fixture `mock_all_stages` in `tests/integration/test_orchestrator_graph.py` stubbed every runner except `visual`, the stage #2518 put between lld and spec. Once lld passed, `current_stage` was `visual`, and `_run_stage_node` returned `{}` for a stage with no runner. The state did not change, `_route_after_stage` sent the graph back to `run_stage`, and the run looped until `GraphRecursionError`.

CI passed because it never ran the test. Its integration step selects `-m integration`, and the file has no such marker: `--collect-only -m integration` on it deselects all 9 tests. No environment difference was involved.

- The fixture gains a `visual` runner.
- `assemblyzero/workflows/orchestrator/graph.py`: a stage with no runner raises `MissingStageRunnerError`, which names the stage, the runners present and `STAGE_ORDER`. `done` still returns no update.
- `tests/unit/test_orchestrator_stage_runners.py` (new, 5 tests) holds `STAGE_RUNNERS` and `STAGE_ORDER` to the same set and checks the raise directly. It also runs the compiled graph with `visual`'s runner removed, with a recursion limit of 50, and expects `MissingStageRunnerError`. A control runs the same graph with every runner and reaches `done`.

## #4733: the spend lock is checked against its owner

`tests/test_universal_claude_md.py` has `STATE_FILES`, a closed list with one entry, `~/.claude/claude-spend.lock`, which gives its reason and its owner, `assemblyzero/core/seats.py` `LOCK_NAME`. For that path the check asserts that `LOCK_NAME` equals the basename; it does not look for the file. Every other `~/.claude/` path must still exist.

## #3730: ADR numbers are placed by the repository the law names

`find_unresolved_adr_references` reads each `Projects/<Repo>/docs/adrs/NNNN-` path in the law and maps the number to the repository it names, taken from the text at run time. A citation of `ADR-NNNN` is looked up there, and in AssemblyZero only when the text names no repository. A number named in two repositories cannot be placed. Every failure names the lines that cite the number.

The checkers now take the text as an argument. `tests/unit/test_universal_claude_md_checkers.py` (new, 7 tests) runs them on fixtures in the unit tier, because the live-law tests skip wherever the law is not on disk.

## Left open

On the installed law, ADR-0003 still fails, because the law gives it no path. The law's ADR-0003 citation gains its path in a separate change; this test goes green when the operator deploys the law.
