# LLD Review: 180-Feature: N9 Cleanup Node

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The design for the N9 Cleanup Node is generally robust, employing a good separation of concerns between the node logic and pure helper functions. The safety mechanisms for worktree removal are well-defined. However, the logic for **Lineage Archival** is currently decoupled from the "Success/Merged" state, which means every workflow run (even intermediate ones) will immediately move debugging artifacts from `active/` to `done/`. This hinders developer iteration and debugging.

## Open Questions Resolved
- [x] ~~Should N9 be skipped entirely (route straight to END) when running in dry-run / local-only mode with no PR?~~ **RESOLVED: Yes.** Rely on the `issue_number` check in `route_after_document`. If running locally *with* an issue number, the safety checks (PR merged status) in the node prevent destructive actions, which is sufficient.
- [x] ~~Should the learning summary generation use an LLM call, or should it be purely deterministic extraction from lineage artifacts?~~ **RESOLVED: Deterministic extraction.** Use regex/parsing to extract coverage and iteration counts. It is fast, free, and sufficient for the defined metrics.
- [x] ~~What is the maximum acceptable latency for N9 before it should be made async/optional?~~ **RESOLVED: 10 seconds.** Implement `subprocess.run(timeout=10)` for all external CLI calls (gh, git) to prevent hanging.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | N9 node added to graph (N8→N9→END) | T010, T280, T290 | ✓ Covered |
| 2 | Worktree removed only when PR merged | T060, T070-T110 | ✓ Covered |
| 3 | Local branch deleted after worktree removal | T120-T150 | ✓ Covered |
| 4 | Lineage directory moved active/ to done/ | T160-T180 | ✓ Covered |
| 5 | Learning summary generated in done/ | T190-T230, T260 | ✓ Covered |
| 6 | If PR not merged, skip worktree cleanup | T030, T040 | ✓ Covered |
| 7 | If lineage missing, skip archival | T050 | ✓ Covered |
| 8 | Errors caught and logged (non-fatal) | T270 | ✓ Covered |
| 9 | Learning summary format documented | T240, T250 | ✓ Covered |
| 10 | State updated with N9 fields | T300 | ✓ Covered |

**Coverage Calculation:** 10 requirements covered / 10 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation pending Tier 2 fixes.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found. Worktree removal is correctly guarded by PR status and explicitly avoids `--force`.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Lineage Archival Logic (Developer Experience):**
    *   **Issue:** The current pseudocode (Section 2.5) executes Lineage Archival (Step 3) *unconditionally* if the directory exists, regardless of whether the PR is merged.
    *   **Impact:** If a developer is iterating locally (run -> fail -> fix -> run), the first run's artifacts will be immediately moved to `done/`. The developer expects `active/` to contain the current context for debugging. Moving it prematurely clutters `done/` with intermediate attempts and clears the active workspace.
    *   **Recommendation:** Align Lineage Archival with the "Done" state.
        *   Modify logic: Generate the Learning Summary in `active/` first.
        *   **IF** `pr_merged` is True: Move `active/` to `done/` (including the new summary).
        *   **ELSE**: Leave `active/` in place (containing the new summary) so the developer can inspect it.
    *   *Update REQ-4 and Logic 2.5 to reflect this conditionality.*

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** PASS.

## Tier 3: SUGGESTIONS
- **Timeout Implementation:** Ensure the `subprocess` calls in `cleanup_helpers.py` utilize the `timeout` parameter (e.g., 10s) to prevent the workflow from hanging indefinitely if GitHub is unreachable.
- **Summary Location:** In the "not merged" case, writing the `learning-summary.md` into the `active/` directory is highly beneficial for the developer to quickly see the "Coverage Gap Analysis" without digging into raw logs.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 2 issue (Lineage Archival Logic) first
[ ] **DISCUSS** - Needs Orchestrator decision