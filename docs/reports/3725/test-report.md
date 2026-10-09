# Test Report: #3725 with #3817, #3808, #3818, #3819

## New tests: `tests/unit/test_adversarial_review_halts.py` (30)

- **One per caught exception type** (work order step 7). Each drives the node with the failure injected and asserts:
  - `route_after_adversarial` returns `HALT`;
  - `error_message` names the seat, the spec, the exception type and its message;
  - the verdict is not "skipped";
  - an ERROR line reaches stderr.

  The types are `RateLimitError` (quota), `ForbiddenModelError` (at the call and at client build), `GeminiModelDowngradeError`, `TimeoutError_`, `GeminiEmptyResponseError`, and `ValueError` (client build).
- **No non-mock path returns `adversarial_verdict == "skipped"`.**
  - An AST check: `_skipped` is called exactly once, inside the `mock_mode` branch.
  - Every failure type, asserted not to be "skipped".
  - The mock run still skips and routes to N8.
- **HALT alerts.** A graph built from the real node, router and HALT node, with the `operator_alerts` fixture: a quota failure records one alert naming it.
- **One per remaining sweep site:**
  - node: no implementation files; unreadable context file; malformed response; rejected file not removable; zero valid tests; write failure;
  - gemini: empty success; unknown model; unexpected exception keeps its type;
  - validator: no assertions; parse after compile;
  - writer: no cases; empty code; write failure; staging dir not removable.

**Before the fix, measured.** I set the seven source changes aside by named-path stash and ran the file against the original code, with a measurement copy that stubbed the two new error classes so it would collect. **29 failed and 1 passed.** The pass is `test_the_mock_run_still_skips`, which pins behaviour the work order keeps (step 5). The stash was reapplied, checked and dropped, and the copy was deleted.

## Changed tests

- `test_adversarial_node.py`:
  - every "skipped" expectation is now the error and the halt;
  - the node tests use a real implementation file (`/fake/module.py` now fails, correctly, as unreadable);
  - the mock-violation test asserts the rejected file is removed and the review fails.
- `test_adversarial_gemini.py`: an unknown model raises.
- `test_adversarial_writer.py`: no cases, and empty code, raise.
- `test_adversarial_validator.py`: a missing assertion is an error and makes the set invalid; a duplicate name alone stays a warning.
- `test_rmtree_sites_are_gated.py`: the allowlist names `_remove_staging_dir`, the function the gated `rmtree` moved to.
- `test_testing_graph_halts_through_halt.py`: `N7_5_adversarial` joins the expected inbound HALT edges.

## Tiers (no speedrun roll running)

```
pytest tests -q                                   22 failed, 11605 passed, 66 skipped, 90 deselected, 6 xfailed
  the 1 failure this change caused                 fixed (HALT's inbound-edge set), file rerun: 8 passed
pytest -m "integration or e2e or adversarial"     83 passed, 7 skipped
```

The other 21 failures also fail on unchanged `main` on this machine, as recorded for PRs #4138 and #4147:
- `test_auto_reviewer_wait_loop.py` (16);
- `TestRunJsGate` (2);
- `test_adr_references_resolve`;
- `test_full_pipeline_success`;
- `test_checkpoint_carries_no_enums`, which passes alone.

## Audits

```
audit_loud_failure.py --check            PASS -- 318 site(s)
audit_halt_sites.py --check              PASS -- 151 halt sites, every one registered
audit_fail_open.py --check --strict      PASS after regeneration (8 sites left, none added)
```

## Lint

Per-file ruff counts against `origin/main` are unchanged or lower (`test_adversarial_writer.py` went from 2 to 1). The new test file has no findings.
