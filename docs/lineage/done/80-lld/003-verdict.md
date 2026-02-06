# LLD Review: 180-Feature: Adversarial Testing Workflow

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate: PASSED
All required elements present.

## Review Summary
The LLD proposes a robust adversarial testing workflow using a separate LLM (Gemini Enterprise) to verify implementation integrity. The security posture is strong with mandatory containerization and AST-based scanning. However, the design is **BLOCKED** due to a Requirement Coverage gap regarding the governance workflow integration (Req 12). While the module logic is well-tested, the integration point into the existing issue runner is not covered by the test plan.

## Open Questions Resolved
- [x] ~~Should adversarial testing run on every commit, before PR, or on-demand?~~ **RESOLVED: Stick to the N2.5 gate (on-demand/pre-review) as specified to control costs. Mandatory on-commit runs should only be enabled for security-critical paths.**
- [x] ~~What scoring mechanism should be used for Testing LLM performance?~~ **RESOLVED: Prioritize "Valid Bugs Found" (True Positives). Apply strict penalties for "Invalid Test Code" (False Positives) or hallucinations.**
- [x] ~~Should Testing LLM be allowed to suggest fixes, or remain purely adversarial?~~ **RESOLVED: Purely adversarial. Separation of concerns is vital; the Implementation LLM must solve the problem, the Testing LLM only finds flaws.**
- [x] ~~What is the fallback if Docker is not available on the developer's machine?~~ **RESOLVED: Fail fast with a clear error. As stated in Section 2.6, containerization is mandatory for security.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Orchestrator runs verification scripts in mandatory Docker | T080, T190 | ✓ Covered |
| 2 | Orchestrator requires user confirmation before execution | T020 | ✓ Covered |
| 3 | `--dry-run` mode displays script content without execution | T010 | ✓ Covered |
| 4 | Shell script inspection blocks dangerous commands | T030, T040 | ✓ Covered |
| 5 | Verification scripts timeout after 5 minutes | T040 | ✓ Covered |
| 6 | Adversarial test suites timeout after 10 minutes | T140 | ✓ Covered |
| 7 | Testing LLM receives implementation and generates tests | T060, Scen 080 | ✓ Covered |
| 8 | Adversarial tests execute without mocks for subprocess/external calls | Scen 080 (Implicit) | ✓ Covered |
| 9 | ImportError and ModuleNotFoundError trigger FAILED_IMPORT | T050 | ✓ Covered |
| 10 | Edge cases (unicode, paths with spaces) are covered | Scen 120, 130 | ✓ Covered |
| 11 | Mocked "integration tests" are flagged as false claims | Scen 110 | ✓ Covered |
| 12 | N2.5 gate integrates into existing issue governance workflow | - | **GAP** |
| 13 | Failure reports include exact test output and claim violated | T070 | ✓ Covered |
| 14 | Per-run costs are logged to CSV | T090, Scen 150 | ✓ Covered |
| 15 | Environment variables are sanitized before script execution | T100, Scen 180 | ✓ Covered |

**Coverage Calculation:** 14 requirements covered / 15 total = **93.3%**

**Verdict:** **BLOCK** (Must be ≥95%)

**Missing Test Scenarios:**
- Requirement #12 (Governance Integration) requires a test verifying that `tools/run_issue_workflow.py` correctly triggers the adversarial gate when conditions are met. Add test: `test_workflow_runner_invokes_adversarial_gate`.

## Tier 1: BLOCKING Issues
No Tier 1 issues found. LLD is solid on Cost, Safety, Security, and Legal fronts.

### Cost
- [ ] No issues found. Model tiering and cost caps are appropriate.

### Safety
- [ ] No issues found. Mandatory containerization and timeouts address safety risks.

### Security
- [ ] No issues found. AST scanning and network isolation provide depth-in-defense.

### Legal
- [ ] No issues found. ZDR usage is specified.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** **BLOCK.** Coverage is 93.3%. Please add a test case for Requirement 12 (integration of the N2.5 gate into `run_issue_workflow.py`) to Section 10.1 and the TDD plan.

## Tier 3: SUGGESTIONS
- **Cost Estimation:** Ensure the `estimate_cost` function accounts for the token count of the *input* implementation files, not just the output generation, as large implementation files will consume significant context window tokens.
- **Testing Strategy:** For Requirement 8 (No mocks in adversarial tests), consider adding a specific instruction to the Testing LLM system prompt to explicitly forbid using `unittest.mock` or `monkeypatch` in generated tests, and potentially add a scan check for `import mock` in the resulting code.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision