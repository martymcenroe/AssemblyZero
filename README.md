# AgentOS

Parameterized agent configuration system for Claude Code. Separates generic agent rules from project-specific customizations using a template-based approach.

## Overview

AgentOS provides:
- **Core rules** (`CLAUDE.md`) - Bash safety, worktree isolation, visible self-checks
- **Template system** - Parameterized configs with `{{VAR}}` placeholders
- **Pre-processor** - Generates concrete configs from templates + project variables

## Quick Start

### 1. Create project configuration

Copy the example to your project:

```bash
mkdir -p YourProject/.claude
cp AgentOS/.claude/project.json.example YourProject/.claude/project.json
```

### 2. Edit variables

```json
{
  "variables": {
    "PROJECT_ROOT": "/c/Users/you/Projects/YourProject",
    "PROJECT_NAME": "YourProject",
    "GITHUB_REPO": "username/YourProject",
    "TOOLS_DIR": "/c/Users/you/Projects/YourProject/tools",
    "WORKTREE_PATTERN": "YourProject-{ID}"
  },
  "inherit_from": "C:\\Users\\you\\Projects\\AgentOS"
}
```

### 3. Generate configs

```bash
poetry run --directory /path/to/AgentOS python /path/to/AgentOS/tools/agentos-generate.py --project YourProject
```

This generates:
- `.claude/settings.json` - Hook configuration
- `.claude/commands/*.md` - Slash commands
- `.claude/hooks/*.sh` - Pre/post tool hooks

## Tools

### agentos-generate.py - Config Generator

Generates project-specific configs from templates:

```bash
poetry run python tools/agentos-generate.py --project YourProject
```

### agentos-permissions.py - Permission Propagation

Syncs friction-free permissions across projects. Removes redundant and stale permissions:

```bash
# Audit a project's permissions
poetry run python tools/agentos-permissions.py --audit --project Aletheia

# Clean redundancies (dry-run first)
poetry run python tools/agentos-permissions.py --clean --project Aletheia --dry-run
poetry run python tools/agentos-permissions.py --clean --project Aletheia

# Sync all projects with auto-promote
poetry run python tools/agentos-permissions.py --sync --all-projects

# Quick check for cleanup integration
poetry run python tools/agentos-permissions.py --quick-check --project Aletheia
```

**Modes:**
| Mode | Description |
|------|-------------|
| `--audit` | Read-only analysis of redundant/stale permissions |
| `--clean` | Remove redundancies and stale session vends |
| `--sync` | Full sync, auto-promotes patterns found in 3+ projects |
| `--quick-check` | Fast check for cleanup integration (exit code 0/1) |
| `--restore` | Restore from backup after --clean |

## Structure

```
AgentOS/
├── CLAUDE.md                    # Core agent rules (read by all projects)
├── pyproject.toml               # Poetry project
├── tools/
│   ├── agentos-generate.py      # Template pre-processor
│   └── agentos-permissions.py   # Permission propagation
└── .claude/
    ├── project.json.example     # Variable template for new projects
    └── templates/
        ├── settings.json.template
        ├── commands/
        │   └── cleanup.md.template
        └── hooks/
            ├── pre-edit-check.sh.template
            ├── pre-edit-security-warn.sh.template
            ├── pre-commit-report-check.sh.template
            └── post-edit-lint.sh.template
```

## Template Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{{PROJECT_ROOT}}` | Unix-style absolute path | `/c/Users/me/Projects/MyApp` |
| `{{PROJECT_NAME}}` | Project name for patterns | `MyApp` |
| `{{GITHUB_REPO}}` | GitHub repo for `gh` CLI | `username/MyApp` |
| `{{TOOLS_DIR}}` | Path to project tools | `/c/Users/me/Projects/MyApp/tools` |
| `{{WORKTREE_PATTERN}}` | Worktree naming pattern | `MyApp-{ID}` |

## Core Rules (from CLAUDE.md)

### Bash Command Safety
- No `&&`, `|`, or `;` in commands (triggers permission prompts)
- Use `git -C /path` instead of `cd /path && git`
- One command per Bash tool call

### Worktree Isolation
- All code changes in worktrees, never on main
- Docs can be edited on main
- Pattern: `git worktree add ../ProjectName-{ID} -b {ID}-description`

### Visible Self-Check Protocol
- Every Bash command requires visible scan for violations
- Every tool call requires gate check output

## Inheritance Model

Projects have their own `CLAUDE.md` that **adds to** AgentOS rules:

```
AgentOS/CLAUDE.md          # Generic rules (bash safety, gates, worktree)
    ↓ inherits
YourProject/CLAUDE.md      # Project-specific (repo paths, workflows, tools)
```

## License

MIT
