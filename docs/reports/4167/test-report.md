# Test Report: the unit tier is green on a WSL checkout and tells the truth

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issues** | #4253, #4202, #4249, #4190, #3731, #4242, #4167 |
| **Implementation Report** | `docs/reports/4167/implementation-report.md` |
| **Date** | 2026-10-30 |
| **Machine** | Ubuntu under WSL2 (kernel 6.18.33.2-microsoft-standard-WSL2), 24 threads, checkout on `/mnt/c`; other agents running throughout, one-minute load average 6 to 19 |
| **Python** | 3.14, the worktree's own poetry environment |

Every "before" run below is the new or changed test against the code as it stood before that issue's change: the harness file was copied aside, `HEAD`'s version put back with `git show HEAD:<path> > <path>`, the test run, and the copy restored and checked with `cmp`.

## 2. Per issue

### #4253: no tier sees the machine's agy

| Run | Result |
|---|---|
| `tests/unit/test_agy_isolation.py`, before | 2 failed, 3 passed: `assert '/home/mcwiz/.local/bin/agy' is None` for the client and for `_find_linux_agy()` |
| same, after | 5 passed |
| the 34 unit test files that touch the Gemini client, with the fixture and no other change | 13 failed: the 10 lookup tests (need the marker) and the 3 `TestProgrammingErrorsAreNotRetried` watchdog tests, the CI failure of PR #4252 reproduced locally |
| the five affected files after markers and the stand-in | 77 passed |
| `-m real_agy_lookup` with `HOME` and `PATH` set so no agy exists | 14 passed, 50 deselected |

The Windows-branch test (`test_t1_a_windows_client_finds_no_agy_inside_wsl`) passed before the fix here only because `wsl.exe` is not on this shell's `PATH`; it fails before the fix wherever WSL is reachable.

### #4202: no test writes under the start directory's `data/`

The 105 files are every file in `tests/unit/` that names one of `validate_test_plan`, `validate_mechanical`, `validate_lld_mechanical`, `analyze_requirements`, `run_spec_stage`, `narrated`, `validate_completeness`, `record_failure`, `record_stage_enter`, `record_node_enter`, `record_terminal`, `record_hallucination`, `orchestrator.graph` or `orchestrator import graph` (a `grep -rlE` on those words). The before run was at the branch point, `7542e384`; the after run at `f6a64ad5`. They ran with the worktree's environment's `pytest` from an empty directory outside the worktree.

| Run | Result |
|---|---|
| 105 unit test files that reach the writers, from an empty directory outside the checkout, before | 2,262 passed, 7 skipped, exit 0; left `data/speedrun/telemetry/prompt-failures.jsonl` there, 9 rows with `"repo": "."` (checks `test-plan` 6, `requirements-conflict` 1, `mechanical` 2) |
| same, after (`f6a64ad5`) | 2,269 passed, 7 skipped, exit 0; the directory holds nothing (the seven new isolation tests are the difference) |
| `tests/unit/test_checkout_telemetry_isolation.py`, before | 3 failed, 6 passed: the guarded-paths test (no `START_DIR`), the start-directory test (`FileNotFoundError` in the sink: the record went to `started-here/data/`), and the child-pytest test (`data`, `data/speedrun/telemetry/prompt-failures.jsonl`, `run-records.jsonl` and `data/telemetry` appeared under the empty directory) |
| same, after | 9 passed |

### #4249: the cascade config

