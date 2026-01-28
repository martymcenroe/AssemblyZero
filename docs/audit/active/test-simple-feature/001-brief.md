# Add Logging to Draft Node

Simple feature to add basic logging to the draft node for better debugging.

## User Story
As a developer debugging the issue workflow, I want to see when the draft node starts and completes, so that I can identify performance bottlenecks.

## Requirements
- Add timestamp logging at start of draft() function
- Add timestamp logging at end of draft() function
- Log should include iteration count from state

## Technical Approach
- Use Python's datetime module
- Format: `[HH:MM:SS] Draft node: starting (iteration N)`
- Format: `[HH:MM:SS] Draft node: completed (iteration N)`

## Acceptance Criteria
- Logs appear in console during workflow execution
- Timestamps are accurate
- Iteration count matches state

## Out of Scope
- Structured logging (use print statements)
- Log files (console only)
- Other nodes (only draft node)

Labels: enhancement, logging
