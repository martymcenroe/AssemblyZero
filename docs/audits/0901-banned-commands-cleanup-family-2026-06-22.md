# 0901 — Banned-command landmines: the cleanup family (and the landmine taxonomy)

- **Date:** 2026-06-22
- **Status:** Active — fixes for the cleanup family land with this audit; cross-repo and deprecated-tool items remain tracked.
- **Complements:** `docs/audits/0900-banned-commands-fleet-audit-2026-05-29.md` (the fleet-wide sweep). 0900 catalogues *where* banned commands appear across the fleet at a high level; this doc drills into the **cleanup skill/template/helper family**, names the **landmine taxonomy** (so future sweeps classify consistently), and records the `-D` findings surfaced 2026-06-22.
- **Canonical ban list:** the root `Projects/CLAUDE.md` "Banned commands (ALWAYS)" table. **Canonical safe recipe for squash-merge orphans:** `docs/adrs/0217-squash-merge-orphan-graft-cleanup.md`.
- **Related issues:** #1381, #1382, #1385, #1637, #1647 (closed dup of #1381).

## Why this exists

A *banned-command landmine* is any place in source that **emits, instructs, advertises, or retains** a banned command, even when the live code path happens to be safe. The ban list is a wall (CLAUDE.md "Reading the Banned List"); a landmine is a foothold over it — a future edit, a rendered copy, or a "make the code match the docstring" cleanup that quietly reintroduces the banned form. The danger is rarely the current execution; it is the *next* one.

The cleanup tooling is the single largest source of `git branch -D` (the most-recurred banned command) because it both **describes** branch cleanup (skill + template, in prose and bash) and **renders** into per-repo commands across the fleet. A single `-D` in the template propagates to every repo that renders it.

## Landmine taxonomy

Classify every banned-command hit as one of these — only the first two are immediate-execution risks, but all four are landmines:

| Class | What it is | Example (today) | Why it's a landmine |
|---|---|---|---|
| **EMITTER** | Source that *runs* the banned command | `cleanup.md.template` bash block ran `git branch -D $BRANCH` | Executes the ban on render/run |
| **INSTRUCTOR** | Prose/markdown telling the agent to use it | `cleanup.md.template` Phase 2 "Auto-delete: `git branch -D {branch}`" | The agent obeys instructions; an instructed ban is an executed ban |
| **DOCSTRING TRAP** | Docstring/comment advertises the banned form while code is safe | `cleanup_helpers.delete_local_branch` docstring said "using `-D` (force)"; code used `-d` | Invites a "make the code match the docs" regression that reintroduces `-D` |
| **DEPRECATED-BUT-LIVE** | A deprecated tool still *contains and can run* the banned flag | `merge_sentinel_permissions_prs.py` `--admin` merge | "Deprecated" ≠ removed; it remains a break-glass that an agent could invoke |

**Distinguish landmines from non-landmines:** a banned token inside a GUARD (a hook/lint that *blocks* the command, e.g. `.claude/hooks/bash-gate.sh`, `tools/github_protection_audit.py`) or a DOC that *prohibits* it (this file, ADR-0217, the CLAUDE.md table) is correct and must NOT be "fixed." The audit's job is to separate the wall from the footholds.

## The cleanup family — the skill/template contradiction

The canonical `/cleanup` **skill** (`.claude/skills/cleanup.md`) is **correct**: it explicitly says *"Do NOT use `git branch -D`"* and mandates the ADR-0217 four-step graft + `branch -d`. The **template** (`.claude/templates/commands/cleanup.md.template`), which seeds the per-repo `.claude/commands/cleanup.md` rendered copies, **contradicted** it — emitting `-D` in two places. The helper's **docstring** advertised `-D` while its code was safe. Three artifacts, two of them wrong, describing the same operation.

| Component | Before (2026-06-22) | After / correct behavior | Status |
|---|---|---|---|
| `.claude/skills/cleanup.md` | Correctly bans `-D`, mandates ADR-0217 graft | (unchanged — already correct) | OK |
| `.claude/templates/commands/cleanup.md.template:132` (Phase 2 orphan auto-delete) | INSTRUCTOR: "Auto-delete: `git branch -D {branch}`" | ADR-0217 graft + `branch -d`; graveyard if no squash commit | **FIXED (this audit)** |
| `.claude/templates/commands/cleanup.md.template:~242` (Phase 4 post-merge) | EMITTER: `git branch -D $BRANCH` | ADR-0217 graft recipe (`replace --graft` → `branch -d` → `replace -d`) | **FIXED (this audit)** |
| `assemblyzero/workflows/testing/nodes/cleanup_helpers.py:164` | DOCSTRING TRAP: docstring "using `-D` (force)"; code uses `-d` | Docstring describes `-d` (refuses unmerged); points to ADR-0217 for orphans | **FIXED (this audit, #1637)** |

## The propagation path (why the template matters most)

```
.claude/templates/commands/cleanup.md.template   ← source of truth for per-repo cleanup
            │  (rendered at repo scaffold / sync time)
            ▼
<repo>/.claude/commands/cleanup.md               ← one rendered copy PER REPO (Clio, maintenance, …)
```

Fixing the template stops *new* propagation. The **already-rendered** per-repo copies in other repos still carry `-D` until re-rendered — that is cross-repo work and remains tracked under **#1381** (this AZ-side fix does not touch other repos).

## Remediation status (2026-06-22)

| Item | Issue | Class | Disposition |
|---|---|---|---|
| Template `-D` ×2 | #1381 / #1647 (dup, closed) | EMITTER + INSTRUCTOR | **Fixed in AZ template**; rendered per-repo copies remain under #1381 |
| Helper docstring trap | #1637 | DOCSTRING TRAP | **Fixed + closed** |
| `merge_sentinel_permissions_prs.py --admin` | #1382 / #961 | DEPRECATED-BUT-LIVE | Migrating to in-process classic-PAT (ADR-0216) under #961; removes the `--admin` path |
| `ENGINEERING-JOURNAL.md` stale `-D` guidance | #1385 | DOC (stale, other repo) | Cross-repo (martymcenroe profile repo); tracked in #1385 |

## How to sweep for this class (repeatable)

```bash
# Candidate hits across agent-facing source:
grep -rnE 'branch -D|push .*--force|--force-with-lease|reset --hard|clean -fd|--theirs|worktree remove --force|--admin|--no-verify|--no-gpg-sign' \
  tools/ .claude/skills/ .claude/templates/ assemblyzero/ scripts/
# For each hit, classify: EMITTER / INSTRUCTOR / DOCSTRING-TRAP / DEPRECATED-BUT-LIVE  vs  GUARD / DOC.
# Only the first four are landmines to fix; GUARD/DOC are the wall — leave them.
```

The presence of a banned token is not the finding; the *class* is. A grep that doesn't classify will "fix" the guards and the docs and leave the emitters — exactly backwards.
