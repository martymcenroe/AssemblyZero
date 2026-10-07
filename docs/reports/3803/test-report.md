# Test Report: the rule files stop teaching hand merging (#3803)

## Tests added: `tests/unit/test_merge_instructions.py`

- `test_no_command_block_lands_by_hand[CLAUDE.md]` and `[0935-pr-stuck-recovery.md]`. No ```` ```bash ```` block in either file may contain any of these forms: `gh pr merge`, `gh pr create`, `git checkout`, `git worktree remove`, `git branch -d`, `git push`, `update-branch`, `[skip ci]`, an inline `--body`, or `echo`. The list is closed: every form either file has carried.
- `test_the_check_finds_a_hand_merge` and `test_a_quoted_block_is_not_a_command`: the controls.
- `test_claude_md_keeps_the_archival_override`.

## Test changed

- `tests/unit/test_archive_keeps_venv.py::test_claude_md_runs_the_archive_after_the_tests_and_before_the_driver`. It was named `..._before_the_push` and looked for the line "push and create the PR". It now asserts that the archive runs after the last test run and before the driver, and that the push line is gone.

## Runs, 2026-10-07

- The check, run against `CLAUDE.md` and runbook 0935 as they stand on `origin/main`, flags three forms in the first and nine in the second. So it catches what this change removes.
- The full `tests/unit` tier on `79e18ad1` plus this change: 10991 passed, 66 skipped, 7 deselected, 6 xfailed in 9m 1s. The first run stopped on the archive-order test above, which still pinned the old wording.
- After the archival tool's message changed, its five test files passed (37 tests). The full tier was run again on the final tree: 10991 passed, 66 skipped, 7 deselected, 6 xfailed in 8m 56s. Lineage archival ran after it and had nothing to stage.
- `tools/audit_fail_open.py --check --strict`: PASS. `tools/audit_loud_failure.py --check`: PASS at 333.
- `ruff check` on both test files: clean.
