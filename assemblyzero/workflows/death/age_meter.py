"""Age meter computation and persistence.

Issue #535: Weights closed GitHub issues by label to compute
the age meter score that triggers DEATH.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from github import Github

from assemblyzero.workflows.death.constants import (
    AGE_METER_STATE_PATH,
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHT,
    LABEL_WEIGHTS,
    MAX_ISSUES_FETCH,
)
from assemblyzero.workflows.death.models import AgeMeterState, IssueWeight

logger = logging.getLogger(__name__)


def compute_issue_weight(
    labels: list[str],
    title: str,
    body: str | None = None,
) -> tuple[int, str]:
    """Compute weight for a single issue based on its labels.

    Returns (weight, weight_source) tuple.
    Falls back to DEFAULT_WEIGHT if no matching label found.
    """
    best_weight = 0
    best_source = ""

    for label in labels:
        label_lower = label.lower()
        if label_lower in LABEL_WEIGHTS:
            w = LABEL_WEIGHTS[label_lower]
            if w > best_weight:
                best_weight = w
                best_source = label_lower

    if best_weight == 0:
        logger.warning(
            "No matching label for issue %r, using default weight %d",
            title,
            DEFAULT_WEIGHT,
        )
        return (DEFAULT_WEIGHT, "default")

    return (best_weight, best_source)


def fetch_closed_issues_since(
    repo: str,
    since: str | None,
    github_token: str | None = None,
) -> list[dict]:
    """Fetch closed issues from GitHub since the last DEATH visit.

    Args:
        repo: GitHub repo in "owner/repo" format.
        since: ISO 8601 timestamp. If None, fetches all closed issues.
        github_token: Optional token. Uses GITHUB_TOKEN env var if not provided.

    Returns:
        List of issue dicts with number, title, labels, closed_at, body.

    Raises:
        ValueError: If no GitHub token available.
        RuntimeError: If GitHub API call fails.
    """
    token = github_token or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GitHub token required. Set GITHUB_TOKEN or pass github_token.")

    try:
        gh = Github(token)
        gh_repo = gh.get_repo(repo)

        kwargs: dict[str, Any] = {"state": "closed", "sort": "updated", "direction": "desc"}
        if since:
            kwargs["since"] = datetime.fromisoformat(since.replace("Z", "+00:00"))

        issues = []
        for issue in gh_repo.get_issues(**kwargs):
            if len(issues) >= MAX_ISSUES_FETCH:
                break
            if issue.pull_request is not None:
                continue  # Skip PRs
            issues.append({
                "number": issue.number,
                "title": issue.title,
                "labels": [label.name for label in issue.labels],
                "closed_at": issue.closed_at.isoformat() if issue.closed_at else "",
                "body": issue.body,
            })

        return issues
    except Exception as exc:
        raise RuntimeError(f"GitHub API error: {exc}") from exc


def compute_age_meter(
    issues: list[dict],
    current_state: AgeMeterState | None = None,
) -> AgeMeterState:
    """Compute the age meter score from closed issues.

    If current_state is provided, adds to existing score.
    If None, computes from scratch.
    """
    now = datetime.now(timezone.utc).isoformat()

    if current_state is None:
        state: AgeMeterState = {
            "current_score": 0,
            "threshold": DEFAULT_THRESHOLD,
            "last_death_visit": None,
            "last_computed": now,
            "weighted_issues": [],
            "age_number": 1,
        }
    else:
        state = {**current_state, "last_computed": now}
        # Ensure weighted_issues is a new list to avoid mutating the original
        state["weighted_issues"] = list(current_state["weighted_issues"])

    for issue in issues:
        weight, source = compute_issue_weight(
            labels=issue.get("labels", []),
            title=issue.get("title", ""),
            body=issue.get("body"),
        )
        issue_weight: IssueWeight = {
            "issue_number": issue["number"],
            "title": issue["title"],
            "labels": issue.get("labels", []),
            "weight": weight,
            "weight_source": source,
            "closed_at": issue.get("closed_at", ""),
        }
        state["weighted_issues"].append(issue_weight)
        state["current_score"] += weight

    return state


def load_age_meter_state(
    state_path: str = AGE_METER_STATE_PATH,
) -> AgeMeterState | None:
    """Load persistent age meter state from disk. Returns None if no state exists."""
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load age meter state from %s: %s", state_path, exc)
        return None


def save_age_meter_state(
    state: AgeMeterState,
    state_path: str = AGE_METER_STATE_PATH,
) -> None:
    """Persist age meter state to disk. Atomic write via tempfile."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    dir_name = os.path.dirname(state_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, state_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def check_meter_threshold(state: AgeMeterState) -> bool:
    """Check if age meter crossed threshold. Returns True if DEATH should arrive."""
    return state["current_score"] >= state["threshold"]