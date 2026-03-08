## Objective
Eliminate the "PowerShell Trap" by creating a shell utility that automatically handles Bash-wrapping on Windows.

## Requirements
1. **Detection:** Detect `win32` and Bash-specific characters (`&&`, `2>&1`, etc.).
2. **Wrapping:** Automatically wrap commands in `bash -c '...'` with correct single-quoting.
3. **Efficiency:** Reduces turn-waste caused by shell syntax mismatches.

## Acceptance Criteria
- [ ] Standard Bash commands execute correctly from LangGraph nodes on Windows without manual wrapping.

## Related
- #588 (Systemic Guard)