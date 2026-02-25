"""Cascade detection pattern definitions.

Issue #358: Auto-Approve Safety — Prevent Cascading Task Execution

Contains regex patterns for detecting cascade-risk scenarios in model output.
Patterns are organized by category and scored by risk weight.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)

# Default config file location relative to project root
_DEFAULT_CONFIG_PATH = Path("data/unleashed/cascade_block_patterns.json")


class CascadePattern(TypedDict):
    """A single pattern definition for cascade detection."""

    id: str
    category: Literal[
        "continuation_offer",
        "numbered_choice",
        "task_completion_pivot",
        "scope_expansion",
    ]
    regex: str
    description: str
    risk_weight: float
    examples: list[str]


def load_default_patterns() -> list[CascadePattern]:
    """Load the built-in cascade detection patterns.

    Returns the hardcoded baseline pattern set derived from 3 months
    of production cascade incidents. These patterns catch common
    cascade scenarios across Claude and Gemini model outputs.

    Returns:
        List of CascadePattern definitions (15+ patterns).
    """
    return [
        # ── continuation_offer ──
        {
            "id": "CP-001",
            "category": "continuation_offer",
            "regex": r"(?i)\bshould I (continue|proceed|start|begin|move on)\b",
            "description": "Detects 'Should I continue/proceed/start' offers",
            "risk_weight": 0.7,
            "examples": ["Should I continue with the next issue?"],
        },
        {
            "id": "CP-002",
            "category": "continuation_offer",
            "regex": r"(?i)\bdo you want me to (continue|proceed|start|begin)\b",
            "description": "Detects 'Do you want me to continue' offers",
            "risk_weight": 0.7,
            "examples": ["Do you want me to proceed?"],
        },
        {
            "id": "CP-003",
            "category": "continuation_offer",
            "regex": r"(?i)\bshall I (continue|proceed|start|begin|move on)\b",
            "description": "Detects 'Shall I continue/start' offers",
            "risk_weight": 0.7,
            "examples": ["Shall I begin the next task?"],
        },
        {
            "id": "CP-004",
            "category": "continuation_offer",
            "regex": r"(?i)\bwould you like me to (continue|proceed|start|begin)\b",
            "description": "Detects 'Would you like me to continue' offers",
            "risk_weight": 0.7,
            "examples": ["Would you like me to start issue #44?"],
        },
        {
            "id": "CP-005",
            "category": "continuation_offer",
            "regex": r"(?i)\bready to (continue|proceed|start|begin|move on)\b",
            "description": "Detects 'Ready to continue/move on' offers",
            "risk_weight": 0.6,
            "examples": ["Ready to move on to the next one?"],
        },
        # ── numbered_choice ──
        {
            "id": "CP-010",
            "category": "numbered_choice",
            "regex": r"(?mi)^\s*1[.\)]\s*(yes|continue|proceed|go ahead)",
            "description": "Detects '1. Yes/Continue' numbered option",
            "risk_weight": 0.5,
            "examples": ["1. Yes, continue"],
        },
        {
            "id": "CP-011",
            "category": "numbered_choice",
            "regex": r"(?mi)^\s*2[.\)]\s*(no|stop|wait|hold)",
            "description": "Detects '2. No/Stop' numbered option",
            "risk_weight": 0.5,
            "examples": ["2. No, stop here"],
        },
        {
            "id": "CP-012",
            "category": "numbered_choice",
            "regex": r"(?is)(which option|choose|select).{0,30}\n\s*1[.\)].{0,50}\n\s*2[.\)]",
            "description": "Detects 'Choose: 1. X  2. Y' structured options",
            "risk_weight": 0.4,
            "examples": ["Choose:\n1. Option A\n2. Option B"],
        },
        # ── task_completion_pivot ──
        {
            "id": "CP-020",
            "category": "task_completion_pivot",
            "regex": r"(?i)\bI(?:'ve| have)?\s+(finished|completed|fixed|solved|done|updated|resolved|handled|addressed)\b.{0,80}(should I|shall I|want me to|let me|now|next)",
            "description": "Detects 'I finished/solved X. Should I do Y?' pivot",
            "risk_weight": 0.8,
            "examples": ["I've finished issue 42. Should I start 43?", "I solved issue 1. Should I do issue 2?"],
        },
        {
            "id": "CP-021",
            "category": "task_completion_pivot",
            "regex": r"(?i)(that's|that is) (done|complete|fixed|finished).{0,80}(should|shall|want|would|let me|next)",
            "description": "Detects 'That's done. What next?' pivot",
            "risk_weight": 0.7,
            "examples": ["That's done. What should I tackle next?"],
        },
        {
            "id": "CP-022",
            "category": "task_completion_pivot",
            "regex": r"(?i)(task|issue|bug|feature).{0,30}(complete|done|fixed|resolved).{0,80}(next|now|also|another)",
            "description": "Detects 'Issue resolved. Now for the next' pivot",
            "risk_weight": 0.6,
            "examples": ["Issue #42 resolved. Now for the next one."],
        },
        {
            "id": "CP-023",
            "category": "task_completion_pivot",
            "regex": r"(?i)I('ve| have) (finished|completed|fixed|solved|done).{0,80}(now let me|let me also|let me now)",
            "description": "Detects 'I finished X. Now let me do Y' self-directed pivot",
            "risk_weight": 0.8,
            "examples": ["I've completed the refactor. Now let me also update the tests."],
        },
        {
            "id": "CP-024",
            "category": "task_completion_pivot",
            "regex": r"(?i)\b(done|finished|complete|all set)[!\.].*?(what'?s next|what now|now what)",
            "description": "Detects 'Done! What's next?' completion signal",
            "risk_weight": 0.7,
            "examples": ["Done! What's next?", "Finished. What now?"],
        },
        # ── scope_expansion ──
        {
            "id": "CP-030",
            "category": "scope_expansion",
            "regex": r"(?i)while I'm (at it|here),? I (could|should|can|might) (also|additionally)",
            "description": "Detects 'While I'm at it, I could also' expansion",
            "risk_weight": 0.6,
            "examples": ["While I'm at it, I could also refactor the auth module."],
        },
        {
            "id": "CP-031",
            "category": "scope_expansion",
            "regex": r"(?i)I (also|additionally) noticed.{0,80}(should I|want me to|shall I)",
            "description": "Detects 'I also noticed — should I fix it?' expansion",
            "risk_weight": 0.6,
            "examples": ["I also noticed a bug — should I fix it?"],
        },
        {
            "id": "CP-032",
            "category": "scope_expansion",
            "regex": r"(?i)there (are|is) (also|another|more|additional).{0,80}(should I|want me to|shall I)",
            "description": "Detects 'There are also X — should I?' expansion",
            "risk_weight": 0.6,
            "examples": ["There are also some lint warnings — should I fix those?"],
        },
        {
            "id": "CP-033",
            "category": "scope_expansion",
            "regex": r"(?i)\bshould I (also|additionally)\b",
            "description": "Detects 'Should I also do X?' scope expansion offers",
            "risk_weight": 0.6,
            "examples": ["Should I also add type hints?", "Should I additionally fix the linting?"],
        },
    ]


def load_user_patterns(
    config_path: str | Path | None = None,
) -> list[CascadePattern]:
    """Load user-defined patterns from cascade_block_patterns.json.

    Merges with defaults. User patterns can override built-in patterns
    by using the same pattern ID.

    Args:
        config_path: Path to user config. If None, uses default location
                     at data/unleashed/cascade_block_patterns.json.

    Returns:
        Merged list of patterns (user overrides take precedence).
        Returns empty list if file not found or invalid.
    """
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        logger.debug("User pattern config not found at %s", config_path)
        return []

    try:
        raw = config_path.read_text(encoding="utf-8")
        config = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "Failed to load user cascade patterns from %s: %s", config_path, exc
        )
        return []

    if not isinstance(config, dict):
        logger.warning("Invalid cascade pattern config format at %s", config_path)
        return []

    if not config.get("enabled", True):
        logger.debug("User cascade patterns disabled in config")
        return []

    patterns = config.get("patterns", [])
    if not isinstance(patterns, list):
        logger.warning("Invalid patterns field in %s", config_path)
        return []

    # Validate each pattern has required fields
    valid_patterns: list[CascadePattern] = []
    required_keys = {"id", "category", "regex", "description", "risk_weight"}
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        if not required_keys.issubset(pattern.keys()):
            logger.warning("Skipping invalid pattern (missing keys): %s", pattern.get("id", "unknown"))
            continue
        # Validate regex compiles
        try:
            re.compile(pattern["regex"])
        except re.error as exc:
            logger.warning("Skipping pattern %s with invalid regex: %s", pattern["id"], exc)
            continue
        # Set defaults for optional fields
        if "examples" not in pattern:
            pattern["examples"] = []
        valid_patterns.append(pattern)  # type: ignore[arg-type]

    return valid_patterns


def merge_patterns(
    defaults: list[CascadePattern],
    overrides: list[CascadePattern],
) -> list[CascadePattern]:
    """Merge two pattern lists, with overrides taking precedence by ID.

    Args:
        defaults: Base pattern list.
        overrides: Override patterns (same ID replaces default).

    Returns:
        Merged pattern list preserving order (defaults first, then new overrides).
    """
    override_map: dict[str, CascadePattern] = {p["id"]: p for p in overrides}
    override_ids_used: set[str] = set()

    merged: list[CascadePattern] = []
    for default in defaults:
        if default["id"] in override_map:
            merged.append(override_map[default["id"]])
            override_ids_used.add(default["id"])
        else:
            merged.append(default)

    # Append any override patterns with new IDs (not in defaults)
    for override in overrides:
        if override["id"] not in override_ids_used:
            merged.append(override)

    return merged