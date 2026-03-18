"""Configuration constants for AssemblyZero LLD review.

This module defines constants that control LLD review behavior,
including model hierarchy and credential paths.
"""

import os
from pathlib import Path

# =============================================================================
# Model Hierarchy (NEVER downgrade for reviews)
# =============================================================================

# Primary review model - highest reasoning tier available
# Issue #773: Default to Claude Opus via Max subscription (free)
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "claude-opus-4-6")

# Acceptable fallback models
REVIEWER_MODEL_FALLBACKS = ["claude-sonnet-4-6"]

# Forbidden models - fail closed rather than use these
FORBIDDEN_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash",
    "gemini-2.5-lite",
    "gemini-lite",
    "gemini-3-pro-preview",
    "gemini-3-pro",
]

# =============================================================================
# Claude Model (REQ-2: Claude 4.6)
# =============================================================================

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

# =============================================================================
# Credential Paths
# =============================================================================

CREDENTIALS_FILE = Path.home() / ".assemblyzero" / "gemini-credentials.json"
ROTATION_STATE_FILE = Path.home() / ".assemblyzero" / "gemini-rotation-state.json"
GEMINI_API_LOG_FILE = Path.home() / ".assemblyzero" / "gemini-api.jsonl"

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