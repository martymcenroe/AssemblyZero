"""Configuration constants for AgentOS LLD review.

This module defines constants that control LLD review behavior,
including model hierarchy and credential paths.
"""

import os
from pathlib import Path

# =============================================================================
# Model Hierarchy (NEVER downgrade for reviews)
# =============================================================================

# Primary review model - highest reasoning tier available
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gemini-3-pro-preview")

# Acceptable fallback models (Pro-tier only)
REVIEWER_MODEL_FALLBACKS = ["gemini-3-pro"]

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
GEMINI_API_LOG_FILE = Path.home() / ".agentos" / "gemini-api.jsonl"

# =============================================================================
# Retry Configuration
# =============================================================================

MAX_RETRIES_PER_CREDENTIAL = 3
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0

# =============================================================================
# Logging Paths (Issue #57: Session-Sharded Logging)
# =============================================================================

# Permanent audit trail (consolidated from shards)
DEFAULT_AUDIT_LOG_PATH = Path("logs/review_history.jsonl")

# Active session shards directory (gitignored, ephemeral)
LOGS_ACTIVE_DIR = Path("logs/active")

# =============================================================================
# Prompt Paths
# =============================================================================

LLD_REVIEW_PROMPT_PATH = Path("docs/skills/0702c-LLD-Review-Prompt.md")
LLD_GENERATOR_PROMPT_PATH = Path("docs/skills/0705-lld-generator.md")

# =============================================================================
# Output Paths
# =============================================================================

LLD_DRAFTS_DIR = Path("docs/llds/drafts")
