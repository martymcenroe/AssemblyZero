# Context Window Budget Audit — Issue #404

**Date:** 2026-02-20
**Status:** Complete

## Problem

Fresh Claude Code sessions started at ~14% context consumed before the first user message. Identity facts (GitHub username, AWS account) were only injected at compaction time via a `PreCompact` hook, causing early-session hallucinations.

## Findings

### Token Budget Breakdown (Before)

| Source | Lines | Bytes | ~Tokens | Notes |
|--------|-------|-------|---------|-------|
| Claude Code system prompt | ~2000+ | ~15K+ | ~4,000+ | Not controllable |
| Root `CLAUDE.md` | 122 | 5,009 | ~1,250 | Universal rules |
| Project `CLAUDE.md` | 34-73 | 1,061-2,309 | ~265-577 | Per-project |
| Project `MEMORY.md` | 34-49 | 1,909-2,637 | ~477-660 | Auto memory |
| Root `MEMORY.md` | 25 | 1,572 | ~393 | Cross-project |
| Git status snapshot | ~10-20 | ~500 | ~125 | Auto-injected |
| **Total user-controllable** | **~350** | **~15,049** | **~3,760** | |

### Redundancies Found (10 items)

1. **"NEVER use `~`"** — 3 files (Root CLAUDE.md, critical-facts.txt, Aletheia MEMORY.md)
2. **"NEVER kill other agents"** — 2 files but missing from CLAUDE.md
3. **`poetry run python`** — 3 files (Root CLAUDE.md, Root MEMORY.md, AZ MEMORY.md)
4. **Source of truth rule** — 2 files (Root CLAUDE.md, AZ MEMORY.md)
5. **Dangerous paths** — 2 files (Root CLAUDE.md, AZ MEMORY.md)
6. **Post-merge cleanup** — 2 files (AZ CLAUDE.md, AZ MEMORY.md)
7. **Nested Claude fix** — 2 files with **conflicting advice** (`unset` vs `CLAUDECODE=`)
8. **Expensive workflow re-runs** — 2 files (Two-Strike Rule + AZ MEMORY.md)
9. **Numbered options rule** — 2 files (Root CLAUDE.md, Root MEMORY.md)
10. **Workflow commands** — 3 files (Root CLAUDE.md, Aletheia MEMORY.md, AZ MEMORY.md)

### Missing from CLAUDE.md

- GitHub username (`martymcenroe`) — only in `critical-facts.txt`
- AWS identity — only in `critical-facts.txt`
- "NEVER kill other agents" — only in Aletheia MEMORY.md

## Changes Made

### Root `CLAUDE.md` (universal rules)
- **Added:** Identity section with GitHub username, repos, AWS, domain
- **Added:** "NEVER kill other agents" to Safety section
- **Removed:** 3 resolved gotchas (LLD auto-fix, deadlock fix, test plan validator)
- **Compressed:** Task Timing from 10 lines to 1 line
- **Net:** 122 → 120 lines, 5,009 → 4,747 bytes (-5%)

### AssemblyZero `MEMORY.md`
- **Removed:** 5 items duplicating Root CLAUDE.md (dangerous paths, poetry, source of truth, expensive workflows, key rules)
- **Fixed:** `unset CLAUDECODE` → standardized on `CLAUDECODE=` (matches CLAUDE.md)
- **Removed:** `~` paths in Gemini credentials (replaced with absolute paths)
- **Net:** 49 → 23 lines, 2,637 → 1,027 bytes (-61%)

### Aletheia `MEMORY.md`
- **Removed:** 7 items duplicating Root CLAUDE.md (tilde rule, kill rule, workflow commands, --yes flag, old LLD name, deadlock bug, CLAUDECODE fix)
- **Net:** 34 → 24 lines, 1,909 → 1,078 bytes (-44%)

### Root `MEMORY.md` (cross-project)
- **Removed:** `poetry run python` rule (in Root CLAUDE.md)
- **Removed:** Numbered options rule (in Root CLAUDE.md)
- **Net:** 25 → 23 lines, 1,572 → 1,345 bytes (-14%)

### `critical-facts.txt`
- **Kept as-is** — still useful as PreCompact fallback, but all facts now also in Root CLAUDE.md

## Results

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total user-controllable bytes | 15,049 | 12,119 | **-19%** |
| Total lines | 350 | 310 | **-11%** |
| Cross-file redundancies | 10 | 0 | **Eliminated** |
| Conflicting instructions | 1 | 0 | **Fixed** |
| Identity facts in CLAUDE.md | No | Yes | **Front-loaded** |

## Context Budget Guideline

**Target: <10% initial context consumption** across all projects.

The ~14% figure includes the Claude Code system prompt (~4K+ tokens) which we can't control. Our user-controllable files contribute ~3K tokens (~1.5%). The system prompt is the dominant factor.

**Principles:**
1. CLAUDE.md is the single source of truth — MEMORY.md only for things NOT in CLAUDE.md
2. Identity facts go in CLAUDE.md (front-loaded), not hooks (post-compaction)
3. Reference tables belong in CLAUDE.md only if needed in >50% of sessions
4. Each MEMORY.md entry should state why it's not in CLAUDE.md
