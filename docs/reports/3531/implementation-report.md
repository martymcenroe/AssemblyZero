# Implementation Report — The unit suite stays out of the operator's home state (#3531)

Parent: #3502. Found 2026-09-24 while writing the #3511 test.

## What was wrong

`save_state_snapshot` writes to `assemblyzero/core/state_persistence.py`'s
`STATE_DIR`, which is `~/.assemblyzero/workflow_state/`; `resume_contract.py`
and `halt_node.py` import that name and hold their own copies; and
`log_workflow_execution` appends to `WORKFLOW_AUDIT_FILE`, which is
`~/.claude/assemblyzero/workflow-audit.jsonl` and, being absolute, is
unchanged by the `target_repo /` join in front of it. Nothing in
`tests/conftest.py` redirected any of the four, so isolation was left to
each test. Some did it (`test_halt_node.py`, the mock-run tests of #3512,
#3533 and #3510); the rest did not. The directory held `testing-4242.json`
and `resume-contract-testing-4242.json` from a fixture issue number, a real
`check_and_consume("testing", 4242)` would have read them, and 46,308 of
the audit log's 59,609 lines named a target under the OS temp directory.

## What changed

`tests/home_state_guard.py`, new:

- `GUARDED_PATHS`: the two paths above.
- `redirect(monkeypatch, root)`: points all four bindings at `root`. It also
  records the bindings' original values the first time it runs, for
  `real_bindings()`.
- `snapshot(paths)` and `changes(before, after)`: `{path: (size, mtime_ns)}`
  for every file under the guarded paths, and the lines that differ.

`tests/conftest.py`:

- `home_state_stays_out_of_home`, autouse, unconditional: every test's halt
  snapshots, resume contracts and audit lines land under its own `tmp_path`.
  A test that patches a binding itself still wins, since its monkeypatch runs
  later; the existing per-test patches are untouched.
- `pytest_sessionstart` snapshots the real paths; `pytest_sessionfinish`
  compares, prints each added, removed or changed path under a `FAIL:` line,
  and sets the session's exit status to 1. Requirement 2: the check on the
  fixture's knowledge, so a writer nobody redirected fails the run it first
  appears in.

`tests/unit/test_path_constants_absolute.py`: its two assertions about
`WORKFLOW_AUDIT_FILE` (absolute, under `~/.claude`, #1151) describe the
constant's design, and the redirected attribute can no longer answer that.
They read `real_bindings()["WORKFLOW_AUDIT_FILE"]` now.

## What did not change

- The 4242 files and the audit log's test lines are left in place. The
  issue says the operator judges them; a script that clears them is the
  subject of a separate issue now that the suite has stopped adding to them.
- Other home paths (`~/.assemblyzero/telemetry`, `metrics_cache.json`,
  `gemini-credentials.json`, `~/.claude/assemblyzero/hourglass`) are not
  guarded here. The issue names the two that tests were found writing; a
  path that a later run shows tests writing gets added to `GUARDED_PATHS`
  and the same guard catches it.
