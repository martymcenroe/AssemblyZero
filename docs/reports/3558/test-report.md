# Test Report — The archival tool deletes nothing (#3558)

## What was run

From the main checkout's venv, against this worktree
(`PYTHONPATH=<worktree>`, `--rootdir <worktree>`, `-p no:cacheprovider`):

```
tests/unit/test_archival_tool_passes_the_guard.py tests/unit/test_worktree_cleanup.py tests/unit/test_rmtree_sites_are_gated.py
25 passed, 1 warning in 9.01s
```

The guard test ran, not skipped: this machine has the shell guard
installed, and the `CLAUDE.md` command fed to it from this worktree was
not denied.

```
poetry run ruff check <the four changed .py files>
All checks passed!
```

## The new tests fail on the old tool

`tools/archive_worktree_lineage.py` was stashed by name, the new file run,
and the stash popped:

```
tests/unit/test_archival_tool_passes_the_guard.py
4 failed, 1 passed, 1 warning in 0.78s
FAILED ...::TestTheToolDeletesNothing::test_no_deletion_call_remains
FAILED ...::TestTheToolDeletesNothing::test_clean_ephemeral_is_gone
FAILED ...::TestMainRunsTheThreeStepsAndNothingElse::test_main_archives_stages_and_evicts_in_order
FAILED ...::TestTheGuardLetsTheCommandThrough::test_the_claude_md_command_is_not_denied
```

The fourth is the one that matters: on the old tool the guard denies the
`CLAUDE.md` command (exit 2, "Python script contains banned deletion
call"), and on the new one it does not. The test that passes on both,
`test_claude_md_prescribes_the_same_command`, pins that the procedure did
not move to meet the tool.

## What each test shows

| Test | Shows |
|---|---|
| `test_no_deletion_call_remains` | Requirement 1: no `rmtree`, `unlink`, `remove`, `removedirs` or `rmdir` call, and no `from shutil import rmtree`, anywhere in the tool. |
| `test_clean_ephemeral_is_gone` | The function is removed, not renamed. |
| `test_claude_md_prescribes_the_same_command` | The `CLAUDE.md` step is unchanged. |
| `test_main_archives_stages_and_evicts_in_order` | Requirement 2: `require_linked_worktree`, `archive_lineage`, `stage_archived`, `evict_poetry_venv`, in that order, and no cleaning step between. |
| `test_the_claude_md_command_is_not_denied` | The acceptance criterion, against the real guard: skipped where the guard is not installed (CI), run here. |
| `test_worktree_cleanup.py::test_full_archive_workflow` | Requirement 3: after archiving, `.coverage` and `__pycache__` are still in the worktree, for `git worktree remove` to take. |
| `test_rmtree_sites_are_gated.py::TestTheSitesThatAssertOwnership` | The main-checkout refusal still holds for `evict_poetry_venv`; the site walk finds 6 sites and 6 allowlist entries. |

## Not verified

- The tool run end to end by an agent through the guard inside a real
  merge sequence. The next PR of this session runs the `CLAUDE.md` step as
  written, which is the live test.
- The full unit tier was not run for this change: the tool has three test
  files as readers and all three ran. CI runs the full tier on the PR.
