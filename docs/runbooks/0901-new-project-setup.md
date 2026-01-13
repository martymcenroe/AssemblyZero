# 0901 - New Project Setup

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-01-13

---

## Purpose

Initialize a new project to use AgentOS infrastructure, enabling:
- Inherited CLAUDE.md rules from AgentOS
- Generated configs from templates (hooks, settings)
- User-level skills (`/cleanup`, `/onboard`, `/friction`, etc.)
- Session logging and permission management

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Git installed | `git --version` |
| Poetry installed | `poetry --version` |
| AgentOS cloned | `ls /c/Users/mcwiz/Projects/AgentOS` |
| GitHub CLI (optional) | `gh --version` |

---

## Procedure

### Step 1: Create Project Directory

```bash
mkdir /c/Users/mcwiz/Projects/YourProject
cd /c/Users/mcwiz/Projects/YourProject
git init
```

### Step 2: Create `.claude` Directory Structure

```bash
mkdir -p .claude
```

### Step 3: Create `project.json`

Create `.claude/project.json` with your project's values:

```json
{
  "variables": {
    "PROJECT_ROOT": "/c/Users/mcwiz/Projects/YourProject",
    "PROJECT_NAME": "YourProject",
    "GITHUB_REPO": "your-username/YourProject",
    "TOOLS_DIR": "/c/Users/mcwiz/Projects/YourProject/tools",
    "WORKTREE_PATTERN": "YourProject-{ID}"
  },
  "inherit_from": "C:\\Users\\mcwiz\\Projects\\AgentOS"
}
```

**Variable Reference:**

| Variable | Purpose | Example |
|----------|---------|---------|
| `PROJECT_ROOT` | Unix-style path for Bash commands | `/c/Users/mcwiz/Projects/YourProject` |
| `PROJECT_NAME` | Human-readable name, worktree patterns | `YourProject` |
| `GITHUB_REPO` | For `gh --repo` commands | `owner/repo` |
| `TOOLS_DIR` | Path to project's tools directory | `/c/Users/mcwiz/Projects/YourProject/tools` |
| `WORKTREE_PATTERN` | Worktree naming convention | `YourProject-{ID}` |

### Step 4: Run the Generator

```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-generate.py --project YourProject
```

**Expected output:**
```
Project:   C:\Users\mcwiz\Projects\YourProject
Templates: C:\Users\mcwiz\Projects\AgentOS\.claude\templates
Variables: ['PROJECT_ROOT', 'PROJECT_NAME', 'GITHUB_REPO', 'TOOLS_DIR', 'WORKTREE_PATTERN']

Generated files:
  C:\Users\mcwiz\Projects\YourProject\.claude\settings.json
  C:\Users\mcwiz\Projects\YourProject\.claude\hooks\pre-edit-check.sh
  C:\Users\mcwiz\Projects\YourProject\.claude\hooks\post-edit-lint.sh
  ...

Done! Generated N files.
```

### Step 5: Create Project CLAUDE.md (Recommended)

Create a `CLAUDE.md` in the project root:

```markdown
# CLAUDE.md - YourProject

You are a team member on this project, not a tool.

## First Action

Read the AgentOS core rules at `C:\Users\mcwiz\Projects\AgentOS\CLAUDE.md`.

---

## Project Identifiers

- **Repository:** `your-username/YourProject`
- **Project Root (Windows):** `C:\Users\mcwiz\Projects\YourProject`
- **Project Root (Unix):** `/c/Users/mcwiz/Projects/YourProject`
- **Worktree Pattern:** `YourProject-{IssueID}`

---

## Project Overview

[Brief description of what this project does]

---

## GitHub CLI

Always use explicit repo flag:
```bash
gh issue create --repo your-username/YourProject --title "..." --body "..."
```

---

## You Are Not Alone

Other agents may work on this project. Coordinate via GitHub Issues.
```

### Step 6: Create Session Logs Directory

```bash
mkdir -p docs/session-logs
```

### Step 7: Initial Commit

```bash
git add .
git commit -m "chore: initialize project with AgentOS"
```

### Step 8: Create GitHub Repository (Optional)

```bash
gh repo create your-username/YourProject --private --source=. --push
```

---

## Verification Checklist

| Check | Command | Expected |
|-------|---------|----------|
| project.json exists | `cat .claude/project.json` | Shows your variables |
| Generated files exist | `ls .claude/` | settings.json, hooks/ |
| Hooks executable | `ls -la .claude/hooks/` | Execute permission set |
| CLAUDE.md exists | `cat CLAUDE.md` | Shows project info |
| Git initialized | `git status` | Clean working tree |

---

## Troubleshooting

### "No project.json found"

The generator requires `.claude/project.json`. Create it per Step 3.

### "Templates directory not found"

Ensure `inherit_from` in project.json points to AgentOS:
```json
"inherit_from": "C:\\Users\\mcwiz\\Projects\\AgentOS"
```

### "Unsubstituted placeholders"

Some templates use variables you haven't defined. Check the warning message and add missing variables to project.json.

### Hooks not running

On Windows/Git Bash, hooks may need execute permission:
```bash
chmod +x .claude/hooks/*.sh
```

---

## Related Documents

- [0600-command-reference.md](../skills/0600-command-reference.md) - Available commands
- [AgentOS CLAUDE.md](../../CLAUDE.md) - Core rules inherited by all projects
- [project.json.example](../../.claude/project.json.example) - Template with all variables documented

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-13 | Initial version |
