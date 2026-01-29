# Issue Review: Per-Repo Workflow Database

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Technical Product Manager & Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The issue is structurally sound with clear user stories and technical approach. However, it contains a critical ambiguity regarding failure states (safety) and a contradiction regarding the scope of migration tools. These must be resolved to ensure the "Definition of Ready."

## Tier 1: BLOCKING Issues

### Security
- [ ] No blocking issues found.

### Safety
- [ ] **Undefined Fail-Safe Strategy:** Under *Requirements > Database Location Logic*, item 4 states: "Graceful error if repo root cannot be determined (fall back to global?)". This is an open question, not a requirement. Undefined fallback behavior poses a data safety risk (accidental corruption of global state).
    *   **Recommendation:** Change to a declarative statement. **Fail Closed** is recommended (e.g., "If repo root cannot be determined and no env var is set, exit with error message").

### Cost
- [ ] No blocking issues found.

### Legal
- [ ] No blocking issues found.

## Tier 2: HIGH PRIORITY Issues

### Quality
- [ ] **Scope Contradiction:**
    *   "Out of Scope" states: "Automatic migration of existing checkpoints... is out of scope".
    *   "Files to Create" lists: `tools/migrate_workflow_db.py`.
    *   "Definition of Done" lists: "Create optional migrate_workflow_db.py script".
    *   **Recommendation:** Clarify if the migration script is part of this ticket or a future task. If it is in this ticket, remove it from "Out of Scope".
- [ ] **Acceptance Criteria Feasibility:** The criteria "Running 150 concurrent workflows across repos causes no conflicts" is quantifiable but difficult to verify manually.
    *   **Recommendation:** Specify *how* this is verified (e.g., "via provided bash script `tests/stress_test.sh`") or reduce to a reasonable manual test number (e.g., 3 concurrent sessions).

### Architecture
- [ ] No blocking issues found.

## Tier 3: SUGGESTIONS
- **Taxonomy:** Add labels `enhancement`, `workflow`, `dx`.
- **Effort:** Add T-shirt size estimate (Likely "Small").

## Questions for Orchestrator
1. Should the system default to "Fail Closed" (error) if not in a repo, or strictly require an Environment Variable for non-repo execution?

## Verdict
[ ] **APPROVED** - Ready to enter backlog
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision