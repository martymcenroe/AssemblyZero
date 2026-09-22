# Implementation Report — Track Six Untracked Work Products (#3436)

## What This Change Is

Six files that already existed on disk, untracked, are now tracked. No existing
file is touched. `git diff --cached --diff-filter=MD --name-only` returns zero
lines: there are no modifications and no deletions, only additions. The change
is 6 files, 237 insertions.

| file | lines | what it is |
|---|---|---|
| `docs/standards/0031-gemini-actor-critic-loop.md` | 29 | ADR 0031 — the actor-critic loop required of Gemini-driven autonomous loops |
| `docs/prompts/true-nostop.txt` | — | the no-stop prompt that drove the autonomous audit loop |
| `tools/fix_az_workflow_concurrency.py` | 111 | one-shot tool for the workflow concurrency repair |
| `dispatch/gemini_audit_failure_blog.md` | — | first-person write-up of the audit-automation failure |
| `dispatch/gemini_audit_failure_paper.md` | — | longer treatment of the same |
| `dispatch/sandbox_illusion.md` | — | essay on why OS-level isolation does not contain agentic evasion |

## Why This Is a Change Worth Making

An untracked file has no recovery path. Deletion, an overwrite, or a bad merge
removes it with nothing in git able to bring it back. Several of these had been
sitting exposed for over a week.

Staging alone is not sufficient and was not treated as sufficient. `git add`
writes the blob into `.git/objects`, which survives deletion of the working
file, but the blob is unreferenced and a `git gc` prunes it. Staging buys time;
only a commit discharges the obligation.

## What Was Deliberately Left Out

Two groups of files were found in the same sweep and are not here.

**`tools/hermes_pin_workflow_shas.py`.** Its docstring describes another repo's
CI gate configuration — which workflow refs were mutable and how they were
pinned. That repo is private. Its *name* is permitted on a public surface
because the operator has published a public companion that names it, but the
configuration detail is contents, not name, and AssemblyZero is public. It is
also tooling for that other repo rather than for this one. Parked at
`data/scratch-2026-09-21-repo-clean/rehomed-from-repo-root/` for transfer.

**Ten scratch artifacts** — issue bodies, `gh_issues.json`, the audit's
`manually_read*.txt` pair, a throwaway import check, a one-off shell script.
These were sitting in the repo root, which is not where working files belong.
Rehomed to the same gitignored scratch directory.

## Placement

The three essays join two siblings of the same genre already tracked under
`dispatch/` on main, taking that directory from 2 tracked files to 5. The ADR
and the prompt go to the directories their kind already occupies. No new
top-level directory is introduced.
