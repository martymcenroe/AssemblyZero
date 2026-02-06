"""Runbook template for N8 documentation node.

Issue #93: N8 Documentation Node

Generates operational runbooks for workflow features following AssemblyZero standards.
"""

import re
from datetime import datetime
from pathlib import Path


def extract_procedure_from_lld(lld_content: str) -> list[str]:
    """Extract procedure steps from LLD content.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of procedure steps.
    """
    steps = []

    # Look for Implementation, Procedure, or Steps sections
    patterns = [
        r"##?\s*(?:\d\.?\s*)?(?:Implementation|Procedure|Steps|Workflow)\s*\n(.*?)(?=\n##?\s*\d|$)",
        r"###?\s*(?:\d\.?\s*)?Step\s+\d+.*?\n(.*?)(?=\n###?\s*|$)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, lld_content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            # Extract numbered items or bullet points
            items = re.findall(r"(?:^\d+\.|[-*])\s+(.+?)(?=\n\d+\.|\n[-*]|\n\n|$)", match, re.MULTILINE)
            steps.extend([item.strip() for item in items])

    return steps[:15]  # Limit to 15 steps


def extract_prerequisites_from_lld(lld_content: str) -> list[str]:
    """Extract prerequisites from LLD content.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of prerequisites.
    """
    prereqs = []

    # Look for Prerequisites, Requirements, or Dependencies sections
    pattern = r"##?\s*(?:\d\.?\s*)?(?:Prerequisites|Dependencies|Requirements)\s*\n(.*?)(?=\n##?\s*|$)"
    match = re.search(pattern, lld_content, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
        items = re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n\n|$)", content)
        prereqs.extend([item.strip() for item in items[:10]])

    return prereqs


def extract_verification_from_lld(lld_content: str) -> list[str]:
    """Extract verification steps from LLD content.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of verification steps.
    """
    verifications = []

    # Look for Verification, Testing, or Validation sections
    pattern = r"##?\s*(?:\d\.?\s*)?(?:Verification|Testing|Validation|Test Plan)\s*\n(.*?)(?=\n##?\s*|$)"
    match = re.search(pattern, lld_content, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
        items = re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n\n|$)", content)
        verifications.extend([item.strip() for item in items[:10]])

    return verifications


def get_next_runbook_number(runbooks_dir: Path) -> int:
    """Get next runbook number from existing files.

    Args:
        runbooks_dir: Path to runbooks directory.

    Returns:
        Next available runbook number.
    """
    if not runbooks_dir.exists():
        return 907  # Start after existing runbooks

    max_num = 906  # Default starting point
    for f in runbooks_dir.glob("*.md"):
        match = re.match(r"^(\d+)-", f.name)
        if match:
            num = int(match.group(1))
            max_num = max(max_num, num)

    return max_num + 1


def generate_runbook(
    feature_name: str,
    lld_content: str,
    issue_number: int,
    repo_root: Path,
    implementation_files: list[str] | None = None,
) -> Path:
    """Generate a runbook from LLD content.

    Args:
        feature_name: Name of the feature.
        lld_content: Full LLD markdown content.
        issue_number: GitHub issue number.
        repo_root: Repository root path.
        implementation_files: List of implementation file paths.

    Returns:
        Path to generated runbook.
    """
    runbooks_dir = repo_root / "docs" / "runbooks"
    runbooks_dir.mkdir(parents=True, exist_ok=True)

    # Get next runbook number
    runbook_num = get_next_runbook_number(runbooks_dir)

    # Sanitize feature name for filename
    filename = feature_name.lower().replace(" ", "-").replace("/", "-")
    filename = re.sub(r"[^a-z0-9-]", "", filename)
    runbook_path = runbooks_dir / f"{runbook_num:04d}-{filename}.md"

    # Extract content from LLD
    prereqs = extract_prerequisites_from_lld(lld_content)
    steps = extract_procedure_from_lld(lld_content)
    verifications = extract_verification_from_lld(lld_content)

    # Get mermaid diagram if present
    diagram_pattern = r"```mermaid\n(.*?)```"
    diagram_match = re.search(diagram_pattern, lld_content, re.DOTALL)
    diagram = f"```mermaid\n{diagram_match.group(1)}```" if diagram_match else None

    # Build runbook content
    content_parts = [
        f"# {runbook_num:04d} - {feature_name}",
        "",
        "**Category:** Runbook / Operational Procedure",
        "**Version:** 1.0",
        f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "---",
        "",
        "## Purpose",
        "",
        f"Operational runbook for {feature_name} (Issue #{issue_number}).",
        "",
        "---",
        "",
        "## Prerequisites",
        "",
    ]

    if prereqs:
        content_parts.append("| Requirement | Check |")
        content_parts.append("|-------------|-------|")
        for prereq in prereqs:
            content_parts.append(f"| {prereq} | `verify` |")
    else:
        content_parts.append("- Standard AssemblyZero environment")
        content_parts.append("- GitHub CLI authenticated (`gh auth status`)")
        content_parts.append("- Poetry environment active")

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

    content_parts.extend([
        "## Procedure",
        "",
    ])

    if steps:
        for i, step in enumerate(steps, 1):
            content_parts.append(f"### Step {i}: {step[:50]}{'...' if len(step) > 50 else ''}")
            content_parts.append("")
            content_parts.append(step)
            content_parts.append("")
    else:
        content_parts.append("*Procedure steps to be documented.*")
        content_parts.append("")

    content_parts.extend(["---", ""])

    content_parts.extend([
        "## Verification",
        "",
    ])

    if verifications:
        content_parts.append("| Check | Command | Expected |")
        content_parts.append("|-------|---------|----------|")
        for verif in verifications:
            content_parts.append(f"| {verif[:30]}... | `verify` | Pass |")
    else:
        content_parts.append("| Check | Command | Expected |")
        content_parts.append("|-------|---------|----------|")
        content_parts.append("| Feature works | `run feature` | Success |")

    content_parts.extend(["", "---", ""])

    content_parts.extend([
        "## Troubleshooting",
        "",
        "### Common Issues",
        "",
        "*Document common issues and resolutions here.*",
        "",
        "---",
        "",
        "## Related Documents",
        "",
        f"- [Issue #{issue_number}](https://github.com/issues/{issue_number})",
        f"- [LLD-{issue_number:03d}](../lld/active/LLD-{issue_number:03d}.md)",
        "",
    ])

    if implementation_files:
        content_parts.extend([
            "## Implementation Files",
            "",
        ])
        for f in implementation_files:
            content_parts.append(f"- `{f}`")
        content_parts.append("")

    content_parts.extend([
        "---",
        "",
        "## Revision History",
        "",
        "| Version | Date | Changes |",
        "|---------|------|---------|",
        f"| 1.0 | {datetime.now().strftime('%Y-%m-%d')} | Initial version (auto-generated) |",
        "",
    ])

    runbook_path.write_text("\n".join(content_parts), encoding="utf-8")
    return runbook_path
