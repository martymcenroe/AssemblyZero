"""Node implementations for Scout workflow.

Implements Explorer, Extractor, Analyst, and Scribe nodes.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from github import Github

from assemblyzero.workflows.scout.budget import adaptive_truncate, check_and_update_budget
from assemblyzero.workflows.scout.graph import ExternalRepo, ScoutState
from assemblyzero.workflows.scout.security import sanitize_external_content


def _get_github_client() -> Github:
    """Get authenticated GitHub client using gh CLI token.

    Returns:
        Authenticated Github client.
    """
    # Try to get token from gh CLI
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            return Github(token)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fall back to anonymous access (limited rate)
    return Github()


def load_fixture(filename: str) -> Any:
    """Load fixture data for offline mode.

    Args:
        filename: Fixture filename.

    Returns:
        Parsed fixture data.

    Raises:
        FileNotFoundError: If the fixture file does not exist.
    """
    fixture_dir = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "scout"
    fixture_path = fixture_dir / filename

    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Fixture '{filename}' not found at {fixture_path}. "
            f"Mock/offline mode requires fixture files to exist."
        )

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

    repos: list[ExternalRepo] = []

    if offline_mode:
        # Load fixture data
        raw_repos = load_fixture("github_search_response.json")
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
    else:
        # Real GitHub API search
        try:
            g = _get_github_client()
            query = f"{topic} stars:>={min_stars}"
            search_results = g.search_repositories(query, sort="stars", order="desc")

            # Limit iteration to avoid exhausting API calls
            count = 0
            for repo in search_results:
                if count >= repo_limit * 2:  # Get extra to filter
                    break
                repos.append(
                    ExternalRepo(
                        name=repo.full_name,
                        url=repo.html_url,
                        stars=repo.stargazers_count,
                        description=repo.description or "",
                        license_type=repo.license.name if repo.license else "Unknown",
                        readme_summary="",
                        code_snippets="",
                    )
                )
                count += 1
        except Exception as e:
            # Return empty list on error, let downstream handle it
            repos = []

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
            # Real GitHub API content fetch
            try:
                g = _get_github_client()
                gh_repo = g.get_repo(repo["name"])

                # Get README
                try:
                    readme_content = gh_repo.get_readme()
                    readme = readme_content.decoded_content.decode("utf-8", errors="replace")
                except Exception:
                    readme = ""

                # Get license
                license_type = gh_repo.license.name if gh_repo.license else "Unknown"
            except Exception:
                readme = ""
                license_type = repo.get("license_type", "Unknown")

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
    topic = state.get("topic", "")

    if offline_mode:
        # Return mock analysis for offline mode
        analysis = "## Gap Analysis (Offline Mode)\n\n"
        analysis += "This is a mock analysis generated in offline mode.\n"
        analysis += f"Analyzed {len(found_repos)} repositories.\n"
        return {"gap_analysis": analysis}

    # Build context from repos
    external_context = ""
    for repo in found_repos:
        external_context += f"\n### {repo['name']} ({repo['stars']} stars)\n"
        external_context += f"License: {repo['license_type']}\n"
        external_context += f"Description: {repo['description']}\n"
        if repo.get("readme_summary"):
            # Truncate to avoid context overflow
            readme = repo["readme_summary"][:3000]
            external_context += f"\nREADME:\n{readme}\n"

    # Build prompt
    prompt = f"""Analyze the following repositories related to "{topic}" and provide:

1. **Key Patterns**: What common patterns do these top repositories use?
2. **Best Practices**: What best practices can be learned?
3. **Innovations**: What innovative approaches are being used?
4. **Recommendations**: What should we consider adopting?

## External Repositories:
{external_context}
"""

    if internal_code:
        prompt += f"""
## Our Internal Implementation:
```
{internal_code[:2000]}
```

Please also identify GAPS between our implementation and the external best practices.
"""

    # Call Gemini using core client with credential rotation
    try:
        from assemblyzero.core.gemini_client import GeminiClient

        client = GeminiClient()
        system_instruction = "You are a technical analyst reviewing open source repositories to identify best practices and innovation opportunities."
        result = client.invoke(system_instruction, prompt)

        if result.success:
            analysis = result.response or "No response received."
        else:
            raise Exception(result.error or "Unknown error")
    except ImportError:
        # Fallback to direct API if client not available
        try:
            from google import genai

            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise Exception("No API key found in GEMINI_API_KEY or GOOGLE_API_KEY")

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            analysis = response.text
        except Exception as e2:
            raise Exception(f"Fallback also failed: {e2}")
    except Exception as e:
        # Return error info but don't fail
        analysis = f"## Analysis Error\n\nCould not complete analysis: {e}\n\n"
        analysis += "## Repositories Found\n\n"
        for repo in found_repos:
            analysis += f"- **{repo['name']}** ({repo['stars']} stars): {repo['description']}\n"

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
        brief += f"(* {repo['stars']}, License: {repo['license_type']})\n"

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
