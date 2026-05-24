# Runbook 0936 — gh CLI Aliases

**Purpose:** document the operator's `gh` CLI aliases — what they do, where they live, and how to add new ones. Resolves the recurring confusion between `gh` CLI aliases and shell aliases that share names.

## The two mechanisms (don't conflate)

GitHub CLI aliases live in `gh`'s own config. Invoked as `gh <name>`. Configured via `gh alias set`.

Shell aliases live in `~/.bash_profile`. Invoked as `<name>` directly. Configured via the shell `alias` builtin.

These are different mechanisms with different invocation patterns. A name like `gh-count` may exist as either or both. They don't conflict at the bash level (one is a shell command, one is a `gh` subcommand) but they can confuse the operator about which one is actually working.

| Mechanism | Invocation | Defined where | Inspected with |
|---|---|---|---|
| gh CLI alias | `gh <name>` | `gh alias set <name> '<cmd>'` (persists to `~/.config/gh/config.yml`) | `gh alias list` |
| Shell alias | `<name>` | `alias <name>='<cmd>'` in `~/.bash_profile` | `alias <name>` or `type <name>` |

## Current inventory

### gh CLI aliases (inspect with `gh alias list`)

| Alias | Invoked as | What it does | Implementation |
|---|---|---|---|
| `co` | `gh co <pr>` | `gh pr checkout` shortcut | built-in `gh` shortcut |
| `gh-count` | `gh gh-count` | Today's contribution breakdown (commits, issues, PRs, reviews, repos) | `automation-scripts/tools/gh_daily_contributions.py` |
| `gh-reviews` | `gh gh-reviews` | All-time review count + 12-month breakdown + projection to 1% graph spoke | `automation-scripts/tools/gh_review_projection.py` |

### Shell aliases (inspect with `alias` or `type`)

None for GitHub-specific workflows at present. (Two orphans in `dotfiles/common/.bash_profile` are tracked for cleanup in AZ#1245 — see the divergence trap below.)

## How to add a new gh CLI alias

For commands that wrap a Python tool (the common case):

```bash
gh alias set <name> '!cd ~/Projects/automation-scripts && poetry run python tools/<file>.py'
```

For commands that pipe `gh` output directly:

```bash
gh alias set <name> 'api "search/issues?q=..." --jq ".total_count"'
```

The leading `!` indicates a shell-out (any arbitrary command). Without `!`, the value is passed as `gh` subcommand arguments.

After setting, verify with:

```bash
gh alias list | grep <name>
gh <name>   # smoke-test that it runs end-to-end
```

Then update this runbook's inventory table.

## The divergence trap (lesson learned 2026-05-24)

`dotfiles/common/.bash_profile` contains two shell aliases (`gh-count`, `gh-issue-list`) that **never load**. The dotfiles auto-sync mechanism handles `dotfiles/home/.bash_profile` only (equal to the operator's local `~/.bash_profile`); nothing sources `common/`. Verify with `type gh-count` — returns `not found` in any login shell.

The operator had been thinking `gh-count` worked as a shell alias when in fact `gh-count` works as a `gh` CLI alias invoked as `gh gh-count`. Two near-namesake mechanisms with one working and one orphaned, both visible to a casual file-read of the dotfiles source.

**Rule:** before claiming a shell alias works, verify with `type <name>` in a fresh login shell. Before claiming a `gh` CLI alias works, verify with `gh alias list | grep <name>`. The two mechanisms are inspected differently. Reading the source file is not verification — only invocation in the right context is.

The orphaned aliases are tracked for cleanup in AZ#1245.

## Where each mechanism's config persists

| Mechanism | File | Sync behavior |
|---|---|---|
| gh CLI aliases | `~/.config/gh/config.yml` (key `aliases:`) | Per-machine; not synced anywhere by default |
| Shell aliases | `~/.bash_profile` | Auto-syncs to `dotfiles/home/.bash_profile` per SECTION 0 of `~/.bash_profile` |

`gh` CLI aliases are NOT in the dotfiles auto-sync. Document them in this runbook so they're recoverable on a fresh machine.

## References

- AZ#1244 — work that produced this runbook
- AZ#1245 — orphaned dotfiles aliases cleanup (follow-up)
- `automation-scripts/tools/gh_daily_contributions.py` — `gh-count` implementation
- `automation-scripts/tools/gh_review_projection.py` — `gh gh-reviews` implementation
- `~/.bash_profile` SECTION 0 — dotfiles auto-sync mechanism
