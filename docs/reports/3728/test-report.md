# Test Report: the operator alert path (#3728)

## Tests added

`tests/unit/test_alert.py`:
- `test_delivers_email_logs_and_is_loud`: one SES call to `OPERATOR_CONTACT`, from the configured sender, with the issue number in the subject and the cause in the body. One line in `alerts.jsonl`. Standard error starts with `ERROR [ALERT]`. The record's time carries an offset.
- `test_no_sender_raises_and_prints_the_undelivered_record`.
- `test_ses_failure_raises`.
- `test_unwritable_log_raises_after_the_email`: the email is still sent once, then the log failure raises.
- `test_sender_env_wins_over_file`.
- `test_unusable_sender_file_raises`, three cases: bad JSON, an empty `email_from`, and a non-object.
- `test_channel_check_needs_a_sender`, `test_channel_check_needs_credentials`, `test_channel_check_returns_the_sender`.
- `test_the_unit_tier_cannot_reach_real_ses`: without a patched client, `alert_operator` hits the conftest guard and `RealAlertTransportReached` escapes.

## Runs, 2026-10-06

- `tests/unit/test_alert.py`: 12 passed.
- `test_alert.py` plus every test file that imports `operator_notify`: 31 passed, before the restructure that removed the three fall-through handlers.
- Full `tests/unit` tier, run with nothing else on the machine: 10836 passed, 68 skipped, 7 deselected, 6 xfailed in 9m 31s. Two earlier full runs each failed one load-sensitive test while other work ran beside them: `test_windows_paths_marker`, then `test_max_input_latency`. Both pass alone; filed as #3731.
- `tools/audit_fail_open.py --check --strict`: `PASS -- 310 files, 9539 sites examined, no new fail-open, denominator matches.`
- `tools/audit_halt_sites.py --check`: PASS.
- Real send: `tools/send_test_alert.py` delivered from Ubuntu at 11:01 PM Central (see the implementation report).
