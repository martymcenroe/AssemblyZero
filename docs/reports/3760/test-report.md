# Test report: #3760

## New: `tests/unit/test_import_check_names_the_real_module.py` (3)

- `test_the_message_names_the_module_that_exists`: with `src/boostgauge/skins/stingray.py` on disk, `from boostgauge.stingray import draw_telltales` fails and the message contains `did you mean` and `` `boostgauge.skins.stingray` ``.
- `test_no_suggestion_when_nothing_shares_the_name`: `boostgauge.nowhere` fails with no `did you mean`.
- `test_a_module_only_on_the_base_is_suggested`: a real git repo whose `skins/stingray.py` exists only on branch `arc`, checked out on `main`; the suggestion comes from the base.

## Runs, 2026-10-07, Ubuntu (WSL)

- With the change stashed (named path): 2 failed (the two suggestion cases), 1 passed (no-match, unchanged). With it: 3 passed.
- With the import suites (`test_spec_calls_existing_code`, `test_import_checker_base`, `test_implementation_spec_workflow`): 222 passed, after the lint repair below.
- `tools/audit_halt_sites.py --check`: PASS. Fail-open baseline regenerated: only `sites_examined` moves (9593 to 9603).
- Full `tests/unit`: 10953 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 15s (before the one-line lint repair, which changes no behaviour: two `endswith` calls folded into one tuple call).
- `ruff check`: `validate_completeness.py` 6/6 against `main` after folding the two `endswith` calls (PIE810); the new test file clean after dropping an unused `noqa`.
