# Implementation Report — The archival tool deletes nothing (#3558)

Parent: #3502. Question 7 of the 2026-09-24 handoff.

## What was wrong

AssemblyZero `CLAUDE.md` ("Merging PRs") tells an agent to run
`tools/archive_worktree_lineage.py --worktree . --issue N --main-repo .`
inside the worktree before creating the PR. The shell guard reads a script
for deletion calls before it lets an agent run it, and `clean_ephemeral`
carried `shutil.rmtree` and `unlink`. Fed the command from this checkout,
the guard answered:

```
BLOCKED: banned command inside script
The script 'tools/archive_worktree_lineage.py' is refused: banned command inside script: Python script contains banned deletion call
```

Every PR of 2026-09-24 skipped the step; it happened to be a no-op each time
because no lineage existed. #3518 gated the site (`require_linked_worktree`,
#3528) rather than removing it, which satisfies this repository's
`test_rmtree_sites_are_gated.py` and not the guard, which reads the token.

`clean_ephemeral` deleted `.coverage`, `__pycache__`, `.pytest_cache` and
`.assemblyzero/audit` from the worktree. All four are gitignored, and the
sequence the tool sits in ends with `git worktree remove`, which deletes
every ignored file in the worktree without asking (the #397 guard exists
because it does). The function pre-deleted what the next command deletes.

## What changed

`tools/archive_worktree_lineage.py`: `clean_ephemeral` is removed, `main()`
no longer calls it, and the module docstring lists the three remaining steps
and says the tool deletes nothing and why. `archive_lineage`,
`stage_archived` and `evict_poetry_venv` are unchanged. `shutil` stays
imported for `copytree`. `CLAUDE.md` is unchanged: the fix is in the tool,
not the procedure.

Tests:

- `tests/unit/test_archival_tool_passes_the_guard.py`, new: an `ast` walk
  finds no `rmtree`, `unlink`, `remove`, `removedirs` or `rmdir` call and no
  `from shutil import rmtree`; `clean_ephemeral` is gone; `CLAUDE.md` still
  prescribes the same command; `main()` calls `require_linked_worktree`,
  `archive_lineage`, `stage_archived` and `evict_poetry_venv` in that order
  and nothing else; and, where `~/.claude/hooks/shell-guard.sh` exists, the
  `CLAUDE.md` command fed to it as a PreToolUse payload is not denied (exit
  2 is the guard's deny; the test runs from the checkout so the script path
  resolves to the tool under test).
- `tests/unit/test_worktree_cleanup.py`: `TestCleanEphemeral` goes with the
  function; `test_full_archive_workflow` now asserts the caches are left in
  place.
- `tests/unit/test_rmtree_sites_are_gated.py`: the `clean_ephemeral`
  `ALLOWLIST` entry is dropped (the test fails on an entry whose site is
  gone), the site count is 6, and the main-checkout refusal test keeps its
  `evict_poetry_venv` half.

## What did not change

- The archive's own move-aside of a previous archive (#3518) and the #3528
  refusal of a main checkout.
- `git worktree remove` and its guard (#397): the caches and the scratch
  audit directory are theirs to take, as they always were at the end of the
  sequence.
