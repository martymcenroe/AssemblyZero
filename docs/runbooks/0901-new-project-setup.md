# 0901 - New Project Setup

**Category:** Runbook / Operational Procedure
**Version:** 2.7
**Last Updated:** 2026-05-26

---

## Purpose

Initialize a new project with the canonical AssemblyZero structure, enabling:
- Full directory scaffold (31 directories)
- GitHub repository creation and configuration
- Inherited CLAUDE.md rules from AssemblyZero
- Session logging and agent coordination

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Git installed | `git --version` |
| Poetry installed | `poetry --version` |
| AssemblyZero cloned | `ls /c/Users/mcwiz/Projects/AssemblyZero` |
| GitHub CLI | `gh auth status` |

> **Classic PAT required (in-process, no `gh auth` swap).** The setup script's privileged steps (workflow upload via Contents API, repo settings PATCH, branch protection PUT) use the in-process classic-PAT pattern from [ADR-0216](../adrs/0216-in-process-classic-pat-decryption.md). Prerequisites: `~/.secrets/classic-pat.gpg` must exist (one-time setup procedure in `tools/_pat_session.py`'s docstring) and `~/.gnupg/gpg-agent.conf` must have `default-cache-ttl 0` + `max-cache-ttl 0` (post-2026-04-30 hardening — see [standard 0017](../standards/0017-classic-pat-fleet-tooling-reference-architecture.md)). Pinentry will prompt for the gpg passphrase once when the script reaches the privileged section. The user must run the script personally; agents must NOT invoke it via their tool surfaces.

---

## Quick Start (Automated)

