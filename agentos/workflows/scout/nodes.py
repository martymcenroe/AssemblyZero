"""Node implementations for Scout workflow.

Implements Explorer, Extractor, Analyst, and Scribe nodes.
"""

import json
from pathlib import Path
from typing import Any

from agentos.workflows.scout.budget import adaptive_truncate, check_and_update_budget
from agentos.workflows.scout.graph import ExternalRepo, ScoutState
from agentos.workflows.scout.security import sanitize_external_content


def load_fixture(filename: str) -> Any:
    """Load fixture data for offline mode.

    Args:
        filename: Fixture filename.

    Returns:
        Parsed fixture data.
    """
    fixture_dir = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "scout"
    fixture_path = fixture_dir / filename

    if not fixture_path.exists():
        # Return empty data if fixture doesn't exist
        return []

    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def explorer_node(state: ScoutState) -> dict[str, Any]:
    """Search for repositories and apply hard limit.

    CRITICAL: Bounds results immediately after search to prevent
    downstream nodes from processing unbounded lists.

    Args:
        state: Current workflow state.

    Returns:
        State updates with found_repos.
    """
    topic = state.get("topic", "")
    min_stars = state.get("min_stars", 100)
    offline_mode = state.get("offline_mode", False)
    repo_limit = state.get("repo_limit", 3)

    if offline_mode:
        # Load fixture data
        raw_repos = load_fixture("github_search_response.json")
    else:
        # TODO: Implement real GitHub API search
        # For now, return empty list
        raw_repos = []

    # Convert to ExternalRepo format
    repos: list[ExternalRepo] = []
    for repo in raw_repos:
        repos.append(
            ExternalRepo(
                name=repo.get("full_name", ""),
                url=repo.get("html_url", ""),
                stars=repo.get("stargazers_count", 0),
                description=repo.get("description", ""),
                license_type="Unknown",
                readme_summary="",
                code_snippets="",
            )
        )

    # CRITICAL: Bound the results immediately
    # Sort by stars descending and take top N
    sorted_repos = sorted(repos, key=lambda x: x["stars"], reverse=True)
    top_repos = sorted_repos[:repo_limit]

    return {"found_repos": top_repos}


def extractor_node(state: ScoutState) -> dict[str, Any]:
    """Extract content from repositories with budget awareness.

    Args:
        state: Current workflow state.

    Returns:
        State updates with enriched repos and token usage.
    """
    found_repos = state.get("found_repos", [])
    current_usage = state.get("current_token_usage", 0)
    max_tokens = state.get("max_tokens", 30000)
    offline_mode = state.get("offline_mode", False)

    updated_repos: list[ExternalRepo] = []

    for repo in found_repos:
        # Pre-fetch budget check
        if current_usage >= max_tokens:
            break

        # Fetch content
        if offline_mode:
            content = load_fixture("github_content_response.json")
            readme = content.get("readme", "") if isinstance(content, dict) else ""
            license_type = content.get("license", "Unknown") if isinstance(content, dict) else "Unknown"
        else:
            # TODO: Implement real GitHub API content fetch
            readme = ""
            license_type = "Unknown"

        # Sanitize content
        clean_readme = sanitize_external_content(readme)

        # Update budget with safety buffer
        new_usage, ok = check_and_update_budget(current_usage, clean_readme, max_tokens)

        if ok:
            repo_copy = dict(repo)
            repo_copy["readme_summary"] = clean_readme
            repo_copy["license_type"] = license_type
            updated_repos.append(ExternalRepo(**repo_copy))
            current_usage = new_usage
        else:
            # Budget limit hit, stop extraction
            break

    return {
        "found_repos": updated_repos,
        "current_token_usage": current_usage,
    }


def gap_analyst_node(state: ScoutState) -> dict[str, Any]:
    """Analyze gaps between internal and external code.

    Implements adaptive retry on context window errors.

    Args:
        state: Current workflow state.

    Returns:
        State updates with gap analysis.
    """
    internal_code = state.get("internal_code_content", "")
    found_repos = state.get("found_repos", [])
    offline_mode = state.get("offline_mode", False)

    if offline_mode:
        # Return mock analysis for offline mode
        analysis = "## Gap Analysis (Offline Mode)\n\n"
        analysis += "This is a mock analysis generated in offline mode.\n"
        analysis += f"Analyzed {len(found_repos)} repositories.\n"
        return {"gap_analysis": analysis}

    # TODO: Implement real LLM analysis with retry logic
    # For now, return placeholder
    analysis = f"Gap analysis for {len(found_repos)} repositories."

    return {"gap_analysis": analysis}


def scribe_node(state: ScoutState) -> dict[str, Any]:
    """Generate the final Innovation Brief.

    Args:
        state: Current workflow state.

    Returns:
        State updates with final brief.
    """
    topic = state.get("topic", "")
    gap_analysis = state.get("gap_analysis", "")
    found_repos = state.get("found_repos", [])

    brief = f"# Innovation Brief: {topic}\n\n"
    brief += "## Executive Summary\n\n"
    brief += f"Analyzed {len(found_repos)} top repositories.\n\n"

    brief += "## Repositories Analyzed\n\n"
    for repo in found_repos:
        brief += f"- [{repo['name']}]({repo['url']}) "
        brief += f"(⭐ {repo['stars']}, License: {repo['license_type']})\n"

    brief += "\n## Gap Analysis\n\n"
    brief += gap_analysis or "No analysis available."

    return {"final_brief": brief}


def confirmation_node(state: ScoutState) -> dict[str, Any]:
    """Check for data privacy confirmation.

    Args:
        state: Current workflow state.

    Returns:
        State updates or error if not confirmed.
    """
    confirmed = state.get("confirmed", False)
    internal_file = state.get("internal_file_path")

    if internal_file and not confirmed:
        return {
            "errors": ["Data privacy confirmation required. Use --yes to confirm."],
        }

    return {}
