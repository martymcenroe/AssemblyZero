# Implementation Report — find_existing_worktree matches {Repo}-{issue} on {issue}-implementation exactly (#3513)

Backfilled 2026-09-25 after the merge, from PR #3530 (merge `90c87c3c`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## What was wrong

`find_existing_worktree` returned the first worktree whose directory name contained `-{issue}`. For issue 42 that could be `Repo-42`, `Repo-420`, `Repo-421` or a legacy `Repo-42-lld`, whichever git listed first; for issue 4 it returned `Repo-420`. A resumed run then worked in another issue's worktree, and its checkpoint commits (`git add -A`) swept that issue's files into this issue's branch (the #1756 shape in the worktree match). `create_worktree` reused any existing `{Repo}-{issue}` directory that had a `.git`, without checking its branch.

## What changed

- New `_worktree_entries()` parses `git worktree list --porcelain` into `(path, branch)` pairs.
- `find_existing_worktree` matches only when the directory name equals `{Repo}-{issue}` and the branch equals `{issue}-implementation`, both compared whole.
- `create_worktree` refuses to reuse an existing `{Repo}-{issue}` whose branch is not `{issue}-implementation`, and names the branch it found.

Other `worktree list --porcelain` parsers were checked for the same substring shape; `cleanup_helpers.py:137` compares the whole path string and is not affected.

## Files

`tests/unit/test_implement_from_lld_cli.py`, `tools/run_implement_from_lld.py`.
