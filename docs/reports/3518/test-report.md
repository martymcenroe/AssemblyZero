# Test Report — Every shutil.rmtree is a move-aside or asserts ownership (#3518, #3231, #3528)

Backfilled 2026-09-25 after the merge, from PR #3539 (merge `c8e350a1`) and its body (#3559). The runs quoted are the ones the PR reported; none was re-run for this backfill.

## Tests the PR added

New file `tests/unit/test_rmtree_sites_are_gated.py`, 12 tests:

- The `ast` allowlist: every `shutil.rmtree` call, including `from shutil import rmtree` aliases, must be in `ALLOWLIST` with its gate named; no entry may outlive its site; the count was pinned at 7 so the test cannot pass by vacuum (6 since #3558).
- One behaviour test per changed site, against real git where git matters. The #3528 test ran `clean_ephemeral` and `evict_poetry_venv` against a main checkout and asserted that both refuse, that the planted caches survive, and that `poetry env remove` is never called.

Existing tests updated: `test_archive_readonly.py` (targets carry an archive's `logs/`), `test_requirements_audit.py` (n2 is moved aside, not removed), `test_worktree_cleanup.py` (the cache-list tests stand the refusal down; the integration test builds a real linked worktree).

## Results the PR reported

On the old code, 9 of the 12 fail. The full local unit tier results are in the PR's first comment.

## Not verified for this backfill

- Nothing was re-run.
