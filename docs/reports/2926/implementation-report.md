# Implementation Report — N7.5 on the sanctioned transport (#2926, #3546)

Parent: #3502. The audit's verbatim record of the defect is #2932; the
operator authorized this repair on 2026-09-24, late evening, in this session.

## What was wrong

`AdversarialGeminiClient._discover_provider` tried four module names under
`assemblyzero.utils` that do not exist, caught the `ImportError` on each, and
fell through to `google.genai.Client()`. That SDK reads `GOOGLE_API_KEY` then
`GEMINI_API_KEY` from the environment; the machine still carried a
`GEMINI_API_KEY` from the free-trial rotation #1605 retired on 2026-06-23, and
Google answered `API_KEY_INVALID`. The client's catch-all renamed that to
`Gemini API error (status=400)` inside a `GeminiTimeoutError`, the node saw a
timeout, retried once with a longer timeout, and skipped itself. Every run log
on disk from 2026-07-31 to 2026-09-24 shows the same two lines and no
adversarial verdict was ever returned.

Two more things were wrong at the LangGraph boundary, and #2018 is the name of
the class:

- `mock_mode` was not in `AdversarialNodeState`, so the node could not see it
  and decided by whether a client could be built. On a machine with any Gemini
  key, a `--mock` rehearsal called the paid API (#3546).
- N7.5's outputs (`adversarial_verdict` and the rest) were not in
  `TestingWorkflowState`, so LangGraph dropped them on the way out of the node.
  Nothing downstream could ever have said what the review did. Also the node
  read `issue_id`, which the testing state never carries (it has
  `issue_number`), so the writer named every adversarial file for issue 0.

## What changed

`assemblyzero/workflows/testing/adversarial_gemini.py`

- `ADVERSARIAL_PROVIDER_SPEC = "gemini:3.1-pro"`, built from the same alias
  `resolve_adversarial_model` checks against `FORBIDDEN_MODELS`.
- `__init__` with no provider: `resolve_adversarial_model()`, then
  `get_provider(ADVERSARIAL_PROVIDER_SPEC)`. A forbidden alias is refused before
  any transport exists.
- `_discover_provider`, the `google.genai` strategy and the LangChain strategy
  are deleted. `_invoke_provider` accepts an `LLMProvider` (the sanctioned
  shape) or a plain callable (tests). A failed `LLMCallResult` raises
  `GeminiQuotaExhaustedError` when rate-limited, otherwise `GeminiTimeoutError`
  carrying the transport's own message and status; `generate_adversarial_tests`
  passes both through unchanged rather than re-wrapping them as
  "exceeded 120s timeout".

`assemblyzero/workflows/testing/nodes/adversarial_node.py`

- `mock_mode` skips before any client is built.
- Construction failure is narrowed to `(ForbiddenModelError, ValueError)`; the
  broad `except Exception` from #1602 existed for `genai.Client()` raising on a
  missing key, which no longer exists.
- One call. The retry-once block is gone: the transport already retried and
  rotated (#1907), and the second lap was what printed "timeout — retrying" on
  every run whose cause was a dead key.
- Every skip is `_skipped(state, reason)`: verdict `"skipped"`, reason set. The
  no-client path used to say `"success"`.
- `adversarial_summary(state)` renders one line: did not reach this step / did
  not run: reason / errored: error / ran; N test(s) written; verdict V.
- The writer gets `issue_id or issue_number`.

State declarations

- `AdversarialNodeState`: `mock_mode`, `issue_number`; verdict literal gains
  `"skipped"`.
- `TestingWorkflowState`: `adversarial_verdict`, `adversarial_error`,
  `adversarial_test_count`, `adversarial_skipped_reason`, `generated_test_files`.
- `OrchestrationState`: `adversarial_summary`, initialised to `""`.

Where the outcome is written

- `tools/run_implement_from_lld.py`: the final report prints the summary line
  on both the SUCCESS and FAILED paths; `.implement-status-{issue}.json` gains
  an `adversarial` block (verdict, test_count, skipped_reason, summary).
- `orchestrator/stages.py`: the impl stage stores `adversarial_summary(sub_result)`
  in state; the pr stage appends it to the PR body, or "did not reach this
  step" when state has none.

Housekeeping

- `tests/fixtures/fail_open_baseline.json`: three keys dropped, for the two
  deleted `_discover_provider` handlers and the deleted retry handler
  (`run_adversarial_node::except_handler::7`). `audit_fail_open.py --check`
  passes on the tree.
- `tests/integration/test_adversarial_integration.py`: opt-in via
  `AZ_LIVE_ADVERSARIAL_PROBE=1`, builds the sanctioned client, and does not skip
  on a transport error.

## What did not change

- N7.5 stays non-blocking; `route_after_adversarial` always proceeds to N8.
- `verify_model_is_pro` and the response-text quota scan are as they were.
- `resolve_adversarial_model` and its tests are unchanged.
- The standalone `--reviewer` default is #3517's, not this PR's.

## For the operator

`GEMINI_API_KEY` is still set in the machine environment. Nothing sanctioned
reads it and, after this change, nothing unsanctioned does either; #2926 asks
for it to be removed. That is a change to your user environment variables, so
it is yours to make; the closing comment on #2926 says how.
