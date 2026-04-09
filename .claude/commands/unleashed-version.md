---
description: Unleashed Version Check
scope: global
---

# Unleashed Version Check

Check the version of unleashed wrapping this Claude Code session.

## Instructions

Run this Bash command to check the unleashed version:

```bash
echo $UNLEASHED_VERSION
```

Then report the result to the user:

- If the variable is set (e.g., "1.3.0"), report: "Running under unleashed v{version}"
- If the variable is empty/unset, report: "Not running under unleashed (or unleashed < 1.3.1)"

Keep the response brief - just report the version status.
