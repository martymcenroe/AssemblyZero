"""Constants for the Hourglass Protocol.

Issue #535: Weight tables, thresholds, and configuration.
"""

from __future__ import annotations

from pathlib import Path

# Issue weight mapping: label -> weight
LABEL_WEIGHTS: dict[str, int] = {
    # +1: Fixes reality but doesn't change the shape
    "bug": 1,
    "fix": 1,
    "hotfix": 1,
    "patch": 1,
    # +3: Adds capability
    "enhancement": 3,
    "feature": 3,
    "feat": 3,
    # +5: Changes what the system *is*
    "persona": 5,
    "subsystem": 5,
    "new-component": 5,
    "new-workflow": 5,
    # +8: Changes how everything else works
    "foundation": 8,
    "rag": 8,
    "pipeline": 8,
    "infrastructure": 8,
    # +10: The old map is now wrong
    "architecture": 10,
    "cross-cutting": 10,
    "breaking": 10,
    "breaking-change": 10,
}

DEFAULT_WEIGHT: int = 2
DEFAULT_THRESHOLD: int = 50
CRITICAL_DRIFT_THRESHOLD: float = 30.0
MIN_CONFIDENCE_THRESHOLD: float = 0.5
MAX_ISSUES_FETCH: int = 500

# Drift severity weights
DRIFT_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 10.0,
    "major": 5.0,
    "minor": 1.0,
}

# Paths
# #1151: hourglass state lives OUTSIDE any repo tree. Pre-#1151 these were
# relative paths (e.g., "data/hourglass/history.json"), which meant every
# git worktree inherited a tracked file that hooks/workflows dirtied the
# moment they fired -- blocking `git worktree remove` (no --force per policy)
# and producing the orphan-worktree class of bugs that #1133 then made loud.
# Operational state belongs under ~/.claude/assemblyzero/, never in repo.
_HOURGLASS_DIR = Path.home() / ".claude" / "assemblyzero" / "hourglass"
AGE_METER_STATE_PATH: str = str(_HOURGLASS_DIR / "age_meter.json")
HISTORY_PATH: str = str(_HOURGLASS_DIR / "history.json")
ADR_OUTPUT_PATH: str = "docs/standards/0015-age-transition-protocol.md"
ADR_TEMPLATE_PATH: str = "docs/standards/"