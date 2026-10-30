# Test Report: #4209

- Issue test 1 and requirement 3: the six `would_drop` tests in `tests/unit/test_land_2283_guard.py` are unchanged and pass.
- Issue test 2: `test_a_landed_embed_passes_when_the_workflow_gains_a_step`. The real embed, after a change shaped like #4208 (a step added after checkout, `fetch-depth: 2`, the `# Issues` header and the coverage upload's `if: always()` rewritten), passes the guard, while bare `would_drop` reports the added step.
- Issue test 3: `test_a_pending_embed_with_an_addition_that_would_drop_a_line_fails` (synthetic) and `test_the_real_embed_still_fails_while_pending_and_behind` (the real embed against a `ci.yml` that still carries the pre-landing `# Issues` header and has gained a step). Both fail the guard with the gained lines, and neither reports the header the embed removes on purpose.
- Acceptance 2: `test_the_actual_regression_this_guard_exists_for` is unchanged and passes. `test_the_actual_regression_still_fails_while_pending` runs the same regression through the new guard, with main as it stood then (pre-landing header and main-only integration condition still present): it reports `concurrency:` and the `setup-python@v7` line.
- `test_the_shipped_embed_carries_none_of_the_lines_it_removes`: the landed embed is never judged pending.
- The file: 12 passed.
- Acceptance 1: the proposed workflow for #4208 was generated from its landing script (written against blob `90b853a8`, which is this branch's `ci.yml`) and served in place of `ci.yml` by redirecting `Path.read_bytes` and `Path.read_text` for that one path; the file on disk was not written. The two unit test files that read this repository's `ci.yml`, found by grep, are `tests/unit/test_land_2283_guard.py` and `tests/unit/test_new_repo_python_version.py`. With the proposal served: 23 passed.
- Full unit tier on the branch (`tools/test-gate.py tests/unit/`): 11228 passed, 66 skipped, 7 deselected, 6 xfailed, in 9m54s.
- `ruff check` on the changed file: clean.
