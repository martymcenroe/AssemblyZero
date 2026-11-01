# Test report: #4477, #4478, #4482

## Changed tests

- `tests/unit/test_docs_name_no_deleted_gemini_tool.py` (widened, #4477 T1): `test_no_live_doc_names_a_deleted_tool` checks `gemini-retry`, `gemini-rotate` and `gemini-test-credentials` across the live docs, leaving out the inventory's `docs/lineage/` rows, whose files exist. `test_the_tool_is_gone` covers all three tools.
- `tests/unit/test_gemini_verification_page.py` (new, #4478): `test_t1_no_approved_model_is_forbidden`, `test_t1_the_reviewers_model_is_approved`, `test_t1_the_forbidden_table_is_the_policy_table` (one case for each model on either list) and `test_t2_the_page_names_the_model_of_today`. `test_the_approved_table_has_rows` keeps them from passing on an empty table.
- `tests/unit/test_recovery_plan.py::TestGenerateRecoveryPlan::test_an_auth_halt_points_at_agy_not_a_retired_file` (new, #4482 T1).

## Runs, 2026-11-01

- The new tests against the old text and the old message, set aside with a named stash and restored after: 15 failed, 108 passed.
- On the fix: 122 passed.
