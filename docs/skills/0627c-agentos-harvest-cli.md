# agentos-harvest - CLI Reference

**Tool:** `tools/agentos-harvest.py`

## Quick Start

```bash
# Scan all registered projects
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py

# Scan specific project
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --project Talos

# Output as JSON
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --format json

# Verbose output
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --verbose
```

## Parameters

| Flag | Required | Description |
|------|----------|-------------|
| `--project` | No | Scan only this project |
| `--format` | No | Output format: markdown (default) or json |
| `--verbose` | No | Show detailed scan progress |

## What It Scans

| Category | What It Finds |
|----------|---------------|
| commands | Skills in `.claude/commands/` not in AgentOS |
| tools | Scripts in `tools/` not in AgentOS |
| templates | Template files not in AgentOS |
| permissions | Permission patterns unique to project |
| claude_md | CLAUDE.md sections not in AgentOS |

## Project Registry

Projects must be registered in `.claude/project-registry.json`:

```json
{
  "projects": [
    {"name": "Talos", "path": "C:\\Users\\mcwiz\\Projects\\Talos"},
    {"name": "Aletheia", "path": "C:\\Users\\mcwiz\\Projects\\Aletheia"}
  ]
}
```

## Output

The tool produces a harvest report with:
- Promotion candidates (patterns to move to AgentOS)
- Convergent patterns (found in multiple projects)
- Priority ratings (low/medium/high)
