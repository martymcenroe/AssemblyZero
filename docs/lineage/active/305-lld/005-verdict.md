# LLD Review: 305 - Feature: End-to-End Orchestration Workflow (Issue → Code)

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate: PASSED
All required elements (Issue Link, Context, Proposed Changes) are present.

## Review Summary
This LLD provides a robust design for a meta-workflow orchestrator using LangGraph. The architecture properly modularizes the stages, ensuring the orchestrator acts as a coordinator rather than a monolith. The state management and persistence strategy are well-defined, and the test plan covers all requirements with 100% mapping.

## Open Questions Resolved
- [x] ~~Should the orchestrator support running multiple issues in parallel (batch mode)?~~ **RESOLVED: No.** V1 should be strictly sequential per process. Parallelism adds complexity (log interleaving, race conditions) that is better handled by the user running multiple terminal instances if absolutely necessary.
- [x] ~~What's the retry strategy for external service failures (GitHub API, LLM providers)?~~ **RESOLVED: Exponential Backoff.** Use `tenacity` or LangGraph's built-in retry policies. Suggest: Initial wait 2s, multiplier 2x, max wait 30s, max retries 3. Differentiate between transient (5xx) and permanent (4xx) errors.
- [x] ~~Should stage artifacts be stored in worktree or separate orchestration directory?~~ **RESOLVED: Split Strategy.**
    1.  **Project Artifacts** (LLD, Spec, Code) MUST be stored in the standard repository structure (worktree) to be committed.
    2.  **Orchestration State** (JSON state, locks) MUST be stored in a git-ignored directory (e.g., `.assemblyzero/state/`) to prevent polluting the repo.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Single `orchestrate --issue N` command processes issue from creation to PR | T010 | ✓ Covered |
| 2 | Pipeline handles existing artifacts (skips stages) | T020, T140 | ✓ Covered |
| 3 | State persists between runs to allow resume | T030, T100, T110 | ✓ Covered |
| 4 | Human gates configurable at any stage transition | T040 | ✓ Covered |
| 5 | Dry-run mode shows planned execution | T050 | ✓ Covered |
| 6 | Clear progress reporting (stage, duration, artifacts) | T060 | ✓ Covered |
| 7 | Failed stages report actionable error messages | T070 | ✓ Covered |
| 8 | Resume-from flag allows skipping to specific stage | T080 | ✓ Covered |
| 9 | Concurrent orchestration of same issue prevented via lock file | T090 | ✓ Covered |

**Coverage Calculation:** 9 requirements covered / 9 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found. Retry limits and skip-logic for existing artifacts are adequate cost controls.

### Safety
- [ ] No issues found. Worktree scoping and "Fail Closed" strategy are defined.

### Security
- [ ] No issues found. Secret handling via env vars is standard.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues
No high-priority issues found.

### Architecture
- [ ] No issues found. Path structure matches validated hierarchy.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** PASS (100%).

## Tier 3: SUGGESTIONS
- **State Location:** Explicitly define the path for `save_orchestration_state` in the implementation (e.g., `.assemblyzero/orchestrator/state/{issue_id}.json`) and ensure this directory is added to `.gitignore`.
- **Worktree Isolation:** Ensure the "Ensure worktree exists or create it" step in the `impl` stage uses `git worktree add` (creating a separate directory) rather than switching the main repository's branch. This allows the orchestrator to run in the main repo while the "work" happens in an isolated folder, preventing disruption if the user is working in the main repo.
- **Tracing:** Explicitly configure LangSmith tracing for the orchestrator graph to visualize the meta-flow execution in addition to the sub-workflow traces.

## Questions for Orchestrator
1. None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision