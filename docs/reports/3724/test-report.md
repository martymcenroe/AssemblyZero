# Test Report: the sweep ledger, and core batch 1 (#3724, part of #3581)

## Tests added

- **`tests/unit/test_halt_node.py::TestHaltAlerts`:**
  - `test_every_halt_alerts_once_with_workflow_stage_and_cause`.
  - `test_an_undeliverable_alert_raises_after_the_halt_is_on_disk`: the snapshot is in the per-test state directory before `AlertDeliveryError` propagates.
  - `test_a_named_but_missing_audit_dir_is_reported_not_skipped`.
- **`tests/unit/test_alert.py::test_a_failed_email_still_toasts_on_windows`:** it fails on the old code, where the email raised before the toast ran.
- **`tests/unit/test_fail_open_audit.py`:** `test_alerting_the_operator_is_not_a_finding` and `test_a_handler_that_only_logs_is_still_a_finding`.

## Tests changed

- `tests/unit/test_halt_evidence.py::TestTheHaltEmitsIt::test_a_bundle_failure_never_masks_the_halt` asserts the halt completes and the bundle failure reaches the operator as its own alert. It used to assert a `[WARN]` on stdout.
- `tests/unit/test_resume_contract.py::TestTheHaltWritesTheContract::test_a_contract_write_failure_never_masks_the_halt`: the same, for the contract.
- `tests/unit/test_loud_failure_check.py`: `BASELINE_CEILING` lowered to 329.

## Runs, 2026-10-07

- Every HALT-related file passes: `test_halt_node`, `test_cap_bundles`, `test_halt_evidence`, `test_halt_legibility`, `test_resume_contract` and `test_testing_graph_halts_through_halt`. So do `test_alert`, `test_fail_open_audit` and `test_loud_failure_check`.
- Full `tests/unit` tier on `79e18ad1`, with the machine quiet: 10992 passed, 66 skipped, 7 deselected, 6 xfailed in 9m 14s. Lineage archival ran inside the worktree after it and had nothing to stage.
- `tools/audit_loud_failure.py --check`: PASS at 329. `tools/audit_fail_open.py --check --strict`: PASS. `tools/audit_halt_sites.py --check`: PASS.
- Ledger quote check: `verify_findings` matched all 215 quoted lines to their files (107 and 108).

## CI failure on PR #3770, and the fix

- The driver stopped at `checks_failed` on head `f60885e9`, with nothing merged. The e2e tier halted a workflow, and the HALT node reached the real `alert_operator`. The recorder and the transport refusal lived in `tests/unit/conftest.py`, so only the unit tier had them. I had run only the unit tier before pushing.
- Fix: `RealAlertTransportReached`, `_no_real_alert_transport` and `operator_alerts` moved to `tests/conftest.py`, so every tier gets them. `test_alert.py` imports the exception from there.
- The fix branch merged `origin/main` (one commit, #3805) rather than rebasing, because the branch was already pushed.
- All four tiers were then run on the merged tree: see below.
