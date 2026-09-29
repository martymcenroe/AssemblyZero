# Implementation Report: Phase 2 (Mechanical hooks)

## Overview
Added support for mechanical build hooks via `.unleashed.json` to allow projects like Palaestra to compile code before testing.

## Changes Made
1. **New Node (`N4_5_mechanical_hooks`)**:
   - Created `assemblyzero/workflows/testing/nodes/mechanical_hooks.py` with `mechanical_hooks` which parses `.unleashed.json` in the project root.
   - If `post_implement_command` is present, it executes it using `subprocess.run(shell=True)`.
   - After execution, it runs `git add .` to automatically stage any newly generated artifacts so they are included in the PR commit.
2. **Graph Integration**:
   - Updated `assemblyzero/workflows/testing/nodes/__init__.py` to export the new node.
   - Updated `assemblyzero/workflows/testing/graph.py` to insert `N4_5_mechanical_hooks` between `N4b_completeness_gate` and `N5_verify_green`.
   - Updated routing in `assemblyzero/workflows/testing/nodes/completeness_gate.py` to route `PASS/WARN` to `N4_5_mechanical_hooks`.
3. **Atlas Updates**:
   - Updated `assemblyzero/workflows/testing/atlas.py` to include `N4_5_mechanical_hooks` at ordinal 8.
   - Shifted all subsequent node ordinals by 1.
   - Updated `TOTAL_STEPS` to 14.

## Testing
- Created `tests/unit/test_mechanical_hooks.py` which mocks a `.unleashed.json` and verifies that the `post_implement_command` runs and stages the files.
- Ensured fail-open conditions are satisfied by running `tools/audit_fail_open.py`.
- Verified `test_completeness_gate.py` and `test_testing_atlas.py` updated to expect the new node.
