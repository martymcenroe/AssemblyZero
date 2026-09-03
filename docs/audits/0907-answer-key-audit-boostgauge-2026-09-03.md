# Answer-key audit — C:\Users\mcwiz\Projects\boostgauge

Generated 2026-09-03 12:16:46. The shipped code on main is the answer key; a refusal below is a gate rejecting content the operator shipped.

A refusal on `impl.path_enforcement` means the LLD's file plan and the shipped file names disagree: the gate holds the drafter to a plan the hand build did not follow. A refusal on the test-file gates means a hand-written test delegates its assertion to a helper the gate cannot see.

## Coverage — counted, not estimated

- Features: 6
- Files examined: 17
- LLDs examined: 1
- Merged commits examined: 6
- Verdicts: 50; refusals: 6

## Per gate

| gate | ran | refused |
|---|---|---|
| impl.deterministic_failure | 9 | 0 |
| impl.file_generation_failed | 17 | 0 |
| impl.path_enforcement | 7 | 4 |
| impl.scenario_ratio_guard | 1 | 0 |
| impl.test_file_validation | 9 | 2 |
| lld.mechanical_validation | 1 | 0 |
| pr.commit_message_guard | 6 | 0 |

## Refusals — each one is a false positive by construction

- #4 `impl.path_enforcement` on `src/boostgauge/collectors/__init__.py`: Rejected: 'src/boostgauge/collectors/__init__.py' not in LLD-specified paths. Did you mean 'src/boostgauge/collectors/windows.py'?
- #4 `impl.path_enforcement` on `tests/benchmark/test_sweep_cost.py`: Rejected: 'tests/benchmark/test_sweep_cost.py' not in LLD-specified paths. Did you mean 'tests/benchmark/test_windows_sweep.py'?
- #4 `impl.path_enforcement` on `tests/integration/test_windows_sweep_crosscheck.py`: Rejected: 'tests/integration/test_windows_sweep_crosscheck.py' not in LLD-specified paths. Did you mean 'tests/integration/test_windows_collector.py'?
- #4 `impl.path_enforcement` on `tests/unit/test_collector_source_pin.py`: Rejected: 'tests/unit/test_collector_source_pin.py' not in LLD-specified paths. Did you mean 'tests/unit/test_collector.py'?
- #41 `impl.test_file_validation` on `tests/unit/test_telltale.py`: Function 'test_V4_equal_timestamp_is_accepted' has no assertion statements
- #332 `impl.test_file_validation` on `tests/visual/test_stingray_dynamic.py`: Function 'test_dynamic_256_matches_baseline' has no assertion statements

## Every verdict

