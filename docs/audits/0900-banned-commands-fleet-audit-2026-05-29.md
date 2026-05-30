# Fleet audit: banned commands across martymcenroe repos (2026-05-29)

**Status:** complete (subagent-driven, incremental writes; finished 2026-05-29)
**Trigger:** `dependabot_review.py::cleanup_worktree` was found to codify `git restore .` (universal CLAUDE.md banned 2026-05-29). Operator: "audit every tool across 64 repos to find out if that is coded into a tool or skill or command anywhere."
**Search scope:** all patterns in the universal CLAUDE.md banned table AND the principle-table operations.
**Method:** Hybrid — `gh search code` for origin-wide coverage, local `git grep` where clones exist for full context. Read-only — no modifications.
**Reporter:** subagent (general-purpose), brief delivered with explicit no-modification constraints.

## Patterns audited

From `C:\Users\mcwiz\Projects\CLAUDE.md` § "Banned commands (ALWAYS)" and § "Destroying uncommitted state — the principle":

| ID | Pattern | Source |
|----|---------|--------|
| B1 | `git push --force` | banned table |
| B2 | `git push --force-with-lease` | banned table |
| B3 | `git push -f` (short form) | banned table |
| B4 | `git clone git@` (SSH form) | banned table |
| B5 | `git reset --hard` | banned table |
| B6 | `git clean -fd`, `-fdx`, `-fdX`, `-f -d` | banned table |
| B7 | `git restore .` / `git restore <path>` (without `--staged` or `--source`) | banned table (added 2026-05-29) |
| B8 | `git checkout --` (older form of B7) | principle table |
| B9 | `git branch -D` | banned table |
| B10 | `git worktree remove --force` / `-f` | banned table |
| B11 | `--theirs` in `git rebase` / `git merge` context | banned table |
| B12 | `--no-verify` on commit/push | banned table |
| B13 | `--no-gpg-sign` on commit/push | banned table |
| B14 | `gh pr merge --admin` | banned table |
| B15 | `gh pr merge --auto` | banned table |
| B16 | `gh pr review --approve` (self-approval pattern) | banned table |

## Triage classes

Each finding is classified as one of:

- **CODE** — pattern appears in active script logic (Python `subprocess.run([...])`, shell `command`, workflow `run:` block, etc.). **Fix needed.**
- **DOC** — pattern appears in documentation as a warning/example/anti-pattern. **No fix needed**, may warrant cross-link.
- **COMMENT** — pattern appears in code comments referencing the banned command (often warnings). **No fix needed.**
- **TEST_FIXTURE** — pattern appears in test code intentionally exercising the failure path. **Review case-by-case.**
- **GENERATED** — pattern appears in auto-generated files (lockfiles, etc.). **No fix needed.**
- **FALSE_POSITIVE** — substring match that isn't the dangerous pattern. **No fix needed.**

## Findings (incremental)

<!-- The subagent appends rows here as it finds them. Format:
- **[ID] [CLASS]** `repo/path:line` — `<matched line excerpt, trimmed>` — note: <brief context>
-->

<!-- findings below -->

- **[B7] [CODE]** `AssemblyZero/tools/dependabot_review.py:543` — `run(["git", "-C", str(worktree), "restore", "."])` — note: cleanup_worktree's pre-worktree-remove "defensive" restore; codifies the banned pattern; finding that triggered this audit

- **[B16] [FALSE_POSITIVE]** `AssemblyZero/tools/dependabot_review.py:349` — `["gh", "pr", "review", str(pr_number), "--repo", repo, "--approve", ...]` — note: approves dependabot[bot]'s PR, not own; banned pattern is self-approval — this is the sanctioned path per CLAUDE.md "Cerberus-AZ auto-approves after pr-sentinel; let it" applies to user PRs, not dependabot PRs

