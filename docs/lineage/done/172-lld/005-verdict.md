# LLD Review: 172-Feature: Add smoke test that actually runs the workflow after TDD completion

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid addition to the TDD workflow to catch integration issues via subprocess execution of entry points. The architecture and safety considerations are generally sound. However, the design is **BLOCKED** due to a Tier 2 Quality issue: Requirement 5 (configuration/disablement) is missing from the Test Plan, resulting in insufficient test coverage (<95%).

## Open Questions Resolved
- [x] ~~Should smoke tests run in parallel or sequentially?~~ **RESOLVED: Sequentially.** For the MVP, sequential execution reduces complexity (avoiding race conditions on stdout/stderr capture) and resource contention. Given the budget of 30s timeout and expected 5-20 entry points running `--help` (which should be sub-second), the total duration will be negligible. Parallelization can be added later if latency becomes a bottleneck.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | TDD workflow runs smoke test after green phase passes | T080 | ✓ Covered |
| 2 | Smoke test imports and runs the actual entry point (via subprocess) | T020 | ✓ Covered |
| 3 | ImportError/ModuleNotFoundError fails the workflow with clear error message | T030, T040, T070 | ✓ Covered |
| 4 | Smoke test results are recorded in workflow state for reporting | T050, T060 | ✓ Covered |
| 5 | Smoke test can be disabled via configuration for faster iteration | - | **GAP** |

**Coverage Calculation:** 4 requirements covered / 5 total = **80%**

**Verdict:** **BLOCK** (Threshold is 95%)

**Missing Test Scenarios:**
- A test scenario (e.g., T090) is required to verify that if `state["smoke_test_enabled"]` is False, the smoke test logic is skipped and the workflow proceeds or remains in Green state without error.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation regarding Cost, Safety, Security, and Legal tiers.

### Cost
- No issues found.

### Safety
- No issues found.

### Security
- No issues found.

### Legal
- No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- No issues found.

### Observability
- No issues found.

### Quality
- [ ] **Requirement Coverage:** **BLOCK**. The Test Plan in Section 10 misses Requirement 5 ("Smoke test can be disabled..."). Please add a test case to `tests/unit/test_smoke_test_node.py` ensuring the feature respects the disable flag.

## Tier 3: SUGGESTIONS
- **Subprocess Safety:** In `run_smoke_test`, ensure `subprocess.run` is called with `shell=False` to prevent shell injection, even though inputs are globed.
- **Discovery Safety:** In `discover_entry_points`, consider explicitly excluding `__pycache__` or hidden directories (`.*`) to prevent trying to run non-source files if the glob is too permissive.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision