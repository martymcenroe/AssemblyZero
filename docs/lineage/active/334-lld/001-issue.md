---
repo: martymcenroe/AgentOS
issue: 334
url: https://github.com/martymcenroe/AgentOS/issues/334
fetched: 2026-02-05T13:21:06.988300Z
---

# Issue #334: bug: LLD workflow infinite loop - 'Add (Directory)' silently skipped, errors not printed

## Summary

The LLD workflow can loop indefinitely (17+ iterations observed) when an LLD declares directory creation using "Add (Directory)" change type. Three compounding bugs cause this:

1. **"Add (Directory)" entries silently skipped** - Validator ignores them
2. **Validation errors not printed** - User sees "failed" but never WHY
3. **No error audit trail** - Errors not saved to lineage folder

## Reproduction

```bash
# On RCA-PDF-extraction-pipeline repo, issue #25
poetry run python tools/run_requirements_workflow.py --type lld --gates none --yes --repo /path/to/RCA-PDF --issue 25
```

Output shows 17 drafts, all failing with:
```
[ROUTING] Mechanical validation failed - returning to drafter
```

No details about WHAT failed. Lineage folder has 17 drafts but zero error files.

## Root Cause #1: Silent Skip of Directory Entries

**File:** `validate_mechanical.py` lines 450, 468-469

```python
valid_change_types = {"add", "modify", "delete", "create", "update", "remove"}
...
if change_type_lower not in valid_change_types:  # "add (directory)" NOT in set!
    continue  # SILENTLY SKIPPED
```

LLD correctly declares:
| Path | Change Type | Result |
|------|-------------|--------|
| `src/ingestion/` | Add (Directory) | **SKIPPED** |
| `src/ingestion/__init__.py` | Add | **FAILS** (parent missing) |

The directory entry is ignored, then the file entry fails because its parent doesn't exist.

## Root Cause #2: Errors Not Printed

**File:** `graph.py` line 153

```python
print("    [ROUTING] Mechanical validation failed - returning to drafter")
# Says WHAT but not WHY - state["error_message"] is never printed
```

The actual errors exist in state but user never sees them:
```
MECHANICAL VALIDATION FAILED:
  - Parent directory does not exist for Add file: src/ingestion/__init__.py
  - Parent directory does not exist for Add file: src/ingestion/modules/__init__.py
```

## Root Cause #3: No Audit Trail

Lineage folder after 17 failures:
```
docs/lineage/active/25-lld/
├── 001-issue.md
├── 002-draft.md  (no error saved)
├── 003-draft.md  (no error saved)
...
└── 017-draft.md  (no error saved)
```

No record of WHY each draft failed.

## Proposed Fixes

### Fix #1: Normalize Change Types

```python
# In parse_files_changed_table()
change_type = match.group(2).strip()

# Normalize "Add (Directory)" → "Add"
if "(" in change_type:
    change_type = change_type.split("(")[0].strip()
```

### Fix #2: Print Errors in Router

```python
def route_after_validate(state):
    if state.get("lld_status") == "BLOCKED":
        errors = state.get("validation_errors", [])
        if errors:
            print("    [VALIDATION ERRORS]")
            for err in errors[:5]:
                print(f"      - {err}")
        print("    [ROUTING] Returning to drafter")
        return "N1_generate_draft"
```

### Fix #3: Save Errors to Lineage

Save validation errors to lineage folder (e.g., `002-validation-errors.md`) so there's an audit trail.

## Impact

- Workflow loops until max iterations (20) or user interrupt
- ~2 minutes wasted per draft × 17 drafts = ~34 minutes of API calls
- User has no visibility into what's wrong
- No audit trail for debugging

## Files to Modify

| File | Change |
|------|--------|
| `agentos/workflows/requirements/nodes/validate_mechanical.py` | Normalize change types |
| `agentos/workflows/requirements/graph.py` | Print validation errors |
| `agentos/workflows/requirements/nodes/validate_mechanical.py` | Save errors to lineage |

## Labels

`bug`, `workflow`, `priority:high`