- **[B1] [CODE]** `github-readme-stats/scripts/push-theme-readme.sh:15` — `git push --force --quiet --set-upstream origin-$BRANCH_NAME $BRANCH_NAME` — note: in FORK of upstream repo (anuraghazra/github-readme-stats); not operator-authored, but lives in martymcenroe's fork; CI script for theme-readme auto-update
- **[B12] [CODE]** `github-readme-stats/scripts/push-theme-readme.sh:13` — `git commit --no-verify --message "docs(theme): auto update theme readme"` — note: same upstream-fork file; `--no-verify` on commit

- **[B7] [CODE]** `AssemblyZero/tools/backfill_assemblyzero_flag.py:270` — `run(["git", "restore", "--staged", "--worktree", ".unleashed.json"], cwd=repo_path)` — note: `--staged --worktree` form discards BOTH index AND working-tree edits on the specific file; destructive of uncommitted work (matches the principle-table operation); used as rollback after a failed commit

- **[B1] [CODE]** `github-readme-stats/.github/workflows/deploy-prep.yml:20` — `push_options: "--force"` — note: git-auto-commit-action with --force push; in FORK (anuraghazra/github-readme-stats); guarded by `if: github.repository == 'anuraghazra/github-readme-stats'` so won't actually fire on the fork

- **[B9] [CODE]** `AssemblyZero/.claude/skills/cleanup.md:211` — `Action: \`git -C ... branch -D {branch-name}\`` — note: Phase 2 step "Auto-Delete Orphaned LOCAL Branches" — instructs Claude to use `branch -D` on orphan branches; ADR-0217 says use the four-step graft + `-d` recipe instead
- **[B9] [CODE]** `AssemblyZero/.claude/skills/cleanup.md:378` — `git -C /c/Users/mcwiz/Projects/{PROJECT_NAME} branch -D $BRANCH` — note: Phase 4 cleanup template instructs Claude to use `branch -D` after merge; should be `-d` per universal CLAUDE.md merge sequence
- **[B9] [CODE]** `AssemblyZero/.claude/templates/commands/cleanup.md.template:130` — `Auto-delete: \`git -C {{PROJECT_ROOT}} branch -D {branch-name}\`` — note: template version of same skill; renders into per-repo cleanup commands
- **[B9] [CODE]** `AssemblyZero/.claude/templates/commands/cleanup.md.template:218` — `git -C {{PROJECT_ROOT}} branch -D $BRANCH` — note: template post-merge cleanup; same as cleanup.md:378 above

- **[B9] [CODE]** `Clio/.claude/commands/cleanup.md:130` — `Auto-delete: \`git -C /c/Users/mcwiz/Projects/Clio branch -D {branch-name}\`` — note: rendered from AssemblyZero cleanup.md.template; same branch -D instruction
- **[B9] [CODE]** `maintenance/.claude/commands/cleanup.md:130` — `Auto-delete: \`git -C /c/Users/mcwiz/Projects/maintenance branch -D {branch-name}\`` — note: rendered from AssemblyZero cleanup.md.template; same branch -D instruction

- **[B14] [CODE]** `AssemblyZero/tools/merge_sentinel_permissions_prs.py:134` — `"--admin",` in `gh pr merge` args list — note: deprecated tool per universal CLAUDE.md ("v1 MUST NOT be used as a template"); flow is disable enforce_admins → `gh pr merge --admin` → re-enable enforce_admins; user-run via classic PAT auth swap; superseded by ADR-0216 in-process classic-PAT pattern

- **[B15] [DOC]** `Aletheia-598/docs/audits/10816-audit-dependabot-prs.md:118` — `gh pr merge $PR --repo martymcenroe/Aletheia --merge --auto` — note: runbook code block for "Phase 3: Batch Merge Attempt"; uses `--auto` flag which is no-op per universal CLAUDE.md (`allow_auto_merge: false` fleet-wide); Aletheia-598 is a worktree dir; older runbook style superseded by `/dependabot` skill

