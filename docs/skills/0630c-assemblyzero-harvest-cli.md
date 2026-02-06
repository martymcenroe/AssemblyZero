# assemblyzero-harvest - CLI Reference

**Tool:** `tools/assemblyzero-harvest.py`

## Quick Start

```bash
# Scan all registered projects
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-harvest.py

# Scan specific project
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-harvest.py --project Talos

# Output as JSON
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-harvest.py --format json

# Verbose output
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-harvest.py --verbose
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
| commands | Skills in `.claude/commands/` not in AssemblyZero |
| tools | Scripts in `tools/` not in AssemblyZero |
| templates | Template files not in AssemblyZero |
| permissions | Permission patterns unique to project |
| claude_md | CLAUDE.md sections not in AssemblyZero |

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
- Promotion candidates (patterns to move to AssemblyZero)
- Convergent patterns (found in multiple projects)
- Priority ratings (low/medium/high)
