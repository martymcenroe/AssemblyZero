"""Pre-write validation hook for LLD path enforcement.

Issue #188: Validates that file writes target paths specified in the LLD.
Reports writes to non-LLD paths with helpful messages including the closest
matching LLD path suggestion.

**#2736: the LLD's file list is a plan, not a contract.** Operator ruling of
2026-09-04. `validate_file_write` still answers the question it always
answered -- is this path in the list -- and `path_advisory` turns that answer
into the sentence the implementation stage prints. Nothing here ends a run any
more. The evidence was the answer-key audit against boostgauge `main`: four of
issue #4's seventeen shipped files, three of them tests, were refused for
paths LLD-004 never named. The design named four files; the build wrote eight.

The traversal check is the one refusal that survives as a refusal, because it
is not a judgement about a plan -- a path escaping the repository is an
infrastructure fact, and no ruling about design documents speaks to it.
"""

from difflib import SequenceMatcher
from pathlib import PurePosixPath
from typing import TypedDict

from assemblyzero.core.gate_registry import advised

#: What `path_advisory` says instead of refusing (#2736). The Section 2.1
#: reference is the LLD heading the path list is read from, named so a reader
#: of the log knows which document to open.
PATH_GATE_KEY = "impl.path_enforcement"
PATH_ADVISORY_CONTINUES = (
    "The file is written; the LLD's file list is a plan, not a contract."
)


class PathValidationResult(TypedDict):
    """Result of validating a file write path."""

    allowed: bool
    requested_path: str
    closest_match: str | None
    reason: str


def validate_file_write(
    requested_path: str,
    allowed_paths: set[str],
    strict: bool = True,
) -> PathValidationResult:
    """Validate a file write request against LLD-specified paths.

    Args:
        requested_path: The path being written to.
        allowed_paths: Set of LLD-allowed paths.
        strict: If True, reject non-LLD paths. If False, warn only.

    Returns:
        PathValidationResult with allow/reject decision.
    """
    normalized = _normalize_path(requested_path)

    # Check for path traversal
    if _is_path_traversal(normalized):
        return {
            "allowed": False,
            "requested_path": requested_path,
            "closest_match": None,
            "reason": f"Rejected: path traversal attempt detected in '{requested_path}'",
        }

    # Exact match
    if normalized in allowed_paths:
        return {
            "allowed": True,
            "requested_path": requested_path,
            "closest_match": None,
            "reason": "Path matches LLD specification",
        }

    # Normalized match (try with/without leading components)
    for allowed in allowed_paths:
        if _paths_equivalent(normalized, allowed):
            return {
                "allowed": True,
                "requested_path": requested_path,
                "closest_match": allowed,
                "reason": f"Path matches LLD specification (normalized from '{allowed}')",
            }

    # Not allowed
    closest = find_closest_lld_path(normalized, allowed_paths)
    suggestion = f" Did you mean '{closest}'?" if closest else ""

    return {
        "allowed": False,
        "requested_path": requested_path,
        "closest_match": closest,
        "reason": f"Rejected: '{requested_path}' not in LLD-specified paths.{suggestion}",
    }


def find_closest_lld_path(
    requested_path: str, allowed_paths: set[str]
) -> str | None:
    """Find the most similar allowed path using sequence matching.

    Args:
        requested_path: The rejected path.
        allowed_paths: Set of allowed LLD paths.

    Returns:
        Most similar path, or None if no paths are close enough.
    """
    if not allowed_paths:
        return None

    best_match = None
    best_ratio = 0.0

    for allowed in allowed_paths:
        ratio = SequenceMatcher(None, requested_path, allowed).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = allowed

    # Only suggest if similarity is reasonable (> 40%)
    if best_ratio > 0.4:
        return best_match
    return None


def _normalize_path(path: str) -> str:
    """Normalize a file path for comparison."""
    if not path:
        return ""
    normalized = str(PurePosixPath(path))
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _paths_equivalent(path1: str, path2: str) -> bool:
    """Check if two paths refer to the same file after normalization."""
    return _normalize_path(path1) == _normalize_path(path2)


def _is_path_traversal(path: str) -> bool:
    """Check if a path contains directory traversal attempts."""
    return ".." in PurePosixPath(path).parts


def path_advisory(requested_path: str, allowed_paths: set[str]) -> str:
    """What `impl.path_enforcement` says about a path it did not expect (#2736).

    Returns "" when the path is in the LLD's list, when the LLD names no paths
    at all, or when the gate has nothing to say. Otherwise returns the
    advisory, tagged with the gate key by `advised()` so a log line can be
    counted against the registry rather than matched as prose.

    This is the whole of the gate now. It is called for its sentence, never for
    a decision: every caller writes the file either way. `advised()` refuses a
    key whose registry row still halts, so this function cannot be wired up
    while the row and the code disagree.

    Path traversal is deliberately NOT advisory here -- it is reported by
    `validate_file_write` and handled by the caller as the infrastructure fault
    it is, not as a disagreement with a design document.
    """
    if not allowed_paths:
        return ""
    result = validate_file_write(requested_path, allowed_paths)
    if result["allowed"]:
        return ""
    suggestion = (
        f" Closest planned path: '{result['closest_match']}'."
        if result["closest_match"]
        else ""
    )
    return advised(
        PATH_GATE_KEY,
        f"'{requested_path}' is not in the LLD's Section 2.1 list.{suggestion}",
        continues=PATH_ADVISORY_CONTINUES,
    )
