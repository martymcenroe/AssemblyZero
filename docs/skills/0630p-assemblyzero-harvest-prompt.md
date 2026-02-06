# assemblyzero-harvest - Prompt Reference

**Tool:** `tools/assemblyzero-harvest.py`

## When to Use

Use `assemblyzero-harvest.py` when you need to:
- Find patterns in child projects that should be promoted to AssemblyZero
- Identify convergent patterns (same thing in multiple projects)
- Audit what child projects have added beyond AssemblyZero base

## Examples

### Full Harvest

> "Scan all projects for patterns to promote to AssemblyZero"

Agent will run:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-harvest.py
```

### Specific Project Audit

> "What has Talos added that AssemblyZero doesn't have?"

Agent will run:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-harvest.py --project Talos --verbose
```

### JSON for Processing

> "Get harvest report as JSON for further analysis"

Agent will run:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-harvest.py --format json > harvest-report.json
```

## Integration with `/promote`

The `/promote` skill uses harvest output to identify what to promote. Workflow:

1. Run `assemblyzero-harvest.py` to identify candidates
2. Review candidates with user
3. Use `/promote` to move approved patterns to AssemblyZero

## Convergent Patterns

Patterns found in 2+ projects are marked `convergent: true` and given higher priority. These are strong candidates for promotion since multiple projects independently developed the same solution.
