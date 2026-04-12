# ADR-0215: Claude Hook Canonical Locations

**Status:** Accepted
**Date:** 2026-04-12
**Categories:** Process, Tooling

## 1. Context

Claude Code hooks configured in `~/.claude/settings.json` currently reference scripts living in three different locations with no single canonical source:

- **User-local** — `~/.claude/hooks/*.sh` — 6 scripts, not under version control, edited in place
- **AssemblyZero** — `AssemblyZero/.claude/hooks/*.sh` — 5 scripts, versioned in this repo, some overlap with user-local
- **dotfiles** — `dotfiles/.claude/hooks/*.sh` — 2 scripts, versioned in the dotfiles repo, references a `dotfiles/.claude/settings.json` that has diverged from the live `~/.claude/settings.json`

Adding a new hook (the `post-plan-write.sh` shipped in this PR for the plan-archiver work on unleashed #275/#276) forced the question: where does this one live, and where should all hooks live long term?

## 2. Inventory of current hooks

Hooks referenced by the live `~/.claude/settings.json` as of 2026-04-12:

| Hook | Path | Matcher | Canonical source today |
|------|------|---------|-----------------------|
| `secret-guard.sh` | `~/.claude/hooks/` | PreToolUse / Bash | user-local (also copy in dotfiles) |
| `bash-gate.sh` | `~/.claude/hooks/` | PreToolUse / Bash | user-local (also copy in dotfiles) |
| `pre-commit-report-check.sh` | `~/.claude/hooks/` | PreToolUse / Bash | user-local only |
| `pre-edit-check.sh` | `~/.claude/hooks/` | PreToolUse / Edit\|Write | user-local only |
| `pre-edit-security-warn.sh` | `~/.claude/hooks/` | PreToolUse / Edit\|Write | user-local only |
| `secret-file-guard.sh` | `AssemblyZero/.claude/hooks/` | PreToolUse / Edit\|Write | AZ (this repo) |
| `post-edit-lint.sh` | `~/.claude/hooks/` | PostToolUse / Edit\|Write | user-local only |
| `post-plan-write.sh` (NEW) | `AssemblyZero/.claude/hooks/` | PostToolUse / Edit\|Write | AZ (this repo) |

Additional scripts present in each directory but NOT referenced by any hook in `~/.claude/settings.json`:

- `AssemblyZero/.claude/hooks/post_output_cascade_check.py`
- `AssemblyZero/.claude/hooks/post-commit`
- `AssemblyZero/.claude/hooks/bash-gate.sh` (duplicate of user-local — history unclear)
- `AssemblyZero/.claude/hooks/secret-guard.sh` (duplicate of user-local — history unclear)
- `dotfiles/.claude/hooks/bash-gate.sh`
- `dotfiles/.claude/hooks/secret-guard.sh`

## 3. Decision

**New rule for all future hooks:** canonical source is `AssemblyZero/.claude/hooks/`. `~/.claude/settings.json` references them via absolute path (`/c/Users/mcwiz/Projects/AssemblyZero/.claude/hooks/{name}.sh`).

**Why AssemblyZero and not dotfiles or unleashed:**

- **dotfiles** — the live `~/.claude/settings.json` has diverged significantly (~105 lines vs 24 in dotfiles). Sync is broken. Using dotfiles as canonical would require fixing the sync first, and the user memory "Never push to dotfiles repo directly — edit `~/.bash_profile`, auto-sync handles the rest" only covers bash_profile, not `.claude`. Out of scope.
- **unleashed** — unleashed is a Python wrapper product, not a dotfiles/config home. Adding a top-level `hooks/` dir there mixes concerns.
- **AssemblyZero** — already hosts `.claude/commands/` as canonical source for user skills (synced by `unleashed/src/skill_sync.py` to `~/.claude/commands/`), already has a `.claude/hooks/` dir with one production hook (`secret-file-guard.sh`) referenced by the live settings. AZ is the existing pattern.

**Rule:** the new `post-plan-write.sh` lives in AZ. The existing user-local hooks are NOT migrated in this ADR — that's a follow-up chore — but new hooks MUST go to AZ unless there's a written exception.

**No sync script for hooks (yet).** Unlike `.claude/commands/` (synced by `skill_sync.py` because `~/.claude/commands/` is the path Claude Code reads skills from), `.claude/hooks/` files are referenced by absolute path from `~/.claude/settings.json`. They do NOT need to be copied anywhere — Claude Code invokes them directly via the path in the settings file. This means no sync fragility: if AZ is on disk, the hook works; if AZ is moved, the hook path breaks the same way `secret-file-guard.sh` would.

## 4. Settings.json source of truth

Separately: the live `~/.claude/settings.json` is the working copy. The `dotfiles/.claude/settings.json` has drifted. The decision here is **NOT** to back-port the live settings into dotfiles in this PR (see unleashed #275 open question "edit both and reconcile later"). A future ADR / chore will reconcile them. For now: edit `~/.claude/settings.json` directly when adding hooks, and accept that dotfiles is a stale copy.

## 5. Follow-up (not in this PR)

1. Move the 6 user-local `~/.claude/hooks/*.sh` scripts into `AssemblyZero/.claude/hooks/` and update `~/.claude/settings.json` paths. One PR, pure move, verify each hook still fires.
2. Delete the unused duplicates in `AssemblyZero/.claude/hooks/` (`bash-gate.sh`, `secret-guard.sh`) or promote them to canonical and point settings at them.
3. Reconcile `dotfiles/.claude/settings.json` with the live file, or remove the stale copy from dotfiles.
4. Decide whether `.claude/hooks/post_output_cascade_check.py` and `.claude/hooks/post-commit` should be wired up or deleted.

## 6. Consequences

**Good:**

- One canonical home for new hooks — no per-case relocation debate.
- AZ is already trusted as a canonical source for `.claude/commands/`; reusing it for hooks is consistent.
- No new sync tooling. The absolute-path model keeps hooks simple.

**Bad:**

- Absolute paths tie the hook config to the specific filesystem layout. Moving `~/Projects/AssemblyZero` breaks every hook that references it. This risk is pre-existing (the `secret-file-guard.sh` reference has the same exposure).
- Existing user-local hooks are left in place, so the state is "new hooks in AZ, old hooks in `~/`" until the follow-up migration runs. Mixed state is confusing.
- The sync problem with `dotfiles/.claude/settings.json` is acknowledged but not fixed here.
