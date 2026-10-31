"""Wiki page template for N8 documentation node.

Issue #93: N8 Documentation Node

Generates wiki pages from LLD content following AssemblyZero wiki standards.
"""

import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _loud(message: str) -> None:
    """One ERROR line on stderr and in the log (ADR 0236 property 1)."""
    logger.error("[WIKI] %s", message)
    print(f"ERROR [WIKI] {message}", file=sys.stderr, flush=True)


def extract_overview_from_lld(lld_content: str) -> str:
    """Extract overview section from LLD content.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        Extracted overview text, or empty string if not found.
    """
    # Look for Section 1 (Overview, Context, or similar)
    patterns = [
        r"##?\s*1\.?\s*(?:Overview|Context|Context & Goal|Introduction)\s*\n(.*?)(?=\n##?\s*\d|$)",
        r"##?\s*Overview\s*\n(.*?)(?=\n##?\s*|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, lld_content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def extract_mermaid_diagram(lld_content: str) -> str | None:
    """Extract first mermaid diagram from LLD content.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        Mermaid diagram block including fence, or None if not found.
    """
    pattern = r"```mermaid\n(.*?)```"
    match = re.search(pattern, lld_content, re.DOTALL)
    if match:
        return f"```mermaid\n{match.group(1)}```"
    return None


def extract_features_from_lld(lld_content: str) -> list[str]:
    """Extract key features/requirements from LLD.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of feature descriptions.
    """
    features = []

    # Look for requirements section
    req_pattern = r"##?\s*(?:\d\.?\s*)?(?:Requirements|Features|Proposed Changes)\s*\n(.*?)(?=\n##?\s*\d|$)"
    match = re.search(req_pattern, lld_content, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
        # Extract bullet points or numbered items
        items = re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n\n|$)", content)
        if items:
            features.extend([item.strip() for item in items[:10]])  # Limit to 10

    return features


def generate_wiki_page(
    feature_name: str,
    lld_content: str,
    issue_number: int,
    repo_root: Path,
) -> Path:
    """Generate a wiki page from LLD content.

    Args:
        feature_name: Name of the feature for the wiki page title.
        lld_content: Full LLD markdown content.
        issue_number: GitHub issue number.
        repo_root: Repository root path.

    Returns:
        Path to generated wiki page.

    Raises:
        ValueError: naming the feature, the issue and the headings searched,
            after an ERROR line and before anything is written, when the LLD
            has no overview (ADR 0236). The page used to say "*Overview not
            extracted from LLD.*" in its place.
    """
    # Extract content from LLD
    overview = extract_overview_from_lld(lld_content)
    if not overview:
        message = (
            f"the wiki page for {feature_name} (issue #{issue_number}) cannot be "
            f"written from its LLD: the LLD has no overview (headings searched: "
            f"'1. Overview', '1. Context', '1. Context & Goal', "
            f"'1. Introduction', 'Overview')"
        )
        _loud(message)
        raise ValueError(message)
    diagram = extract_mermaid_diagram(lld_content)
    features = extract_features_from_lld(lld_content)

    wiki_dir = repo_root / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize feature name for filename
    filename = feature_name.replace(" ", "-").replace("/", "-")
    filename = re.sub(r"[^a-zA-Z0-9-]", "", filename)
    wiki_path = wiki_dir / f"{filename}.md"

    # Build wiki page content
    content_parts = [
        f"# {feature_name}",
        "",
        f"> Generated from [Issue #{issue_number}](../issues/{issue_number})",
        "",
        "---",
        "",
        "## Overview",
        "",
    ]

    content_parts.append(overview)

    content_parts.extend(["", "---", ""])

    if diagram:
        content_parts.extend([
            "## Architecture",
            "",
            diagram,
            "",
            "---",
            "",
        ])

    if features:
        content_parts.extend([
            "## Key Features",
            "",
        ])
        for feature in features:
            content_parts.append(f"- {feature}")
        content_parts.extend(["", "---", ""])

    content_parts.extend([
        "## Related",
        "",
        f"- [Issue #{issue_number}](../issues/{issue_number})",
        f"- [LLD](../docs/lld/active/LLD-{issue_number:03d}.md)",
        "",
    ])

    wiki_path.write_text("\n".join(content_parts), encoding="utf-8")
    return wiki_path


def update_wiki_sidebar(wiki_page_path: Path, section: str = "Reference") -> bool | None:
    """Update wiki sidebar to include new page.

    Args:
        wiki_page_path: Path to the new wiki page.
        section: Sidebar section to add the page under.

    Returns:
        True if the sidebar was updated; False if it already links the page;
        None if the wiki has no `_Sidebar.md`. False and None are both
        legitimate answers and quiet (ADR 0236 rule 6; ledger 0908, 169 and
        N8's 289): `generate_wiki_page` makes the wiki directory itself, so a
        repository with no wiki gets a page and no sidebar, and most have
        none. They used to be one answer, False, so N8 could not say which;
        N8 now names each.
    """
    wiki_dir = wiki_page_path.parent
    sidebar_path = wiki_dir / "_Sidebar.md"

    if not sidebar_path.is_file():
        return None

    # Get page name from filename (without .md)
    page_name = wiki_page_path.stem
    display_name = page_name.replace("-", " ")

    # Read current sidebar
    sidebar_content = sidebar_path.read_text(encoding="utf-8")

    # Check if page already in sidebar
    if page_name in sidebar_content:
        return False  # Already present

    # Find section and add link
    section_pattern = rf"(### {section}\s*\n)(.*?)(?=\n###|\Z)"
    match = re.search(section_pattern, sidebar_content, re.DOTALL)

    if match:
        # Add new link after section header
        section_header = match.group(1)
        section_content = match.group(2)
        new_link = f"- [{display_name}]({page_name})\n"

        # Insert at end of section (before next section or end)
        lines = section_content.strip().split("\n")
        lines.append(new_link.strip())
        new_section_content = "\n".join(lines) + "\n"

        sidebar_content = sidebar_content.replace(
            match.group(0),
            section_header + new_section_content,
        )
        sidebar_path.write_text(sidebar_content, encoding="utf-8")
        return True

    # Section not found - append to end
    sidebar_content += f"\n---\n\n### {section}\n\n- [{display_name}]({page_name})\n"
    sidebar_path.write_text(sidebar_content, encoding="utf-8")
    return True
