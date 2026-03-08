## Problem
On Windows, the `run_shell_command` tool is hardcoded to use `powershell.exe -NoProfile -Command`. While this is a sensible default for many Windows users, it creates significant friction and "token waste" for engineers who operate primarily in POSIX-like environments on Windows (e.g., GitBash, MSYS2, or Cygwin).

When an agent is running in a GitBash session, it expects a Bash-compliant environment. However, when it invokes `run_shell_command`, the command is intercepted by the PowerShell parser. This leads to failures for standard Bash constructs like `&&`, `||`, redirection `2>&1`, and heredocs `<<EOF`.

## Proposed Solution
Add a configuration option (e.g., in `settings.json` or as a CLI flag) to specify the shell executable for `run_shell_command`.

**Example `settings.json`:**
```json
{
  "tools": {
    "shell": {
      "executable": "bash",
      "args": ["-c"]
    }
  }
}
```

## Benefits
1. **Consistency:** Agents can operate in the same shell environment as the user.
2. **Efficiency:** Reduces "failed turns" caused by shell syntax mismatches, saving tokens and time.
3. **Flexibility:** Allows power users on Windows to leverage their preferred shell without complex `bash -c '...'` wrapping in every tool call.

## Context
This request comes from a professional engineering environment (AssemblyZero) where we rely on strict protocol adherence and distributed autonomy across 40+ repositories. Forced PowerShell usage in a Bash-centric workflow is a major friction point.