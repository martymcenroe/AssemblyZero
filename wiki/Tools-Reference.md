# Tools Reference

> AssemblyZero core tools for multi-agent orchestration, Gemini verification, and permission management

---

## Overview

AssemblyZero provides a suite of Python tools that enable enterprise-grade AI agent orchestration. These tools handle:

- **Gemini Integration** - Credential rotation, retry logic, model validation
- **Permission Management** - Friction tracking, permission propagation
- **Configuration** - Project setup, template generation
- **Cross-Project Operations** - Pattern harvesting, credential management

---

## Gemini Tools

### gemini-retry.py

**Purpose:** Ensures Gemini 3 Pro reviews succeed even under load.

**Key Features:**
- Credential rotation when account quota exhausted
- Exponential backoff for temporary capacity issues
- Model validation (rejects silent downgrades to Flash)
- Auto-switches to stdin for large prompts (>10KB)
- Logs all attempts to `logs/gemini-retry-*.jsonl`

**Usage:**
```bash
# With inline prompt
poetry run python tools/gemini-retry.py --prompt "Review this LLD" --model gemini-3-pro-preview

# With prompt file (recommended for large prompts)
poetry run python tools/gemini-retry.py --prompt-file /path/to/prompt.txt --model gemini-3-pro-preview
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success - response printed to stdout |
| 1 | Permanent failure - all credentials exhausted |
| 2 | Invalid arguments |

**Environment Variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_RETRY_MAX` | 20 | Max retry attempts |
| `GEMINI_RETRY_BASE_DELAY` | 30 | Initial delay (seconds) |
| `GEMINI_RETRY_MAX_DELAY` | 600 | Max delay cap (seconds) |

**Why This Exists:**
- `QUOTA_EXHAUSTED` (account limit) needs credential rotation, not backoff
- `CAPACITY_EXHAUSTED` (Google servers) benefits from exponential backoff
- Direct CLI calls fail permanently on quota - this tool handles both scenarios

---

### gemini-rotate.py

**Purpose:** Gemini CLI wrapper with automatic credential rotation across multiple Google accounts.

**Key Features:**
- Rotates through API keys and OAuth credentials
- Maximizes available quota across accounts
- Tracks credential status and exhaustion times

**Usage:**
```bash
# Direct usage (like gemini CLI)
poetry run python tools/gemini-rotate.py --prompt "Review this code" --model gemini-3-pro-preview

# Check credential status
poetry run python tools/gemini-rotate.py --status
```

**Configuration:**
Credentials stored in: `~/.assemblyzero/gemini-credentials.json`

---

### gemini-test-credentials.py

**Purpose:** Test Gemini credentials to verify they're working.

**Usage:**
```bash
poetry run python tools/gemini-test-credentials.py
```

---

## Permission Tools

### zugzwang.py

**Purpose:** Real-time permission friction logger. Track every permission prompt to identify patterns and reduction opportunities.

**Why "Zugzwang":** In chess, zugzwang is when any move worsens your position. Permission prompts are similar - you must respond, but responding interrupts your flow.

**Usage:**
```bash
# Interactive mode - run in separate terminal
poetry run python tools/zugzwang.py

# One-shot log
poetry run python tools/zugzwang.py --log "Bash(git push) - approved"

# View last 10 entries
poetry run python tools/zugzwang.py --tail 10

# Clear log
poetry run python tools/zugzwang.py --clear
```

**Interactive Shortcuts:**
| Shortcut | Action |
|----------|--------|
| `.b <text>` | Log as BASH category |
| `.s <text>` | Log as SPAWNED category |
| `.d <text>` | Log as DENIED category |
| `.a <text>` | Log as APPROVED category |
| `.m` | Multi-line mode |
| `.t [n]` | Show last n entries |
| `.c` | Clear log |
| `.q` | Quit |

**Output:** `logs/zugzwang.log`

---

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

**ALWAYS use gemini-retry.py, NEVER call gemini CLI directly:**

```bash
# WRONG - will fail permanently on quota
gemini --prompt "..." --model gemini-3-pro-preview

# RIGHT - handles quota and retries
poetry run python tools/gemini-retry.py --prompt "..." --model gemini-3-pro-preview
```

---

## Related Pages

- [Gemini Verification](Gemini-Verification) - How Gemini integration works
- [Permission Friction](Permission-Friction) - Why friction tracking matters
- [Quick Start](Quick-Start) - Getting started with AssemblyZero
- [Audits Catalog](Audits-Catalog) - Available governance audits