| Run | Result |
|---|---|
| `test_checkout_telemetry_isolation.py`, before | 3 failed, 9 passed: guarded paths lacked the config; `load_user_patterns()` returned `[]` (the checkout's copy) instead of `['CP-4249']`; the guard did not contain the path. The kept-behaviour test (no config written) passed |
| same, after | 12 passed |
| neighbours: `test_cascade_detector.py`, `test_cascade_action.py` | 73 passed with the isolation file |
| neighbours: `tests/integration/test_cascade_hook_integration.py`, `test_circular_imports.py`, `test_mechanical_hooks.py` | 49 passed |

Evidence that no test wrote the file: the primary checkout's copy has modification time 2026-02-25 10:31:53 Central and is 365 bytes; the 4:37 PM time #4249 cites equals the `git worktree add` of `../AssemblyZero-3780p1` at 21:37:06 UTC (4:37 PM CDT) in session `1b2e2a0c`.

### #4190 and #3731: the cascade detector's timing tests

| Run | Result |
|---|---|
| old tests, full four-file run from the checkout, load average 19 | `test_max_input_latency` failed: 5.25 ms |
| old tests, four files from another directory | `test_typical_input_latency` failed: 5.49 ms |
| old tests, pytest pinned to one core shared with three CPU burners | `test_max_input_latency` failed: 6.22 ms; 3 passed |
| new tests, same pinning, burners still running | 8 passed |
| new tests, three runs back to back, load average 11.5 to 11.8 | 8 passed each time |
| benchmark tier alone, `-m benchmark tests/benchmark`, load average 6 | 2 failed: 5.62 ms (typical) and 6.70 ms (cap); the hook's real path reads the config from `/mnt/c` each call |
| `pytest tests/benchmark` with the default options | 2 deselected |

Calibration, the fastest of 20 and of 50 interleaved rounds, load average 14.8: linear ratio 9.3 and 9.4; quadratic fixture 89.0 and 89.4; overhead 1.06 and 1.04 (typical), 1.03 and 1.01 (cap); 5 ms slower detector 17.67 and 17.70 (typical), 4.54 and 4.53 (cap); ReDoS inputs 0.78 and 1.15.

### #3731, requirement 2: no unit test bounds wall-clock time

Added by the parent session after verifying the branch (commit "the last five unit tests that bound wall-clock time show the mechanism instead"). A search of `tests/unit` for files that read a clock (`perf_counter()`, `monotonic()`, `time.time()`) and assert a time against a bound found five such assertions beyond the cascade detector's: `test_credential_backoff.py:264`, `test_emergency_stop_windows_paths.py:218`, `test_llm_idle_timeout.py:150` and `:177`, `test_speedrun_emergency_stop.py:157`. Each now shows the mechanism instead, and each was run against a mutant with the mechanism removed:

| Test | Now asserts | Mutant | Result against it |
|---|---|---|---|
| `test_credential_backoff.py::test_backoff_with_notification_wakeup` | the first wait the waiter asks for is at most the 0.3 s cooldown | the cooldown left out of the wait computation | failed: `first wait asked for 0.9999778270721436s, past the 0.3s cooldown` |
| `test_llm_idle_timeout.py::test_a_silent_call_is_killed_at_the_idle_threshold` | `timeout_kind == "idle"` and the child did not exit 0 | the idle kill removed | failed: `the child ran to its end; the kill did not land` |
| `test_llm_idle_timeout.py::test_a_call_that_goes_quiet_mid_stream_is_still_killed` | the same | the same | failed: `the child slept out its 60s; the kill did not land` |
| `test_speedrun_emergency_stop.py::test_stop_lands_while_the_child_is_still_running` (renamed from `test_stop_lands_within_a_poll_interval`) | the watch fired and the child did not exit 0 | KillWatch's tree kill removed | failed: `the child slept out its 30s; the stop did not land` |
| `test_emergency_stop_windows_paths.py::test_the_launcher_returns_the_kill_verdict` | the kill verdict, and no "finished" marker from a child that writes one when its 120 s are up | not run | Windows-only; skipped on this machine and on CI |

`test_llm_idle_timeout.py::test_a_streaming_call_is_not_killed_however_long_it_runs` asserted a lower bound (`elapsed >= 12`); it now counts the 13 events the child prints. The four files: 54 passed, 11 skipped (Windows-only) with the mechanisms in place.

### #4242: `TestRunJsGate`

| Run | Result |
|---|---|
| `-k TestRunJsGate`, before | 2 failed, 7 passed: the two cleanup tests |
| same, after | 11 passed |
| refusal test against a mutant with the ownership gate removed | 2 failed (`main checkout`, `not a repository`); tool restored and compared with `HEAD` |
| `test_dependabot_review.py` and `test_dependabot_worktree_guard.py` | 155 passed |

### #4167: the eleven tests

| Run | Result |
|---|---|
| the four files from the checkout, before | all 11 passed (1 failure in the run was `test_max_input_latency`, #4190) |
| the four files from another directory, before | 6 failed, 4 errors, 1 skipped: the 11, exactly |
| `test_runs_on_real_lineage`, before, from a directory holding an empty `docs/lineage/active` | failed: "No verdict files found in docs/lineage/active" |
| the four files from another directory, after | 106 passed |
| the four files from the checkout, after | 106 passed |

## 3. The full unit tier, run once

`poetry run pytest tests/unit -q -p no:cacheprovider` from the worktree at `f6a64ad5`, 2026-10-30 7:15 to 7:25 PM Central; output in the worktree's `data/unit-tier-final.txt` (not tracked).

```
2 failed, 11557 passed, 66 skipped, 7 deselected, 6 xfailed, 13 warnings in 591.97s (0:09:51)
```

The session guard printed no `FAIL:` line: no test wrote into the home state, the telemetry logs or the cascade config.

| Failure | On the branch's parent? | Cause |
|---|---|---|
| `tests/unit/test_extract_and_discard.py::TestBlockedVerdictExtraction::test_blocked_verdict_stores_summary_not_prose` | yes: fails identically with `7542e384`'s `tests/conftest.py` and `tests/checkout_telemetry_guard.py` put back (the test file is unchanged) | `KeyError: 'test_plan_status'`: the stand-in verdict carries no rationale, which #3802's parser now requires. The `3780-core-part-1` branch has the test fix (`57457dca`, "the two extraction tests' stand-in verdicts carry their rationale"); this branch does not. |
| `tests/unit/test_extract_and_discard.py::TestApprovedVerdictExtraction::test_approved_verdict_stores_summary_not_prose` | yes, the same | the same |

Warnings, 13, none from this change:

| Count | Type | Source | Message |
|-------|------|--------|---------|
| 12 | `PytestCollectionWarning` | `assemblyzero/workflows/testing/framework_detector.py:17` | cannot collect test class `TestFramework` because it has a `__new__` constructor (an `Enum` whose name starts with `Test`, imported into 12 test modules) |
| 1 | `UserWarning` | `langchain_core/utils/pydantic.py:42` | Core Pydantic V1 functionality is not compatible with Python 3.14 or greater (a dependency) |

No timing test failed. Said plainly about load: the machine was light during this run (one-minute load average 3.88 at the start and 0.76 at the end), so this run alone does not show the timing tests hold under load. That evidence is the one-core contention runs in section 2, where the old check failed and the new ones passed.

### Not in scope: #3737

`tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` fails with `GraphRecursionError` (recursion limit 10007) on this branch, and fails the same way with the parent's `tests/conftest.py` and `tests/checkout_telemetry_guard.py` put back. These changes do not affect it.
