# Permission Friction

> The #1 adoption blocker for AI coding assistants - and how AssemblyZero solves it

---

## The Problem

Every time an AI coding assistant needs permission, the developer's flow breaks:

```
Developer: "Add logging to the auth module"
Agent: Starts working...
[PERMISSION PROMPT] "Allow: cat /path/to/file.py?"
Developer: *clicks approve*
Agent: Continues...
[PERMISSION PROMPT] "Allow: sed -i 's/old/new/' file.py?"
Developer: *clicks approve*
Agent: Continues...
[PERMISSION PROMPT] "Allow: git commit -m 'Add logging'"
Developer: *clicks approve*
...
```

**Each interruption:**
- Breaks concentration (23 minutes to recover full focus)
- Adds 5-30 seconds of mechanical clicking
- Creates resentment toward the tool
- Accumulates into hours of lost productivity per week

At 15-20 permission prompts per hour, developers abandon the tool.

---

## Why Friction Happens

### 1. Pattern Mismatch

The permission system uses pattern matching:
```
Allowed: "git commit"
Actual:  "git commit -m 'message'"
Result:  PROMPT (pattern doesn't match exactly)
```

### 2. Bash Flags

Flags break patterns:
```
Allowed: "head /path/to/file"
Actual:  "head -n 50 /path/to/file"
Result:  PROMPT (flags aren't in pattern)
```

### 3. Path Variations

Same path, different formats:
```
Allowed: "/c/Users/dev/project/file.py"
Actual:  "C:\\Users\\dev\\project\\file.py"
Result:  PROMPT (Windows vs Unix format)
```

### 4. Spawned Agents

Sub-agents inherit incomplete permissions:
```
Main Agent: Has learned patterns
Spawned Agent: Starts fresh
Result:  PROMPT (every command is new)
```

---

## AssemblyZero Solutions

### 1. Dedicated Tools Instead of Bash

The most friction comes from Bash command variations. AssemblyZero substitutes dedicated tools:

| Bash Command | Friction Risk | AssemblyZero Alternative |
|--------------|--------------|---------------------|
| `cat file.py` | HIGH | Read tool (always auto-approved) |
| `head -n 50 file.py` | HIGH | Read tool with `limit` |
| `grep pattern file` | HIGH | Grep tool (always auto-approved) |
| `sed -i 's/old/new/'` | HIGH | Edit tool (always auto-approved) |
| `find . -name "*.py"` | HIGH | Glob tool (always auto-approved) |

**Result:** 80%+ reduction in Bash-related friction.

### 2. Permission Pattern Learning

When friction occurs, learn the pattern:

```
[FRICTION EVENT]
Command: git -C /project push -u origin feature-branch
Pattern needed: "git -C /*/Projects/* push"

[ADDED TO ALLOWED PATTERNS]
Future executions: AUTO-APPROVED
```

### 3. Permission Propagation

Patterns learned in one project propagate to others:

```
Project A: Learns "poetry run python tools/*.py"
Project B: Inherits pattern (found in 3+ projects)
Project C: Inherits pattern

Auto-promote threshold: 3 projects
```

Tool: `assemblyzero-permissions.py --sync --all-projects`

### 4. Spawned Agent Instructions

When spawning sub-agents, include permission-safe rules:

```markdown
## PERMISSION-SAFE EXECUTION RULES

1. Use dedicated tools instead of Bash:
   - Read tool instead of cat/head/tail
   - Grep tool instead of grep/rg
   - Glob tool instead of find/ls

2. For .claude/ paths (session logs):
   - NEVER use `head -n X /path` (flags break patterns)
   - USE Read tool with `limit` parameter

3. Safe Bash patterns (known to work):
   - `git -C /absolute/path status`
   - `poetry run python /path/script.py`
   - `npm install --prefix /path`
```

### 5. Friction Logging (Zugzwang Protocol)

Real-time tracking identifies friction patterns:

```markdown
## FRICTION LOG - Session 2026-01-21-001

| Time | Tool | Command | Friction | Resolution |
|------|------|---------|----------|------------|
| 09:15 | Bash | `head -n 50 /path` | YES | Used Read tool |
| 09:22 | Bash | `git -C /path status` | NO | Pattern matched |
| 09:45 | Bash | `npm install` | YES | Added pattern |

Session friction rate: 4.3%
Patterns added: 1
```

---

## Measurement

### Key Metrics

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| **Friction Rate** | < 5% | > 10% | > 20% |
| **Prompts per Hour** | < 3 | > 6 | > 12 |
| **Pattern Coverage** | > 95% | < 90% | < 80% |

### Friction Rate Calculation

```
Friction Rate = Permission Prompts / Tool Calls

Example session:
- Tool calls: 47
- Permission prompts: 2
- Friction rate: 4.3% ✓
```

### Maturity Curve

Projects improve over time:

```
Week 1:  18% friction (new project, many patterns to learn)
Week 2:  12% friction (common patterns added)
Week 4:   6% friction (most patterns learned)
Week 8:   3% friction (mature project)
Steady:   2% friction (edge cases only)
```

---

## Tools

### assemblyzero-permissions.py

Permission management utility:

```bash
# Audit current permission patterns
poetry run python tools/assemblyzero-permissions.py --audit --project MyProject

# Clean redundant patterns (dry-run)
poetry run python tools/assemblyzero-permissions.py --clean --project MyProject --dry-run

# Sync patterns across all projects
poetry run python tools/assemblyzero-permissions.py --sync --all-projects

# Quick check for cleanup integration
poetry run python tools/assemblyzero-permissions.py --quick-check --project MyProject
```

### /sync-permissions Skill

Quick cleanup during sessions:

```
/sync-permissions
```

Removes:
- One-time session vends (accumulated permission approvals)
- Redundant patterns (covered by broader patterns)
- Stale patterns (for removed projects)

---

## Impact

### Before AssemblyZero

```
Typical developer day:
- 6 hours of work
- 15 permission prompts per hour
- 90 prompts per day
- 10 seconds each = 15 minutes of clicking
- Plus context-switch cost: ~2 hours of degraded focus
```

### After AssemblyZero

```
With friction optimization:
- Same 6 hours of work
- 2 permission prompts per hour (new edge cases)
- 12 prompts per day
- 2 minutes of clicking
- Minimal context-switch cost
```

**Time recovered: 15 minutes direct + 1.5 hours focus = ~2 hours/day**

At $75/hour fully-loaded cost: **$150/developer/day** in recovered productivity.

---

## Implementation Checklist

### For New Projects

1. [ ] Generate configs with `assemblyzero-generate.py`
2. [ ] Run initial session to discover patterns
3. [ ] Run `--audit` to see friction points
4. [ ] Add common patterns to settings
5. [ ] Sync across projects with `--sync`

### For Existing Projects

1. [ ] Run `--audit` to identify current friction
2. [ ] Replace Bash commands with dedicated tools in CLAUDE.md
3. [ ] Add spawned agent instructions
4. [ ] Run `--clean` to remove redundancies
5. [ ] Monitor friction rate over time

### For Teams

1. [ ] Establish friction rate targets (< 5%)
2. [ ] Include friction in session reviews
3. [ ] Share patterns across team projects
4. [ ] Track friction trends in dashboards

---

## Related Pages

- [Measuring Productivity](Measuring-Productivity) - Full KPI framework
- [Quick Start](Quick-Start) - Getting started guide
- [Multi-Agent Orchestration](Multi-Agent-Orchestration) - Architecture overview
