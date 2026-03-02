```python
"""Verification strategies — check claims against filesystem/codebase reality.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from assemblyzero.spelunking.models import (
    Claim,
    ClaimType,
    VerificationResult,
    VerificationStatus,
)


_DEFAULT_EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", ".mypy_cache", ".tox", ".pytest_cache"}
_MAX_GREP_MATCHES = 10
_MIN_SEARCH_TERM_LENGTH = 3


def verify_claim(
    claim: Claim,
    repo_root: Path,
) -> VerificationResult:
    """Verify a single claim against filesystem/codebase reality. Dispatches by claim type."""
    dispatch = {
        ClaimType.FILE_COUNT: _verify_file_count_claim,
        ClaimType.FILE_EXISTS: _verify_file_exists_claim,
        ClaimType.TECHNICAL_FACT: _verify_technical_claim,
        ClaimType.UNIQUE_ID: _verify_unique_id_claim,
        ClaimType.TIMESTAMP: _verify_timestamp_claim,
    }

    handler = dispatch.get(claim.claim_type)
    if handler is None:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.UNVERIFIABLE,
            evidence=f"No verification strategy for claim type: {claim.claim_type.value}",
        )

    try:
        return handler(claim, repo_root)
    except Exception as exc:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=str(exc),
        )


def _verify_file_count_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for FILE_COUNT claims."""
    # Parse verification_command: "glob dir/pattern | count"
    parts = claim.verification_command.replace(" | count", "").replace("glob ", "")
    directory = repo_root / Path(parts).parent
    glob_pattern = Path(parts).name
    expected = int(claim.expected_value)
    return verify_file_count(directory, expected, glob_pattern, claim)


def _verify_file_exists_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for FILE_EXISTS claims."""
    file_path = Path(claim.expected_value)
    return verify_file_exists(file_path, repo_root, claim)


def _verify_technical_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for TECHNICAL_FACT claims."""
    return verify_no_contradiction(claim.expected_value, repo_root, claim=claim)


def _verify_unique_id_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for UNIQUE_ID claims."""
    directory = repo_root / Path(claim.expected_value)
    return verify_unique_prefix(directory, claim=claim)


def _verify_timestamp_claim(claim: Claim, repo_root: Path) -> VerificationResult:
    """Dispatch for TIMESTAMP claims."""
    return verify_timestamp_freshness(claim.expected_value, claim=claim)


def verify_file_count(
    directory: Path,
    expected_count: int,
    glob_pattern: str = "*.py",
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Count files matching pattern in directory and compare to expected."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.FILE_COUNT,
            source_file=Path(""),
            source_line=0,
            claim_text=f"{expected_count} files in {directory.name}/",
            expected_value=str(expected_count),
            verification_command=f"glob {directory}/{glob_pattern} | count",
        )

    if not directory.exists():
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )

    actual_files = list(directory.glob(glob_pattern))
    actual_count = len(actual_files)

    if actual_count == expected_count:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            actual_value=str(actual_count),
            evidence=f"Found {actual_count} files matching {glob_pattern} in {directory.name}/",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        actual_value=str(actual_count),
        evidence=f"Found {actual_count} files matching {glob_pattern} in {directory.name}/, expected {expected_count}",
    )


def verify_file_exists(
    file_path: Path,
    repo_root: Path,
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Verify that a referenced file actually exists on disk. Path traversal protected."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.FILE_EXISTS,
            source_file=Path(""),
            source_line=0,
            claim_text=str(file_path),
            expected_value=str(file_path),
            verification_command=f"path_exists {file_path}",
        )

    resolved = (repo_root / file_path).resolve()

    if not _is_within_repo(resolved, repo_root):
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Path traversal detected: {file_path} resolves outside repo root",
        )

    if resolved.exists():
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            actual_value=str(file_path),
            evidence=f"File exists at {file_path}",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        evidence=f"File not found: {file_path}",
    )


def verify_no_contradiction(
    negated_term: str,
    repo_root: Path,
    exclude_dirs: list[str] | None = None,
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Grep codebase for presence of something claimed to be absent."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.TECHNICAL_FACT,
            source_file=Path(""),
            source_line=0,
            claim_text=f"not {negated_term}",
            expected_value=negated_term,
            verification_command=f"grep_absent {negated_term}",
        )

    if len(negated_term) < _MIN_SEARCH_TERM_LENGTH:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.UNVERIFIABLE,
            evidence=f"Search term '{negated_term}' too short (min {_MIN_SEARCH_TERM_LENGTH} chars)",
        )

    excluded = set(exclude_dirs) if exclude_dirs else _DEFAULT_EXCLUDE_DIRS
    matches: list[str] = []

    for py_file in repo_root.rglob("*.py"):
        # Check if file is in an excluded directory
        if any(part in excluded for part in py_file.parts):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for line_num, line in enumerate(content.splitlines(), start=1):
            if re.search(re.escape(negated_term), line, re.IGNORECASE):
                rel_path = py_file.relative_to(repo_root)
                truncated_line = line.strip()[:100]
                matches.append(f"{rel_path}:{line_num}: {truncated_line}")
                if len(matches) >= _MAX_GREP_MATCHES:
                    break
        if len(matches) >= _MAX_GREP_MATCHES:
            break

    if not matches:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            evidence=f"Term '{negated_term}' not found in codebase",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        actual_value=negated_term,
        evidence=f"Found '{negated_term}' in {matches[0]}"
        + (f" (+{len(matches) - 1} more)" if len(matches) > 1 else ""),
    )


def verify_unique_prefix(
    directory: Path,
    prefix_pattern: str = r"^(\d{4})-",
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Verify that no two files in a directory share the same numeric prefix."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.UNIQUE_ID,
            source_file=Path(""),
            source_line=0,
            claim_text=f"Unique prefixes in {directory.name}/",
            expected_value=str(directory),
            verification_command=f"check_unique_prefix {directory}",
        )

    if not directory.exists():
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Directory not found: {directory}",
        )

    prefix_map: dict[str, list[str]] = {}
    compiled_pattern = re.compile(prefix_pattern)

    for file_path in sorted(directory.iterdir()):
        if file_path.is_file():
            match = compiled_pattern.match(file_path.name)
            if match:
                prefix = match.group(1)
                prefix_map.setdefault(prefix, []).append(file_path.name)

    collisions = {
        prefix: files for prefix, files in prefix_map.items() if len(files) > 1
    }

    if not collisions:
        total = sum(len(files) for files in prefix_map.values())
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            evidence=f"All {total} prefixes are unique",
        )

    collision_details = []
    for prefix, files in sorted(collisions.items()):
        collision_details.append(f"Prefix {prefix} used by: {', '.join(files)}")

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.MISMATCH,
        actual_value=f"{len(collisions)} collision(s)",
        evidence="; ".join(collision_details),
    )


def verify_timestamp_freshness(
    claimed_date: str,
    max_age_days: int = 30,
    claim: Optional[Claim] = None,
) -> VerificationResult:
    """Check whether a claimed date is within the freshness threshold."""
    if claim is None:
        claim = Claim(
            claim_type=ClaimType.TIMESTAMP,
            source_file=Path(""),
            source_line=0,
            claim_text=f"Date: {claimed_date}",
            expected_value=claimed_date,
            verification_command=f"check_freshness {claimed_date}",
        )

    try:
        parsed_date = datetime.strptime(claimed_date, "%Y-%m-%d").date()
    except ValueError:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.ERROR,
            error_message=f"Cannot parse date: {claimed_date}",
        )

    age_days = (date.today() - parsed_date).days
    if age_days < 0:
        age_days = 0

    if age_days <= max_age_days:
        return VerificationResult(
            claim=claim,
            status=VerificationStatus.MATCH,
            actual_value=f"{age_days} days old",
            evidence=f"Date {claimed_date} is {age_days} days old (threshold: {max_age_days} days)",
        )

    return VerificationResult(
        claim=claim,
        status=VerificationStatus.STALE,
        actual_value=f"{age_days} days old",
        evidence=f"Date {claimed_date} is {age_days} days old (threshold: {max_age_days} days)",
    )


def _is_within_repo(file_path: Path, repo_root: Path) -> bool:
    """Check that resolved path is within repo_root boundary."""
    try:
        file_path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False
```
