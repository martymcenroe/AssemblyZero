# Add Logging to Draft Node

## User Story
As a developer debugging the issue workflow,
I want to see when the draft node starts and completes,
So that I can identify performance bottlenecks.

## Objective
Add timestamp-based console logging to the draft node to provide visibility into execution timing and iteration state.

## UX Flow

### Scenario 1: Normal Workflow Execution
1. Developer runs the issue workflow
2. Draft node begins execution, prints `[HH:MM:SS] Draft node: starting (iteration N)`
3. Draft node completes execution, prints `[HH:MM:SS] Draft node: completed (iteration N)`
4. Result: Developer sees timing and iteration info in console output

### Scenario 2: Multiple Iterations
1. Developer runs workflow that triggers multiple draft iterations
2. Each iteration logs start/complete with incrementing iteration count
3. Result: Developer can trace timing across iterations to spot bottlenecks

## Requirements

### Logging
1. Print a timestamped log line at the start of the `draft()` function
2. Print a timestamped log line at the end of the `draft()` function
3. Include the current iteration count from state in each log line

### Format
1. Timestamp format: `[HH:MM:SS]`
2. Start format: `[HH:MM:SS] Draft node: starting (iteration N)`
3. Complete format: `[HH:MM:SS] Draft node: completed (iteration N)`

## Technical Approach
- **Timestamps:** Use Python's `datetime.datetime.now().strftime("%H:%M:%S")`
- **Output:** Use `print()` statements (no structured logging)
- **Iteration count:** Read from existing state object passed to `draft()`

## Security Considerations
No security impact — this adds console print statements only with no sensitive data.

## Files to Create/Modify
- `nodes/draft.py` — Add print statements at start and end of `draft()` function

## Dependencies
- None

## Out of Scope (Future)
- Structured logging framework — deferred to future issue
- Log file output — console only for now
- Logging in other nodes — only draft node in this issue

## Acceptance Criteria
- [ ] `[HH:MM:SS] Draft node: starting (iteration N)` prints when draft node begins
- [ ] `[HH:MM:SS] Draft node: completed (iteration N)` prints when draft node finishes
- [ ] Timestamps reflect actual wall-clock time
- [ ] Iteration count matches the value in workflow state
- [ ] No logging added to any node other than draft

## Definition of Done

### Implementation
- [ ] Core feature implemented
- [ ] Unit tests written and passing

### Tools
- N/A

### Documentation
- [ ] Update wiki pages affected by this change
- [ ] Add new files to `docs/0003-file-inventory.md`

### Reports (Pre-Merge Gate)
- [ ] `docs/reports/{IssueID}/implementation-report.md` created
- [ ] `docs/reports/{IssueID}/test-report.md` created

### Verification
- [ ] Run 0817 Wiki Alignment Audit - PASS (if wiki updated)

## Testing Notes
Run the workflow and verify console output contains the expected log lines. To test multiple iterations, trigger a workflow state that causes the draft node to execute more than once and confirm iteration counts increment correctly.