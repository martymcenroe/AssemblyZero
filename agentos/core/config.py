"""Configuration constants for AgentOS governance.

This module defines constants that control governance behavior,
including model hierarchy and credential paths.
"""

import os
from pathlib import Path

# =============================================================================
# Model Hierarchy (NEVER downgrade for governance)
# =============================================================================

# Primary governance model - highest reasoning tier available
GOVERNANCE_MODEL = os.environ.get("GOVERNANCE_MODEL", "gemini-3-pro-preview")

# Acceptable fallback models (Pro-tier only)
GOVERNANCE_MODEL_FALLBACKS = ["gemini-3-pro"]

# Forbidden models - fail closed rather than use these
FORBIDDEN_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash",
    "gemini-2.5-lite",
    "gemini-lite",
]

# =============================================================================
# Credential Paths
# =============================================================================

CREDENTIALS_FILE = Path.home() / ".agentos" / "gemini-credentials.json"
ROTATION_STATE_FILE = Path.home() / ".agentos" / "gemini-rotation-state.json"

# =============================================================================
# Retry Configuration
# =============================================================================

MAX_RETRIES_PER_CREDENTIAL = 3
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0

# =============================================================================
# Logging Paths
# =============================================================================

DEFAULT_AUDIT_LOG_PATH = Path("logs/governance_history.jsonl")

# =============================================================================
# Prompt Paths
# =============================================================================

LLD_REVIEW_PROMPT_PATH = Path("docs/skills/0702c-LLD-Review-Prompt.md")
LLD_GENERATOR_PROMPT_PATH = Path("docs/skills/0705-lld-generator.md")

# =============================================================================
# Output Paths
# =============================================================================

LLD_DRAFTS_DIR = Path("docs/llds/drafts")
