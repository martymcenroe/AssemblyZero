---
repo: martymcenroe/AssemblyZero
issue: 409
url: https://github.com/martymcenroe/AssemblyZero/issues/409
fetched: 2026-02-19T16:36:14.046779Z
---

# Issue #409: Implementation spec workflow: four minor context gaps

## Context

Investigation of the implementation spec workflow found it has **excellent** codebase context injection overall (unlike the requirements workflow, issue #401). However, four minor gaps were identified during the review.

None are blocking. All are polish-level improvements.

## Gap 1: No CLAUDE.md or README injection

**Current:** The spec generator receives LLD + file excerpts + pattern references.
**Missing:** Project-specific rules (CLAUDE.md), README guidance, and architecture docs.
**Impact:** Low — patterns usually contain style guidance implicitly.
**Fix:** Add `read_key_project_files()` call (from #401's shared module `core/codebase_analysis.py`) to `analyze_codebase` node.

## Gap 2: Pattern references are line-based, not full-file

**Current:** `find_pattern_references()` returns first 50-100 lines of similar files.
**Concern:** If the relevant pattern spans lines 150-200, the spec only sees lines 1-100.
**Impact:** Very low — signatures and docstrings are usually in the first 50 lines.
**Fix:** Use AST-based summarization (same as file excerpts) instead of head-N truncation for Python pattern files.

## Gap 3: No cross-file dependency analysis

**Current:** Each file in Section 2.1 is analyzed independently.
**Missing:** How files import/depend on each other (e.g., "this node imports from state.py").
**Impact:** Low — LLD Section 2.1 should document dependencies, but the spec generator doesn't verify or augment this.
**Fix:** Parse import statements from each file and cross-reference against the files_to_modify list.

## Gap 4: Prompt truncation drops the middle

**Current:** When prompt exceeds 120KB, `_truncate_prompt()` keeps first 40% + last 30% and drops the middle.
**Risk:** If critical file excerpts or pattern references land in the middle of the prompt, they're lost silently.
**Impact:** Low — truncation only triggers at 120KB (rare in practice).
**Fix:** Truncate by dropping lowest-relevance pattern references (whole items) instead of slicing the prompt string. Same approach as Issue #373's lesson: drop whole files, never truncate mid-content.

## Relationship to Other Issues

- **#401** (requirements workflow context injection) — the shared module (`core/codebase_analysis.py`) created for #401 can be reused for Gap 1 and Gap 2 here.
- **#373** (file summarization) — Gap 4's fix follows the same principle.

## Acceptance Criteria

- [ ] Spec generator receives CLAUDE.md/README from target repo
- [ ] Pattern references use AST summarization instead of head-N
- [ ] Import dependencies cross-referenced for files_to_modify
- [ ] Prompt truncation drops whole items by relevance, not mid-string slicing