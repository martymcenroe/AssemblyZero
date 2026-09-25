# Test Report — N7.5 on the sanctioned transport (#2926, #3546)

## What was run

From the main checkout's venv, against this worktree
(`PYTHONPATH=<worktree>`, `--rootdir <worktree>`, `-p no:cacheprovider`).

The nine touched test files together, before the last two tests were added:

```
tests/unit/test_adversarial_node.py tests/unit/test_adversarial_gemini.py
tests/unit/test_implement_status_file.py tests/unit/test_fail_open_audit.py
tests/unit/test_impl_invoke_payload_is_declared.py tests/unit/test_orchestrator_stages.py
tests/unit/test_pr_stale_remote.py tests/unit/test_orchestrator_state.py
tests/unit/test_implement_from_lld_cli.py
294 passed, 1 warning in 12.11s
```

After the last additions (the pr-body test and the three status-file tests):

```
tests/unit/test_adversarial_node.py tests/unit/test_adversarial_gemini.py tests/unit/test_implement_status_file.py
96 passed, 1 warning in 0.84s

tests/unit/test_orchestrator_stages.py -k TestRunPrStage
4 passed, 51 deselected, 1 warning in 0.42s
```

Full unit tier, run to completion before the PR was opened:

```
tests/unit
2 failed, 10643 passed, 21 skipped, 7 deselected, 5 xfailed, 13 warnings in 651.49s (0:10:51)
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_it_refuses_only_the_two_runs_that_moved_their_tests
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_every_other_draft_passes
```

The two failures are #3468's pair (a unit test that reads another repo's
working tree with hardcoded counts; red locally, skipped in CI), present on
`main` before this change and unrelated to it. Nothing else in the tier
moved.

```
poetry run ruff check <every changed .py file>
All checks passed!

tools/audit_fail_open.py --check
PASS -- 305 files, 9371 sites examined, no new fail-open.
```

## The new tests fail on the old sources

The eight changed source and fixture files were stashed by name
(`git stash push -- <paths>`), the new tests run, and the stash popped.

```
tests/unit/test_adversarial_node.py tests/unit/test_adversarial_gemini.py tests/unit/test_implement_status_file.py
1 warning, 2 errors in 0.72s
E   ImportError: cannot import name 'ADVERSARIAL_PROVIDER_SPEC' from 'assemblyzero.workflows.testing.adversarial_gemini'
E   ImportError: cannot import name 'adversarial_summary' from 'assemblyzero.workflows.testing.nodes.adversarial_node'
```

Both adversarial test files fail at collection on the old sources, which
stops the session before the third file runs; the third file alone:

```
tests/unit/test_implement_status_file.py
3 failed, 10 passed
FAILED ...::TestAdversarialReviewIsOnTheRecord::test_a_skipped_review_names_its_reason
FAILED ...::TestAdversarialReviewIsOnTheRecord::test_a_review_that_ran_names_its_count
FAILED ...::TestAdversarialReviewIsOnTheRecord::test_a_run_that_never_reached_the_node_says_so

tests/unit/test_orchestrator_stages.py -k TestRunPrStage
1 failed, 3 passed
FAILED ...::TestRunPrStage::test_pr_body_says_what_the_adversarial_review_did
```

## What each new test shows

| Test | Shows |
|---|---|
| `TestTheSanctionedTransport::test_the_default_provider_comes_from_get_provider_with_the_gemini_spec` | With no injected provider the client calls `get_provider("gemini:3.1-pro")`, once, and keeps what it returns. |
| `...::test_a_forbidden_alias_is_refused_before_any_transport_is_built` | With the alias patched to `flash`, construction raises `ForbiddenModelError` and `get_provider` is never called. |
| `...::test_an_llm_provider_is_invoked_with_the_prompts_and_the_timeout` | An `LLMProvider` receives the adversarial system prompt, the code under test, and `timeout_seconds=120`. |
| `...::test_the_reply_metadata_carries_the_model_the_transport_used` | `metadata["model"]` is `LLMCallResult.model_used`, which `verify_model_is_pro` then checks. |
| `...::test_a_reported_failure_carries_the_transport_message_not_a_timeout` | A failed result with `API key not valid` and status 400 surfaces as `GeminiTimeoutError` whose message holds both, and not "exceeded 120s timeout". #2926's first requirement. |
| `...::test_a_rate_limit_is_a_quota_error` | `rate_limited=True` surfaces as `GeminiQuotaExhaustedError`. |
| `...::test_no_discovery_and_no_sdk_import_remain` | No `_discover_provider`; an `ast` walk of the module finds no import from `google`, `importlib`, `langchain_core` or `assemblyzero.utils`. |
| `TestTheRequestedModelIsChosenNotSpelled::test_the_spec_sent_is_the_alias_that_was_checked` | `ADVERSARIAL_PROVIDER_SPEC == f"gemini:{ADVERSARIAL_MODEL_ALIAS}"`. |
| `TestMockRunsMakeNoNetworkCall::test_the_flag_is_in_the_node_schema` | `mock_mode` is an `AdversarialNodeState` key. |
| `...::test_a_mock_run_skips_with_the_reason_and_opens_no_socket` | With `socket.create_connection` and `socket.socket.connect` patched to record and refuse, and the client NOT patched, a `mock_mode` state yields verdict `skipped`, a reason naming the mock run, and no connect. #3546 requirement 1. |
| `...::test_the_flag_crosses_the_langgraph_boundary` | The node added to a `StateGraph(TestingWorkflowState)` and invoked with `mock_mode: True` returns the skip, and the verdict and reason survive the boundary back out. Fails on the old schema in both directions. |
| `TestAdversarialSummary` (4) | The four shapes of the summary line. |
| `TestRunAdversarialNode::test_a_reported_failure_is_recorded_once_and_not_retried` | One call to the client, the transport's message in the reason, no second lap. Replaces `test_timeout_triggers_retry`. |
| `TestAdversarialReviewIsOnTheRecord` (3) | `.implement-status-{issue}.json` carries the `adversarial` block for a skip, a run, and a state that never reached N7.5. |
| `TestRunPrStage::test_pr_body_says_what_the_adversarial_review_did` | The pr stage puts `state["adversarial_summary"]` in the PR body, and "did not reach this step" when the state has none. |

The skip-verdict updates (`test_quota_skip`, `test_downgrade_skip`,
`test_empty_implementation_skip`, `test_no_client_available_skips`,
`test_it_skips_rather_than_raising`) assert `skipped` where they asserted
`error` or `success`.

## Deleted with the strategy they tested

`TestGenerateContentConfigIsAcceptedBySdk` (4) and
`TestTheResolvedModelReachesTheWireAndTheMetadata` (2) pinned the
`google.genai` request shape (#2281, #2286); `test_auto_discovery_import_error`
and `test_langchain_provider_strategy` pinned the discovery and LangChain
paths. None of that code exists now.

## Not verified here

- The live call. `tests/integration/test_adversarial_integration.py` is
  opt-in (`AZ_LIVE_ADVERSARIAL_PROBE=1`) and spends one `agy` call; it was not
  run in this session. The stage 6 rehearsal (step 9 of the sequence) runs
  the implementation workflow under `--mock`, which after this change makes no
  call at N7.5 by construction.
- The orchestrator's impl stage writing `adversarial_summary` is covered by
  the boundary test and the pr-stage test, not by a run of `run_impl_stage`,
  which needs a worktree and a full testing workflow.