- **[B10] [CODE]** `AssemblyZero/tools/backup_universal_claude_md.py:104` — `_git("worktree", "remove", "--force", str(worktree), cwd=AZ_ROOT, check=False)` — note: "leftover from previous failed run" cleanup before creating new worktree; banned worktree remove --force
- **[B10] [CODE]** `AssemblyZero/tools/backup_universal_claude_md.py:165` — `_git("worktree", "remove", "--force", str(worktree), cwd=AZ_ROOT, check=False)` — note: finally-block worktree cleanup after PR creation; banned worktree remove --force

- **[B7] [DOC]** `AssemblyZero/ideas/backlog/inhumer-deletion-workflow.md:43,55,70` — proposes "If red, `git restore` everything"; "`git restore` rollback if tests fail after deletion"; "Rolls back via `git restore` if tests fail" — note: brief/proposal for future tool; not implemented yet but if implemented as written would codify B7; should be revised in brief to use `git stash` instead

- **[B10] [DOC]** `AssemblyZero/docs/audits/0834-audit-worktree-hygiene.md:135` — `git worktree remove --force /path/to/worktree` — note: runbook "Force Removal (CAUTION)" section instructs operator to use banned pattern after "confirming no valuable changes"; superseded by universal CLAUDE.md banned table
- **[B9] [DOC]** `AssemblyZero/docs/audits/0834-audit-worktree-hygiene.md:136` — `git branch -D branch-name` — note: same audit doc; immediate follow-on to the worktree force removal

