

```python
"""Sample module for codebase retrieval AST parsing tests.

Issue #92: Codebase Retrieval System (RAG Injection)

This fixture contains a variety of Python constructs to test AST extraction:
- Public class with docstring and typed methods
- Public top-level function with type hints
- Private class (should be skipped)
- Private function (should be skipped)
"""

from __future__ import annotations

from typing import Any


class GovernanceAuditLog:
    """Audit logging for governance events.

    Tracks all governance-related actions in the system
    for compliance and debugging purposes.
    """

    def log_event(self, event: str, severity: str = "info") -> bool:
        """Log a governance event.

        Args:
            event: Description of the event.
            severity: Event severity level.

        Returns:
            True if the event was logged successfully.
        """
        return True

    def get_recent(self, count: int = 10) -> list[dict[str, str]]:
        """Get recent audit log entries.

        Args:
            count: Number of entries to retrieve.

        Returns:
            List of audit log entry dictionaries.
        """
        return []


class ConfigValidator:
    """Validates configuration dictionaries against schemas."""

    def validate(self, config: dict[str, Any], schema: str = "default") -> bool:
        """Validate a configuration dictionary.

        Args:
            config: Configuration to validate.
            schema: Schema name to validate against.

        Returns:
            True if valid.
        """
        return True


def compute_file_hash(file_path: str, algorithm: str = "md5") -> str:
    """Compute hash of a file's content.

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm to use.

    Returns:
        Hex digest of the file hash.
    """
    return ""


def format_report(entries: list[dict[str, str]], title: str = "Report") -> str:
    """Format entries into a human-readable report.

    Args:
        entries: List of entry dictionaries.
        title: Report title.

    Returns:
        Formatted report string.
    """
    return ""


def parse_timestamps(raw: str) -> list[str]:
    """Parse ISO 8601 timestamps from raw text.

    Args:
        raw: Raw text containing timestamps.

    Returns:
        List of parsed timestamp strings.
    """
    return []


class _PrivateProcessor:
    """Internal processor - should NOT be indexed."""

    def process(self) -> None:
        """Process internally."""
        pass


def _internal_helper() -> None:
    """Internal helper - should NOT be indexed."""
    pass
```
