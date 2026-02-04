# LLD Review: #194-Feature: Lu-Tze: The Janitor - Automated Repository Hygiene Workflow

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a solid foundation for the automated hygiene workflow using LangGraph. The design is modular and follows the "Sweeper -> Fixer -> Reporter" pattern well. However, implementation is **BLOCKED** primarily due to Tier 1 Safety concerns regarding destructive worktree pruning operations that occur outside the repository root, and undefined interfaces for the Harvest probe dependencies. These must be addressed before coding begins.

## Open Questions Resolved
- [x] ~~Should worktree staleness threshold (14 days) be configurable via CLI or config file?~~ **RESOLVED: Yes, add `--worktree-days` CLI argument (default: 14) to allow adjustment without code changes.**
- [x] ~~For the harvest probe, should we create a new issue or integrate with existing AgentOS issue tracking?~~ **RESOLVED: Integrate findings into the single "Janitor Report" issue to maintain the workflow's aggregation pattern and reduce notification noise.**
- [x] ~~What is the exact format expected from `agentos-harvest.py` for the harvest probe integration?~~ **RESOLVED: Define strict contract: `{"drift_detected": bool, "files": list[str], "summary": str}`. Fail gracefully if output differs.**
- [x] ~~Should `--create-pr` require a specific branch naming convention?~~ **RESOLVED: Yes, enforce `janitor/fix-{timestamp}` to ensure uniqueness and allow programmatic identification of Janitor-created branches.**

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Executes all probes | T130, T140, T150 | ✓ Covered |
| 2 | `--dry-run` flag shows pending fixes without modification | T090 | ✓ Covered |
| 3 | Broken markdown links auto-fixed | T070 | ✓ Covered |
| 4 | Stale worktrees automatically pruned | T080 | ✓ Covered |
| 5 | Unfixable issues create/update "Janitor Report" | T100 | ✓ Covered |
| 6 | Existing report updated (not duplicated) | T110 | ✓ Covered |
| 7 | `--silent` mode produces no stdout | T160 | ✓ Covered |
| 8 | Exit code 0 (clean) vs 1 (issues) | T160, T170 | ✓ Covered |
| 9 | `--reporter local` writes to files | T120 | ✓ Covered |
| 10 | CI execution with `GITHUB_TOKEN` authenticates | T100 (Auto-Live) | ✓ Covered |
| 11 | Probe crashes are isolated | T140 | ✓ Covered |

**Coverage Calculation:** 11 requirements covered / 11 total = **100%**

**Verdict:** PASS

## Tier 1: BLOCKING Issues

### Cost
- [ ] No issues found.

### Safety
- [ ] **Worktree Scope Violation (CRITICAL):** The `WorktreesProbe` and `Fixer` operate on git worktrees which, by definition, may reside *outside* the repository root. While necessary for the feature, this violates the standard safety rule "All file operations must be scoped to the worktree."
    *   **Recommendation:** You must implement a "Double-Check" mechanism in `Fixer.fix_stale_worktree`. Before calling `git worktree remove`, the code must explicitly verify that the target path is currently listed in `git worktree list --porcelain`. Do not rely on cached probe results. This prevents accidental deletion of non-worktree directories if the state drifts.
- [ ] **Destructive Act Confirmation:** `git worktree remove` deletes files.
    *   **Recommendation:** Ensure the `--auto-fix` flag is explicitly required for this operation. If `--auto-fix` is false, the Fixer must strictly SKIP these operations (as per logic flow), not prompt interactively (to ensure headless safety).

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Undefined Dependency Interface:** The design relies on `agentos-harvest.py` but Section 1 explicitly states the format is unknown. You cannot implement a probe without a defined schema.
    *   **Recommendation:** Formalize the expected JSON schema in `agentos/workflows/janitor/state.py` (as resolved in Open Questions) and add validation logic in `HarvestProbe`.
- [ ] **Git Worktree Logic:** The definition of "Stale" in `_is_stale` (14 days AND (merged OR deleted)) is safe, but verifying "merged OR deleted" for a detached worktree can be complex.
    *   **Recommendation:** Ensure `_is_stale` handles the "detached head" state gracefully where no branch name is associated.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Gap in Unit Testing for Auth:** Requirement 10 is covered by Integration test T100, but there is no *Unit* test verifying that `GitHubReporter` correctly reads `GITHUB_TOKEN` from the environment when `gh` CLI is not interactive.
    *   **Recommendation:** Add a unit test `T105` mocking `os.environ` to verify `_check_gh_auth` logic without calling external APIs.

## Tier 3: SUGGESTIONS
- **CLI:** Consider adding a `--force` flag for worktree pruning to override safety checks if absolutely necessary (but keep it hidden/advanced).
- **Performance:** `git blame` in `TodoProbe` can be very slow on large files. Consider a file size limit or line count limit for the blame lookup.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision