# 0853 - Fleet Mutation-Flag Audit (--apply / --execute compliance)

**Auditor:** Claude Opus 4.7 (1M context), AssemblyZero session
**Date:** 2026-05-23
**Scope:** all `martymcenroe/*` repos under `C:\Users\mcwiz\Projects\` (58 GitHub repos + local-only meta dirs)
**Trigger:** AZ #1230 mandatory-to-close clause (fleet audit + per-tool issues for non-conformant tools)
**Issue:** [#1230](https://github.com/martymcenroe/AssemblyZero/issues/1230)

## Rule audited

Per `Projects/CLAUDE.md` § "Destructive Scripts — `--apply` and `--execute`" (codified 2026-05-23):

- **`--apply`** — canonical mutation flag for normal scripts. Default mode is dry-run.
- **`--execute`** — substituted for `--apply` IFF the script's source contains any command from the **Banned commands (ALWAYS)** table in `Projects/CLAUDE.md` § Safety.
- **Typed-confirmation gate** inside the `--execute` branch via `require_confirmation(operation, target)` (AZ #1231; implementation: `tools/_gate.py`).

## Methodology

Per the Clio session comment on AZ #1231 + lessons from the morning's first-attempt failure (Grep tool defaults skipped `.gitignore`'d paths, hiding `Hermes/data/migrate-email.py`):

1. **Enumerate the fleet.** `gh repo list martymcenroe --limit 200 --json name` → 58 GitHub repos. Locally there are also archived clones, wikis, and meta dirs.
2. **Identify candidate tools.** `gh search code --owner martymcenroe '"--apply"' --limit 100` and `'"--execute"' --limit 100` across all extensions. Local cross-check via `Grep` tool with explicit per-repo paths.
3. **Filter false positives.** Lineage docs, session captures, PTY logs, and docstring mentions that match the regex but are not real argparse declarations were excluded by inspecting context.
4. **Inspect each real tool** for:
   - Argparse flag name (`--apply` vs `--execute`)
   - Operational use of any banned command (subprocess.run / os.system / explicit shell invocation of `git push --force`, `git reset --hard`, `git branch -D`, `git clean -fd`, `git worktree remove --force`, `--theirs`, `--no-verify`, `--no-gpg-sign`, `gh pr merge --admin`, `gh pr review --approve` on own PR, `gh pr merge --auto`, `dd`, `mkfs`, `shred`, `format`)
5. **Decision matrix per tool:**

   | Flag in use | Banned command present operationally? | Verdict |
   |---|---|---|
   | `--apply` | No | **conformant** |
   | `--apply` | Yes | non-conformant: should rename to `--execute` and add gate |
   | `--execute` | Yes | conformant (verify gate added once `_gate.py` ships) |
   | `--execute` | No | non-conformant: should rename to `--apply` |

## Results (15 candidate tools across 5 repos)

### AssemblyZero/tools/ (7 tools, all `--apply`)

| Tool | Flag | Banned cmd? | Verdict |
|---|---|---|---|
| `backfill_assemblyzero_flag.py` | `--apply` (L329) | no | **conformant** |
| `backfill_canonical_labels.py` | `--apply` (L169) | no | **conformant** |
| `deploy_auto_reviewer_workflow.py` | `--apply` (L567) | no (docstring mentions `gh pr merge --admin` as a non-use) | **conformant** |
| `update-doc-refs.py` | `--apply` (L253) | no | **conformant** |
| `remediate_fleet_branch_protection.py` | `--apply` (L190) + `--confirm-yes` belt-and-braces | no | **conformant** |
| `remediate_patent_general_protection.py` | `--apply` (L153) | no | **conformant** (fixed today via #1228/PR #1229) |
| `verdict-analyzer.py` | `args.apply` subcommand pattern (L146) | no | **conformant** |

### Aletheia/tools/ (1 tool)

| Tool | Flag | Banned cmd? | Verdict |
|---|---|---|---|
| `admin_subscriptions.py` | `--apply` (L191), also has explicit `--dry-run` default=True (L189) | no | **conformant** |

### career/dashboard/scripts/ (2 TypeScript tools)

| Tool | Flag | Banned cmd? | Verdict |
|---|---|---|---|
| `purge-stale-alerts.ts` | `--apply` (L169 `args.has("--apply")`) | no | **conformant** |
| `triage-unknown-questions.ts` | `--apply` (L31 `process.argv.includes("--apply")`) | no | **conformant** |

### unleashed/ (4 tools)

| Tool | Flag | Banned cmd? | Verdict |
|---|---|---|---|
| `scripts/backfill_session_ts_utc.py` | `--apply` (L132) | no | **conformant** |
| `scripts/migrate_plans_to_per_project.py` | `--apply` (L480) | no | **conformant** |
| `src/fleet_branch_cleanup.py` | `--apply` (L332) | no (uses `git branch -d` lowercase per ADR-0217, not `-D`) | **conformant** |
| `src/lock_sweep.py` | `--apply` (L193) | no | **conformant** |

### Hermes (handed off to separate session)

| Tool | Flag | Status |
|---|---|---|
| `data/migrate-email.py` | `--execute` (L657) | **handed off via Hermes#476** — `data/` is `.gitignore`d, hid the file from the morning's first audit pass; needs per-repo session to verify operational banned-command status and either retrofit with gate (if banned) or rename to `--apply` (if not banned) |

## Summary

| Category | Count |
|---|---|
| **Conformant tools (use `--apply`, no banned command)** | 14 |
| **Non-conformant tools in AZ-audited fleet** | 0 |
| **Hand-off (separate repo session)** | 1 (Hermes#476) |
| **Per-tool issues filed** | 0 |

## Audit verdict

**The AZ-audited portion of the fleet (14 of 15 candidate tools across 4 repos) is fully conformant with the codified two-tier mutation-flag rule.** No per-tool issues filed.

The lone outstanding candidate (`Hermes/data/migrate-email.py`) was identified during the morning's investigation that triggered AZ #1228/#1230/#1231; ownership transferred to Hermes#476 per the one-session-per-repo discipline.

## Re-execution

To re-run this audit:

```bash
# Fleet enumeration
gh repo list martymcenroe --limit 200 --json name,visibility

# Code search (GitHub-indexed)
gh search code --owner martymcenroe '"--apply"' --limit 100
gh search code --owner martymcenroe '"--execute"' --limit 100

# Local filesystem (defeats gitignore + hidden-dir skips)
for repo in /c/Users/mcwiz/Projects/*/; do
    grep -rEn --include='*.py' --include='*.sh' --include='*.ts' --include='*.tsx' \
        --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.git \
        --exclude-dir=dist --exclude-dir=build --exclude-dir=.venv --exclude-dir=venv \
        --exclude-dir=site-packages \
        '"--execute"|"--apply"' "$repo" 2>/dev/null
done
```

The default `Grep` tool exclusions (`.gitignore`-respect, hidden-dir skip) MUST be defeated for fleet audits. The morning's first-attempt failure that produced AZ #1230 was caused by trusting default exclusions and missing `Hermes/data/migrate-email.py` (gitignored under `data/`).

## Audit Record

| Date | Auditor | Findings | Issues Filed |
|------|---------|----------|--------------|
| 2026-05-23 | Claude Opus 4.7 | 14 conformant, 0 non-conformant in AZ-audited fleet; 1 handed off (Hermes#476) | 0 (none needed in AZ-audited fleet) |
