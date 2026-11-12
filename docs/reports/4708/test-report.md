# Test report: #4708, #4709

Run in Ubuntu (WSL) in the worktree's own poetry environment.

## New tests

- `tests/unit/test_home_state_guard.py::TestTheTracedWritersAreRedirected` (#4708 R1, T1): the buffer, history and age-meter bindings, the two defaults included, point under `tmp_path`; an emitted event with no DynamoDB client lands in the test's own buffer and leaves the real one unchanged; the rest node, unpatched, writes `history.json` and `age_meter.json` under `tmp_path` and leaves the real hourglass unchanged.
- `tests/unit/test_home_state_guard.py::TestTheSessionGuard` (#4708 R2, T2): `TRACED_PATHS` is the buffer and the hourglass directory, `snapshot()` defaults to all four paths, and `real_bindings()` holds the design values. `test_a_session_that_writes_a_traced_path_fails_with_it_named`, for each of the two, runs a child session whose home is under `tmp_path` and whose one test writes the path directly, past every binding: it exits 1 and names the file.
- `tests/unit/test_orchestrator_stages.py::TestTriageBriefStaysOutOfTheSystemTemp` (#4709 T1): the brief lands under `tmp_path` and the system temp gains no `orchestrator-issue-4709-*.md`. Without the module's autouse fixture `mkstemp` writes to the system temp, which is not under `tmp_path`, so the test fails.

## Targeted

`test_home_state_guard.py`, `test_orchestrator_stages.py`, `test_path_constants_absolute.py`, `tests/unit/test_death/`, `test_telemetry_emitter.py` and `test_telemetry_emitter_loud_failure.py`: 161 passed. `test_profile_bench.py`: 21 passed, the real buffer unchanged.

## Acceptance, measured

- #4708 AC1: after the final full run, `~/.assemblyzero/telemetry-buffer` and `~/.claude/assemblyzero/hourglass` have the same files, sizes and mtimes as before it, and the session guard reported nothing.
- #4709 AC1: `/tmp` held 24 `orchestrator-issue-*.md` files from earlier runs before the targeted run, and 24 after the final full run.

## Full suite

`poetry run pytest -q -p no:cacheprovider -rf` on this branch.

The first run, before the `test_profile_bench.py` change: 15064 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, and the session guard failed the run with `added: ~/.assemblyzero/telemetry-buffer/2026-11-12.jsonl`. That is the third writer the implementation report describes.

The final run: 15064 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 24 min 15 s, with no guard failure. Every failure is in a file this branch does not touch, and each is already failing on `main` and tracked:

- 16 in `tests/test_auto_reviewer_wait_loop.py` (#4528).
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` (#4529, #3737).
- `tests/test_universal_claude_md.py::test_adr_references_resolve` (#3730).

All 18 were run on `origin/main` (d1de7a95) in a detached worktree: 18 failed, the same 18.
