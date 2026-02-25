"""Action handlers for cascade detection results.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Dispatches actions (allow, block, alert) based on cascade detection results.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from assemblyzero.hooks.types import CascadeDetectionResult, CascadeRiskLevel
from assemblyzero.telemetry.cascade_events import create_cascade_event, log_cascade_event

if TYPE_CHECKING:
    pass


def handle_cascade_detection(
    result: CascadeDetectionResult,
    session_id: str,
    model_output: str,
    alert_enabled: bool = True,
) -> bool:
    """Execute the recommended action from a cascade detection.

    Depending on the detection result, it will:
    - allow: return True (auto-approve may proceed)
    - block_and_prompt: log event, return False (force human input)
    - block_and_alert: log event, show alert, return False

    Args:
        result: The CascadeDetectionResult from detect_cascade_risk.
        session_id: Current session identifier for telemetry.
        model_output: Full model output for logging context.
        alert_enabled: Whether to show visual/audible alert on block.

    Returns:
        True if auto-approval should proceed, False if blocked.
    """
    action = result["recommended_action"]

    if action == "allow":
        # Optionally log allowed checks (if log_all_checks is configured)
        return True

    # For block_and_prompt and block_and_alert
    action_taken = "blocked" if action == "block_and_prompt" else "alerted"

    # Log the cascade event
    try:
        event = create_cascade_event(
            result=result,
            session_id=session_id,
            model_output=model_output,
            action_taken=action_taken,
        )
        log_cascade_event(event)
    except Exception:  # noqa: BLE001
        # Telemetry failure must not affect blocking behavior
        pass

    # Print block message to stderr
    message = format_block_message(result)
    if action == "block_and_alert" and alert_enabled:
        # Add alert decoration
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"\U0001f6a8 ALERT: {message}", file=sys.stderr)
        print(f"{'=' * 60}\n", file=sys.stderr)
    else:
        print(f"\n{message}\n", file=sys.stderr)

    return False


def format_block_message(
    result: CascadeDetectionResult,
) -> str:
    """Format a human-readable message explaining why auto-approve was blocked.

    Shown to the user when cascade detection fires, explaining what
    was detected and asking them to make the decision manually.

    Args:
        result: The detection result.

    Returns:
        Formatted message string for terminal display.
    """
    risk_level = result["risk_level"]
    if isinstance(risk_level, CascadeRiskLevel):
        risk_name = risk_level.value.upper()
    else:
        risk_name = str(risk_level).upper()

    confidence = result["confidence"]
    pattern_ids = result["matched_patterns"] if result["matched_patterns"] else ["unknown"]
    matched_text = result["matched_text"]

    # Truncate matched text for display
    if len(matched_text) > 100:
        matched_text = matched_text[:100] + "..."

    lines = [
        "\u26a0\ufe0f  CASCADE DETECTED \u2014 Auto-approve blocked",
        f"Risk Level: {risk_name} (confidence: {confidence:.2f})",
        f"Matched Patterns: {', '.join(pattern_ids)}",
        f'Trigger: "{matched_text}"',
        "",
        "The AI is offering to continue to the next task. Please provide manual input.",
        "Type your response to decide what happens next.",
    ]
    return "\n".join(lines)