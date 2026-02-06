# 0008 - Documentation Convention (c/p Pattern)

**File:** `docs/standards/0008-documentation-convention.md`
**Status:** Active
**Version:** 2026-01-14

---

## Purpose

Every reusable component (skill, tool, runbook) MUST have two documentation files:
- **`c` (CLI)** - How to run manually from the terminal
- **`p` (Prompt)** - How to use via Claude conversation

This convention ensures users can always choose between token efficiency (CLI) and guided assistance (Prompt).

---

## Why This Matters

| Scenario | Best Choice | Reason |
|----------|-------------|--------|
| Routine task | CLI | Saves tokens, faster |
| Unfamiliar with options | Prompt | Claude guides you |
| Batch operations | CLI | Scriptable |
| Want analysis/recommendations | Prompt | Claude can interpret results |
| Debugging/troubleshooting | Prompt | Claude can adapt |
| Token budget is tight | CLI | No LLM cost |

**Neither approach is "better" - they serve different needs.**

---

## Naming Convention

```
{NUMBER}c-{name}-cli.md       # CLI documentation
{NUMBER}p-{name}-prompt.md    # Prompt documentation
```

### Examples by Category

| Category | Range | Example |
|----------|-------|---------|
| AssemblyZero skills | 062x-069x | `0622c-onboard-cli.md`, `0622p-onboard-prompt.md` |
| Project runbooks | 109xx | `10901c-file-inventory-cli.md`, `10901p-file-inventory-prompt.md` |
| Python tools | varies | `{num}c-toolname-cli.md`, `{num}p-toolname-prompt.md` |

---

## Required Sections: CLI Document (`c`)

```markdown
# {NUMBER}c - {Name} CLI

**Purpose:** One-line description of what this does.

---

## Prerequisites

(Dependencies, setup steps)

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `tool command1` | What it does |
| `tool command2` | What it does |

---

## Workflow

### 1. Step One

(Exact commands with code blocks)

### 2. Step Two

(Continue with examples)

---

## Options Reference

(Full flag/option documentation)

---

## See Also

- [Prompt version]({NUMBER}p-{name}-prompt.md)
```

---

## Required Sections: Prompt Document (`p`)

```markdown
# {NUMBER}p - {Name} Prompt

**Purpose:** One-line description of what this does.

---

## When to Use

Use the **prompt method** when:
- (scenarios where Claude adds value)

Use the **[CLI method]({NUMBER}c-{name}-cli.md)** when:
- (scenarios where manual is better)

---

## Example Prompts

### Task 1

> "Natural language request..."

Claude will:
1. Step Claude takes
2. Step Claude takes

### Task 2

> "Another natural language request..."

---

## Natural Language Queries

(Examples of follow-up questions users can ask)

---

## Tips

(Best practices for using with Claude)

---

## See Also

- [CLI version]({NUMBER}c-{name}-cli.md)
```

---

## Cross-Referencing

**Every c document MUST link to its p counterpart and vice versa.**

In the CLI doc:
```markdown
## See Also
- [{NUMBER}p - {Name} Prompt]({NUMBER}p-{name}-prompt.md) - Using with Claude
```

In the Prompt doc:
```markdown
## When to Use
Use the **[CLI method]({NUMBER}c-{name}-cli.md)** when:
```

---

## When to Create c/p Documentation

**CREATE c/p docs for:**
- Skills/commands (`/onboard`, `/cleanup`, etc.)
- Python tools that users run directly
- Runbooks/procedures with multiple steps
- Any reusable component that could be run manually OR via Claude

**DON'T create c/p docs for:**
- Internal helper functions
- One-off scripts that won't be reused
- Configuration files
- Pure reference documentation (ADRs, standards like this one)

---

## Checklist for New Components

When creating a new skill, tool, or runbook:

- [ ] Created `{num}c-{name}-cli.md` with all required sections
- [ ] Created `{num}p-{name}-prompt.md` with all required sections
- [ ] Both docs cross-reference each other
- [ ] Added to relevant index file (0600-command-index.md, runbook-index.md, etc.)
- [ ] CLI doc has exact commands (copy-pasteable)
- [ ] Prompt doc has natural language examples

---

## Enforcement

This standard applies to:
- **AssemblyZero** - All skills in `docs/skills/`
- **All child projects** - Runbooks, tools, procedures

Agents should:
1. Check for existing c/p docs before creating new ones
2. Create BOTH docs when adding new components (not just one)
3. Update BOTH docs when modifying functionality

---

## History

| Date | Change |
|------|--------|
| 2026-01-14 | Created. Formalized c/p convention from skills and maintenance runbooks. |
