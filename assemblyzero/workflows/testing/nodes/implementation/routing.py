"""Model routing logic for file generation.

Issue #641: Route scaffolding/boilerplate files to Haiku to reduce API spend.
"""

import logging
from pathlib import Path

from assemblyzero.core.config import CLAUDE_MODEL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
"""Model identifier for Claude Haiku — used for cheap/simple file generation."""

SMALL_FILE_LINE_THRESHOLD: int = 50
"""Files with estimated line count below this threshold route to Haiku."""

_BOILERPLATE_BASENAMES: frozenset[str] = frozenset({"__init__.py", "conftest.py"})
"""Filenames that are always routed to Haiku regardless of size."""


def _get_default_model() -> str:
    """Return the configured default model (Sonnet).

    Delegates to the same config source that call_claude_for_file uses.
    """
    return CLAUDE_MODEL


def select_model_for_file(
    file_path: str,
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> str:
    """Return the model ID to use for generating the given file.

    Routing rules (evaluated in order):
      1. is_test_scaffold=True  -> HAIKU_MODEL
      2. basename is __init__.py or conftest.py -> HAIKU_MODEL
      3. estimated_line_count > 0 and < SMALL_FILE_LINE_THRESHOLD -> HAIKU_MODEL
      4. Otherwise -> configured default (Sonnet)

    Args:
        file_path: Relative or absolute path to the file being generated.
            Only the basename is used for filename-based routing rules.
        estimated_line_count: Expected line count of the generated file.
            Pass 0 (default) when unknown; 0 disables line-count routing.
            Negative values are treated as unknown (same as 0).
        is_test_scaffold: True when this file is being generated as a test
            scaffold by the N2 node; overrides all other routing rules.

    Returns:
        Model identifier string suitable for passing to the Anthropic client.

    Raises:
        TypeError: If file_path is not a str.
    """
    if not isinstance(file_path, str):
        raise TypeError(
            f"file_path must be a str, got {type(file_path).__name__}"
        )

    basename = Path(file_path).name

    # Rule 1: Test scaffold override
    if is_test_scaffold:
        logger.info(
            "Routing %s -> %s (reason: test_scaffold)", file_path, HAIKU_MODEL
        )
        return HAIKU_MODEL

    # Rule 2: Boilerplate filename
    if basename in _BOILERPLATE_BASENAMES:
        logger.info(
            "Routing %s -> %s (reason: boilerplate_filename)",
            file_path,
            HAIKU_MODEL,
        )
        return HAIKU_MODEL

    # Rule 3: Small file by line count
    if 0 < estimated_line_count < SMALL_FILE_LINE_THRESHOLD:
        logger.info(
            "Routing %s -> %s (reason: small_file, lines=%d)",
            file_path,
            HAIKU_MODEL,
            estimated_line_count,
        )
        return HAIKU_MODEL

    # Rule 4: Default (Sonnet)
    default_model = _get_default_model()
    logger.info(
        "Routing %s -> %s (reason: default)", file_path, default_model
    )
    return default_model