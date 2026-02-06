"""LangGraph state and workflow definition for Scout.

Defines the ScoutState and workflow graph structure.
"""

from typing import List, Optional, TypedDict


class ExternalRepo(TypedDict):
    """External repository data."""

    name: str  # "owner/repo"
    url: str  # html_url
    stars: int
    description: str
    license_type: str  # e.g., "MIT", "Apache-2.0", "Unknown"
    readme_summary: str  # Summarized content (truncated)
    code_snippets: str  # Relevant code content (truncated) - Optional


class ScoutState(TypedDict):
    """State for Scout workflow."""

    topic: str
    internal_file_path: Optional[str]
    internal_code_content: Optional[str]
    min_stars: int
    max_tokens: int  # Budget limit
    current_token_usage: int  # Running total
    found_repos: List[ExternalRepo]
    repo_limit: int  # Hard limit on number of repos to analyze (default 3)
    gap_analysis: Optional[str]
    final_brief: str
    errors: List[str]
    offline_mode: bool  # Flag for dev/testing
    confirmed: bool  # User confirmed data privacy


def create_initial_state(
    topic: str,
    internal_file_path: Optional[str] = None,
    min_stars: int = 100,
    max_tokens: int = 30000,
    repo_limit: int = 3,
    offline_mode: bool = False,
    confirmed: bool = False,
) -> ScoutState:
    """Create initial Scout workflow state.

    Args:
        topic: Search topic.
        internal_file_path: Optional internal file to compare against.
        min_stars: Minimum stars for repo search.
        max_tokens: Maximum token budget.
        repo_limit: Maximum repos to analyze.
        offline_mode: Use fixtures instead of API.
        confirmed: User confirmed data privacy.

    Returns:
        Initial ScoutState.
    """
    return ScoutState(
        topic=topic,
        internal_file_path=internal_file_path,
        internal_code_content=None,
        min_stars=min_stars,
        max_tokens=max_tokens,
        current_token_usage=0,
        found_repos=[],
        repo_limit=repo_limit,
        gap_analysis=None,
        final_brief="",
        errors=[],
        offline_mode=offline_mode,
        confirmed=confirmed,
    )
