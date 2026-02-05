# {IssueID} - Implementation Plan: {Title}

**Issue:** #{IssueID}
**Status:** Draft | Active | Complete
**Created:** {YYYY-MM-DD}
**Author:** {Model Name}

---

## Purpose

Implementation Plans are for **process and configuration changes** that don't require traditional code (no new `.py`, `.js`, `.ts` files). Use this template for:

- Documentation updates (CLAUDE.md, standards, protocols)
- Configuration changes (settings.json, permission rules)
- Workflow improvements (CI/CD, hooks, commands)
- Process refinements (audit procedures, templates)

**Not for:** Feature implementations with code → Use `0102-TEMPLATE-feature-lld.md`

---

## Problem Statement

{What problem does this solve? Include concrete evidence.}

**Evidence:** {Specific examples, error messages, metrics}

---

## Root Cause Analysis

{Why does the problem exist? What's the underlying cause?}

**Key Insight:** {The core realization that drives the solution}

---

## Solution Strategy

{High-level approach. What's the general idea?}

---

## Implementation Phases

### Phase 1: {Phase Title}

**File:** `{path/to/file}`
**Change Type:** ADD | MODIFY | REMOVE

**Current State:**
```
{What the file looks like now, if modifying}
```

**New State:**
```
{What the file should look like after}
```

**Rationale:** {Why this change?}

---

### Phase 2: {Phase Title}

{Repeat structure for each phase}

---

## Files to Modify

| File | Change Type | Description |
|------|-------------|-------------|
| `{path}` | ADD / MODIFY / REMOVE | {Brief description} |

---

## Verification Plan

### Test 1: {Test Name}

1. {Step 1}
2. {Step 2}
3. Expected: {What should happen}

### Test 2: {Test Name}

{Repeat for each test}

---

## Success Criteria

- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] {Criterion 3}

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| {Risk description} | High/Medium/Low | {How addressed} |

---

## Review Log

*Track reviews here if needed.*

| Date | Reviewer | Verdict | Notes |
|------|----------|---------|-------|
| {date} | {reviewer} | APPROVED / FEEDBACK | {summary} |
