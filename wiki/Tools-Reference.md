# Tools Reference

> AssemblyZero core tools for multi-agent orchestration, Gemini verification, and permission management

---

## Overview

AssemblyZero provides a suite of Python tools that enable enterprise-grade AI agent orchestration. These tools handle:

- **Gemini Integration** - The `agy` transport, retry logic, model validation
- **Permission Management** - Friction tracking, permission propagation
- **Configuration** - Project setup, template generation
- **Cross-Project Operations** - Pattern harvesting, credential management

---

## Gemini Tools

There is no Gemini command-line tool in `tools/`. The workflows call Gemini themselves, through the Antigravity CLI (`agy`) on the subscription, and `assemblyzero/core/gemini_client.py` is that transport. It retries transient capacity errors with exponential backoff and refuses a forbidden model. There are no credentials to rotate.

---

## Permission Tools

### assemblyzero-permissions.py

**Purpose:** Manage permissions across master (user-level) and project-level settings files.

**Key Insight:** Claude Code permissions DO NOT INHERIT - they REPLACE. When a project has its own permissions block, it completely overrides the parent.

**Modes:**

| Mode | Description |
|------|-------------|
| `--audit` | Read-only analysis of session vends |
| `--clean` | Remove session vends AND protected deny entries |
| `--quick-check` | Fast check for cleanup integration (exit code 0/1) |
| `--merge-up` | Clean all projects, merge to master, sync to Projects level |
| `--restore` | Restore from backup |
| `--repair` | Fix invalid JSON by deleting broken project files |

**Usage:**
```bash
# Audit a project
poetry run python tools/assemblyzero-permissions.py --audit --project Aletheia

# Clean with dry-run
poetry run python tools/assemblyzero-permissions.py --clean --project AssemblyZero --dry-run

# Quick check for cleanup scripts
poetry run python tools/assemblyzero-permissions.py --quick-check --project Aletheia

# Merge up and sync across all projects
poetry run python tools/assemblyzero-permissions.py --merge-up --all-projects

# Repair broken JSON
poetry run python tools/assemblyzero-permissions.py --repair --all-projects
```

**Protected Permissions:**
These are NEVER allowed in deny lists (automatically removed):
- `Bash(python:*)`
- `Bash(python3:*)`

---

## Configuration Tools

### assemblyzero-generate.py

**Purpose:** Generate concrete configs from parameterized templates.

**How It Works:**
1. Reads templates from `AssemblyZero/.claude/templates/`
2. Reads variables from project's `.claude/project.json`
3. Outputs concrete configs to project's `.claude/` directory

**Files Processed:**
- `commands/*.md.template` → `commands/*.md`
- `hooks/*.sh.template` → `hooks/*.sh`
- `settings.json.template` → `settings.json`

**Usage:**
```bash
# Generate configs for a project
poetry run python tools/assemblyzero-generate.py --project /path/to/project

# Relative to Projects directory
poetry run python tools/assemblyzero-generate.py --project Aletheia

# Also set up encrypted ideas folder
poetry run python tools/assemblyzero-generate.py --project Aletheia --ideas
```

**Template Variables:**
Templates use `{{VARIABLE}}` syntax. Common variables:
- `{{GITHUB_REPO}}` - Repository name (e.g., `mcwiz/Aletheia`)
- `{{PROJECT_NAME}}` - Project name (e.g., `Aletheia`)
- `{{PROJECT_ROOT}}` - Project root path

---

### assemblyzero_config.py

**Purpose:** Centralized configuration management for AssemblyZero paths.

**Usage in Python:**
```python
from assemblyzero_config import config

# Get paths in Windows format
root = config.assemblyzero_root()           # C:\Users\...\AssemblyZero
projects = config.projects_root()       # C:\Users\...\Projects

# Get paths in Unix format (for Bash)
root_unix = config.assemblyzero_root_unix()  # /c/Users/.../AssemblyZero
```

**Configuration File:** `~/.assemblyzero/config.json`

---

## Cross-Project Tools

### assemblyzero-harvest.py

**Purpose:** Scan child projects to discover patterns that should be promoted to AssemblyZero.

Part of the bidirectional sync architecture - patterns emerge in projects, get harvested, and promoted to core.

**Usage:**
```bash
# Scan all registered projects
poetry run python tools/assemblyzero-harvest.py

# Scan specific project
poetry run python tools/assemblyzero-harvest.py --project Talos

# Output as JSON
poetry run python tools/assemblyzero-harvest.py --format json
```

**What It Finds:**
- Commands that exist in child projects but not AssemblyZero
- Tools that have been duplicated
- Permissions that should be elevated
- CLAUDE.md patterns worth generalizing

---

### assemblyzero_credentials.py

**Purpose:** Secure credential management using system keychain with fallback to encrypted files.

**Features:**
- Stores credentials in Windows Credential Manager / macOS Keychain
- Falls back to file-based storage if keychain unavailable
- Used by gemini-rotate.py for API key management

---

## Utility Tools

### claude-usage-scraper.py

**Purpose:** Scrape Claude usage data for cost tracking and metrics.

---

### append_session_log.py

**Purpose:** Append entries to session logs in standard format.

---

### update-doc-refs.py

**Purpose:** Update cross-references in documentation files.

---

## Best Practices

### Tool Execution Pattern

Always run tools through Poetry to ensure correct dependencies:

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/TOOL_NAME.py [args]
```

### Path Formats

| Context | Format | Example |
|---------|--------|---------|
| Bash commands | Unix-style | `/c/Users/mcwiz/Projects/...` |
| Python Path objects | Windows-style | `C:\Users\mcwiz\Projects\...` |
| Config files | Both supported | Check tool documentation |

### Gemini Reviews

**Run a Gemini review through a workflow, which calls `agy`. The `gemini` CLI is retired:**

```bash
poetry run python tools/run_requirements_workflow.py --type lld --issue 42
```

---

## Related Pages

- [Gemini Verification](Gemini-Verification) - How Gemini integration works
- [Permission Friction](Permission-Friction) - Why friction tracking matters
- [Quick Start](Quick-Start) - Getting started with AssemblyZero
- [Audits Catalog](Audits-Catalog) - Available governance audits
