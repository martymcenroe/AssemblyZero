

```python
#!/usr/bin/env python3
"""Claude Code PostToolUse hook — cascade detection.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Reads model output from stdin (Claude Code hook contract), runs cascade
detection, and exits with appropriate code:
- exit(0): Allow (no cascade detected, or below threshold)
- exit(2): Block (cascade detected, requires human input)

This hook is invoked by Claude Code after every tool use that produces
output. It only blocks when cascade risk is MEDIUM or above.
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    """Claude Code PostToolUse hook entry point."""
    try:
        # Read hook input from stdin (Claude Code hook contract)
        raw_input = sys.stdin.read()

        # Parse the hook input — Claude hooks pass JSON with tool_output field
        model_output = ""
        try:
            hook_data = json.loads(raw_input)
            # Claude Code hook format: {"tool_name": "...", "tool_input": {...}, "tool_output": "..."}
            model_output = hook_data.get("tool_output", "")
            if not isinstance(model_output, str):
                model_output = str(model_output) if model_output else ""
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat the raw input as the model output
            model_output = raw_input

        if not model_output.strip():
            sys.exit(0)

        # Import here to handle import errors gracefully
        from assemblyzero.hooks.cascade_detector import detect_cascade_risk
        from assemblyzero.hooks.cascade_action import handle_cascade_detection

        # Run detection
        result = detect_cascade_risk(model_output)

        # Get session ID from environment or generate a placeholder
        session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown-session")

        # Handle the detection result
        should_allow = handle_cascade_detection(
            result=result,
            session_id=session_id,
            model_output=model_output,
        )

        if should_allow:
            sys.exit(0)  # Allow auto-approve
        else:
            sys.exit(2)  # Block auto-approve

    except SystemExit:
        raise  # Let sys.exit() propagate
    except Exception as exc:  # noqa: BLE001
        # Fail open for hook crashes — don't brick Claude Code
        print(f"[cascade_check] Hook error (failing open): {exc}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
```