> **`--cerberus-pem` is required** for any invocation that creates a GitHub repo (#1206). Download the .pem first from https://github.com/settings/apps/cerberus-az > Private keys > Generate, then pass its path to the script. The only override is `--no-github` (local scaffold only). Full procedure in [0927](0927-new-repo-human-checklist.md#4-deploy-cerberus-secrets-if-needed).

### Create a New Private Repository

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new_repo.py MyNewProject --cerberus-pem /c/Users/mcwiz/Downloads/cerberus-az.NNN.private-key.pem
```

### Create a Public Repository

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new_repo.py MyNewProject --public --cerberus-pem /c/Users/mcwiz/Downloads/cerberus-az.NNN.private-key.pem
```

### Create Local Only (No GitHub)

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new_repo.py MyNewProject --no-github
```

### Audit Existing Project

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new_repo.py ExistingProject --audit
```

---

## What the Script Creates

### Directory Structure (31 directories)

```
MyNewProject/
├── .claude/
│   ├── commands/
│   ├── hooks/                  # secret-file-guard.sh (per-repo)
│   └── gemini-prompts/
├── .github/
│   ├── dependabot.yml          # version-update config (ecosystems by detection + github-actions)
│   └── workflows/              # auto-reviewer.yml + release.yml (if --lang python and not --no-pypi)
├── data/                       # Ephemeral data (git-ignored fleet-wide)
├── data-g/                     # Git-tracked source-of-truth data (see data-g/README.md)
├── docs/
│   ├── adrs/
│   ├── standards/
│   ├── templates/
│   ├── lld/active/
│   ├── lld/done/
│   ├── reports/active/
│   ├── reports/done/
│   ├── runbooks/
│   ├── session-logs/
│   ├── audit-results/
│   ├── media/
│   ├── legal/                  # ToS, privacy policy
│   └── design/                 # UI mockups, style guides
├── src/
│   └── <module>/               # PyPI scaffold (if --lang python and not --no-pypi)
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── smoke/                  # Quick sanity tests
│   ├── contract/
│   ├── visual/
│   ├── benchmark/
│   ├── security/
│   ├── accessibility/
│   ├── compliance/
│   ├── fixtures/
│   └── harness/
└── tools/
```

### Files Created

| File | Purpose |
|------|---------|
| `.claude/project.json` | Project variables for AssemblyZero |
| `.claude/settings.json` | Hook configuration — wires the `secret-file-guard.sh` PreToolUse hook |
| `.claude/hooks/secret-file-guard.sh` | Blocks file tools (Read/Write/Edit/Grep/NotebookEdit) on `.env`, `.dev.vars`, credentials. Copied from AZ's canonical hook |
| `CLAUDE.md` | Claude agent instructions |
| `GEMINI.md` | Gemini agent instructions |
| `README.md` | Project overview |
| `LICENSE` | PolyForm Noncommercial 1.0.0 (default; pass `--license mit` for MIT) |
| `.gitignore` | Standard ignore patterns |
| `.unleashed.json` | Unleashed wrapper configuration (model, effort, onboard settings) |
| `.github/workflows/auto-reviewer.yml` | Cerberus auto-approval caller workflow |
| `.github/workflows/release.yml` | Tag-triggered PyPI publish via OIDC Trusted Publisher (created when `--lang python` and not `--no-pypi`; needs runbook 0934 pending-publisher registration before first tag push) |
| `.github/dependabot.yml` | Dependabot version-update config; ecosystems detected from project markers (`pyproject.toml`→pip, `package.json`→npm, `Dockerfile`→docker) plus `github-actions` always (#1334) |
| `data-g/README.md` | Git-tracked source-of-truth data directory; counterpart to the fleet-ignored `data/` (#1563) |
| `docs/00003-file-inventory.md` | Project file inventory |
| `pyproject.toml` | Poetry project manifest with dev deps (`pytest`, `pytest-cov`) and `[tool.pytest.ini_options]`. Created when `--lang python` (default). Skip with `--lang none` for non-Python projects. |
| `poetry.lock` | Pinned versions of all transitive deps. Generated by `poetry add` during creation. |
| `tests/conftest.py` | Bootstrap that adds `src/` to `sys.path` so test files can import the project package without a full Poetry install. |
| `src/<module>/__init__.py` | PyPI package scaffold (created when `--lang python` and not `--no-pypi`; `<module>` is `name.lower().replace("-", "_")`) |
| `src/<module>/__main__.py` | PyPI package entry point — `pip install <pkg> && <pkg>` runs `main()` from here |

### GitHub Actions

- Creates repository (private by default, or public with `--public`)
- Pushes initial commit
- Stars the repository

---

## Command Reference

```
usage: new_repo.py [-h] [--public] [--audit] [--no-github]
                         [--license {polyform,mit}] --cerberus-pem PATH
                         [--lang {python,none}] [--no-pypi]
                         name

positional arguments:
  name             Repository name

options:
  --public         Create public repository (default: private)
  --audit          Audit existing structure, don't create
  --no-github      Skip GitHub repository creation (local only). Implies no --cerberus-pem requirement.
  --license {polyform,mit}  License type (default: polyform)
  --cerberus-pem PATH       REQUIRED for GitHub-creating invocations (#1206). Cerberus App
                            .pem path; deploys per-repo Actions secrets. Script exits 1
                            with .pem-acquisition guide if missing.
  --lang {python,none}      Language bootstrap (default: python — Poetry init + pytest +
                            PyPI scaffold via #1074)
  --no-pypi                 Opt-out of PyPI publishing scaffold. Suppresses release.yml
                            and the src/<module>/__init__.py + __main__.py entry-point
                            files. Use for repos that won't ever publish to PyPI. (#1074)
```

---

## Post-Setup Steps

### 1. Cerberus Secrets (Automated via `--cerberus-pem`)

Cerberus secrets are deployed automatically by the script when you pass the required `--cerberus-pem PATH` flag (per #1206). The flag is mandatory for GitHub-creating invocations — the script exits 1 with a .pem-acquisition guide if you forget it. The only human steps are the browser-only ones: downloading the .pem before the script run, and revoking the key in the App UI after. See [0927 §4](0927-new-repo-human-checklist.md#4-deploy-cerberus-secrets-if-needed) for the full procedure.

The script also deploys `auto-reviewer.yml`, configures branch protection, and verifies all of the above end-to-end against origin (per #1200 + #1202). The `pr-sentinel/issue-reference` check is provided fleet-wide by the Cloudflare Worker (per #938 / #939), not by a per-repo workflow file.

### 1a. PyPI Pending-Publisher Registration (If `release.yml` Shipped)

When `--lang python` (default) and not `--no-pypi`, the script ships `.github/workflows/release.yml` for tag-triggered PyPI publish via OIDC Trusted Publisher. The first `git push origin v0.1.0` will fail at the publish step unless you complete the one-time browser registration first. The script surfaces a reminder in its final output (per #1201); the full procedure is in [runbook 0934](0934-pypi-trusted-publisher-setup.md). Opt out of this entirely with `--no-pypi` if the repo will not publish.

### 2. Add Advanced Hooks (Optional)

The script creates a minimal `settings.json` without hooks. For worktree protection and security linting:

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-generate.py --project MyNewProject
```

### 3. Set Up Encrypted Ideas Folder (Optional)

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-generate.py --project MyNewProject --ideas
```

### 4. Customize CLAUDE.md

Edit `MyNewProject/CLAUDE.md` to add project-specific:
- Workflow rules
- Documentation structure
- Forbidden commands
- Integration details

### 5. Create First Issue

```bash
gh issue create --repo your-username/MyNewProject --title "Initial setup" --body "Project scaffolded with AssemblyZero"
```

---

## Verification

### Check Structure

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new_repo.py MyNewProject --audit
```

Expected output:
```
Auditing structure for: C:\Users\mcwiz\Projects\MyNewProject
============================================================

[PASS] All required directories and files present
```

### Check GitHub

```bash
gh repo view your-username/MyNewProject
```

---

## Troubleshooting

### "Directory already exists"

The script won't overwrite existing projects. Use `--audit` to check an existing project:

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new_repo.py ExistingProject --audit
```

### "Could not get GitHub username"

Authenticate with GitHub CLI:

```bash
gh auth login
```

### Audit Shows Missing Items

Create missing directories with `.gitkeep`:

```bash
mkdir -p /c/Users/mcwiz/Projects/MyProject/docs/legal
touch /c/Users/mcwiz/Projects/MyProject/docs/legal/.gitkeep
```

Or check if the item is allowed to be missing in `docs/standards/0011-audit-decisions.md`.

---

## Manual Setup (Alternative)

If you need fine-grained control, see the manual process:

1. Create directory and `git init`
2. Create `.claude/project.json` with variables
3. Run `assemblyzero-generate.py` for configs
4. Create CLAUDE.md, GEMINI.md, README.md
5. Create directory structure manually
6. `git add . && git commit`
7. `gh repo create`

The script automates all of this in one command.

---

## Related Documents

- [0009-canonical-project-structure.md](../standards/0009-canonical-project-structure.md) - Directory structure standard
- [0011-audit-decisions.md](../standards/0011-audit-decisions.md) - Audit exceptions
- [AssemblyZero CLAUDE.md](../../CLAUDE.md) - Core rules inherited by all projects

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-13 | Initial version (manual process) |
| 2.0 | 2026-01-29 | Automated with new_repo.py, added 4 new dirs |
| 2.1 | 2026-04-05 | Added `.unleashed.json` to file table (was in script/schema but missing from docs) |
| 2.2 | 2026-04-05 | Added workflow files to file table. Updated post-setup: branch protection is now automated, Cerberus is the remaining human step. |
| 2.3 | 2026-05-22 | `--cerberus-pem` is now **required** for GitHub-creating invocations (#1206). Quick Start examples updated to include the flag. Post-setup verification extended with GitHub-side checks (#1200) and `pr-sentinel-mm` Worker installation detection (#1202). |
| 2.4 | 2026-05-22 | Fixed `Files Created` table — `LICENSE` row was documented as MIT but the script defaults to PolyForm Noncommercial 1.0.0 (#1198). |
| 2.5 | 2026-05-23 | Multi-section sweep (#1210): `.claude/settings.json` row corrected (not empty — wires the hook); added rows for `.github/workflows/release.yml`, `.claude/hooks/secret-file-guard.sh`, `src/<module>/__init__.py`, `src/<module>/__main__.py`; Directory Structure tree includes `.github/workflows/` and `src/<module>/`; Command Reference adds `--no-pypi` flag and notes `--cerberus-pem` is required; Post-Setup Steps Section 1 rewritten — Cerberus is now automated, not a manual remaining step; added Section 1a for PyPI pending-publisher registration. |
| 2.6 | 2026-05-26 | #1331 — Dependabot now enabled automatically at repo settings level (step 20 in the script). Without this step, the scaffolded `.github/dependabot.yml` was inert on private repos (defect confirmed on `dependabot-honeypot`). Companion tool `tools/enable_dependabot.py` backfills existing repos. See runbook 0927 v6.7 history entry for the under-the-hood table change. |
| 2.7 | 2026-06-10 | #1334 + #1563 — script now generates `.github/dependabot.yml` at creation time (step 11c2; ecosystems detected by marker-file presence plus `github-actions` always; rides the initial commit) so #1331's enablement actually emits version-update PRs, and creates `data-g/` (git-tracked source-of-truth data) alongside the fleet-ignored `data/`. Added file-table rows and directory-tree entries for both. |
