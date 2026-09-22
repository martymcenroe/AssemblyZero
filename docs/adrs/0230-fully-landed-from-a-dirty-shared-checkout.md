# ADR 0230: Reaching Fully Landed from a dirty shared checkout without destroying uncommitted state

**Status:** Accepted (operator-directed 2026-09-22)
**Date:** 2026-09-22
**Categories:** Process, Git Hygiene, No-Force Policy
**Related:** #3437 (this ADR); ADR 0229 (the state this reaches); ADR 0217 (the sibling for orphan branches); ADR 0216 (the agent-writes, operator-runs split this follows); #1852 (the fast-forward branch guard); #944 (worktree removal blocked by a venv); the universal `CLAUDE.md` section "Destroying uncommitted state — the principle, not just the table"

---

## 1. Context

ADR 0229 defines **Fully Landed** — clean tree, no worktrees, no stashes, no open PRs, `main` at parity with `origin/main` — and makes the agent responsible for the final step that reaches parity. It does not say how to get there from the state an agent actually inherits on a checkout that several sessions share:

- local `main` is behind `origin/main`;
- the tree carries another session's uncommitted work — modified tracked files and untracked files, days old, never landed;
- at least one incoming commit on `origin/main` touches one of the modified files, so `git merge --ff-only origin/main` refuses with `Your local changes to the following files would be overwritten by merge`.

Every command that makes the fast-forward succeed by clearing the tree is on the universal banned list: `git restore <path>`, `git checkout -- <path>`, `git reset --hard`, `git stash -u`, `git clean`. Each destroys uncommitted state, and each has been reached for under the rationalisation "the content is equivalent so the destroy is lossless" (documented incident, 2026-05-27; the `git stash -u` incident, 2026-08-14). The universal rules name the permitted alternative in one table cell — a named-path `git stash`, then pull, then drop only after the operator confirms redundancy — and one repo executed a full instance of that sequence on 2026-09-21 as a one-off, twelve-step plan. The procedure existed as a table cell and a closed issue. Nothing an agent could point to said "this is how it is done."

**Observed 2026-09-22.** A private repo's primary checkout: `main` 2 behind `origin/main`; `.gitignore`, `poetry.lock` and `pyproject.toml` modified and five files untracked, all from a session six days earlier that had ported a wrapper to Linux and never committed it; one of the two incoming commits was a dependency bump to `poetry.lock`. The fast-forward was blocked by a file whose local modification was real, unlanded work.

## 2. Decision

**To reach ADR 0229's state from a dirty shared checkout, the agent runs the sequence below. The dirty files leave the primary checkout only by copy; the primary is cleared only by a named-path stash; the one destructive command — the stash drop — is the operator's.**

```bash
# 0. Stage on sight. The blob is now in .git/objects and survives anything
#    that happens to the working file. (Universal rule, 2026-09-21.)
git add <each untracked work product>

# 1. Inventory, and derive the blocking set: dirty paths that an incoming
#    commit also touches. Record all of it before touching anything.
git status --porcelain
git rev-list --left-right --count main...origin/main
git stash list; git worktree list; git branch --list
git diff --name-only HEAD..origin/main          # incoming
#    intersect with the modified paths from --porcelain = the blocking set

# 2. Transport by copy. A worktree from origin/main; the primary is untouched.
git worktree add -b <issue>-<slug> ../<repo>-<issue> origin/main
cp -p <dirty path> ../<repo>-<issue>/<dirty path>   # for each path
cmp <dirty path> ../<repo>-<issue>/<dirty path>     # byte-identical, or stop
#    A path in the blocking set that is GENERATED (a lock file) is not copied:
#    regenerate it in the worktree from origin/main's version plus the
#    intended change (`poetry lock`, etc.) and say so in the PR body.

# 3. Land. One PR per concern, the universal merge sequence, and its Step 3
#    (origin/main moved) is the gate for everything after this line.

# 4. Parity in the primary. Named paths only. Never -u, never bare.
git branch --show-current                         # must print main (#1852);
                                                  # otherwise: git fetch origin main:main and stop here
git stash push -m "<date> inherited: <concern>" -- <path> <path> ...
git merge --ff-only origin/main

# 5. Enumerate the stash — every path it holds, not the ones you remember.
git stash show --name-only stash@{0}
git show --name-only --format="" stash@{0}^3 2>/dev/null   # non-empty only if -u was used: still list it
#    For each path:
git diff --stat stash@{0} HEAD -- <path>
#    empty       -> landed byte-identical
#    non-empty   -> must be explained by a named commit on main (the fix in
#                   PR #N; the lock regenerated in PR #N). Unexplained = STOP.
#    Post the table on the landing issue.

# 6. The drop is the operator's step. Hand over, with the table:
#        git stash drop stash@{0}
#    If the stash outlives the session, the handoff names it.

# 7. Teardown per the merge sequence's Step 4d/4e: move scratch out,
#    `poetry env remove --all` inside the worktree if poetry created an
#    in-project venv there (#944), `git worktree remove` (never --force),
#    `git fetch --prune`, `git branch -d` (ADR 0217 if it refuses).
```

Three properties hold throughout. **The agent never runs a command that discards uncommitted state.** Copy, stash-by-name and fast-forward are all preserving. **The stash is a safety net, not the transport.** The work reaches `main` through the worktree and a reviewed PR; the stash exists only so the fast-forward can happen, and only between steps 4 and 6. **Enumeration is a program.** Step 5 is a fixed list of commands whose output is posted, not a judgement that the stash "should be" redundant.

## 3. Alternatives considered

