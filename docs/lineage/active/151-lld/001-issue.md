# Issue #151: fix: --select flag defined but never implemented in run_requirements_workflow.py

## Severity: MEDIUM

## Problem

The `--select` flag is defined in argparse and checked in validation, but NO interactive picker code exists. The feature is documented in runbooks but completely non-functional.

## Location

**File:** `tools/run_requirements_workflow.py`

**Defined (line 90-93):**
```python
parser.add_argument(
    "--select",
    action="store_true",
    help="Interactively select input file/issue",
)
```

**Checked (lines 318-324):**
```python
if args.type == "issue" and not args.brief and not args.select:
    print("ERROR: --brief or --select required for issue workflow")
    return 1

if args.type == "lld" and not args.issue and not args.select:
    print("ERROR: --issue or --select required for LLD workflow")
    return 1
```

**Implementation:** NONE - no picker code anywhere

## Impact

- Users who pass `--select` get validation to pass but then nothing happens
- Feature documented in `docs/runbooks/0907-unified-requirements-workflow.md`
- Issue #95 "Add --select flag and LLD status tracking" was closed but feature incomplete

## Expected Behavior

When `--select` is passed:
- For issue workflow: Show interactive picker of files in `ideas/active/`
- For LLD workflow: Show interactive picker of open GitHub issues

## Suggested Implementation

Use `fzf`, `inquirer`, or simple numbered menu to let user select.

## Found By

Comprehensive codebase scan for stub implementations.

## Related

- Issue #95 (closed but incomplete)