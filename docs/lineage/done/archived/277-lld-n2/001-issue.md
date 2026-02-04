---
repo: martymcenroe/AgentOS
issue: 277
url: https://github.com/martymcenroe/AgentOS/issues/277
fetched: 2026-02-04T17:08:38.487596Z
---

# Issue #277: feat: Add mechanical LLD validation node to catch path/consistency errors before Gemini review

## Problem

LLD-272 passed Gemini review but contained critical errors that Python could have caught:

| Error | What Happened | Mechanical Fix |
|-------|---------------|----------------|
| Wrong file paths | `src/nodes/...` instead of `agentos/workflows/testing/nodes/...` | `Path.exists()` check |
| Section inconsistency | Graph runner in Definition of Done but not in Files Changed | Cross-reference parse |
| Risk mitigation not designed | "Track token count" claimed but no function for it | Keyword tracing |

**Root cause:** We trusted LLMs (Claude drafting, Gemini reviewing) to catch errors that are trivially detectable with Python. LLMs are unreliable. Mechanical validation is deterministic.

## Solution

### 1. Add `validate_lld_mechanical` Node to LangGraph

Insert BEFORE Gemini review in the requirements workflow graph:

```
generate_draft → validate_lld_mechanical → human_gate → review
```

**Checks to implement:**

```python
def validate_lld_mechanical(state: RequirementsWorkflowState) -> RequirementsWorkflowState:
    """Mechanical validation - no LLM judgment. Fail hard on errors."""
    
    lld_content = state["current_draft"]
    repo_root = Path(state["repo_root"])
    errors = []
    
    # 1. Parse Section 2.1 file table
    files = parse_files_changed_table(lld_content)
    
    # 2. Validate paths exist (for Modify/Delete)
    for f in files:
        path = repo_root / f["path"]
        if f["change_type"] in ("Modify", "Delete"):
            if not path.exists():
                errors.append(f"Section 2.1: '{f['path']}' marked {f['change_type']} but does not exist")
        elif f["change_type"] == "Add":
            if not path.parent.exists():
                errors.append(f"Section 2.1: Parent directory for '{f['path']}' does not exist")
    
    # 3. Detect placeholder prefixes (src/, lib/, app/)
    for f in files:
        if f["path"].startswith(("src/", "lib/", "app/")):
            # Check if this prefix actually exists in repo
            prefix = f["path"].split("/")[0]
            if not (repo_root / prefix).exists():
                errors.append(f"Section 2.1: '{f['path']}' uses '{prefix}/' but that directory doesn't exist")
    
    # 4. Cross-reference Definition of Done with Files Changed
    dod_files = extract_files_from_section(lld_content, "## 12. Definition of Done")
    fc_files = {f["path"] for f in files}
    missing = dod_files - fc_files
    if missing:
        errors.append(f"Section 12 references files not in Section 2.1: {missing}")
    
    # 5. Trace risk mitigations to implementation
    mitigations = extract_mitigations_from_risks(lld_content)  # Section 11
    functions = extract_function_names(lld_content)  # Section 2.4
    for mitigation in mitigations:
        keywords = extract_keywords(mitigation)  # e.g., "token count" -> ["token", "count"]
        if not any(kw in func.lower() for kw in keywords for func in functions):
            errors.append(f"Section 11 claims '{mitigation}' but no matching function in Section 2.4")
    
    # 6. FAIL HARD if any errors
    if errors:
        state["validation_errors"] = errors
        state["lld_status"] = "BLOCKED"
        state["error"] = "MECHANICAL VALIDATION FAILED:\n" + "\n".join(f"  - {e}" for e in errors)
        return state
    
    return state
```

### 2. Update Template (0102-feature-lld-template.md)

**Add Section 2.1.1:**

```markdown
### 2.1.1 Path Validation (Mechanical - Auto-Checked)

Before Gemini review, paths are verified programmatically:
- All "Modify" files must exist in repository
- All "Add" files must have existing parent directories  
- All "Delete" files must exist in repository
- No placeholder prefixes (`src/`, `lib/`, `app/`) unless directory exists

If validation fails, the LLD is BLOCKED before reaching Gemini.
```

**Add Section 12.1:**

```markdown
### 12.1 Traceability (Mechanical - Auto-Checked)

- Every file mentioned in this section must appear in Section 2.1
- Every risk mitigation in Section 11 must have corresponding function in Section 2.4
```

### 3. Update Review Prompt (0702c)

Add to Gemini instructions:

> "Note: File paths and section cross-references are validated mechanically before this review. Focus on design quality, not path correctness."

This clarifies Gemini's role: design review, not filesystem validation.

## Implementation Changes

| File | Change |
|------|--------|
| `agentos/workflows/requirements/nodes/validate_mechanical.py` | New file - mechanical validation node |
| `agentos/workflows/requirements/graph.py` | Insert node before review |
| `agentos/workflows/requirements/state.py` | Add `validation_errors: list[str]` field |
| `docs/templates/0102-feature-lld-template.md` | Add sections 2.1.1 and 12.1 |
| `docs/templates/0702c-*.md` | Update Gemini instructions |

## Acceptance Criteria

- [ ] Mechanical validation runs before Gemini review
- [ ] Invalid paths (Modify file doesn't exist) → BLOCKED with clear error
- [ ] Placeholder prefixes without matching directory → BLOCKED
- [ ] Definition of Done / Files Changed mismatch → BLOCKED  
- [ ] Risk mitigation without implementation → WARNING (non-blocking initially)
- [ ] LLD-272's errors would be caught by this gate
- [ ] Template updated with new sections
- [ ] Review prompt updated

## Out of Scope

- Semantic validation (that's Gemini's job)
- Syntax validation of pseudocode
- Any check requiring LLM judgment

## Why This Matters

Every LLD that passes review with bad paths wastes:
- Gemini tokens on reviewing broken specs
- Implementation time discovering errors
- User time debugging "file not found"

Mechanical validation catches these in <1 second with zero tokens.