# Implementation Report: the core/ package under standard 0034 (#3581 step 5)

The rule is ADR 0236 and standard 0034. This PR takes the `assemblyzero/core/` module issues from the #3581 sweep, highest harm first. Each module's sites are fixed, tested, and marked in ledger 0908.

## Scope

The modules a target run passes through, in order of harm. Harm means a failure the run reads as success on the model path, the verdict path or the resume path; failures that lose a record come after.

Taken last, because no target run passes through them:
- `fail_open_audit.py` (#3775), an audit tool;
- `gate_registry.py`'s halt-site scanner (#3776), an audit tool;
- `scripted_provider.py` (#3792), used only by mock rolls and replays.

## Also carried

- `tests/unit/test_alert_channel_at_start.py::test_the_implementation_workflow` passes a temporary `--repo`, and its stand-ins fail if reached (#4161). Measured against the old source, it had run a mock implementation run into the worktree.
- **#4161: the checkout's three telemetry logs.** Stage records (`data/speedrun/telemetry/run-records.jsonl`), prompt failures (`data/speedrun/telemetry/prompt-failures.jsonl`) and hallucination checks (`data/telemetry/hallucination-log.jsonl`) take their root from the caller, and a test that runs a node from the checkout hands them the checkout. `tests/checkout_telemetry_guard.py` holds the redirect and the guarded paths:
  - an autouse fixture in `tests/conftest.py` sends any write aimed at the checkout to the test's `tmp_path`, and a write to any other root goes where it was sent;
  - `convergence.records_path` and `prompt_telemetry.telemetry_path` are replaced as module attributes, and `record_hallucination_event` in each of the three places it is bound;
  - a session guard beside the home-state one (#3531) fails the run if any of the three files appears or changes, naming them.

## Modules

### llm_provider.py (#3780, 31 sites) and provider_storm.py (#3787, 1 site)

A provider's failed `LLMCallResult` is its declared contract: every caller reads `success` and routes a failure to HALT, which alerts (#3724). So the fixes make each failed result loud, turn silent successes into failed results, and raise what is not a transport failure.

- **One loud line for every failed call.** `log_llm_call` already receives every failed result. It now also writes `ERROR [LLM] provider=... model=... call failed: ...` to stderr and the log. That covers the timeout (953), the non-zero exit (1016), the transport error (1145), the missing key (1372), the API error (1387) and the Gemini failure (1756). The no-CLI result (826) and the open circuit breaker (1555) now go through `log_llm_call`; they returned without it.
- **Three silent successes are failures.** JSON that is neither the result object nor the event list (1085), an empty result (1103) and output that is not JSON (1113) used to be successes holding the raw stdout or `""`. `_extract_text_from_stream_events` no longer falls back to the raw stdout either. Each is now a failed, non-retryable call.
- **The stream's pipes say what went wrong** (487, 505, 510, 517, 553). The pumps record a prompt that could not be written, stdout or stderr that could not be read, lines that were not JSON (counted, the first quoted), and a pump still running after the drain. Any of them fails the call, even on exit 0.
- **The handlers raise what they do not own.** `ClaudeCLIProvider.invoke` returns a failed call for `OSError` and `SubprocessError` only. `AnthropicProvider.invoke` does so for the API's own errors only. `GeminiProvider.invoke` does so for what `classify_agy_error` recognises as agy's (rate limit, capacity, authentication, timeout). Anything else is a fault in this code and is raised; it used to look like weather and be retried.
- **Configuration that cannot be used raises.** An unreadable `.env` (291) is no longer read as "no key", and a bad `AZ_LLM_IDLE_TIMEOUT` (412, 418) no longer runs on the default with a warning.
- **An unpriced model is refused before it spends** (1248). It used to cost $0.00, so `--budget` never counted it; `_calculate_cost` raises as the backstop.
- **The fallback says so, loudly** (1596, 1609, 1617): the primary's failure, the breaker tripping, and both providers failing.
- **The rate-limit flag reads `error_type` directly** (1729). The `hasattr` guard would have read a changed contract as "not rate-limited".
- **The recording wrap has no handler** (2009, 2010). It used to run the roll on the bare transport when the recorder could not be set up, losing the model record and replay inputs with nothing said.
- **The storm probe says why it could not run** (723, 757, 769, 772). It raises with the cause instead of returning False. A probe that will not drain after its kill is an ERROR line, and the timed-out probe is still the answer.
- **`provider_storm.diagnose` alerts** (147) when its probe raises, naming the cause. The storm reading still stands, so the roll still halts.

Baseline: six entries leave (`AnthropicProvider.invoke`, `ClaudeCLIProvider.invoke` and `GeminiProvider.invoke` handlers; `_recorded`'s handler and tag; `diagnose`'s handler). The fail-open audit lost 11 findings.

### gemini_client.py (#3777, 12 sites)

The agy transport every default target run uses.

- **The loop has no handler around the call** (598, 601). `_invoke_via_cli` reports every transport failure as `(False, "", reason)`. The old loop raised that reason as `RuntimeError` only to catch it with `except Exception`. That also caught programming errors and returned them as "Programming error (not retried)" failed calls. Now an exception is a fault and propagates.
- **Every failed attempt is loud with its cause** (520, 598), and so is the final failure, with every attempt's cause (671). A retry is logged with its wait (660).
- **A missing agy fails at once** (454). It was a failed attempt, retried with backoff until the call budget ran out.
- **Finding agy says what it found** (174, 199, 200, 208). A Windows agy on PATH is refused out loud, naming its path. A `wsl.exe` that cannot run raises, where it used to be cached as "agy not found" for the life of the process. An unreadable WSL `HOME` is said.
- **A killed agy that will not drain** is an ERROR line (514); the timeout stays the call's answer.
- **A Gemini response with no `modelVersion` raises** (730). It was recorded as "gemini-unknown".

Baseline: two entries leave (`GeminiClient.invoke`'s handler; `_find_wsl_agy.run`'s tag). The fail-open audit lost 2 findings.

### verdict_schema.py (#3802, 4 sites fixed, 1 won't-do)

- **A verdict without its rationale is not a verdict** (196, 208). `rationale` is one of VERDICT_SCHEMA's two required keys, and it used to be filled in as `""`. `parse_structured_verdict` now returns None for it, so the reviewer's caller rejects the review loudly and HALT alerts.
- **An empty document raises** (651). `scan_residual_questions("")` reported "no open questions", the verdict finalize needs to pass.
- **An empty verdict cannot be compared** (703). `same_blocking_issues` raises, naming the empty side. "Not stagnant" sent the drafter round again with no feedback to act on.
- **Won't do: 716, the line comparison.** The ledger prescribed raising when either verdict is not JSON. But the requirements workflow stores rendered feedback in `current_verdict` by design (#506): bullet lines and a summary, never the reviewer's JSON. For it the line comparison is the comparison, not a fallback from a failed parse, and raising would end two-strike stagnation detection for every blocked round. The docstring says so now; `test_716_*` pin it; the ledger row and #3802 record the won't-do.
- **Found while here:** `validate_lld_final` returns `[]` (a pass) for empty content, a site the sweep did not record. Added to #3867, for the requirements batch.

### seats.py (#3793, 6 sites)

The spend-lock reads already failed closed: an unreadable home, lock or lift time counted as "locked", so no seat ran on an Anthropic model. What was missing was the reason.

- **They still fail closed, and now alert** (149, 173, 191). Each handler calls `alert_operator` with the path and the cause. An operator whose lock file is unreadable learns why his Claude seats refuse, instead of finding them refused.
- **On Linux, an unreadable `/proc/version` raises** (128). It used to mean "not WSL, so no other side", which silently dropped the Windows spend lock from the check. Off Linux, nothing is read and there is no other side.
- **`current_profile_name` has no handler** (776, 777). A profile that could not be read wrote telemetry rows naming the default profile as the one that ran.
- All five withdrawn `# fail-open:` tags are gone.

Baseline: six entries leave (five tags and `current_profile_name`'s handler). The fail-open audit lost 5 findings. Its three remaining lock handlers count as handled because they call `alert_operator`; a helper that only printed was not enough for it.

### resume_contract.py (#3788, 8 sites)

The contract exists so a resume never runs against a world nobody checked. Each site let one through.

- **Only absence hashes as absent** (53, 54, 148). `_sha256_file` returns None only when the file does not exist; one that exists but cannot be read raises with its cause. It used to hash as absent, reported as "now missing".
- **An unreadable or corrupt contract refuses the resume** (126, 127). It used to read as no contract, and the resume went ahead unverified, the one thing the contract prevents. `check_and_consume` refuses it with an alert naming the path and the way past it: move it aside to run without verification.
- **An unreadable input refuses the resume** with an alert naming the cause.
- **A refusal alerts** (196). "The world changed since the halt" used to reach only the console, and the operator found out by rerunning.
- **A verified contract that cannot be deleted alerts** (223, 224). The resume does not depend on the deletion, so it proceeds, but a leftover contract would be checked again by the next launch for that issue.

Baseline: three tags leave. The fail-open audit lost 3 findings.

### interface_surface.py (#3779, 12 sites)

The module grounds the LLD drafter in the target's real signatures. Its documented contract was that every entry point degrades to an empty map with a warning, and called that not a pipeline failure. ADR 0236 retires the carve-out: an empty or partial map is the drafter working blind, inventing the functions this module exists to stop it inventing.

- **Every failure raises, naming the file and the cause:**
  - a file that does not parse (107); the first 50 lines used to stand in for its interface;
  - a walk that fails (267);
  - an import target that cannot be read (319); it used to read as "imports nothing";
  - an unreadable file (394); it used to drop silently out of the map;
  - a file outside the root (408); it used to be keyed by its bare name;
  - a root that is not a directory (445, 518);
  - a related path that cannot be resolved (472);
  - the two entry points' broad handlers are gone (492, 552).
- **Two outcomes are not failures, and are said.** A repo with no Python files has an empty surface, logged (449). Files left out to fit the character budget are named in the log, where it gave only a count (402).
- **Callers.** Both live in the requirements package. `analyze_codebase` and `generate_draft` still wrap the call in a broad handler that logs and continues (their own ledger rows), so runs are unchanged until the requirements batch routes those to HALT. The implementation-spec stage calls `summarize_python_file` on the base branch's non-test files; one that does not parse now stops that stage, where its head used to be shown as its API.

Baseline: both entry points' handlers leave. The fail-open audit lost 12 findings.

### validation/test_plan_validator.py (#3801, 5 sites)

The test plan used to shrink without a word.

- **A missing Section 3 is loud** (136). The empty list stays its contract, since the coverage check turns it into "No requirements found in Section 3", but its cause was a WARNING.
- **A missing Section 10, or one with no scenario rows, is loud and an error** (225, 237). A Section 10 heading that holds no table at all used to be reported as missing; it now says what it is.
- **No row drops out of a scenario table** (248, 262). Inside a table whose header starts `ID`, `Test ID` or `#`, a row with too few cells or an ID that is neither a number nor a T-number is recorded. `extract_test_scenarios` takes an optional `problems` list; `validate_test_plan` passes one and makes each entry a `parse` error violation, so the plan fails. Other tables in Section 10 (coverage targets and the like) are not scenarios, are not read as such, and raise nothing.

### settlement.py (#3795, 5 sites)

Settlement decides whether a launch may reuse an artifact instead of drafting it again. Every doubt still resolves toward "unsettled", which drafts; what changes is that a failure says so.

- **An input that exists and cannot be read alerts** (111, 112). `sha256_path` still returns None for it, which `verify` reports as a named mismatch, so the stage drafts. It now calls `alert_operator` with the path and the cause. An absent input stays quiet: a landed LLD's working copy is deleted when its PR merges, and absence is an answer.
- **A binding doc outside the repo raises** (176, 177). It used to be keyed by its absolute path, which names one machine's layout: the same doc read from the other side of WSL is a different key, and the settlement silently stops holding.
- **An artifact that cannot be hashed is never settled** (259). `build_settlement` reads the artifact directly and raises, naming it. A record with no artifact hash can never match, so it used to be written and then ignored by every later launch.
- **Caller.** `orchestrator/stages.py::settle_stage` still wraps the call in a broad handler that prints and continues (its own ledger row, orchestrator package), so a settlement that raises costs the next launch a redraw, as before.

Baseline: both tags leave. The fail-open audit lost 2 findings.

### capacity.py (#3773, 7 sites)

The capacity gate decides whether `tools/orchestrate.py` may start a run. Every failure in it used to read as "available", so a recorded exhaustion could be ignored and the run spent the healthy provider's quota finding out.

- **A state file that cannot be read, or is not a JSON object, raises** (74, 75). It used to read as "nothing recorded". The new `CapacityStateError` names the file and the cause and says how to clear it. A missing file is still no record, and quiet.
- **A write that fails raises** (89). It used to pass, so an exhaustion was never remembered and the next run started blind. `CapacityStateError` is a `RuntimeError`, not an `OSError`, so `ClaudeCLIProvider.invoke` does not read it as "claude -p could not be run".
- **A stored time that is not an ISO time raises** (212), and so does a record with no time at all (223). Both used to read as "available". A record whose reset time is null still expires after `UNKNOWN_RESET_COOLDOWN`: `record_exhaustion` writes null when the provider named no reset time, by design.
- **Gemini is reported as not checked** (237). Nothing on this machine records Gemini's quota; agy holds it. `ProviderCapacity` gains `checked`, and Gemini's status is `checked=False`, `available=False`, and its summary says the transport preflight checks it with a real call before every workflow's first draft. `blocked_providers` lists only what is known to be exhausted, so Gemini blocks nothing here, and is no longer called available.
- **An unknown provider raises** (264). It used to be reported as available.
- **Callers.** In `llm_provider.py`, `record_exhaustion` and `clear_exhaustion` run inside `ClaudeCLIProvider.invoke`, whose handler re-raises anything that is not a transport error, so a broken state file now ends the call with `CapacityStateError` where it used to pass. `tools/orchestrate.py` calls `blocked_providers` with no handler: a broken state file ends the run before it starts with a traceback and exit 1, but no alert (outside `core/`, its own ledger row).

Baseline: no entries leave, since the module had no broad handler or tag; rewriting it moved three `tools/new_repo.py` line numbers that the merge of `main` had left stale. The fail-open audit lost 3 findings (`_load_state`, `_save_state`, `_claude_capacity._dt`).

### preflight.py (#3786, 5 sites)

The Gemini transport check runs at requirements N1 and spec N2 before anything is drafted. A failed check is still a failed `PreflightResult`, its declared contract: both nodes return its warning as `error_message`, both graphs route that to HALT, and HALT alerts. What was missing is the loud line where it fails.

- **Every failed check is loud** (83, 94, 102). A new `_failed` writes `ERROR [PREFLIGHT]` to stderr and the log, naming the model, the step that failed and that the workflow halts before it drafts, and returns the failed result with the same warning text as before.
- **A fault in the probe raises** (94, 95). The broad handler and its tag are gone. The probe now catches only what the transport raises when it cannot be used (`OSError`, `SubprocessError`, and `GeminiClient`'s `RuntimeError` for a `wsl.exe` that cannot run or a reply agy broke), plus `GeminiClient`'s `ValueError` for a refused model id. Anything else is a bug, and it used to look like an agy outage.
- **An unknown Gemini alias raises** (64). `gemini_model_for` used to probe the default model, so the preflight passed on a model the run would never call. It now looks the alias up the way `GeminiProvider` does, lower-cased, and raises with the same message. Seat resolution lets an unknown alias through, so `preflight_for_specs` is where it is first met: it turns the raise into a loud failed check, so the run halts through HALT, and remembers nothing, since no probe ran.
- **Callers.** `generate_draft` (requirements) and `generate_spec` (implementation spec) call `preflight_for_specs` outside any handler. A fault the probe now raises leaves the node, and `tools/run_requirements_workflow.py`'s broad handler prints it and exits 1 without an alert (its own ledger row, `tools/`).

Baseline: two entries leave (the tag and the handler). The fail-open audit lost 1 finding.

### retry.py (#3789, 3 sites)

`with_retry` already raised every failure to its caller. What it did not do is say so where the operator looks.

- **Every giving up is an ERROR line on stderr and the log** (66, 73, 95), naming the call, the error and why it is not tried again: not retryable, a timeout already retried once, or every attempt spent (with the count). The first two used to be stdout lines; running out of attempts said nothing. The error is still raised, and the caller owns what stops and the alert.
- A retry that is about to sleep and try again is not a failure, and stays a stdout line.
- **Callers.** None in `assemblyzero/` or `tools/`: the workflows retry through `assemblyzero/utils/retry.py`'s `with_retry`, a different function. Only `tests/unit/test_retry.py` imports this one.

Baseline: no entries in either, before or after.

### retry_gate.py (#3790, 1 site)

- **An unknown failure class raises** (209), naming it and the four the gate knows. `should_retry` looked it up with `dict.get`, found nothing, and gave it the caller's whole budget, the same answer as a transient failure. The check runs before fail-fast, which answers "no retry" for every class and would otherwise hide one that is not a class.
- **Callers.** All three pass a class the gate knows: `orchestrator/graph.py` and `testing/nodes/implementation/orchestrator.py` pass `classify_failure`'s answer, and `utils/retry.py` passes `LLMCallResult.failure_class`, which every provider sets from `classify_failure` or as `"permanent"`, or `classify_failure`'s answer when it is empty. A raise would be a bug in a new caller, and it propagates.

Baseline: no entries in either. The fail-open audit examines one more site (the new raise).

### errors.py (#3774, 1 site)

- **An unreadable `retry-after` header is an ERROR line** (365), on stderr and the log, naming the value and that the caller's own backoff is used instead. It used to be dropped in silence. The rate limit is still classified as `RateLimitError` and raised with no hint, as before: the header is a hint, and its absence is not what stops anything. A 429 with no header stays quiet; no hint is an answer.
- **Callers.** `classify_anthropic_error` is the only caller, and `AnthropicProvider` its only user.

Baseline: no entries in the loud-failure baseline. The handler stays in the old fail-open audit's baseline, which still counts a handler that falls through to `return None` without calling `alert_operator`; the prescription here is the ERROR line, not an alert per rate limit.

### stage_watchdog.py (#3796, 1 site)

The watchdog prints a progress line for a running stage and never kills it; bounding a call is the provider's job. A stage at six times its nominal was a stdout line, repeated every tick, seen only by someone at the terminal.

- **A stall alerts the operator** (139). The first STALLED tick calls `alert_operator` with the stage, the elapsed time, the ratio and the nominal, and says the stage keeps running. Nothing here can stop it, so the alert is the whole response. It is sent once per stage run; later ticks print as before.
- **An alert that cannot be delivered is raised when the stage ends.** `alert_operator` writes the undelivered record to stderr and raises `AlertDeliveryError`; the watchdog's thread ends on it, and `__exit__` raises it in the stage's own thread, unless the stage is already raising its own error.
- SLOW stays a louder line, not a failure. A stage with no nominal, or one waiting on the operator, gets no verdict and no alert, as before.
- **Callers.** `orchestrator/graph.py`, `tools/run_implement_from_lld.py` and `tools/run_requirements_workflow.py` wrap a stage in the watchdog with no handler of their own; an undelivered alert ends the stage there. `run_requirements_workflow.py`'s broad handler prints it and exits 1 (its own ledger row).

Baseline: no entries in either. The fail-open audit examines nine more sites.

### state_persistence.py (#3797, 1 site fixed, 1 won't-do)

- **A snapshot that exists and cannot be read raises** (77), naming the file and the cause. `load_state_snapshot` used to return None for it, the same answer as "no snapshot was written". An absent snapshot is still None.
- **Won't do: 42, the `str()` of a value JSON cannot hold.** The ledger prescribed raising. But `save_state_snapshot`'s one caller is HALT, which writes the snapshot before it writes the recovery plan and alerts; a raise would cost every halt whose state holds such a value its recovery plan and its alert, the opposite of the rule. And nothing reads the snapshot back as state: `load_state_snapshot` has no caller in `assemblyzero/` or `tools/`, and the resume contract only hashes the file. The docstring says so now; `test_42_*` pin it; the ledger row and #3797 record the won't-do.
- **Callers.** `load_state_snapshot` has none outside its tests. `save_state_snapshot` is unchanged for HALT.

Baseline: no entries in the loud-failure baseline. The fail-open audit lost 1 finding (`load_state_snapshot`'s handler); `save_state_snapshot`'s stays, with the won't-do.

### run_record.py (#3791, 24 sites)

The run record is what a standalone LLD or implementation run leaves for the session that cleans up after it: the teed console (`<tag>.log`) and the events log. Nothing the run produces reads it. `factory_report.py` and the replay read only the roll's `run-issue*` logs, and the speedrun readers that glob every events log key on the roll's `START` and `EXIT` lines, which a standalone record never writes. So a record that cannot be written alerts the operator and does not stop the run: a raise from inside a `print`, or from the `crash` call in a tool's handler, would cost the run its result, or hide its own error and skip the tool's alert. Two things do raise.

- **A run log that refuses a write or a flush alerts once** (77, 78, 87, 88). Both tees read the log through the record, which detaches it from both before the alert goes out, since the alert prints through the same stream; the run goes on console-only. A tee that outlives its record (a logging handler made during the run holds one) writes to the console only, where it used to write into a closed file and drop the error.
- **git that cannot answer raises** (103, 104, 107). `_git` raises the new `GitQueryError`, naming the command, the target and the cause (the exception, or the exit code and stderr), where it returned `(False, reason)`.
- **No partial left-in-place list** (134, 144, 155, 165). `left_in_place` raises when any of its four questions fails. It used to put an "unknown" line in that question's place beside the answers to the rest, and the finishing commands built from such a list could offer `git branch -d` for a branch that an unlisted worktree still held. The record writes the list as unknown, with the cause and an instruction to inspect the target by hand, prints the same on the console, and alerts. A crashed run asks twice (`crash`, then `finish`); the second asking is an ERROR line, not a second alert.
- **A run log that cannot be opened alerts** (271, 272), and the run starts console-only, as before.
- **A head git cannot read alerts** (283), and the start event carries the cause where it said `unknown`.
- **A profile the record cannot describe raises** (318, 319). Every entry point prints the same seat table with `describe` just before it calls `announce_profile`, so this raise is what `describe` already does; a seat that does not resolve would otherwise fail its stage after the run had spent on the stages before it.
- **A console that refuses the left-in-place list alerts** (378, 379), naming the events log that holds the list. The streams are restored in a `finally`, so an undelivered alert on the way out does not leave the tee installed.
- **An events log that refuses a line alerts once** (410, 411), with the cause and the line. Each later lost line is an ERROR line on stderr carrying it, so a broken events log is one alert, not one per node and model call.
- **An ERROR line that stderr cannot take alerts** (420, 421), with the line. The warning helper is gone.
- **A run log that will not close alerts** (434, 435). One that has already refused a write and then will not close is an ERROR line.
- **Callers.** `tools/run_requirements_workflow.py` and `tools/run_implement_from_lld.py` call `start`, `node`, `crash` and `finish`, none of which raises over its own record now; an alert that cannot be delivered (`AlertDeliveryError`) propagates from them, as the ADR requires. `profile` is reached through `model_record.announce_profile`, which every entry point calls outside a handler, so its raise exits 1 with a traceback and no alert (the entry points' own ledger rows, `tools/`), as `describe` just before it already did.

Baseline: ten entries leave (nine tags and `profile`'s handler). The fail-open audit lost 9 findings.

### model_record.py (#3782, 4 sites)

The model record says which seat, spec and model answered every call, so that a comparison between profiles is not a guess. `tools/compare_profiles.py` reads the same fields from `calls.jsonl`; the `model` lines in the run record's events log are read by people.

- **A spec the seat registry refuses raises** (70, 71). `_resolved_id` used to record it with an empty model id, on the belief that scripted and test-only specs end there. They do not: `mock:` and `scripted:` resolve to their model. What reached the handler was a spec with no provider, or one resolving to a model `FORBIDDEN_MODELS` fences, recorded as answered by nothing. Through `get_provider` a forbidden Gemini model is already refused by `GeminiClient` before the call returns, so this raise is the backstop for a `RecordingProvider` built around a spec its transport was not built from.
- **A run record that cannot take a call's line alerts** (123, 124), with the cause, the seat and the spec, and `record_call` returns False. The call already happened, and its result is returned untouched, since nothing the run produces reads that line. An `AlertDeliveryError` from the record (its own alert could not be delivered) is raised as it came, not alerted a second time.
- **Callers.** `call_fields` and `record_call` have one caller, `RecordingProvider.invoke`, which has no handler: a refused spec ends the call there with `ProfileError` and reaches the node that made it. `record_call`'s return value is not read.

Baseline: four entries leave (both handlers and both tags). The fail-open audit lost 2 findings.

### call_recording.py (#3772, 10 sites)

The recording (`calls.jsonl`) is the replay's input, and the launch gate (#2724) waits on replays: `ReplayProvider` answers call N with recorded response N only while the code sends recorded prompt N. Its readers are `tools/replay_run.py` (through `read_calls` and `speedrun/replay.py`'s `recording_for`) and `tools/compare_profiles.py` (its own reader, counting calls and verdicts per seat). A call the run consumed and the recording lacks makes every replay diverge at it as if the code had changed, the false finding #2731 exists to replace. So the write raises: the recording holds every call the run used, or the run stops.

- **A write that fails raises** (153, 154, 251). `_append` raises the new `RecordingError`, naming the file and the cause, before the call's result is returned, so the run never consumes a call its recording does not hold; a resume makes the call again and records it. It used to return False, and the call site discarded it (251), so there is nothing left to check there. `RecordingError` is not an `OSError`.
- **A line that is not a call record raises** (179, 180, 187), naming the file and the line. The ledger prescribed an ERROR line beside the count for 179. Raising goes further, for two reasons: a recording with a call missing is not a shorter recording but a wrong one, which replays as a divergence at the gap, and the count is what `_next_seq` numbered the next call by, so it numbered it into the gap. One line is still counted, not read: a final line with no newline, the write of a process that died in it. The newline is part of every write, so its call never reached the run, and the recording is read up to it, quietly; `RecordingSummary.unreadable` now counts only that.
- **An append after a partial last line raises** (284). `_next_seq` discarded the count, and the next call was written onto the end of the partial line, and the two read as one bad line. The error says to remove the partial line, whose call never reached the run, and resume.
- **Every replay refusal is loud** (353, 372). `_refuse` writes `ERROR [REPLAY]` to stderr and the log with the divergence, and still returns the failed result, the provider contract: the node reports it as its error, and the replay runner reads `divergence`.
- **A recorded call with no `success` field is refused** (388). It was served as a success, so a failed call recorded without one would replay as an answer. The refusal says what the record lacks, through a new `Divergence.why`, and keeps the `ReplayProvider:` prefix the runner matches on.
- **Callers.** `RecordingProvider.invoke` wraps every transport `get_provider` builds while a run is armed, and has no handler, so a `RecordingError` reaches the node that made the call; `utils/retry.py`'s `with_retry` catches nothing, so it is never retried. Nodes that wrap their call in a broad handler turn it into whatever they turn every failure into (their own rows). `tools/replay_run.py` calls `recording_for` outside its graph handler, so a recording with a bad line ends the replay with a traceback and no alert (its own row, `tools/`); its graph handler reports a raise inside the replay as the replay's divergence.

Baseline: three entries leave (both tags and `_append`'s handler). The fail-open audit lost 2 findings.

### audit.py (#3771, 5 sites)

`ReviewAuditLog` writes review decisions to session shards, and `tail` merges them with the consolidated history. Nothing in `assemblyzero/` or `tools/` reads it today: the package exports it, and `tools/view_audit.py`, its one reader, imports two names the module does not define (reported separately). A reader of `tail` takes the list as the whole log, so a short list is a wrong answer, and each skip raises.

- **A timeout finding the repo root keeps its cause** (130). It is chained (`from exc`), and the message names the command, the limit and the directory, and says to pass `repo_root`.
- **A line that is not a JSON object raises** (238, 267), in the history and in a shard alike, naming the file and the line's number in the file (counted from the top, where `tail` reads only the end of the history). Such lines used to be skipped. A JSON line that is not an object used to crash the sort with an `AttributeError` naming neither.
- **A file that cannot be read raises its `OSError`** (242, 270), which names it. A history read as `[]` and a shard skipped both used to come back as a log missing their entries. An absent history, and no shards, are still no entries: nothing has been logged, or everything has been consolidated.
- **A shard removed after it was listed raises** (270). The consolidator moves a shard into the history and deletes it; one deleted between `tail`'s listing and its read has its entries in neither part of what `tail` read. Shards are read without an existence check, since they were listed a moment before, so that race is a `FileNotFoundError`, not an empty shard.
- `_read_jsonl_safe` is now `_read_jsonl`, since it no longer swallows anything; it reads the history when `tail` is asked for every entry, and every read shares one line parser.
- **Callers.** None outside the module and the package export. `tools/view_audit.py` fails at import, before it could call `tail`.

Baseline: no entries in the loud-failure baseline, before or after, since the module had no broad handler or tag. The fail-open audit lost 4 findings (the four handlers in the two readers).

### halt_evidence.py (#3778, 7 sites)

The HALT node builds the bundle after the halt has alerted and its state snapshot and recovery plan are on disk. So every site keeps the bundle and names what it could not read; nothing is left out as if it were not there. The bundle gains `unread_evidence`, a list of every piece it could not gather, rendered as "Evidence that could not be read" and counted in the draft issue body.

- **An unreadable lineage artifact alerts** (43, 44). `_sha256` now raises. `_artifact_inventory` catches the `OSError`, keeps the row with no hash and the cause under `unreadable`, and calls `alert_operator` with the path, the cause, the workflow, the repo and the issue. The markdown shows the cause in the table and says the byte-identical groups are over the readable files only. The ledger prescribed an ERROR line. An alert goes further, because an unreadable file in the run's lineage is a defect the operator must hear about away from the terminal. A raise would cost him the whole bundle (the events, every other artifact's hash and the draft issue) for one file, when the halt is already alerted.
- **A corrupt record in the preservation log alerts and keeps its place** (85, 86). Only the tail the bundle carries is read now (the last `PRESERVED_TAIL` non-empty lines), so a corrupt line before it shapes nothing and is not read. A line in the tail that is not JSON, or is JSON but not an object (which used to crash the render with `AttributeError`), alerts with the file and the line number and keeps its place as `{"corrupt_line": n, "cause": ...}`, so the tail is never short. An alert, not the ledger's ERROR line, for the reason given at 43.
- **An unreadable preservation record alerts** (91, 92), with the file and the cause, and is named in `unread_evidence`; the tail is empty. An alert, not the ledger's ERROR line, for the same reason. An absent record stays quiet: a repo where no branch was ever preserved has none.
- **An audit dir the state names that is not a directory is an ERROR line** (120), on stderr and the log, naming the directory, and it is named in `unread_evidence`. Not an alert: the HALT node's copies into the audit dir (`_require_audit_dir`, in both the resume-contract and the evidence blocks) raise on the same directory, and each is alerted with it named, so a third alert would repeat them. A state that names no audit dir stays quiet.
- **When the reporter fails.** An `AlertDeliveryError` raised inside the bundle propagates out of `build_halt_evidence`. The HALT node's handler then tries to alert that the halt's evidence bundle was not written, which raises too, so the HALT node raises after the state snapshot, the recovery plan and the halt's own alert are written. The run exits non-zero with the undelivered records on stderr.
- **Callers.** `halt_node.halt_with_plan` catches every exception out of the bundle and alerts, as before. None swallows the new raise quietly.

Baseline: three entries leave (`_sha256`'s tag and both of `_preserved_tail`'s). The fail-open audit lost 3 findings.

### operator_notify.py (#3783, 7 sites)

These are the transports under the alert path: `alert._send_email` and `alert._show_toast` call `send_email` and `show_toast`, and so does the visual gate's escalation (`visual_gate/server.py`'s `_escalate`). The module's "non-fatal by construction" docstring is retired. Every failure that means a notification did not reach the operator now raises `AlertDeliveryError`, the alert path's own error, imported lazily because `alert` imports this module. Both functions return None on success, where they returned a reason string.

- **A toast that cannot be spawned raises** (199, 200), with the title and the exception's type and message, chained from it. It raises `AlertDeliveryError` specifically because `alert_operator`'s `except AlertDeliveryError` prints the undelivered record and every reason before it re-raises; a plain `OSError` would skip that report on Windows.
- **A toast whose PowerShell exits non-zero raises** (205), with the exit code and the first 200 characters of stderr.
- **An email with no sender raises** (231), naming the subject, the recipient and where to set a sender (`AZ_OPERATOR_EMAIL_FROM` or `notify.email_from`). The `NotifyConfig.email_from` comment no longer says that empty means "disabled".
- **A failed SES send raises** (255, 256), with the subject, the recipient, the sender and the exception, chained. `alert._send_email` already wraps any exception into `AlertDeliveryError("email: ...")`, so the alert path's message is now `email: AlertDeliveryError: email ... not sent: RuntimeError: ...`.
- **A toast asked for on a host that is not Windows is an ERROR line** (183), on stderr and the log, naming the title and the host. Nothing is spawned, and it returns None. Not a raise: the visual gate toasts on a schedule (10 minutes, 30, then hourly) on every host, and a raise would end every Ubuntu wait at its first toast, over a channel that host does not have. Not an alert: on Ubuntu an alert is an email, one an hour, about not toasting. The alert path never reaches this branch, since it calls `show_toast` only when `sys.platform` is `win32`.
- **When the reporter fails.** These functions are the reporter's last step. Their raise reaches `alert_operator`, which has already written the loud line and the record to stderr, appends the record to `alerts.jsonl` in a `finally`, prints "NOT DELIVERED" with the reasons, and raises; the process exits non-zero.
- **A caller that does not catch the new raise.** In `visual_gate/server.py`'s `_escalate`, a failed toast (on Windows) or a failed or sender-less backstop email now propagates out of `wait_for_feedback` and the gate, where it used to be one stdout line and the wait went on. Its own ledger rows (server.py:242, :264) prescribe catching it and alerting through `alert_operator`; until that lands, a failed escalation ends the visual gate's wait with the error. A `NotifyConfig` with no sender now ends the wait at the email threshold, 4 hours by default. That includes an operator who set the sender only in the home directory's `.assemblyzero/alert.json`, which `NotifyConfig` does not read.
- `alert._show_toast` still checks for a reason string from `show_toast`, which now returns None or raises, so its `if reason:` branch is dead code. It is harmless.

Baseline: four entries leave (each function's handler and tag). The fail-open audit lost 2 findings.

### operator_wait.py (#3784, 2 sites)

`wants_color` decides whether a line is painted amber.

- **An `isatty` that fails on an open stream raises its own error** (41, 42). A bad descriptor or a detached buffer used to read as "not a terminal". A stream with no `isatty`, and a closed stream, are still quietly not a terminal: `closed` is checked before `isatty` is called, and the write meant for a closed stream raises on its own, so the colour decision has nothing to add. The ledger prescribed an ERROR line. A raise was chosen for three reasons. The painted line is about to be written to the same broken stream. An ERROR line followed by False is the substitute shape the fail-open audit reports as new once the tag is gone. And an alert per painted line would flood, since the stage watchdog paints one a tick.
- **Callers that do not catch the new raise.** In `stage_watchdog._run` the exception ends the watchdog thread, and Python prints its traceback. In `visual_gate/server.py`'s `wait_for_feedback` and in `visual_gate/gate.py` it propagates out of the wait. In each, the `print` or `log` of the painted line to the same broken stream would raise next anyway.

Baseline: one entry leaves (the tag). The fail-open audit lost 1 finding.

### merge_driver.py (#3781, 1 site)

- **A landing that names no PR number or no squash SHA raises** (163). `land` raises `MergeDriverError` when the driver exits 0 and prints its landed line, but its output names no PR number or no squash SHA. It used to return a `Landing` with `pr_number=None` or an empty SHA, and the callers recorded a landed stage with an empty PR URL. The error carries the driver's output and says the PR may have merged: read the output, and do not run the driver again, the route the merge rules give for a merged landing.
- **The PR number is read from all four lines the driver names it on.** The raise is right only if it does not fire on a real landing. `parse_output` read the number only from `created PR #N`. The driver also names it on `reusing open PR #N` (a rerun with its PR still open), on `merged PR #N`, and, on a rerun after the merge, on `PR #N from <branch> already merged with this tip; ...`. Without those, every rerun that reused its PR would now raise after a real landing. All four are the driver's own fixed lines, read from its source, so they stay a closed set read by prefix.
- **Callers.** `workflows/orchestrator/stages.py` (a failed stage, routed to HALT, which alerts), `workflows/requirements/git_operations.py` (re-raised as `GitOperationError`) and `tools/run_implement_from_lld.py` (a stopped finish naming the kept worktree and branch). None swallows it.

Baseline: no entries in the loud-failure baseline, before or after: 163 is a narrow site the parser does not see. The fail-open audit's findings are unchanged; it examines two more sites.

### pr_poll.py (#3785, 1 site)

- **A payload that is not a pull request's state raises** (86). `poll_verdict` raises `ValueError`, naming the payload (the first 200 characters of its repr), when the payload is not an object, has no boolean `merged`, or has no `state` of open or closed. That covers the `{}` a failed or unparsed `gh api` call leaves in both callers, GitHub's error object, an all-null jq projection, and a list. It used to read as "wait", so a poller sat out its whole bound and ended as a timeout with the cause gone.
- An open PR whose `mergeable_state` is `unknown`, null, `blocked`, `has_hooks` or `draft` still waits. GitHub computes the state lazily, and `blocked` resolves on its own (#1399).
- **Callers that do not catch the new raise.** `tools/wait_for_pr.py`'s `fetch` still returns `{}` on a failed or unparseable call (its own rows, wait_for_pr.py:71 and :74), so the first such call now raises out of `wait` and `main`, and the tool exits non-zero with the traceback instead of polling to exit 4. Those rows prescribe an ERROR line with the return code and stderr, which is the tool's to add. `tools/dependabot_review.py`'s `wait_for_mergeable` prints its WARNING about the unreadable answer and then passes `{}`, which now raises on the first poll. In the fleet worker mode, the `except BaseException` around each repo's worker prints `[ERROR] worker for <repo> raised` and records the repo as errored; in the sequential mode it propagates out of the run. Its row (dependabot_review.py:950) prescribes an ERROR line on stderr and stopping the poll.

Baseline: no entries in the loud-failure baseline, before or after (a narrow site). The fail-open audit's findings are unchanged; it examines one more site.

### section_utils.py (#3794, 2 sites)

- **A stripper that cannot be imported propagates its `ImportError`** (146, 147). `drafter_authored` still imports the injected-block stripper lazily, for the same import cycle, and no longer catches `ImportError`. It used to return the document unstripped, so the requirement extractor read the injected table as continuation text of the requirement above it.
- The ledger's third row for this file (288, unmapped feedback returns `""`) is compliant, and is not one of this issue's sites.
- **Callers.** `core/validation/test_plan_validator.py` (line 129) and `workflows/testing/nodes/load_lld.py` (lines 538 to 566). Neither catches `ImportError` around the call, so it propagates to whatever runs them. An `ImportError` of a module in this package means the install is broken, and every other import from it would fail the same way.

Baseline: one entry leaves (the tag). The fail-open audit lost 1 finding.

### tdd_path_tracking.py (#3798, 1 site)

- **A stale scaffold that cannot be removed raises** (124). `cleanup_stale_scaffold` no longer catches the `OSError` from the removal, so the removal's own error propagates, naming the file in its `filename`. It used to log a WARNING, and the stale scaffold stayed beside the real tests, where pytest collects and runs it with them. A scaffold already absent is still skipped by the existence check, since there is nothing to remove, and a run with no current test path still returns.
- **Callers.** None in `assemblyzero/` or `tools/`. Only `tests/unit/test_tdd_path_tracking.py` calls it.

Baseline: no entries in the loud-failure baseline, before or after (a narrow handler the parser does not see). The fail-open audit lost 1 finding, `cleanup_stale_scaffold`'s handler, which leaves its baseline.

### text_sanitizer.py (#3799, 1 site)

- **A value that is not text raises** (72). `strip_emoji` raises `TypeError`, naming the type and the first 120 characters of the value's repr, for anything that is neither a string nor None. It used to return `str()` of it, unstripped: a bytes response became `"b'...'"`, and a parsed object became its repr, each passed on as the model's answer. None is still the empty string, its documented "no text".
- **Callers.** `core/gemini_client.py` (723), `core/llm_provider.py` (1240, 1503, 1907) and `workflows/testing/adversarial_gemini.py` (382), each passing a response that is a string on every path today. None of them catches `TypeError` around the call. In `ClaudeCLIProvider.invoke` the handler is for `OSError` only, so a `TypeError` propagates as a fault.

Baseline: no entries in either, before or after, since the site is not a handler. The fail-open audit examines one fewer site.

### utf8_console.py (#3800, 1 site)

`widen` keeps its two tiers.

- **A stream that refuses both tiers is an ERROR line** (83). When a stream refuses both UTF-8 and `errors="replace"`, `widen` writes an ERROR line to stderr and the log naming the stream (its repr) and both refusals with their types, then returns False as before. It used to return False in silence, and the first character the stream's encoding lacks then killed the report with a `UnicodeEncodeError` and no word about why. An ERROR line, as the ledger prescribes, and not a raise: the tools call `install()` at import to protect their reports, and an unwidened stream still prints every character its encoding has. Not an alert: the failure it predicts is loud on its own when it happens.
- Tier 1 falling back to tier 2 stays quiet (ledger line 76, compliant), and a stream with no `reconfigure` (a `StringIO`, a capture object) is still left alone quietly.
- **An edge, recorded rather than changed.** When the stream that refuses is stderr itself, and it is closed or dead, the ERROR line written to it raises out of `install()` at the tool's import, where it used to pass in silence.
- **Callers.** `install()` in this module, which 16 tools under `tools/` call at import: `answer_key_audit`, `audit_fail_open`, `audit_halt_sites`, `check_requirements`, `check_requirements_form`, `factory_report`, `golden_disasters`, `heal_report`, `orchestrate`, `prompt_failure_report`, `prompt_revision_rank`, `readonly_attribute_audit`, `replay_run`, `speedrun_overlay`, `speedrun_roll` and `stash_audit`. None reads the return value for control flow.

Baseline: no entries in the loud-failure baseline, before or after (narrow handlers). The fail-open audit keeps both of `widen`'s entries under the same keys, since the ledger keeps both handlers.

### fail_open_audit.py (#3775, 5 sites)

An audit is only as good as what it examined, so nothing it cannot cover is skipped any more. A new `ScanError(RuntimeError)` is raised, naming the file or the directory and the cause, chained from it.

- **A handler type `ast.unparse` cannot render raises** (595, 596). The `except Exception` around `ast.unparse(node.type)` is gone. Such a type used to be labelled "an exception", a finding that named nothing.
- **A file that cannot be read or parsed raises** (699, 700). `scan_file` raises `ScanError` for an `OSError`, `SyntaxError` or `ValueError`, naming the path relative to the root. It used to be appended to `files_unparseable` and skipped. The utf-8-sig reading for files with a BOM is unchanged.
- **A scope directory that does not exist raises** (739). `scan` raises `ScanError` for a scope entry that is not a directory; it used to skip it with `continue`.
- **Won't do: rule 5, deleting a field that only carried swallowed errors.** `Coverage.files_unparseable` is now always empty, but `tools/audit_fail_open.py`'s `render_report` prints it, and the tool was outside the fix's modules. The field is kept, with a comment saying so. Left for a follow-up: delete the field together with the tool's "Files that would NOT parse" lines and `tests/unit/test_fail_open_audit.py::TestTheRepoGate::test_every_file_in_scope_parsed`, which asserts it is empty. The scan raising is now what proves every file parsed.
- **Callers.** `tools/audit_fail_open.py`'s `main` calls `scan` and does not catch `ScanError`, so the tool exits non-zero with the traceback naming the file. `tests/unit/test_fail_open_audit.py` calls both.

Baseline: three entries leave (`_Scanner._exception_text`'s handler and tag, and `scan_file`'s tag). The fail-open audit lost 2 findings.

### gate_registry.py (#3776, 4 sites), the halt-site scanner

- **A file the halt-site walker cannot read or parse raises** (1240, 1241). `scan_halt_sites` raises a new `HaltScanError(RuntimeError)` for a `SyntaxError`, `ValueError` or `OSError`, naming the file relative to the root, with the cause, chained. It used to append the file to `files_unparseable` and skip it with `continue`.
- **A registry row whose site is not a site key raises** (1453, 1454). `renumberings` raises `ValueError` naming the row and the value, chained from `_site_parts`'s error, for a site that is not `path::qualname::kind::index`. It used to pass over the row with `continue` and leave it in the phantom list. A well-formed phantom is still reported as a phantom, not raised.
- **Won't do: rule 5.** `WalkCoverage.files_unparseable` is now always empty, but `tools/audit_halt_sites.py` (line 155) prints it and `tests/unit/test_gate_registry.py` (line 57) asserts it empty, and both are outside this module. It is kept, with a comment. Left for the same follow-up as `fail_open_audit.py`'s field: delete it with its two readers.
- **Found while here, not fixed, since it is not a ledger site.** `scan_halt_sites` walks `root / subdir` with `rglob`, and a subdir that does not exist yields no files, so the walk returns no sites and `files_scanned == 0` in silence. `fail_open_audit.scan` now raises on the same case (its row 739); the walker has no row for it. The line is `base = root / subdir` in `scan_halt_sites`.
- **Callers.** `tools/audit_halt_sites.py` (lines 139, 206, 223) calls both and catches neither, so it exits non-zero with the traceback. The tests that call them are `test_gate_registry.py` and `test_halt_site_renumbering.py`.

Baseline: two entries leave (both tags). The fail-open audit lost 2 findings.

### scripted_provider.py (#3792, 2 sites)

The scripted provider answers mock rolls and replays. A script that cannot answer is a failed run, never a quiet default answer.

- **A rule with nothing to answer raises** (136). `_load` raises `ValueError` naming the stage for a rule with no `response`, no `fixture` and no `fail_with`; it used to answer `""` as a success. An explicit `response=""` is still an answer the script wrote, a replayed empty reply. The raise leaves `invoke` after the call is recorded, as a missing fixture file already did.
- **A call no rule answers is an ERROR line** (241): no rule matches, rules for two stages match, or the round is past the scripted ones. It still returns the failed `LLMCallResult` that the caller routes to HALT, which alerts, and now also writes an ERROR line to stderr and the log, with the same message, at the point of the miss. An ERROR line, as the ledger prescribes: the failed result is the caller's contract and HALT already alerts, so a second alert per miss would repeat it. A `fail_with` rule (ledger line 260, compliant) is the script failing on purpose, and prints nothing.
- **Callers.** `core/llm_provider.py`'s `get_provider` hands out the active instance for a `scripted:` spec, and `speedrun/replay.py` builds the rules; every rule it builds carries a `response` or a `fail_with`. `core/call_recording.py`, `core/seats.py` and `tools/replay_run.py` use it too. The new `ValueError` propagates out of `invoke` into whichever node made the call.

Baseline: no entries in either, before or after, since neither site is one the parser sees. The fail-open audit examines one fewer site.

### alert.py (#4247, no ledger row)

Added after the twelve. `alert_operator` wrote its loud line and its record to `sys.stderr` first, with no protection, so a broken pipe, a closed stream or a missing one (`sys.stderr is None`, as under pythonw) raised before the email and the alerts log were tried.

- **A broken stderr is a delivery failure like any other.** `_write_stderr(text)` writes and flushes, and raises `AlertDeliveryError("stderr: ...")` naming the cause for an `OSError` or a `ValueError`, or when there is no stderr.
- **Every step is attempted.** `_attempt_every(steps)` runs the steps in order (stderr, the email, the toast on Windows, the log), each later step in a `finally` of the one before. The failures are raised together, as before: the last one propagates, and each earlier one is in its `__context__` chain, which the existing "NOT DELIVERED" report prints. This is the chaining the nested `finally` blocks already gave the email, the toast and the log, extended to stderr.
- **The "NOT DELIVERED" report goes through `_write_stderr` too.** On a working stderr it prints as before. On a broken one it raises its own `AlertDeliveryError` naming stderr, with every other failure in its context, so nothing is lost and no `OSError` replaces the delivery error.
- **When the reporter fails.** This is the reporter. With stderr gone, the operator still gets the email (and the toast on Windows), the alerts log still gets the record, and the process still gets `AlertDeliveryError` and exits non-zero.
- **Callers.** The contract is unchanged: it returns the record on delivery and raises `AlertDeliveryError` otherwise. `stage_watchdog` catches `AlertDeliveryError` specifically, and still does.

Baseline: no entries in either, before or after; the new handler raises. The fail-open audit examines four more sites.

## Also carried: #4163, a committed test artifact the tiers kept appending to

`audit/calls.jsonl` was committed by accident in PR #3573: three call recordings of fixture text from a test run. The call recorder's context is a module global, and a test that left it armed made every later model call in the process write there, under pytest's working directory. The measurement run for #3801 added a fourth line, which dirtied a tracked file. The fix:

- `tests/conftest.py`'s `call_recording_disarmed` resets the recorder before and after every test, in every tier.
- The artifact is removed, and `/audit/` is ignored.
