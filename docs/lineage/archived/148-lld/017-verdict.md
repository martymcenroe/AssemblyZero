# LLD Review: 148-Fix: Cross-repo workflow invocation broken by poetry --directory

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD effectively addresses the cross-repo invocation issue by implementing a standard environment variable override pattern (`AGENTOS_TARGET_REPO`) with CLI precedence. The testing strategy is robust, covering all permutations of CLI args, environment variables, and fallback behaviors with 100% automated scenarios.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found. The `AGENTOS_TARGET_REPO` variable explicitly defines the scope (worktree) for the session, adhering to safety protocols by establishing a bounded context.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues
No high-priority issues found.

### Architecture
- [ ] No issues found.

### Observability
- [ ] No issues found.

### Quality
- [ ] No issues found. Section 10 exceeds the 95% coverage threshold and properly defines automated acceptance criteria without human delegation.

## Tier 3: SUGGESTIONS
- **Path Expansion:** Ensure `resolve_target_repo` handles user expansion (e.g., `~` in paths) using `os.path.expanduser` to improve UX for the environment variable.
- **Logic Consolidation:** The LLD mentions logic changes in both `tools/run_requirements_workflow.py` and `agentos/workflows/requirements/nodes/load_input.py`. Ensure these share the same resolution logic (or that the tool passes the resolved path explicitly to the node) to prevent "Source of Truth" drift between the CLI wrapper and the workflow node.
- **Test Harness:** For Test Scenario 080 (Shell wrapper), ensure the `pytest` harness explicitly invokes the `.sh` file via `subprocess` to validate the shell script export logic, as unit testing Python functions alone won't verify the shell wrapper's behavior.

## Questions for Orchestrator
1. None.

## Verdict
[x] **APPROVED** - Ready for implementation
[ ] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision