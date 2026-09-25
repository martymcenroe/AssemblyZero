# Test Report: every artifact that put Claude in a seat is corrected to the 2026-09-24 law (#3552)

## New tests

`tests/unit/test_the_law_gemini_in_both_seats.py`:

| Test | What it pins |
|---|---|
| `TestTheStandaloneDefaults::test_no_seat_argument_defaults_to_claude` | none of `tools/run_requirements_workflow.py`, `tools/run_implement_from_lld.py`, `tools/run_implementation_spec_workflow.py` contains `default="claude:` |
| `TestNoDocumentPutsClaudeBackInASeat::test_the_tree_is_clean` | the walk over `docs/`, `wiki/`, `tools/`, `assemblyzero/` finds none of the ledger's phrases |
| `TestNoDocumentPutsClaudeBackInASeat::test_the_guard_sees_a_planted_line` | a planted `Claude drafts LLD` under `docs/` is reported as `docs/x.md:1: ...` |
| `TestNoDocumentPutsClaudeBackInASeat::test_the_guard_leaves_history_alone` | the same line under `docs/done/` is not reported |

The tree walk failed on `main` before this change: it found 30 lines across 14 files (the ledger's table). The default values themselves are pinned by `tests/unit/test_agy_both_seats.py`, which #3517 (PR #3555, `532dc07f`) landed while this branch was open, so the two default-pinning tests this branch first carried were removed as duplicates.

The walk matches a closed list of seven phrases by substring after lower-casing. It is not a regex, per this repository's audit rule. `--drafter claude:` was dropped from the list: #3555's docstring keeps `--drafter claude:sonnet --reviewer claude:opus` as its example of an explicit override, which the law permits (ADR 0234, "What it does not change").

## Updated tests

- `tests/unit/test_preflight_transport.py`: two docstrings now date the old defaults; no assertion changed. `TestTheProbeUsesAGeminiModel` still passes with `REVIEWER_MODEL` a Gemini id, because the probe names its own model.

## Runs

Targeted, first pass (defaults, mock paths, gate registry):

```
tests/unit/test_the_law_gemini_in_both_seats.py tests/unit/test_requirements_cli.py
tests/unit/test_preflight_transport.py tests/unit/test_implement_from_lld_cli.py
tests/unit/test_precheck_predicts_the_roll.py tests/unit/test_lld_mock_completes.py
tests/unit/test_lld_mock_is_offline.py tests/unit/test_lld_writes_only_worktree.py
tests/unit/test_impl_standalone_end_state.py tests/unit/test_impl_no_push_before_work.py
tests/unit/test_requirements_config.py tests/unit/test_requirements_gate_escalation.py
tests/unit/test_routing_policy.py
262 passed
```

Targeted, second pass (after the `REVIEWER_MODEL` change):

```
tests/unit/test_assemblyzero_config.py tests/unit/test_gemini_client.py
tests/unit/test_preflight_transport.py tests/unit/test_requirements_audit.py
tests/unit/test_agy_sandbox_args.py tests/unit/test_the_law_gemini_in_both_seats.py
tests/unit/test_gemini_client_capacity.py tests/e2e/test_lld_workflow_mock.py
tests/e2e/test_issue_workflow_mock.py
154 passed, 17 deselected
```

`tools/audit_fail_open.py --check`: PASS, 305 files, 9366 sites examined, no new fail-open, no baseline change.

The two passes above ran before the branch was fast-forwarded to `43ddc9b2`. After it, with the reconciled files:

```
tests/unit/test_the_law_gemini_in_both_seats.py tests/unit/test_agy_both_seats.py
tests/unit/test_requirements_cli.py tests/unit/test_preflight_transport.py
tests/unit/test_assemblyzero_config.py tests/unit/test_gemini_client.py
tests/unit/test_requirements_audit.py
224 passed, 1 warning in 9.10s
```

Full unit tier (`tests/unit`, from the worktree with the main checkout's interpreter and `PYTHONPATH` set to the worktree, on `43ddc9b2` plus this change, no other pytest session running):

```
2 failed, 10705 passed, 21 skipped, 7 deselected, 5 xfailed, 13 warnings in 692.32s (0:11:32)
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_it_refuses_only_the_two_runs_that_moved_their_tests
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_every_other_draft_passes
```

The two failures are #3468's pair: they read another repository's `docs/lineage/done/` on this machine and assert a hardcoded count (open: red locally, skipped in CI), and they fail identically on `main`. The #3531 home-state guard printed nothing.

## Why mock runs are unaffected by Gemini defaults

`generate_draft.py` and `generate_spec.py` call `preflight_for_specs` only when `mock_mode` is false, and `review_test_plan.py` returns the mock review when `state["mock_mode"]` is set. So the rehearsal path (#3502 stage 6) does not reach the agy transport, which the second targeted pass confirms through both e2e mock runs.
