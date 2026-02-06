# Test Report: --auto CLI Flag

**Branch:** `auto-cli-flag`
**Date:** 2026-01-28

## Test Command

```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero-auto-cli-flag python test_auto_mode.py
```

## Test Output

```
============================================================
Testing --auto CLI Flag Implementation
============================================================

Test 1 PASS: --auto flag sets AGENTOS_AUTO_MODE=1

Test 2a PASS: Auto-send check (line 144) returns True
Test 2b PASS: VS Code skip check (line 209) returns True
Test 2c PASS: Verdict preview skip check (line 253) correct
Test 2d PASS: Done folder open check (line 375) returns True

Test 3 PASS: TEST_MODE correctly takes priority over AUTO_MODE

============================================================
ALL TESTS PASSED
============================================================
```

## Test Descriptions

### Test 1: Flag Sets Environment Variable
Verifies that passing `--auto` to `run_issue_workflow.py` correctly sets `AGENTOS_AUTO_MODE=1` in the environment.

**Method:** Simulates argparse with `['run_issue_workflow.py', '--select', '--auto']` and verifies env var is set.

### Test 2: Auto Mode Code Paths
Verifies all four locations that check `AGENTOS_AUTO_MODE` work correctly:

| Test | File | Line | Check |
|------|------|------|-------|
| 2a | `human_edit_draft.py` | 144 | `== "1"` for auto-send |
| 2b | `human_edit_draft.py` | 209 | `== "1"` for VS Code skip |
| 2c | `human_edit_verdict.py` | 253 | `!= "1"` for preview skip |
| 2d | `file_issue.py` | 375 | `== "1"` for done folder |

### Test 3: TEST_MODE Priority
Verifies that when both `AGENTOS_TEST_MODE` and `AGENTOS_AUTO_MODE` are set, TEST_MODE takes priority (expected behavior per code structure at lines 138-147).

## Additional Verification

### Help Output Verification
```bash
$ poetry run python tools/run_issue_workflow.py --help
```

Output confirms `--auto` flag is documented:
```
options:
  --auto           Auto mode: skip VS Code, auto-send to Gemini, open done/ at end
```

### Docstring Verification
The module docstring at `run_issue_workflow.py:1-18` includes:
- Usage example: `python tools/run_issue_workflow.py --select --auto`
- Option description: `--auto  Auto mode: skip VS Code, auto-send to Gemini, open done/ at end`

## Skipped Tests

| Test | Reason |
|------|--------|
| Full workflow with `--auto` only | Would require interactive idea selection (no TEST_MODE) |
| Integration with actual VS Code | Requires VS Code installed and functioning |
| Integration with actual Gemini | Would consume API quota |

## Coverage

All code paths that check `AGENTOS_AUTO_MODE` have been verified:
- 4/4 env var checks tested
- Argument parsing tested
- Help output verified
- Priority with TEST_MODE verified
