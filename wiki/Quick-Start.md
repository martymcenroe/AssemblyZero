# Quick Start

> Get AssemblyZero running in 5 minutes

---

## Prerequisites

- Python 3.11+
- Poetry (Python package manager)
- Git
- Claude Code CLI installed

---

## Step 1: Clone AssemblyZero

```bash
git clone https://github.com/martymcenroe/AssemblyZero.git
cd AssemblyZero
```

---

## Step 2: Install Dependencies

```bash
poetry install
```

---

## Step 3: Configure Your Project

### Create project configuration

```bash
mkdir -p YourProject/.claude
cp AssemblyZero/.claude/project.json.example YourProject/.claude/project.json
```

### Edit variables

```json
{
  "variables": {
    "PROJECT_ROOT": "/c/Users/you/Projects/YourProject",
    "PROJECT_NAME": "YourProject",
    "GITHUB_REPO": "username/YourProject",
    "TOOLS_DIR": "/c/Users/you/Projects/YourProject/tools",
    "WORKTREE_PATTERN": "YourProject-{ID}"
  },
  "inherit_from": "C:\\Users\\you\\Projects\\AssemblyZero"
}
```

### Generate configs

```bash
poetry run --directory /path/to/AssemblyZero \
  python /path/to/AssemblyZero/tools/assemblyzero-generate.py \
  --project YourProject
```

This generates:
- `.claude/settings.json` - Permission patterns
- `.claude/commands/*.md` - Slash commands
- `.claude/hooks/*.sh` - Pre/post tool hooks

---

## Step 4: Create Project CLAUDE.md (Optional)

If your project needs specific rules beyond AssemblyZero core:

```markdown
# CLAUDE.md - YourProject

## Project Context
Brief description of what this project does.

## Build Commands
poetry run pytest
npm run build

## Project-Specific Rules
Any rules specific to this project.
```

---

## Step 5: Start Using

Launch Claude Code in your project:

```bash
cd YourProject
claude
```

The agent now operates under AssemblyZero governance:
- Bash safety rules enforced
- Worktree isolation for code changes
- Gemini verification gates (when configured)
- Permission friction minimized

---

## Verify Installation

### Check worktree isolation

When you give the agent a coding task, it should:
1. Create a worktree before editing code
2. Work in the worktree, not main

### Check Bash rules

The agent should never use `&&`, `|`, or `;` in Bash commands.

### Check friction reduction

Permission prompts should be minimal (< 5% of tool calls).

---

## Next Steps

### Set up Gemini verification

For full governance gates, configure Gemini:

1. Get Gemini API credentials
2. Add to `~/.assemblyzero/credentials.json`
3. Configure gates in project CLAUDE.md

### Customize permissions

Reduce friction by adding project-specific patterns:

```bash
poetry run python tools/assemblyzero-permissions.py \
  --audit --project YourProject
```

### Enable audits

Run security and compliance audits:

```bash
/audit --type security
```

---

## Common Issues

### "File does not exist" with Read tool

**Cause:** Using Unix path format with Windows tools

**Fix:** Use Windows paths (`C:\...`) for Read/Write/Edit/Glob tools

### Permission prompts on every command

**Cause:** Patterns not learned yet

**Fix:** Let patterns accumulate, or run `--sync` to propagate from other projects

### Agent not following rules

**Cause:** CLAUDE.md not being read

**Fix:** Ensure CLAUDE.md is in project root and properly formatted

---

## Resources

- [Multi-Agent Orchestration](Multi-Agent-Orchestration) - Architecture overview
- [Permission Friction](Permission-Friction) - Reduce approval prompts
- [Governance Gates](Governance-Gates) - LLD, implementation, report gates
- [Measuring Productivity](Measuring-Productivity) - Track your metrics
