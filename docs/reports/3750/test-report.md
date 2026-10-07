# Test report: #3750

## New: `tests/unit/test_lld_survives_landing.py` (4)

- `test_the_durable_copy_lives_in_the_gitignored_lineage`: `durable_lld_path(target, 2)` is `<target>/docs/lineage/active/2-lld-handoff/LLD-002.md`.
- `test_after_a_landing_final_lld_path_is_the_durable_copy`: the driver stub lands with the worktree copy already gone (as the driver leaves it); `final_lld_path` is the durable copy, which exists, and the PR URL is recorded.
- `test_a_reported_lld_that_is_gone_is_named_not_blank`: the live shape (APPROVED, a `final_lld_path` that no longer exists, `error_message == ""`) fails the stage with a message naming the missing path.
- `test_no_artifact_at_all_keeps_the_old_reason`: no path at all gives `LLD workflow completed but no artifact produced`, where the old code gave `""`.

## Runs, 2026-10-07, Ubuntu (WSL)

- **The tests catch the bug.** With both source changes stashed (named paths), all 4 failed; with them, 4 passed.
- `tools/audit_halt_sites.py --check`: PASS, 145 halt sites, every one registered. Fail-open baseline regenerated; only its totals move.
- Full `tests/unit`: 10919 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 11s.
- `ruff check`: both edited modules carry the same counts as on `main` (17 and 20); the new test file has none.