- **[B10] [DOC]** `AssemblyZero/docs/lineage/active/94-lld/002-draft.md:376` — `Falls back to \`git worktree remove --force <path>\` if needed.` — note: LLD draft for Janitor workflow (Issue #94); proposes banned pattern as fallback in spec; not implemented yet
- **[B10] [DOC]** `AssemblyZero/docs/lineage/active/94-lld-n1/002-draft.md` — same fallback pattern in related LLD draft

- **[B9] [CODE-ON-STALE-BRANCH]** `Aletheia-598/tools/merge_pr.py:207` — `["git", "branch", "-D", branch_name]` — note: subprocess call with `-D` in branch deletion step of "atomic merge" tool; file was DELETED on Aletheia main via commit c216101 (PR #665, 2026-05-26, closes #664) — still present on stale branch `cleanup-2026-04-27-post-onboard` in this worktree; landing that branch would re-introduce the banned pattern
- **[B10] [CODE-ON-STALE-BRANCH]** `Aletheia-598/tools/merge_pr.py:192` — `["git", "worktree", "remove", worktree_path, "--force"]` — note: same as above; file was already deleted on Aletheia main; lingers on Aletheia-598 worktree branch

- **[B9] [DOC]** `Aletheia-598/docs/ENGINEERING-JOURNAL.md:14` — `use \`git branch -D\` for cleanup` (squash-merged work) — note: 2025-12-08 lesson that predates the banned-list addition; only on Aletheia-598 worktree branch (not Aletheia main); contradicts current ADR-0217 four-step graft + `-d` recipe

- **[B9] [DOC]** `martymcenroe/ENGINEERING-JOURNAL.md:14` — same `git branch -D` cleanup recommendation as Aletheia-598; profile readme repo

<!-- next-append-here -->

## Summary

**Status:** complete (subagent run finished 2026-05-29).

### Tallies by class

- **14 CODE** — patterns in active script/skill/workflow logic. Fix needed.
- **2 CODE-ON-STALE-BRANCH** — patterns in a tool that's already been deleted on main but still lives on an unmerged worktree branch (`Aletheia-598`, branch `cleanup-2026-04-27-post-onboard`). Either merge the deletion forward to that branch, or delete the branch.
- **8 DOC** — patterns appear in runbooks/lessons/specs as instructions or anti-patterns. Several propose banned commands as fallback in not-yet-implemented LLDs — flag those drafts before implementation lands.
- **1 FALSE_POSITIVE** — `gh pr review --approve` on dependabot[bot]'s PRs (sanctioned per `/dependabot` skill design — not self-approval).
- **Hundreds of suppressed instances** classified as: gate/check code (every repo's `.claude/hooks/bash-gate.sh`), test fixtures (`tests/unit/test_shell_security.py`, `tests/unit/test_cleanup_helpers.py`, lineage `*-test-scaffold.py`), runbook anti-pattern tables (`docs/canonical/universal-CLAUDE.md`, `docs/standards/0002-coding-standards.md`, `docs/standards/0003-agent-prohibited-actions.md`, `docs/runbooks/0935-pr-stuck-recovery.md`, etc.), permission deny-lists (`.claude/settings.local.json` `deny` blocks), and `gh label create --force` (gh CLI's overwrite flag — NOT git's destructive `--force`).

### Top repos by CODE-class finding count

1. **AssemblyZero** — 9 CODE findings (5 in `tools/`, 4 in `.claude/skills/cleanup.md` + `.claude/templates/`). The operator's own tooling repo has the most.
2. **github-readme-stats** (fork) — 3 CODE findings, all in upstream code that came with the fork (push-theme-readme.sh, deploy-prep.yml). Two scripts execute `--force` push + `--no-verify` commit; one workflow uses `git-auto-commit-action` with `push_options: "--force"`. The workflow is guarded by `if: github.repository == 'anuraghazra/...'` so it does NOT execute on the operator's fork. The shell scripts could fire if triggered.
3. **Clio, maintenance** — 1 CODE finding each, both in their rendered `.claude/commands/cleanup.md` (from AssemblyZero template).

### Top patterns by CODE-class finding count

1. **B9 (`git branch -D`)** — 7 CODE findings. Three sources: cleanup skill/template (4×), rendered commands in Clio/maintenance (2×), Aletheia-598 stale-branch merge_pr.py (1× CODE-ON-STALE-BRANCH).
2. **B10 (`git worktree remove --force`)** — 3 CODE findings (`backup_universal_claude_md.py` ×2, Aletheia-598 stale-branch merge_pr.py ×1 CODE-ON-STALE-BRANCH).
3. **B7 (`git restore .` / `git restore <path>`)** — 2 CODE findings (`dependabot_review.py`, `backfill_assemblyzero_flag.py`). B7 was added to the banned table 2026-05-29 (today); these pre-date the addition.
4. **B1 (`git push --force`)** — 2 CODE findings, both in github-readme-stats fork (upstream code).
5. **B14 (`gh pr merge --admin`)**, **B12 (`--no-verify`)** — 1 each.

### Notable surprises

- **AssemblyZero's own cleanup skill is the largest source of B9 findings** (4 CODE-class). The skill/template instructs Claude to use `git branch -D` for orphan-branch cleanup and post-merge cleanup. ADR-0217 documents the four-step `git replace --graft` + `-d` recipe as the correct path. This is internal contradiction: AssemblyZero authored both the banned-list and the skill that codifies the banned command. The two-line auto-delete instruction (cleanup.md:211 + template:130) is reachable on `/cleanup` invocations across every repo that has rendered the template.
- **The trigger finding (`dependabot_review.py:543`) was preceded by a known partial fix.** `Aletheia/docs/lessons-learned.md:19` documents discovery of `tools/merge_pr.py` calling banned commands — the same class of issue — on 2026-05-26 with a partial mitigation (delete the tool from Aletheia main via PR #665) but the lesson explicitly calls out "merge_pr.py predating the root ban list by months" and recommends "fleet-wide static audit (AssemblyZero #1311)" — which is what this audit is.
- **`backup_universal_claude_md.py`** (nightly backup of universal CLAUDE.md to S3) ITSELF uses `worktree remove --force` to clean up after each backup. The script that protects the canonical banned-commands list contains banned commands.
- **`merge_sentinel_permissions_prs.py`** is already flagged in universal CLAUDE.md as "v1 MUST NOT be used as a template for new tools" — but the file is still present in `tools/` and the `--admin` call is still active code. If anyone re-runs it (e.g., during another permissions sweep), the banned pattern executes.
- **Two not-yet-implemented LLDs propose banned patterns as fallbacks** — `inhumer-deletion-workflow.md` (proposes `git restore` as rollback step) and `94-lld/002-draft.md` (proposes `worktree remove --force` as fallback in the Janitor workflow). Both can be revised before implementation lands.
- **`Aletheia-598` worktree contains a stale branch** (`cleanup-2026-04-27-post-onboard`) with `tools/merge_pr.py` still on it. That file was DELETED on Aletheia main via PR #665. Whether to delete the worktree's branch or carry the deletion forward is the operator's call.
- **`martymcenroe/ENGINEERING-JOURNAL.md:14`** has stale text recommending `git branch -D`. The corresponding text on Aletheia main was updated; the profile-readme repo (`martymcenroe/martymcenroe`) and Aletheia-598 branch still have the old guidance.

### Recommendations for prioritization

Grouped for the operator's remediation pass. Order is not prescriptive.

**Group 1 — Internal tooling that runs without the user noticing (highest priority because these execute silently):**
- `AssemblyZero/tools/dependabot_review.py:543` (B7, trigger finding)
- `AssemblyZero/tools/backfill_assemblyzero_flag.py:270` (B7)
- `AssemblyZero/tools/backup_universal_claude_md.py:104,165` (B10, nightly scheduled task)

**Group 2 — Skills and templates that propagate the pattern to every repo (highest leverage):**
- `AssemblyZero/.claude/skills/cleanup.md:211,378` (B9)
- `AssemblyZero/.claude/templates/commands/cleanup.md.template:130,218` (B9)
- Re-render every per-repo `.claude/commands/cleanup.md` after the template fix (Clio, maintenance already known; full list will be every repo that ran the cleanup-template renderer).

**Group 3 — Deprecated tools that still execute banned patterns if re-run:**
- `AssemblyZero/tools/merge_sentinel_permissions_prs.py:134` (B14) — either delete (was deprecated in universal CLAUDE.md) or refactor to the ADR-0216 in-process classic-PAT pattern.

**Group 4 — Fork/upstream code (lowest agency, but worth a decision):**
- `github-readme-stats/scripts/push-theme-readme.sh:13,15` (B1, B12)
- `github-readme-stats/.github/workflows/deploy-prep.yml:20` (B1, guarded by upstream-repo check; effectively dormant on the fork)
- Decision: archive the fork, or remove the offending scripts on the fork's master branch.

**Group 5 — Stale-branch hygiene (low priority unless the operator plans to merge those branches):**
- `Aletheia-598/tools/merge_pr.py:192,207` — already deleted on Aletheia main; either merge that deletion forward to the worktree branch or delete the branch.
- `Aletheia-598/docs/ENGINEERING-JOURNAL.md:14` — same branch, same call.

**Group 6 — Documentation hygiene (lowest priority; informational):**
- `martymcenroe/ENGINEERING-JOURNAL.md:14` — update the journal text.
- `AssemblyZero/docs/audits/0834-audit-worktree-hygiene.md:135-136` — revise the "Force Removal (CAUTION)" section.
- `AssemblyZero/ideas/backlog/inhumer-deletion-workflow.md` — revise the brief to use `git stash` instead of `git restore`.
- `AssemblyZero/docs/lineage/active/94-lld/*-draft.md` — revise the LLD to not propose `worktree remove --force` as a fallback.
- `Aletheia-598/docs/audits/10816-audit-dependabot-prs.md:118` (Aletheia-598 worktree only; main already uses `/dependabot` skill instead).