| issue | gate | artifact | outcome | detail |
|---|---|---|---|---|
| #2 | impl.deterministic_failure | `tests/unit/test_session.py` | pass | 0 of 16 test(s) read as stubs |
| #2 | impl.file_generation_failed | `src/boostgauge/session.py` | pass |  |
| #2 | impl.file_generation_failed | `tests/unit/test_session.py` | pass |  |
| #2 | impl.test_file_validation | `tests/unit/test_session.py` | pass |  |
| #2 | pr.commit_message_guard | `merged commit subject` | pass | feat: telltale wiring — four instances from config, sample fan-out, four-slot peaks with None passed |
| #4 | impl.deterministic_failure | `tests/benchmark/test_sweep_cost.py` | pass | 0 of 1 test(s) read as stubs |
| #4 | impl.deterministic_failure | `tests/integration/test_windows_sweep_crosscheck.py` | pass | 0 of 1 test(s) read as stubs |
| #4 | impl.deterministic_failure | `tests/unit/test_collector.py` | pass | 0 of 8 test(s) read as stubs |
| #4 | impl.deterministic_failure | `tests/unit/test_collector_source_pin.py` | pass | 0 of 3 test(s) read as stubs |
| #4 | impl.file_generation_failed | `src/boostgauge/collector.py` | pass |  |
| #4 | impl.file_generation_failed | `src/boostgauge/collectors/__init__.py` | pass |  |
| #4 | impl.file_generation_failed | `src/boostgauge/collectors/windows.py` | pass |  |
| #4 | impl.file_generation_failed | `tests/benchmark/test_sweep_cost.py` | pass |  |
| #4 | impl.file_generation_failed | `tests/integration/test_windows_sweep_crosscheck.py` | pass |  |
| #4 | impl.file_generation_failed | `tests/unit/test_collector.py` | pass |  |
| #4 | impl.file_generation_failed | `tests/unit/test_collector_source_pin.py` | pass |  |
| #4 | impl.path_enforcement | `src/boostgauge/collector.py` | pass | Path matches LLD specification |
| #4 | impl.path_enforcement | `src/boostgauge/collectors/__init__.py` | REFUSE | Rejected: 'src/boostgauge/collectors/__init__.py' not in LLD-specified paths. Did you mean 'src/boostgauge/collectors/windows.py'? |
| #4 | impl.path_enforcement | `src/boostgauge/collectors/windows.py` | pass | Path matches LLD specification |
| #4 | impl.path_enforcement | `tests/benchmark/test_sweep_cost.py` | REFUSE | Rejected: 'tests/benchmark/test_sweep_cost.py' not in LLD-specified paths. Did you mean 'tests/benchmark/test_windows_sweep.py'? |
| #4 | impl.path_enforcement | `tests/integration/test_windows_sweep_crosscheck.py` | REFUSE | Rejected: 'tests/integration/test_windows_sweep_crosscheck.py' not in LLD-specified paths. Did you mean 'tests/integration/test_windows_collector.py'? |
| #4 | impl.path_enforcement | `tests/unit/test_collector.py` | pass | Path matches LLD specification |
| #4 | impl.path_enforcement | `tests/unit/test_collector_source_pin.py` | REFUSE | Rejected: 'tests/unit/test_collector_source_pin.py' not in LLD-specified paths. Did you mean 'tests/unit/test_collector.py'? |
| #4 | impl.scenario_ratio_guard | `docs/lld/active/LLD-004.md` | pass | 26 scenario(s), 8 requirement(s) |
| #4 | impl.test_file_validation | `tests/benchmark/test_sweep_cost.py` | pass |  |
| #4 | impl.test_file_validation | `tests/integration/test_windows_sweep_crosscheck.py` | pass |  |
| #4 | impl.test_file_validation | `tests/unit/test_collector.py` | pass |  |
| #4 | impl.test_file_validation | `tests/unit/test_collector_source_pin.py` | pass |  |
| #4 | lld.mechanical_validation | `docs/lld/active/LLD-004.md` | pass |  |
| #4 | pr.commit_message_guard | `merged commit subject` | pass | feat: auto-calibrated thresholds — 100 is this machine's own high; seed at 2.5x so the needle starts |
| #5 | impl.deterministic_failure | `tests/unit/test_app.py` | pass | 0 of 7 test(s) read as stubs |
| #5 | impl.file_generation_failed | `src/boostgauge/app.py` | pass |  |
| #5 | impl.file_generation_failed | `tests/unit/test_app.py` | pass |  |
| #5 | impl.test_file_validation | `tests/unit/test_app.py` | pass |  |
| #5 | pr.commit_message_guard | `merged commit subject` | pass | feat: the window — frameless always-on-top gauge, drag, keyed transparency, wheel resize, hover tool |
| #7 | impl.deterministic_failure | `tests/unit/test_config.py` | pass | 0 of 25 test(s) read as stubs |
| #7 | impl.file_generation_failed | `src/boostgauge/config.py` | pass |  |
| #7 | impl.file_generation_failed | `tests/unit/test_config.py` | pass |  |
| #7 | impl.test_file_validation | `tests/unit/test_config.py` | pass |  |
| #7 | pr.commit_message_guard | `merged commit subject` | pass | feat: configuration file and CLI — three write moments, threshold-only hot reload, session-only CLI  |
| #41 | impl.deterministic_failure | `tests/unit/test_telltale.py` | pass | 0 of 24 test(s) read as stubs |
| #41 | impl.file_generation_failed | `src/boostgauge/telltale.py` | pass |  |
| #41 | impl.file_generation_failed | `tests/unit/test_telltale.py` | pass |  |
| #41 | impl.test_file_validation | `tests/unit/test_telltale.py` | REFUSE | Function 'test_V4_equal_timestamp_is_accepted' has no assertion statements |
| #41 | pr.commit_message_guard | `merged commit subject` | pass | feat: auto-calibrated thresholds — 100 is this machine's own high; seed at 2.5x so the needle starts |
| #332 | impl.deterministic_failure | `tests/visual/test_stingray_dynamic.py` | pass | 0 of 14 test(s) read as stubs |
| #332 | impl.file_generation_failed | `src/boostgauge/skins/stingray.py` | pass |  |
| #332 | impl.file_generation_failed | `tests/visual/test_stingray_dynamic.py` | pass |  |
| #332 | impl.test_file_validation | `tests/visual/test_stingray_dynamic.py` | REFUSE | Function 'test_dynamic_256_matches_baseline' has no assertion statements |
| #332 | pr.commit_message_guard | `merged commit subject` | pass | feat: Stingray dynamic layer — four telltales, main needle, pivot cap over the cached face; approved |

## Not runnable against a finished artifact

- `impl.stagnation.coverage`: needs two iterations of a live green loop
- `impl.stagnation.test_count`: needs two iterations of a live green loop
- `impl.stagnation.test_identity`: needs two iterations of a live green loop
- `impl.stagnation.full_suite`: needs a live full-suite run
- `impl.stagnation.e2e`: needs a live e2e loop
- `impl.red_phase_failed`: needs pytest run against the pre-implementation tree
- `impl.red.import_errors`: needs pytest run against the pre-implementation tree
- `impl.green.collection_broken`: needs a pytest collection run
- `spec.pinning_refusal`: needs a previous draft and a revision
- `spec.conservation_gate`: needs a previous draft and a revision
- `spec.edit_script_rejected`: needs a spec and a SEARCH/REPLACE revision
- `spec.finalize.draft_guard`: needs a spec draft; none survives on main
- `spec.review.empty_draft`: needs a spec draft; none survives on main
- `spec.review_blocked`: is a reviewer model's verdict, not a mechanical rule
- `spec.reviewer_verdict_unreadable`: is about the reviewer's output
- `impl.reviewer_verdict_unreadable`: is about the reviewer's output
- `impl.test_plan_revision_incomplete`: needs a test-plan revision
- `lld.test_plan_validation`: needs the LLD draft loop
- `lld.best_of_n_unusable`: needs N drafts
- `lld.edit_script_rejected`: needs an LLD and a SEARCH/REPLACE revision
