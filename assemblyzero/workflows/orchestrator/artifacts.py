"""Artifact detection and path management.

Issue #305: End-to-End Orchestration Workflow (Issue → Code)
"""

from __future__ import annotations

from pathlib import Path


def detect_existing_artifacts(issue_number: int) -> dict[str, str | None]:
    """Scan for existing artifacts for an issue.

    Returns dict mapping stage names to artifact paths, or None if not found.
    """
    if issue_number < 1:
        msg = "issue_number must be positive"
        raise ValueError(msg)

    artifacts: dict[str, str | None] = {
        "triage": None,
        "lld": None,
        "spec": None,
        "impl": None,
        "pr": None,
    }

    # Triage: docs/lineage/{issue_number}/issue-brief.md
    triage_path = Path(f"docs/lineage/{issue_number}/issue-brief.md")
    if triage_path.is_file() and triage_path.stat().st_size > 0:
        artifacts["triage"] = str(triage_path)

    # LLD: docs/lld/active/LLD-{issue_number}.md OR docs/lld/active/{issue_number}-*.md
    for lld_dir in [Path("docs/lld/active"), Path("docs/lld/done")]:
        if lld_dir.is_dir():
            # Check exact LLD-N.md first, then N-*.md pattern
            exact = lld_dir / f"LLD-{issue_number}.md"
            if exact.is_file():
                artifacts["lld"] = str(exact)
                break
            matches = sorted(lld_dir.glob(f"{issue_number}-*.md"))
            if matches:
                artifacts["lld"] = str(matches[0])
                break

    # Spec: docs/lineage/{issue_number}/impl-spec.md
    # Also check drafts location
    spec_paths = [
        Path(f"docs/lineage/{issue_number}/impl-spec.md"),
        Path(f"docs/lld/drafts/spec-{issue_number:04d}-implementation-readiness.md"),
    ]
    for spec_path in spec_paths:
        if spec_path.is_file() and spec_path.stat().st_size > 0:
            artifacts["spec"] = str(spec_path)
            break

    # Impl: worktree at ../AssemblyZero-{issue_number}
    worktree_path = Path(f"../AssemblyZero-{issue_number}")
    if worktree_path.is_dir():
        artifacts["impl"] = str(worktree_path)

    # PR: not detectable from filesystem alone (would need GitHub API)
    # Leave as None

    return artifacts


def get_artifact_path(issue_number: int, artifact_type: str) -> Path:
    """Get canonical path for an artifact type.

    Args:
        issue_number: GitHub issue number
        artifact_type: One of 'triage', 'lld', 'spec', 'impl'

    Returns:
        Expected path for the artifact (may not exist yet)

    Raises:
        ValueError: For 'pr' type (URL, not file) or unknown types
    """
    if artifact_type == "triage":
        return Path(f"docs/lineage/{issue_number}/issue-brief.md")
    if artifact_type == "lld":
        return Path(f"docs/lld/active/{issue_number}-*.md")
    if artifact_type == "spec":
        return Path(f"docs/lineage/{issue_number}/impl-spec.md")
    if artifact_type == "impl":
        return Path(f"../AssemblyZero-{issue_number}")
    if artifact_type == "pr":
        msg = "PR artifact is a URL, not a file path"
        raise ValueError(msg)
    msg = f"Unknown artifact_type: {artifact_type}"
    raise ValueError(msg)


def validate_artifact(path: Path, artifact_type: str) -> bool:
    """Validate that artifact exists and has required structure.

    Checks:
      - File/dir exists
      - File is non-empty
      - For lld: contains '## 1. Context' heading
      - For spec: contains '## 1. Overview' heading
      - For triage: contains '##' heading (any h2)
    """
    if artifact_type == "impl":
        # For implementation, just check directory exists
        return path.is_dir()

    if not path.is_file():
        return False

    if path.stat().st_size == 0:
        return False

    content = path.read_text(encoding="utf-8")

    if artifact_type == "lld":
        return "## 1. Context" in content
    if artifact_type == "spec":
        return "## 1. Overview" in content
    if artifact_type == "triage":
        return "## " in content

    return True
