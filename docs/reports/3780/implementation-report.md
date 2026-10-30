# Implementation Report: the core/ package under standard 0034 (#3581 step 5)

The rule is ADR 0236 and standard 0034. This PR takes the `assemblyzero/core/` module issues from the #3581 sweep, highest harm first. Each module's sites are fixed, tested, and marked in ledger 0908.

## Scope

The modules a target run passes through, in order of harm. Harm means a failure the run reads as success on the model path, the verdict path or the resume path; failures that lose a record come after.

Not in this PR, because no target run passes through them:
- `fail_open_audit.py` (#3775), an audit tool;
- `gate_registry.py`'s halt-site scanner (#3776), an audit tool;
- `scripted_provider.py` (#3792), used only by mock rolls and replays.

## Also carried

- `tests/unit/test_alert_channel_at_start.py::test_the_implementation_workflow` passes a temporary `--repo`, and its stand-ins fail if reached (#4161). Measured against the old source, it had run a mock implementation run into the worktree.

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

## Also carried: #4163, a committed test artifact the tiers kept appending to

`audit/calls.jsonl` was committed by accident in PR #3573: three call recordings of fixture text from a test run. The call recorder's context is a module global, and a test that left it armed made every later model call in the process write there, under pytest's working directory. The measurement run for #3801 added a fourth line, which dirtied a tracked file. The fix:

- `tests/conftest.py`'s `call_recording_disarmed` resets the recorder before and after every test, in every tier.
- The artifact is removed, and `/audit/` is ignored.
