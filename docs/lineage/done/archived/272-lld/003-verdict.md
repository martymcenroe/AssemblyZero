# LLD Review: 1272-Bug: Implementation Node Claude Gives Summary Instead of Code

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a robust structural change (file-by-file iteration) to resolve the "summary instead of code" issue. The shift from instruction-based control to mechanical validation is sound. However, there is a critical discrepancy between the Safety section and the Logic flow regarding file overwrite protections, and an architectural concern regarding the "Hard Failure" implementation within a graph node.

## Open Questions Resolved
- [x] ~~Should we support modification of existing files or only new file creation?~~ **RESOLVED: Support both.**
- [x] ~~What is the minimum line threshold for non-trivial files?~~ **RESOLVED: 5 lines.**
- [x] ~~Should syntax validation be language-specific or Python-only initially?~~ **RESOLVED: Python-only initially, extensible.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Implementation node iterates file-by-file through LLD's file list | T090 | ✓ Covered |
| 2 | Each file prompt includes full LLD + all previously completed files as context | T080 | ✓ Covered |
| 3 | Each response is mechanically validated (code block exists, not empty, parses) | T050, T060, T070 | ✓ Covered |
| 4 | First validation failure kills workflow immediately with clear error | T100 | ✓ Covered |
| 5 | No retries - one shot per file | T100 | ✓ Covered |
| 6 | Error message clearly identifies which file failed and why | T060, T070 | ✓ Covered |
| 7 | Previously-failing #225 scenario produces code (not summary) | T090 (Success), T040 (Fail case) | ✓ Covered |

**Coverage Calculation:** 7 requirements covered / 7 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues

### Cost
- [ ] No issues found.

### Safety
- [ ] **Destructive Logic Mismatch:** Section 7.2 states "Check change_type; confirm Modify vs Add" as a safety mitigation for overwriting files. However, Section 2.5 (Logic Flow) Step 3f simply says "Write file to disk" without any check against `FileSpec.change_type`. The logic must explicitly verify that `Modify` targets exist and `Add` targets do not (or explicitly allow overwrite if intended), matching the safety strategy.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Hard Failure Mechanism:** Section 2.5 and 2.6 describe "Fail Hard" as "Exit immediately". In the context of a `LangGraph` node (`src/nodes/implement_code.py`), calling `sys.exit()` is an anti-pattern as it kills the runner process abruptly, potentially preventing state persistence or proper graph teardown. **Recommendation:** Raise a specific typed exception (e.g., `ImplementationError`) that the graph runner catches to exit non-zero, rather than calling `sys.exit()` directly inside the node logic.
- [ ] **State Field Naming:** Section 2.3 defines `completed_files` in `ImplementationState`. Verify this doesn't conflict with any existing `files` or `code` fields in the global state object.

### Observability
- [ ] **Tracing Gap:** The new loop structure involves multiple LLM calls. The LLD does not explicitly mention LangSmith context propagation or tracing tags for these iterative calls. **Recommendation:** Ensure `trace_id` is propagated to the `build_single_file_prompt` and API calls for debugging.

### Quality
- [ ] **Unchecked Budget:** Section 8.2 contains an unchecked checkbox: `[ ] Budget alerts configured at $100 threshold`. Please confirm this is configured or remove the checkbox if not a prerequisite for this specific PR.

## Tier 3: SUGGESTIONS
- **Pseudocode Update:** Explicitly add the `files_to_create[:50]` cap mentioned in Section 7.2 to the logic in Section 2.5 to make the loop bound concrete.
- **Validation Details:** Consider adding "blacklisted phrases" (e.g., "Here is the summary") to the mechanical validator as a fail-fast mechanism before parsing AST.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision