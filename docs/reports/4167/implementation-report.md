# 4167 - Implementation Report: the unit tier is green on a WSL checkout and tells the truth

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issues** | #4253, #4202, #4249, #4190, #3731, #4242, #4167 |
| **Test Report** | `docs/reports/4167/test-report.md` |
| **Implementer** | Claude Opus 5.5 via Claude Code (Ubuntu, WSL) |
| **Date** | 2026-10-30 |
| **Branch** | `4167-unit-tier-green`, cut from `3780-core-loud-failure` at `7542e384` |

The goal, the operator's: the unit tier is green on a WSL checkout and tells the truth. A local tier predicts CI, a load-sensitive test does not fail because the machine is busy, and no test writes into the checkout. Every change is in the test harness or in tests; no module under `assemblyzero/` or `tools/` changed.

## 2. Summary, one issue at a time

### #4253: the tiers could find this machine's agy (commit `4717b5d1`)

As the issue says. `tests/conftest.py` gains the autouse fixture `no_agy_from_the_machine`, which replaces `gemini_client._find_linux_agy` and `_find_wsl_agy` with lookups that find nothing, as CI's do. A test that needs agy present gives its client a stand-in path (`client._agy_cli = "/stand-in/agy"`). A test of the lookup itself carries the new marker `real_agy_lookup` and patches every input the lookup reads: 13 lookup tests carry it, plus one in the new guard file, and all 14 pass with `HOME` and `PATH` set so that no agy exists. The opt-in live adversarial probe carries it too, since it exists to call the real agy.

The fixture reproduced CI's failure at once: the three `TestProgrammingErrorsAreNotRetried` watchdog tests failed locally exactly as on PR #4252's CI run. They get the stand-in the `core/` part-1 branch gave them, byte for byte (`cmp` against `7bbdaac8`'s file), so the two branches merge without a conflict there.

### #4202: tests wrote telemetry under the working directory's `data/` (commit `b5db86e6`)

Checked first what #4161's redirect covers. It redirects a write whose root resolves to the checkout. Run from the checkout, that is every write. Run from anywhere else, it misses one case: three nodes write prompt failures under `state["target_repo"] or "."`, so a test whose state names no repository writes under the directory pytest started in. Measured on this branch before the change: the 105 unit test files that reach the writers, run from an empty directory outside the checkout, passed 2,262 and left `data/speedrun/telemetry/prompt-failures.jsonl` in that directory, 9 rows reading `"repo": "."`, from the test-plan, mechanical and requirements-conflict checks. The session guard did not notice. That is the issue's second evidence item, reproduced.

The redirect in `tests/checkout_telemetry_guard.py` now treats the start directory itself (`START_DIR`, read when `conftest.py` first imports the module at session start) as a guarded root beside the checkout, and the session guard watches each writer's file under both. Only the start directory itself moves, not what lies under it, so a test's own `tmp_path` is never redirected even when a run starts from `/tmp`.

Premise correction: `assemblyzero/speedrun/prompt_ranking.py`, which the issue lists as a writer, only reads the log (`load_telemetry`, `load_durations`); it writes nothing. The other three writers are the ones #4161 already redirected; none was missed.

### #4249: the tracked `data/unleashed/cascade_block_patterns.json` (commit `84b246a9`)

The issue's premise is wrong in its central claim. Nothing writes this file: `load_user_patterns` only reads it, and no code in `assemblyzero/`, `tools/` or `tests/` opens it for writing. The 4:37 PM Central modification time the issue cites is when `git worktree add` created that worktree: the session transcript records the command at 21:37:06 UTC. The primary checkout's copy still carries its 2026-02-25 modification time after eight months of tier runs.

The real defect was the read. `_DEFAULT_CONFIG_PATH` is relative to the working directory, so a test that loaded patterns with no path read the checkout's copy, a file the operator may edit and CI never has edited, and every `detect_cascade_risk` call read it from `/mnt/c`. The requirements still fit: the redirect points `_DEFAULT_CONFIG_PATH` at the per-test sink, and `GUARDED_FILES` carries the checkout's copy, so the first test that ever writes it fails the session. A pinned test asserts that loading and detecting write no config.

### #4190 and #3731: the cascade detector's wall-clock tests (commit `180b675a`)

Both, said plainly: the unit tier now measures what the code controls, without depending on load, and the genuine timing check moved to the benchmark tier.

The four tests (two latency, two ReDoS) asserted absolute bounds, 5 ms average and 100 ms. Most of the 5 ms was not the detector's work: the per-call read of the checkout's cascade config on `/mnt/c` took 2.2 to 3.8 ms of it, against a regex scan of 0.14 ms at 1,000 characters and 1.4 ms at 10,000.

Each unit check now times two calls in interleaved rounds and compares their fastest runs. Load only adds time, and interleaving makes a busy stretch slow both alike, so the ratio is what the code controls:

| Check | Compares | Bound | Measured |
|---|---|---|---|
| T200, T210 overhead | detection against the bare scan of its own patterns, typical 2,000 and cap 10,000 characters | 3x | 1.01 to 1.06 |
| scaling | the 10,000-character cap against 1,000 characters | 30x | 9.3 to 9.4 |
| ReDoS (both) | the pathological input against a benign one of its length | 10x | 0.78 and 1.15 |

Three meta-tests show each bound catches what it is for: 5 ms more per call (the old budget) fails the overhead check on both inputs (4.5x and 17.7x), a quadratic pattern fails the scaling check (89x), and a pattern that rescans the input from every position fails the blow-up check.

The absolute 5 ms budget is a genuine timing check, so it lives in `tests/benchmark/test_cascade_detector_latency.py`, under a new `benchmark` marker that the default `addopts` deselect. It does not gate merges and no CI step runs it; its docstring records the move. It takes the hook's real path, user config read included.

### #4242: the two `TestRunJsGate` tests (commit `dec7cc5e`)

As the issue says. The two cleanup tests run in a linked worktree of a throwaway repository (a `linked_worktree` fixture with real `git init` and `git worktree add`), and a parametrised test asserts that in a main checkout and in a plain directory `node_modules` is left in place and `REFUSED:` is printed on stderr. With the ownership gate removed from `tools/dependabot_review.py` (a temporary mutant, restored and compared with `HEAD`), the refusal test fails in both cases.

### #4167: 7 failed and 4 errors on a WSL checkout (commit `f6a64ad5`)

Re-measured first, by running the named tests. From the checkout, all 11 pass on 2026-10-30. From any other working directory, the same 11 fail, which is the 2026-10-16 result test for test:

| Test | What it read relative to the working directory | From another directory, before |
|---|---|---|
| `TestClaudeMdCascadeRule` (4) | `CLAUDE.md` | 4 failed: a missing file read as "no rule" |
| `TestFixtureSamples` (4) | `tests/fixtures/cascade_samples.json` | 4 errors in the fixture |
| `test_issue_161.py::test_005` | three source paths | failed |
| `TestPreReviewValidationRemoved::test_validate_draft_structure_kept_for_compat` | `generate_draft.py`, then a broken fallback | failed: `import ... as gd` binds the package's re-exported function, which has no `__file__` |
| `TestMain::test_runs_on_real_lineage` | `docs/lineage/active` | skipped when absent; failed ("No verdict files found") when the directory exists empty, as in another repository's checkout |

So the cause was the working directory, not WSL. Each test now resolves its input from its own file's location. The CLAUDE.md check asserts the file is there instead of reporting a missing file as a missing rule, and the lineage test fails, naming the directory, instead of skipping, since the lineage is tracked. After: the four files pass 106 of 106 from the checkout and from another directory.

## 3. Files created

| File | Description |
|------|-------------|
| `tests/unit/test_agy_isolation.py` | #4253 T1: no client and no lookup sees the machine's agy; the stand-in and the marker work |
| `tests/benchmark/test_cascade_detector_latency.py` | #4190, #3731: the absolute 5 ms budget, benchmark tier |

## 4. Files modified

Lines added and removed, from `git diff --numstat 7542e384..HEAD` before the reports commit.

| File | Changes | Description |
|------|---------|-------------|
| `tests/conftest.py` | +54/-6 | the no-agy fixture and marker (#4253); the session-guard headline and docstrings name the start directory (#4202) |
| `tests/checkout_telemetry_guard.py` | +78/-16 | `START_DIR` guarded beside the checkout (#4202); the cascade config redirected and guarded (#4249) |
| `pyproject.toml` | +2/-1 | the `benchmark` marker, deselected in `addopts` (#4190, #3731) |
| `tests/unit/test_checkout_telemetry_isolation.py` | +208/-4 | #4202 and #4249 tests, and the guarded-paths test for both |
| `tests/unit/test_cascade_detector.py` | +162/-40 | load-independent timing checks (#4190, #3731); checkout-anchored inputs (#4167) |
| `tests/tools/test_dependabot_review.py` | +62/-10 | the linked-worktree fixture and the refusal test (#4242) |
| `tests/unit/test_issue_161.py` | +5/-3 | checkout-anchored paths (#4167) |
| `tests/unit/test_mine_verdict_patterns.py` | +11/-6 | checkout-anchored lineage, a failure instead of a skip (#4167) |
| `tests/unit/test_open_questions_loop.py` | +8/-5 | the module's own file, by `importlib` (#4167) |
| `tests/unit/test_agy_wsl_transport.py` | +8/-0 | six lookup tests carry `real_agy_lookup` (#4253) |
| `tests/unit/test_gemini_client.py` | +3/-0 | three lookup tests carry it (#4253) |
| `tests/unit/test_gemini_client_loud_failure.py` | +1/-0 | `TestFindingAgy` (four tests) carries it (#4253) |
| `tests/unit/test_stage_watchdog.py` | +6/-1 | the stand-in agy, identical to the part-1 branch (#4253) |
| `tests/integration/test_adversarial_integration.py` | +2/-0 | the live probe carries `real_agy_lookup` (#4253) |

## 5. Deviations from the issues

| Deviation | Reason | Impact |
|-----------|--------|--------|
| #4202: `prompt_ranking.py` not touched | it reads the log and writes nothing | none |
| #4249 T1 read as: a test's no-path load reads the config the test placed under its own directory | no code writes a default config, so there is nothing to find unless the test puts it there | T1 fails before the redirect (the load read the checkout's empty list) and passes after |
| #4190 R1's "slower than its limit" is expressed as a ratio to the detector's own scan, not as 5 ms | an absolute limit is what made the test measure the machine; R2's route, the move, is used for the absolute budget | a constant 5 ms slowdown still fails the unit tier |
| #3731 R2 ("no unit-tier test asserts an absolute wall-clock bound") is met for the cascade detector's file only | the assignment was the cascade detector's tests | four other unit tests still assert absolute bounds; listed in section 9 |
| #4242 AC1 says "on a WSL checkout and on CI" | no CI step runs `tests/tools/` | the tests pass locally; CI cannot confirm them until `tests/tools/` is in a tier (section 9) |

## 6. Test harness

- **Fixtures (conftest):** `no_agy_from_the_machine` (autouse, every tier). `checkout_telemetry_stays_out_of_the_checkout` now covers the start directory and the cascade config, through `tests/checkout_telemetry_guard.redirect`.
- **Markers:** `real_agy_lookup` (registered in `tests/conftest.py`); `benchmark` (registered in `pyproject.toml`, deselected by default).
- **Fixture (tests/tools):** `linked_worktree`, a real repository and a linked worktree under `tmp_path`.
- **Utilities (`test_cascade_detector.py`):** `_fastest`, `_bare_scan`, `_with_extra_pattern`, `_assert_little_overhead`, `_assert_linear` and `_assert_no_blowup`, with the three bounds as named constants carrying their measurements.
- **Child pytest:** `test_4202_t1_a_run_from_an_empty_directory_leaves_no_data_there` starts pytest in an empty directory under `tmp_path` and runs the probe through all three writers.

## 7. Test coverage

Per issue, the before-the-fix and after results are in the test report. Every new test that guards a fix was run against the code before the fix and failed; the tests that pin kept behaviour passed both times.

The full unit tier, run once at `f6a64ad5`: 2 failed, 11,557 passed, 66 skipped. Both failures are `tests/unit/test_extract_and_discard.py`'s two verdict-extraction tests, which fail identically with the parent's harness; the `3780-core-part-1` branch carries their fix (`57457dca`). Test report, section 3.

## 7a. Loud-failure compliance (standard 0034)

No module under `assemblyzero/` or `tools/` changed, so no production failure path was added or touched. Before every commit, `tools/audit_loud_failure.py --check` reported no new site (263, all in the baseline) and `tools/audit_fail_open.py --check` reported no new fail-open.

Test-side failure paths touched:

| Site | Loud | Logged | Stops | Alerts |
|------|------|--------|-------|--------|
| `tests/conftest.py` `pytest_sessionfinish`, the telemetry guard (now two roots, plus the cascade config) | a `FAIL:` headline and one line per changed path on the terminal | each path: added, removed, or changed with both sizes | the session's exit status is 1 | the failed run is the alert; tests send no mail |
| `test_cascade_detector.py` `_validate_claude_md_cascade_rule` | the assertion names the missing file | the path | the test fails | n/a |
| `test_mine_verdict_patterns.py::test_runs_on_real_lineage` | the assertion names the missing directory | the path | the test fails instead of skipping | n/a |

## 8. Lessons learned

- A test that reads a path relative to the working directory passes on CI by construction, because CI runs from the checkout. The 11 tests of #4167 were exactly that; "WSL" was a coincidence of where the 2026-10-16 run started.
- Two issues (#4202's list of writers, #4249's write) named a cause the code does not have. Reading the module and the session transcript settled both before any fix was designed.
- Most of the cascade detector's "latency" was a file read on `/mnt/c`, not the detector. A wall-clock test cannot tell those apart; a ratio against the detector's own scan can.

## 9. New defects found (not fixed here; for filing)

| Where | What |
|-------|------|
| `assemblyzero/hooks/cascade_patterns.py`, pattern `CP-024` | Quadratic. On `"Done. "` repeated, 1,000 characters took 1.55 ms and 10,000 took 148 ms (95x for 10x): each `Done.` starts a lazy `.*?` scan to the end of the line. Only the 10,000-character cap bounds it. |
| `assemblyzero/hooks/cascade_detector.py:68-71`, through `cascade_patterns.load_user_patterns` | The user config is read from disk on every call. On a `/mnt/c` checkout that read is 2.2 to 3.8 ms of the 5 ms budget, and the benchmark tier, run alone, fails: 5.62 ms and 6.70 ms average. |
| `.github/workflows/ci.yml` | No step runs `tests/tools/` (14 files, none marked `integration`): the unit step runs `tests/unit/` only, and the `tests/ -m ...` steps deselect unmarked tests. #4242's two failures went unseen this way. |
| `tests/unit/test_emergency_stop_windows_paths.py:218`, `test_llm_idle_timeout.py:150` and `:177`, `test_speedrun_emergency_stop.py:157` | The rest of #3731 R2: absolute wall-clock bounds (60 s, 15 s, 15 s, 10 s) on a kill or a stop. Found by searching `tests/unit/` for `elapsed <` and `perf_counter`. |
| 13 more files in `tests/unit/` | A literal search for `Path("docs/`, `Path("tests/`, `Path("assemblyzero/`, `Path("tools/`, `Path("data/` and `Path("CLAUDE.md")` finds 14 test files, 13 besides #4167's (`test_open_questions_loop.py`'s remaining hits are in `TestPromptFile`, which passed from another directory). Some of the 13 only build values; whether each reads its path from the working directory was not checked. A unit tier started from an empty directory would show which. |
