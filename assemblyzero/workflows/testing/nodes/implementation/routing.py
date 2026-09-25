"""Model routing logic for file generation.

Issue #641: Route scaffolding/boilerplate files to a cheaper model to reduce
spend.

#3553/#3563: the routing picks a SEAT, never a model. Scaffolds,
``__init__.py``, ``conftest.py`` and files under fifty lines go to
``impl.code.small``; everything else to ``impl.code``. Which model answers each
seat is the run profile's decision (``gemini.toml`` by default; ``claude.toml``
reproduces the old Sonnet/Haiku split exactly).
"""

import logging
from pathlib import Path

from assemblyzero.core.seats import resolve_active

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CODE_SEAT: str = "impl.code"
"""The coder's seat for ordinary files."""

SMALL_SEAT: str = "impl.code.small"
"""The coder's seat for cheap/simple file generation (Haiku before the law)."""

SMALL_FILE_LINE_THRESHOLD: int = 50
"""Files with estimated line count below this threshold route to the small seat."""

_BOILERPLATE_BASENAMES: frozenset[str] = frozenset({"__init__.py", "conftest.py"})
"""Filenames that always route to the small seat regardless of size."""


def select_seat_for_file(
    file_path: str,
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> str:
    """Return the seat that generates the given file.

    Routing rules (evaluated in order):
      1. is_test_scaffold=True  -> SMALL_SEAT
      2. basename is __init__.py or conftest.py -> SMALL_SEAT
      3. estimated_line_count > 0 and < SMALL_FILE_LINE_THRESHOLD -> SMALL_SEAT
      4. Otherwise -> CODE_SEAT

    Args:
        file_path: Relative or absolute path to the file being generated.
            Only the basename is used for filename-based routing rules.
        estimated_line_count: Expected line count of the generated file.
            Pass 0 (default) when unknown; 0 disables line-count routing.
            Negative values are treated as unknown (same as 0).
        is_test_scaffold: True when this file is being generated as a test
            scaffold by the N2 node; overrides all other routing rules.

    Raises:
        TypeError: If file_path is not a str.
    """
    if not isinstance(file_path, str):
        raise TypeError(
            f"file_path must be a str, got {type(file_path).__name__}"
        )

    basename = Path(file_path).name

    if is_test_scaffold:
        reason = "test_scaffold"
        seat = SMALL_SEAT
    elif basename in _BOILERPLATE_BASENAMES:
        reason = "boilerplate_filename"
        seat = SMALL_SEAT
    elif 0 < estimated_line_count < SMALL_FILE_LINE_THRESHOLD:
        reason = f"small_file, lines={estimated_line_count}"
        seat = SMALL_SEAT
    else:
        reason = "default"
        seat = CODE_SEAT

    logger.info("Routing %s -> %s (reason: %s)", file_path, seat, reason)
    return seat


def select_model_for_file(
    file_path: str,
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> str:
    """Return the provider spec that generates the given file.

    The seat from :func:`select_seat_for_file`, resolved under the active
    profile (the one the N4 or N4c node entered from run state).
    """
    seat = select_seat_for_file(file_path, estimated_line_count, is_test_scaffold)
    return resolve_active(seat).spec
