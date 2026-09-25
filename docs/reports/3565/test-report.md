# Test Report: which model answered every call (#3565)

## New tests

`tests/unit/test_model_record.py`:

| Class / test | Owns | What it pins |
|---|---|---|
| `TestThePerCallRecord::test_outside_a_run_nothing_is_wrapped` | #2731's contract | with no run record and no audit directory, `get_provider` returns the bare transport |
| `...::test_every_call_writes_one_record_naming_the_seat` | T1 | two calls give two records carrying all twelve fields; seat, spec, resolved id, provider class, fallback, success, duration as resolved |
| `...::test_a_spec_the_seat_did_not_resolve_is_recorded_without_a_seat` | T1 | a spec passed straight to `get_provider` is recorded with an empty seat, never a wrong one |
| `...::test_calls_jsonl_carries_the_same_fields` | T1 | with an audit directory armed, the `calls.jsonl` row and the model record agree field by field, and the bodies are still written |
| `...::test_a_fallback_answer_is_recorded_as_the_fallback`, `...::test_a_primary_answer_is_not_a_fallback` | T1, requirement 5 | a `FallbackProvider` whose primary fails reports the fallback's model and `fallback_answered`, and the record says so with the fallback's class and id |
| `TestTheRunRecord::test_the_header_and_one_model_event_per_call` | T2 | the events log opens with `profile name=… sha256=<the loaded dict's hash>` and seventeen seat lines; the count of `model` events equals the count of `calls.jsonl` rows; `finish` closes the sink |
| `TestTheProfileOnEveryRow` | T3 | with no profile announced the name is the default; convergence rows and `run-log.jsonl` rows carry the run's profile, and an explicit `profile=` wins |
| `TestTheStamp` | T4 | the stamp is the resolved reviewer and its spec; `REVIEWER_MODEL` set to nonsense in the environment and in `core.config` changes nothing; with no reviewer passed, the run's profile decides (`claude-opus-4-6` under `claude.toml`) |
| `test_close_sink_only_closes_its_own` | the sink's lifetime | a record cannot close another's sink |

## Runs

FULL_TIER_RESULT
