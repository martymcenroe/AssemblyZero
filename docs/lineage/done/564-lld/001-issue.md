---
repo: martymcenroe/AssemblyZero
issue: 564
url: https://github.com/martymcenroe/AssemblyZero/issues/564
fetched: 2026-03-04T06:52:27.250346Z
---

# Issue #564: Strengthen decision-making overrides against Anthropic system prompt defaults

## Problem

Anthropic's system prompt encourages autonomy and trying alternatives when blocked. This conflicts with user's preferred behavior: **stop, ask, don't guess.**

### The tension

**Anthropic defaults:**
- "If your approach is blocked... consider alternative approaches or other ways you might unblock yourself"
- Encourages being helpful by figuring things out autonomously
- Bias toward action and trying things

**What the user actually wants:**
- STOP on unexpected errors — don't try 3 alternatives before asking
- ASK before guessing — wrong guesses waste more time than asking
- Don't prioritize "getting it done" over "getting it done right"

### Current instructions (deleted from WORKFLOW.md in #554, too vague to override Anthropic)

```
## Decision-Making Protocol

**When you encounter an unexpected error or decision point:**

1. **STOP** - Do not apply quick fixes
2. **Check documentation:** Lessons learned, open issues, design documents
3. **If still unsure: ASK** - Query the orchestrator
4. **Never prioritize "getting it done" over "getting it done right"**

The documentation system exists so you don't need persistent memory. USE IT.
```

### Why the current version fails

The override is only as strong as the instruction is specific. "Check documentation" and "if still unsure, ASK" are easy for the model to deprioritize against Anthropic's stronger, more specific autonomy instructions. Need explicit, specific overrides.

## Required

Write a strengthened version for root CLAUDE.md that:
1. Explicitly names the Anthropic behaviors being overridden
2. Uses specific, unambiguous language (not "if still unsure")
3. Defines what counts as an "unexpected error" vs a routine retry
4. Lives in root CLAUDE.md so it applies to all repos

## Context

Filed from instruction hierarchy audit (#554). The user has observed Claude trying multiple approaches autonomously when it should stop and ask.