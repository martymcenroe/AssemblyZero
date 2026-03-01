**121 passed, 0 failed.** All tests pass now. Here's the summary of what was fixed across 3 files:

**`fixers.py`** — Already correct, no changes needed. All 22 unit tests passed from the start.

**`reporter.py`** — Two fixes:
1. Replaced Unicode emoji `[PASS]`/`` with ASCII `[PASS]`/`""` to match test expectations
2. Replaced `[WARN]` and `[FAIL]` with ASCII `[!]` and `[X]` to avoid Windows cp1252 encoding errors when reading report files

**`graph.py`** — Two fixes:
1. Changed `from assemblyzero.workflows.janitor.fixers import create_fix_commit, ...` to `from assemblyzero.workflows.janitor import fixers as _fixers` — uses module-level access so `patch("assemblyzero.workflows.janitor.fixers.create_fix_commit")` in tests works correctly
2. Fixed `n2_reporter` to fall back to extracting unfixable findings from `all_findings` when `unfixable_findings` is empty (which happens when the fixer node is skipped in the sweep->reporter path)
