# 0901 - Runbook: Nightly AssemblyZero Audit

## Purpose

Comprehensive self-audit of the AssemblyZero documentation system using extended thinking (ultrathink) for deep analysis. This runbook describes how to invoke the audit and what to expect.

## When to Run

- **Nightly:** Automated via PowerShell scheduled task
- **After major documentation changes:** Manual invocation
- **Before significant releases:** Part of pre-release checklist

## Invocation

**PowerShell command (orchestrator runs this):**

```powershell
# Ultrathink mode invocation - specifics provided by orchestrator
# This triggers Claude Code with extended thinking enabled
```

**What to say to Claude:**

```
Run the AssemblyZero Audit (0807) with extended analysis. Use ultrathink for deep conflict detection and redundancy analysis. After findings, offer to batch-create GitHub issues.
```

## What It Does

Invokes `docs/0807-assemblyzero-audit.md` with extended analysis to detect:

### 1. Conflict Detection
- Cross-reference all gate definitions (CLAUDE.md, 0000-GUIDE, 0002, 0004)
- Flag identical text blocks in multiple files
- Identify contradictory instructions

### 2. Redundancy Analysis
- Find duplicate content (>80% similar blocks)
- Identify alias skills/commands that add no value
- Flag stale staging directories

### 3. Promotion Candidates
- Recommendations that are frequently violated (promote to gates)
- Manual checklists that could be automated hooks
- Documentation-only gates that could be enforced

### 4. Model Cost Analysis
- Review audit model assignments
- Flag Opus usage where Haiku/Sonnet would suffice
- Estimate savings from model downgrades

### 5. Stale Content Detection
- IMMEDIATE-PLAN references to closed issues
- Index files out of sync with actual files
- Dead links to legacy or deleted documents

## Output

The audit produces:
1. **Findings summary** displayed in session
2. **Offer to batch-create GitHub issues** for significant findings

### Issue Creation Rules

When Claude offers to create issues:

| Finding Type | Requires Worktree | Branch Directly to Main |
|--------------|-------------------|-------------------------|
| Code changes (.py, .js, .sh) | Yes | No |
| Hook modifications | Yes | No |
| Agent definition changes | Yes | No |
| Documentation-only fixes | No | Yes (per docs-in-main policy) |

## Expected Findings by Category

| Category | Typical Count | Severity |
|----------|---------------|----------|
| Conflicts | 0-3 | High |
| Redundancies | 2-5 | Medium |
| Promotion candidates | 1-3 | Medium |
| Model optimizations | 5-15 | Low |
| Stale content | 0-5 | Low |

## Related Documents

- `docs/0807-assemblyzero-audit.md` - The audit procedure itself
- `docs/0899-meta-audit.md` - Audits the audits
- `docs/0900-runbook-index.md` - Index of all runbooks
- `CLAUDE.md` - Agent operating procedures

## History

| Date | Outcome | Issues Created |
|------|---------|----------------|
| 2026-01-09 | Initial audit | (this runbook created from findings) |
