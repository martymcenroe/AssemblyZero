# Implementation Report: Multi-framework Execution (#3677)

## Overview
Implemented Phase 3 of the testing pipeline upgrades to support repositories with a "physics split" (a Python package at the root and a web app under its own directory) by allowing concurrent testing frameworks (Pytest and Vitest).

## Changes Made
1. **Framework Detection**: Upgraded `framework_detector.py` to return a `list[TestFramework]` instead of a singular framework.
2. **State & Orchestrator**: Adjusted `TestingWorkflowState` to use a list of `framework_configs` and mapped the new list structure in `load_lld.py`.
3. **Execution Logic**: Handled the extraction of single-framework execution blocks in `verify_phases.py` (`_verify_red_pytest_single`, `_verify_green_pytest_single`) and built loop wrappers (`verify_red_phase`, `verify_green_phase`) that aggregate the outputs, min coverage, and max exit codes across frameworks.
4. **Registry & Test Alignments**: Fixed `gate_registry.py` and unit tests (`test_n4_keeps_passing_tests.py`, `test_iteration_isolation.py`, etc.) to align with the new function names and behaviors.
5. **Fail-Open Audit**: Updated the fail-open baseline.
