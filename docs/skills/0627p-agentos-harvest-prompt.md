# agentos-harvest - Prompt Reference

**Tool:** `tools/agentos-harvest.py`

## When to Use

Use `agentos-harvest.py` when you need to:
- Find patterns in child projects that should be promoted to AgentOS
- Identify convergent patterns (same thing in multiple projects)
- Audit what child projects have added beyond AgentOS base

## Examples

### Full Harvest

> "Scan all projects for patterns to promote to AgentOS"

Agent will run:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py
```

### Specific Project Audit

> "What has Talos added that AgentOS doesn't have?"

Agent will run:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --project Talos --verbose
```

### JSON for Processing

> "Get harvest report as JSON for further analysis"

Agent will run:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/agentos-harvest.py --format json > harvest-report.json
```

## Integration with `/promote`

The `/promote` skill uses harvest output to identify what to promote. Workflow:

1. Run `agentos-harvest.py` to identify candidates
2. Review candidates with user
3. Use `/promote` to move approved patterns to AgentOS

## Convergent Patterns

Patterns found in 2+ projects are marked `convergent: true` and given higher priority. These are strong candidates for promotion since multiple projects independently developed the same solution.
