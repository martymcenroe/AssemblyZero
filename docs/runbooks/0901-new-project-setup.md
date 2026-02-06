# 0901 - New Project Setup

**Category:** Runbook / Operational Procedure
**Version:** 2.0
**Last Updated:** 2026-01-29

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

---

## Quick Start (Automated)

### Create a New Private Repository

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new-repo-setup.py MyNewProject
```

### Create a Public Repository

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new-repo-setup.py MyNewProject --public
```

### Create Local Only (No GitHub)

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new-repo-setup.py MyNewProject --no-github
```

### Audit Existing Project

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new-repo-setup.py ExistingProject --audit
```

---

## What the Script Creates

### Directory Structure (31 directories)

```
MyNewProject/
├── .claude/
│   ├── commands/
│   ├── hooks/
│   └── gemini-prompts/
├── data/                       # App data, examples, templates
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
| `.claude/settings.json` | Hook configuration (empty by default) |
| `CLAUDE.md` | Claude agent instructions |
| `GEMINI.md` | Gemini agent instructions |
| `README.md` | Project overview |
| `LICENSE` | MIT License |
| `.gitignore` | Standard ignore patterns |
| `docs/00003-file-inventory.md` | Project file inventory |

### GitHub Actions

- Creates repository (private by default, or public with `--public`)
- Pushes initial commit
- Stars the repository

---

## Command Reference

```
usage: new-repo-setup.py [-h] [--public] [--audit] [--no-github] name

positional arguments:
  name         Repository name

options:
  --public     Create public repository (default: private)
  --audit      Audit existing structure, don't create
  --no-github  Skip GitHub repository creation (local only)
```

---

## Post-Setup Steps

### 1. Add Advanced Hooks (Optional)

The script creates a minimal `settings.json` without hooks. For worktree protection and security linting:

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-generate.py --project MyNewProject
```

### 2. Set Up Encrypted Ideas Folder (Optional)

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-generate.py --project MyNewProject --ideas
```

### 3. Customize CLAUDE.md

Edit `MyNewProject/CLAUDE.md` to add project-specific:
- Workflow rules
- Documentation structure
- Forbidden commands
- Integration details

### 4. Create First Issue

```bash
gh issue create --repo your-username/MyNewProject --title "Initial setup" --body "Project scaffolded with AssemblyZero"
```

---

## Verification

### Check Structure

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new-repo-setup.py MyNewProject --audit
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
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/new-repo-setup.py ExistingProject --audit
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
| 2.0 | 2026-01-29 | Automated with new-repo-setup.py, added 4 new dirs |
