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
