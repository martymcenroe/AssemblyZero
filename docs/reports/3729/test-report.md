# Test Report: #3729 and #4160

## New tests

- **`tests/unit/test_alert_channel_at_start.py` (13).**
  - With `check_alert_channel` raising, each entry point exits 1 with `ERROR [preflight] <entry>` and the reason on stderr, and sends no alert. What it would have called first is a stand-in that must not be reached: the LLD workflow, the issue workflow, the implementation workflow (no graph built, no resume contract consumed), the spec workflow, the orchestrator, the janitor, the scout, the replay and the hourglass (no graph built, no age meter read).
  - `test_a_real_child_process_refuses_with_no_stand_in`: the orchestrator as its own process, nothing patched, a home with no `alert.json` and no sender. It exits 1 at the check, prints no "Starting pipeline", and writes no alerts log.
  - `test_the_child_helper_gives_a_working_channel`: the same child with `child_env_with_alert_channel` passes the check and reaches the merge-driver refusal.
  - The stand-in is in place in every tier, and `require_alert_channel` returns the sender when the channel works.
- **`tests/unit/test_alert.py` (+2)** on the real check: `test_the_start_up_check_refuses_loudly_without_alerting` (exit 1, the reason on stderr, no alerts log) and `test_the_start_up_check_passes_a_working_channel`.
- **`tests/unit/test_az_environment_isolation.py` (11).** The set holds every `AZ_` name the code reads, and nothing else. A probe file with an unlisted name is reported with its file and line (T2 of #4160). Each of the eight is unset in every test (T1), while this machine exports two of them.

## Changed test

- `test_orchestrator_lands_through_driver.py::test_orchestrate_refuses_without_the_driver` runs `orchestrate.py` as a child process. The child now checks the alert channel first, where the tiers' stand-in cannot reach, so it refused there and never reached the driver check under test. The first full tier failed it. It now gives the child `child_env_with_alert_channel`.

## Before the fix, measured

Stashed by named path in the worktree, then reapplied, checked and dropped each time:

- **The nine source files stashed:** 12 of the 13 start-up tests then written failed. The one that passed checks only the conftest stand-in.
- **`tests/conftest.py` stashed:** `test_az_environment_isolation.py` cannot import `AZ_ENVIRONMENT`. In the start-up file, the two stand-in tests failed with `assert 'assemblyzero@martymcenroe.ai' == 'tests@example.invalid'`: without the new conftest, the tests read this machine's real sender. That is #4160's defect, shown on this variable.

## Tiers (no other test run on the machine)

```
pytest tests -q, first run                      23 failed, 11658 passed  (the 22 below + test_orchestrate_refuses_without_the_driver)
pytest tests -q, after the fix                  22 failed, 11661 passed, 66 skipped, 90 deselected, 6 xfailed (13m 06s)
pytest -m "integration or e2e or adversarial"   83 passed, 7 skipped
```

All 22 also fail without this change on this machine, as recorded for PR #4159: `test_auto_reviewer_wait_loop.py` (16), `TestRunJsGate` (2), `test_adr_references_resolve`, `test_full_pipeline_success`, `test_checkpoint_carries_no_enums::test_the_unit_tier_runs_the_serializer_strict`, and `test_max_input_latency` (the environment-sensitive bound of #3731).

## Audits

```
audit_loud_failure.py --check            PASS -- 317 site(s), all in the baseline (#3581)
audit_fail_open.py --check --strict      PASS -- 312 files, 9710 sites examined (baseline regenerated: denominator 9708 to 9710, findings unchanged)
audit_halt_sites.py --check              PASS -- 152 halt sites, every one registered
```

## Lint

The twelve changed Python files carry 84 ruff findings, the same count as on `main`; the two new test files have none.
