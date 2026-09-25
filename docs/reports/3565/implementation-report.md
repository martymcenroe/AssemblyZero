# Implementation Report: which model answered every call (#3565)

Parent: #3562. Built on #3563's seats and profiles.

## What was asked

Every call through `get_provider` is recorded with its seat, spec, resolved model id, provider class, whether a fallback answered and which, effort, duration and token counts, for every run and not only where an audit directory is armed. The run record opens with the profile and logs a `model` event per call. The convergence record and `run-log.jsonl` name the profile. The LLD stamp names the reviewer that ran, not `REVIEWER_MODEL`. `FallbackProvider` reports the provider that answered.

## What changed

| File | Change |
|---|---|
| `assemblyzero/core/model_record.py` (new) | `call_fields` builds one call's record; `record_call` writes it to the open sink; `open_sink` / `close_sink` / `model_record_is_armed`; `announce_profile` makes a loaded profile the process's run profile and writes the record's header |
| `assemblyzero/core/llm_provider.py` | `get_provider` hands its spec and effort to `_recorded`, which now wraps when an audit directory is armed **or** a run record is open, and attributes the call to the seat resolved last when that seat's spec is the one being built. `FallbackProvider` remembers which provider answered: `answered`, `fallback_answered`, and `provider_name` / `model` report the answerer |
| `assemblyzero/core/call_recording.py` | `RecordingProvider` takes spec, effort and seat; every call goes to the model record, and `calls.jsonl` rows carry the same fields beside the bodies |
| `assemblyzero/core/run_record.py` | `start` opens the sink and `finish` closes it; `profile(profile)` writes the name, SHA-256, selection, source, overrides and one line per seat; `model(fields)` writes `model {json}` |
| `assemblyzero/core/seats.py` | `resolve` and `resolve_active` remember the seat they resolved (`last_resolved_seat`); `set_run_profile` / `current_profile_name`; `active_profile` falls back to the run's profile before the environment's precedence, so the seats no state reaches follow the run's `--models` |
| `assemblyzero/speedrun/convergence.py` | every row carries `profile` |
| `assemblyzero/utils/speedrun.py` | `RunLogger.complete_run` takes `profile`, defaulting to the run's |
| `assemblyzero/workflows/requirements/audit.py` | `embed_review_evidence` takes `reviewer_model` and `reviewer_spec`; with neither, the active profile's `requirements.review` seat. `REVIEWER_MODEL` is no longer imported there |
| `assemblyzero/workflows/requirements/nodes/finalize.py` | passes the run's `requirements.review` seat |
| the three standalone tools | `announce_profile(profile)` after loading it |
| `tests/conftest.py` | the run profile and the sink are reset around every test |

## How a call is attributed to a seat

Every node resolves its seat and then builds the provider from that seat's spec, with nothing between the two. The resolver sets a context variable to the seat it returned. The wrapper takes that seat only when the seat's spec is the spec being built. A spec passed straight to `get_provider`, such as an explicit override or a transport probe, is recorded with an empty seat rather than a wrong one.

## What is recorded where

- **The run record** (`<target>/data/speedrun/runs/<tag>-events.log`): the profile header, then a `model {json}` line for each call. This is armed whenever a standalone tool has a record open.
- **`calls.jsonl`**: unchanged in location and arming, because it holds the prompt and response bodies (#2731). Each row now carries the same fields.
- **Tokens**: `input_tokens` and `output_tokens` as the provider reports them. `GeminiProvider` does not report tokens, so they are recorded as 0 for Gemini calls.

## What is not done here

- `orchestrate.py` opens no run record of its own. Under the roll its calls go to `calls.jsonl` wherever a stage arms an audit directory, and its telemetry rows carry the profile name. `--models` on the roll and the orchestrator is #3566.
- A resumed implementation run announces the profile loaded at relaunch, while its nodes read the checkpoint's snapshot. When the two differ, the per-call `model` events are the authority. #3566's refusal to resume under a different profile closes the gap for the roll.
