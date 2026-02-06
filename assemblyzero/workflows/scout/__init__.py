"""Scout workflow - External Intelligence Gathering.

Issue #93: The Scout is a proactive research workflow that searches GitHub
for best practices, analyzes top implementations, and produces an Innovation Brief.
"""

from assemblyzero.workflows.scout.budget import (
    adaptive_truncate,
    check_and_update_budget,
    estimate_tokens,
)
from assemblyzero.workflows.scout.security import (
    get_safe_write_path,
    sanitize_external_content,
    validate_read_path,
)

__all__ = [
    "check_and_update_budget",
    "adaptive_truncate",
    "estimate_tokens",
    "validate_read_path",
    "get_safe_write_path",
    "sanitize_external_content",
]
