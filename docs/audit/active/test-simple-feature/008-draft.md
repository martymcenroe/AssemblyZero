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
2. Draft node begins execution, prints `[HH:MM:SS] Draft node: starting (iteration N)` to stderr
3. Draft node completes execution, prints `[HH:MM:SS] Draft node: completed (iteration N)` to stderr
4. Result: Developer sees timing and iteration info in console output without polluting stdout

### Scenario 2: Multiple Iterations
1. Developer runs workflow that triggers multiple draft iterations
2. Each iteration logs start/complete with incrementing iteration count
3. Result: Developer can trace timing across iterations to spot bottlenecks

### Scenario 3: Missing Iteration Key
1. Developer runs workflow where state does not contain an `iteration` key
2. Draft node safely defaults iteration to `1` instead of crashing
3. Result: Logging works gracefully without `KeyError`

## Requirements

### Logging
1. Log a timestamped line to stderr at the start of the `draft()` function
2. Log a timestamped line to stderr at the end of the `draft()` function
3. Include the current iteration count from state in each log line, defaulting to `1` if missing

### Format
1. Timestamp format: `[HH:MM:SS]`
2. Start format: `[HH:MM:SS] Draft node: starting (iteration N)`
3. Complete format: `[HH:MM:SS] Draft node: completed (iteration N)`

## Technical Approach
- **Timestamps:** Use Python's `datetime.datetime.now().strftime("%H:%M:%S")`
- **Output:** Use `print(..., file=sys.stderr)` to write exact-format strings to stderr. This avoids stdout pollution that could corrupt piped/programmatic output, and avoids the default `logging` module metadata (e.g., `INFO:root:...`) which would conflict with the exact string format required by the Acceptance Criteria. A future structured logging issue can introduce the `logging` module with proper formatter configuration.
- **Iteration count:** Read from state via `state.get('iteration', 1)` to safely handle missing key
- **Log level consideration:** N/A — using `print` to stderr; if migrated to `logging` in future, use `INFO` level

## Security Considerations
No security impact — this adds stderr log statements only with no sensitive data (only timestamps and iteration counters). No PII involved; logs are transient console output.

## Files to Create/Modify
- `nodes/draft.py` — Add `sys` and `datetime` imports, add `print(..., file=sys.stderr)` calls at start and end of `draft()` function

## Dependencies
- None — `iteration` key in state is accessed safely via `.get()` with a default value

## Out of Scope (Future)
- Structured logging framework (e.g., Python `logging` module with formatters) — deferred to future issue
- Log file output — console only for now
- Logging in other nodes — only draft node in this issue

## Acceptance Criteria
- [ ] `[HH:MM:SS] Draft node: starting (iteration N)` prints to stderr when draft node begins
- [ ] `[HH:MM:SS] Draft node: completed (iteration N)` prints to stderr when draft node finishes
- [ ] Timestamps reflect actual wall-clock time
- [ ] Iteration count matches the value in workflow state
- [ ] If `iteration` key is missing from state, defaults to `1` without error
- [ ] No logging added to any node other than draft
- [ ] Output goes to stderr, not stdout

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
Run the workflow and verify stderr contains the expected log lines. Use `capsys` or `capfd` pytest fixtures to capture and assert on stderr output in automated tests. To test multiple iterations, trigger a workflow state that causes the draft node to execute more than once and confirm iteration counts increment correctly. To test the missing key scenario, pass a state object without an `iteration` key and confirm the log shows `iteration 1` with no errors.

**Effort Estimate:** XS (0.5–1 Story Point)

Labels: `enhancement`, `logging`, `type:instrumentation`