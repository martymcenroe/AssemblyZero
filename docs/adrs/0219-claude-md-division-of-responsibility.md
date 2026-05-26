# 0219 - Division of Responsibility Between Universal CLAUDE.md and Per-Repo CLAUDE.md

**Status:** Accepted
**Date:** 2026-05-25
**Supersedes:** none
**Related:** AZ#1258, AZ#1259 (scaffolder refactor implementing this), AZ#1263 (universal CLAUDE.md nightly backup), `patent-general/CLAUDE.md` (lean reference shape)

---

## Context

The scaffolded per-repo `CLAUDE.md` (emitted by `tools/new_repo_setup.py:create_claude_md`) duplicated content already in the universal `CLAUDE.md` (`C:\Users\mcwiz\Projects\CLAUDE.md`, auto-loaded for every project). When the universal `CLAUDE.md` changes (example: 2026-05-24's merge-sequence discussion about `unstable` vs `clean` polling), all per-repo copies become subtly stale. The drift compounds with every universal-CLAUDE.md edit.

Drift evidence: per-repo audit in the private fleet tracker (unleashed#656) showed multiple repos with stale boilerplate inherited from old scaffolder versions, false claims about what universal `CLAUDE.md` contains, and broken references to nonexistent infrastructure (orchestrator gate, wrong report-filename format).

This ADR sets the architectural rule that prevents the duplication.

## The auto-load mechanism (load-bearing)

Claude Code, on session start, walks the parent directory tree from the session's cwd and **auto-loads every `CLAUDE.md` it encounters**. For a session in `C:\Users\mcwiz\Projects\AssemblyZero\subdir\`:

- `C:\Users\mcwiz\Projects\CLAUDE.md` (universal — auto-loaded)
- `C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md` (AZ-specific — auto-loaded because session is under AZ)

For a session in `C:\Users\mcwiz\Projects\Clio\subdir\`:

- `C:\Users\mcwiz\Projects\CLAUDE.md` (universal — auto-loaded)
- `C:\Users\mcwiz\Projects\Clio\CLAUDE.md` (Clio's per-repo — auto-loaded)
- **NOT** `C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md` — Clio is a sibling, not a descendant. Most repos don't use AZ workflow, so this is correct behavior.

**Consequences for the per-repo CLAUDE.md design:**

1. The per-repo file must NOT contain "read the universal CLAUDE.md first" — universal is already in context the moment the session starts. Telling the agent to "read" it is noise that implies the agent has a choice.
2. The per-repo file must NOT reference AssemblyZero unless the repo actually uses AZ workflows. Many repos don't, and writing "read AssemblyZero core rules" into their CLAUDE.md is both wrong (AZ isn't auto-loaded for sibling repos) and over-coupling (presupposes AZ workflow).
3. The per-repo file is ADDITIVE ONLY — it adds project-specific context that the universal (and any auto-loaded parent CLAUDE.md) doesn't have.

## Decision

| Layer | Auto-loaded when | Owns |
|---|---|---|
| **Universal CLAUDE.md** (`C:\Users\mcwiz\Projects\CLAUDE.md`) | Always (every session under `Projects\`) | Fleet-wide rules that apply to every project regardless of language/type: banned commands; merge sequence; PR-issue-references; GitHub-CLI safety; `--admin` / `--no-verify` bans; gpg+classic-PAT pattern; closing-discipline; one-issue-per-concern; communication norms |
| **AssemblyZero/CLAUDE.md** | Sessions rooted under `AssemblyZero/` ONLY | AssemblyZero-canonical workflow scripts; LLD lifecycle gotchas; AZ-specific worktree + archival pattern |
| **Per-repo CLAUDE.md** (scaffolder-emitted) | Sessions in that repo only | ONLY content that's true for THIS repo and false-or-missing for others: project identifiers; project architecture; workflow OVERRIDES (Aletheia's custom `merge_pr.py`); project-specific gotchas; project-type-specific notes |

**Five load-bearing consequences:**

1. **Anti-duplication rule.** Per-repo `CLAUDE.md` must NOT restate the merge sequence, PR rules, branch-protection details, banned commands, or any other content owned by universal `CLAUDE.md`. The universal file is auto-loaded; restating it adds bytes without adding signal, and creates drift surface.

2. **No "read these first" instructions.** Per-repo `CLAUDE.md` must NOT tell the agent to read the universal `CLAUDE.md`, the AssemblyZero `CLAUDE.md`, or any other parent `CLAUDE.md`. Claude Code's directory traversal handles auto-loading. Per-repo content is additive only.

3. **AZ references only when applicable.** Per-repo `CLAUDE.md` must NOT mention AssemblyZero, AZ workflows, AZ runbooks, or AZ tools UNLESS the repo actually uses them. Many repos (browser extensions, publishing repos, simple static sites) do not use AZ workflows; their per-repo `CLAUDE.md` must not pretend otherwise. If a repo does use AZ tools, the per-repo `CLAUDE.md` can mention the specific tools used — but it should not point at AZ's `CLAUDE.md` as a "read this" target.

4. **Overrides require explicit language.** When a repo legitimately overrides a universal rule (Aletheia's *"NEVER use `gh pr merge` directly, use `tools/merge_pr.py`"*), the per-repo `CLAUDE.md` must say so explicitly with the word "override" or equivalent. Otherwise per-repo content is additive only.

5. **Project-type matters.** A Chrome extension repo (Clio, Aletheia), a PyPi-published package (boostgauge), and a Cloudflare Worker (sentinel) need different architecture sections. The scaffolder template needs a project-type branch (proposed in #1259) — not a one-size-fits-all template.

## Reference model

`patent-general/CLAUDE.md` (72 lines) is close to the lean reference shape, with one revision needed: its current "FIRST: Read AssemblyZero Core Rules" line is wrong per consequence #2 above and should be removed in the refactor.

Target structure for the scaffolded per-repo `CLAUDE.md`:

```markdown
# CLAUDE.md - {name} Project

You are a team member on the {name} project, not a tool.

## Project Identifiers

- **Repository:** `{github_user}/{name}`
- **Project Root (Windows):** `{project_path}`
- **Project Root (Unix):** `{projects_root_unix}/{name}`
- **Worktree Pattern:** `{name}-{{IssueID}}`

## Project-Specific Context

_TODO: Add tech stack, architecture, file map, project-type-specific notes,
and any workflow overrides specific to this project. The universal CLAUDE.md
(auto-loaded) covers all fleet-wide rules; this file only adds what is true
for THIS repo specifically._
```

No "FIRST: Read X" line. No AssemblyZero reference unless the repo opts in. ~15 lines of skeleton; project context grows it as the project takes shape.

## Consequences

**Positive:**
- Universal-CLAUDE.md updates propagate automatically (no per-repo refresh needed)
- Per-repo `CLAUDE.md` becomes scannable (~15-30 lines of project content instead of ~80 of mixed boilerplate)
- Per-repo audit becomes trivial — lint for "restates universal content" markers
- Project-type-specific guidance becomes possible without bloating the template
- Repos that don't use AZ workflow stop having misleading "read AZ rules" lines in their `CLAUDE.md`

**Negative:**
- Per-repo `CLAUDE.md` is no longer self-contained — readers must know about the universal-CLAUDE.md auto-load mechanism. Mitigated by the universal `CLAUDE.md` itself being well-organized.
- Legacy per-repo `CLAUDE.md` files become inconsistent with the new shape until refactored. Per-repo remediation is tracked in `unleashed#656`.

## Alternatives considered

- **Keep duplication for self-containment.** Rejected. The 2026-05-24 merge-sequence drift incident already shows the cost: per-repo files become subtly wrong on every universal edit.
- **Inline-include the universal at scaffold time (snapshot).** Rejected for the same reason.
- **Drop per-repo `CLAUDE.md` entirely; everything in universal.** Rejected. Project identifiers and architecture are inherently per-repo. Workflow overrides cannot live in universal without contaminating other repos.
- **Have per-repo `CLAUDE.md` point at AssemblyZero `CLAUDE.md` for shared workflow rules.** Rejected (this was the original v1 draft of this ADR; corrected based on operator feedback 2026-05-25). Most repos don't use AZ workflow. Telling them to read AZ's `CLAUDE.md` is wrong; auto-load only happens for AZ-rooted sessions anyway.

## Implementation

#1259 tracks the scaffolder refactor + lint tool. This ADR is doc-only; the refactor ships as a separate PR. A minimum-viable slice of the template change already shipped via #1266 (template-only, no project-type branching, no lint tool yet).

## Closes

Closes #1258