### A. Clear the tree with `git restore` / `git checkout --` / `git reset --hard` — Rejected, banned

Destroys the uncommitted work. The banned-list entry exists because this was done, more than once, under the equivalence rationalisation.

### B. `git stash push -u` (or `--include-untracked`) — Rejected, banned

Sweeps every untracked file in the tree into the stash, including other sessions' work, which is the operation `git clean -fd` is banned for. The 2026-08-14 incident recovered eight files from a dropped stash's third parent only because nothing had garbage-collected it yet.

### C. Commit the dirty tree in place on a `wip` branch, then switch to `main` — Rejected as a dead end

Durable — a commit survives more than a stash does — but the branch can never be deleted without force: it is not an ancestor of `main`, and once the landed versions differ from the snapshot (a fix applied, a lock regenerated) ADR 0217's equivalence gate correctly reports DIVERGENT, so the graft is unavailable and the branch lives in `graveyard/` forever. The sequence would end with a permanent artefact instead of one operator command.

### D. Overwrite each dirty file with `origin/main`'s content (`git show origin/main:<path> > <path>`), then fast-forward — Rejected

The same destroy as A with a different spelling. The working-tree content is gone the moment the redirect runs.

### E. Leave the primary dirty and behind — Rejected

Fails ADR 0229 on two criteria and hands the identical wall to the next session, which is what had been happening for six days in the observed case.

### F. Copy-transport, named-path stash, enumerated operator drop — Selected

Described above.

## 4. Rationale

The universal rules already contained every element: stage on sight, named-path stash as the alternative to `restore`, the enumeration-before-drop obligation, the operator's confirmation of the drop, and the merge sequence's worktree discipline. What was missing was the order and the statement that they compose into one procedure. Writing it down means an agent facing the wall can point at a decision rather than at a table cell, and a reviewer can check a session against a sequence rather than against a principle.

The drop stays with the operator for the reason ADR 0216 gives: the agent writes the script, the operator runs the step that cannot be undone. Here the agent produces the enumeration table — the evidence that makes the drop safe — and the operator spends the one command. A stash that the agent could drop on its own evidence is a stash it will eventually drop on insufficient evidence.

## 5. Security risk analysis

| Risk | Impact | Likelihood | Severity | Mitigation |
|------|--------|------------|----------|------------|
| The stash is forgotten and outlives the session | State sits in an unlisted place; the next session inherits a "Fully Landed" checkout that is not | Medium | 2 | Step 6: the handoff names it. ADR 0229 criterion 3 makes it visible to any audit |
| A stash made with `-u` by someone else is enumerated by tracked paths only | Untracked files in the third parent are dropped unseen | Low | 3 | Step 5 always runs the `^3` listing, whoever made the stash |
| A copied file conflicts with an incoming commit (generated files: lock files, built assets) | A hand-merged lock file that is wrong for every platform | High for lock files | 2 | Step 2: regenerate in the worktree from `origin/main`'s version; never merge a generated file by hand |
| `git merge --ff-only` moves a branch that is not `main` | Another session's branch is silently rebased (#1852) | Low | 3 | Step 4's `git branch --show-current` guard; `git fetch origin main:main` otherwise |
| `poetry` creates an in-project venv in the worktree and its file locks block `git worktree remove` | Teardown reaches for `--force`, which is banned (#944) | Medium | 2 | Step 7: `poetry env remove --all` inside the worktree first |
| `cmp` reads as a line-ending trap | A byte-identical copy reported as different | Very low | 1 | `cp -p` preserves bytes; git normalises on commit. The CRLF trap applies to git-content-vs-file comparisons, not file-vs-file |

**Residual risk:** minimal when the enumeration table is posted before the drop is handed over.

## 6. Consequences

### Positive

- A dirty shared checkout has a documented, non-destructive path to Fully Landed, and it ends with exactly one operator command.
- Inherited work is landed through a reviewed PR with its own issue, not silently absorbed or silently discarded.
- The procedure is checkable: every step is a listed command with a listed expected output.

### Negative

- More steps than any of the banned shortcuts; a worktree, a PR and a stash where `git restore` would have been one line.
- Fully Landed is not reached until the operator runs the drop, so an agent session cannot report the state as final on its own.

### Neutral

- The stash is short-lived by design; ADR 0229 criterion 3 is the check that it stayed short-lived.

## 7. Implementation

- **First application:** 2026-09-22, a private repo, five paths from a six-day-old session, landed as two PRs (one concern each), lock file regenerated in the worktree, primary cleared by named-path stash, enumeration table posted, drop handed to the operator. Tracked as #3437.
- **Universal `CLAUDE.md`:** the "Destroying uncommitted state" table's `git restore` row already names steps 4–6; this ADR is the procedure that row points at.

## 8. References

- ADR 0229 — The "Fully Landed" State
- ADR 0217 — Squash-merge orphan cleanup via `git replace --graft` (why alternative C dead-ends)
- ADR 0216 — In-process classic-PAT decryption (the agent-writes, operator-runs split)
- Universal `CLAUDE.md` — "Destroying uncommitted state — the principle, not just the table"; "Untracked Work Product Is `git add`ed On Sight"; "Merging PRs (Universal)" Steps 3, 4b, 4d, 4e
- [`git-stash(1)`](https://git-scm.com/docs/git-stash) — pathspec form; the third parent for `-u`
- [`git-merge(1)`](https://git-scm.com/docs/git-merge) — `--ff-only`; "would be overwritten by merge"

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-09-22 | Claude Fable 5.1 | Initial version, written during the first application. See #3437. |
