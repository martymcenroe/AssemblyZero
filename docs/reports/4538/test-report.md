# Test report: #4538

## Unit

`tests/unit/test_agy_agent_warning_scope.py`, 7 tests:

- `test_t1_an_answer_naming_the_flag_passes`: a `status SUCCESS` envelope whose answer contains `--agent` returns ok with that answer. Fails on `main`.
- `test_t1_a_failed_call_naming_the_flag_is_failed_for_its_status`: a `status ERROR` envelope naming the flag fails as `agy status 'ERROR'`, not as an unloaded agent.
- `test_t2_agys_warning_on_stderr_still_fails_a_successful_envelope`: agy's own warning on stderr fails a successful envelope.
- `test_t2_agys_warning_on_plain_stdout_still_fails`: the same warning on plain-text stdout fails the call.
- `test_a_warning_agy_puts_in_the_envelope_outside_the_answer_fails`: a warning in an envelope field other than `response` fails the call.
- `test_the_diagnostics_never_carry_the_answer`: `agy_diagnostics` leaves out `response` and keeps stderr and the other fields.
- `test_without_an_envelope_the_diagnostics_are_both_streams`: with no envelope, both streams are read.

The tests from earlier issues that pin a real warning failing the call still pass unchanged: `test_stdin_path_fails_on_an_agent_warning` (#3623), `test_an_agent_agy_could_not_load_is_a_failed_call` (#3612) and `test_agent_warning_on_stdout_is_failure` (#3624).

## Real calls

None. The fixtures are built from the ledger's record of the three failed calls and from agy's own warning string.

## Full suite

`tests/unit/`: 13,912 passed, 66 skipped, 7 xfailed. The integration, e2e and adversarial tiers with `ASSEMBLYZERO_MOCK_MODE=1`: 84 passed, 7 skipped.
