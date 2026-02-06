"""c/p documentation templates for N8 documentation node.

Issue #93: N8 Documentation Node

Generates CLI (c) and Prompt (p) documentation pairs following:
docs/standards/0008-documentation-convention.md
"""

import re
from datetime import datetime
from pathlib import Path


def get_next_doc_number(docs_dir: Path) -> int:
    """Get next documentation number from existing files.

    Args:
        docs_dir: Path to documentation directory.

    Returns:
        Next available documentation number.
    """
    if not docs_dir.exists():
        return 907  # Start after existing docs

    max_num = 906  # Default starting point
    for f in docs_dir.glob("*c-*.md"):
        match = re.match(r"^(\d+)c-", f.name)
        if match:
            num = int(match.group(1))
            max_num = max(max_num, num)

    return max_num + 1


def extract_commands_from_lld(lld_content: str) -> list[tuple[str, str]]:
    """Extract CLI commands from LLD content.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of (command, description) tuples.
    """
    commands = []

    # Look for code blocks with shell commands
    code_blocks = re.findall(r"```(?:bash|shell|sh)?\n(.*?)```", lld_content, re.DOTALL)
    for block in code_blocks:
        lines = block.strip().split("\n")
        for line in lines:
            line = line.strip()
            # Skip comments and empty lines
            if line.startswith("#") or not line:
                continue
            # Extract commands (simple heuristic)
            if any(line.startswith(cmd) for cmd in ["poetry", "python", "npm", "gh", "git", "pytest"]):
                commands.append((line, "Command from LLD"))

    return commands[:10]  # Limit


def extract_usage_examples(lld_content: str) -> list[str]:
    """Extract usage examples from LLD content.

    Args:
        lld_content: Full LLD markdown content.

    Returns:
        List of usage example strings.
    """
    examples = []

    # Look for Example, Usage, or How to sections
    pattern = r"##?\s*(?:\d\.?\s*)?(?:Example|Usage|How to|Quick Start)\s*\n(.*?)(?=\n##?\s*|$)"
    matches = re.findall(pattern, lld_content, re.DOTALL | re.IGNORECASE)

    for match in matches:
        # Extract bullet points or numbered items
        items = re.findall(r"[-*]\s+(.+?)(?=\n[-*]|\n\n|$)", match)
        examples.extend([item.strip() for item in items[:5]])

    return examples


def generate_cli_doc(
    tool_name: str,
    lld_content: str,
    issue_number: int,
    repo_root: Path,
    implementation_files: list[str] | None = None,
) -> Path:
    """Generate CLI documentation (c document).

    Args:
        tool_name: Name of the CLI tool.
        lld_content: Full LLD markdown content.
        issue_number: GitHub issue number.
        repo_root: Repository root path.
        implementation_files: List of implementation file paths.

    Returns:
        Path to generated CLI doc.
    """
    skills_dir = repo_root / "docs" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    doc_num = get_next_doc_number(skills_dir)
    filename = tool_name.lower().replace(" ", "-").replace("/", "-")
    filename = re.sub(r"[^a-z0-9-]", "", filename)
    doc_path = skills_dir / f"{doc_num}c-{filename}-cli.md"

    # Extract info from LLD
    commands = extract_commands_from_lld(lld_content)

    # Build CLI doc content
    content_parts = [
        f"# {doc_num}c - {tool_name} CLI",
        "",
        f"**Purpose:** CLI reference for {tool_name} (Issue #{issue_number})",
        "",
        "---",
        "",
        "## Prerequisites",
        "",
        "- Python 3.11+",
        "- Poetry environment active",
        "- AssemblyZero installed",
        "",
        "---",
        "",
        "## Quick Reference",
        "",
        "| Command | Description |",
        "|---------|-------------|",
    ]

    if commands:
        for cmd, desc in commands:
            # Truncate long commands
            cmd_display = cmd[:50] + "..." if len(cmd) > 50 else cmd
            content_parts.append(f"| `{cmd_display}` | {desc} |")
    else:
        content_parts.append("| `poetry run python tools/tool.py` | Run tool |")

    content_parts.extend(["", "---", ""])

    content_parts.extend([
        "## Workflow",
        "",
        "### 1. Basic Usage",
        "",
        "```bash",
    ])

    if commands:
        for cmd, _ in commands[:3]:
            content_parts.append(cmd)
    else:
        content_parts.append("poetry run python tools/run_workflow.py --help")

    content_parts.extend([
        "```",
        "",
        "### 2. Common Options",
        "",
        "| Option | Description |",
        "|--------|-------------|",
        "| `--help` | Show help message |",
        "| `--issue N` | Specify issue number |",
        "| `--auto` | Auto mode (no prompts) |",
        "",
        "---",
        "",
        "## Options Reference",
        "",
        "*See `--help` for full options.*",
        "",
        "---",
        "",
        "## See Also",
        "",
        f"- [{doc_num}p - {tool_name} Prompt]({doc_num}p-{filename}-prompt.md)",
        f"- [Issue #{issue_number}](https://github.com/issues/{issue_number})",
        "",
    ])

    doc_path.write_text("\n".join(content_parts), encoding="utf-8")
    return doc_path


def generate_prompt_doc(
    tool_name: str,
    lld_content: str,
    issue_number: int,
    repo_root: Path,
    implementation_files: list[str] | None = None,
) -> Path:
    """Generate Prompt documentation (p document).

    Args:
        tool_name: Name of the tool.
        lld_content: Full LLD markdown content.
        issue_number: GitHub issue number.
        repo_root: Repository root path.
        implementation_files: List of implementation file paths.

    Returns:
        Path to generated Prompt doc.
    """
    skills_dir = repo_root / "docs" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    doc_num = get_next_doc_number(skills_dir)
    filename = tool_name.lower().replace(" ", "-").replace("/", "-")
    filename = re.sub(r"[^a-z0-9-]", "", filename)
    doc_path = skills_dir / f"{doc_num}p-{filename}-prompt.md"

    # Extract usage examples from LLD
    examples = extract_usage_examples(lld_content)

    # Build Prompt doc content
    content_parts = [
        f"# {doc_num}p - {tool_name} Prompt",
        "",
        f"**Purpose:** Natural language guide for using {tool_name} with Claude (Issue #{issue_number})",
        "",
        "---",
        "",
        "## When to Use",
        "",
        "Use the **prompt method** when:",
        f"- You want Claude to guide you through {tool_name}",
        "- You need analysis or recommendations",
        "- The task has complex requirements",
        "",
        f"Use the **[CLI method]({doc_num}c-{filename}-cli.md)** when:",
        "- You know exactly what command to run",
        "- Token efficiency is important",
        "- Running in batch/automated mode",
        "",
        "---",
        "",
        "## Example Prompts",
        "",
        f"### Running {tool_name}",
        "",
        f'> "Run {tool_name.lower()} for issue #{issue_number}"',
        "",
        "Claude will:",
        "1. Load the relevant configuration",
        "2. Execute the workflow",
        "3. Report results",
        "",
    ]

    if examples:
        content_parts.extend([
            "### Additional Examples",
            "",
        ])
        for example in examples:
            content_parts.append(f"> \"{example}\"")
            content_parts.append("")

    content_parts.extend([
        "---",
        "",
        "## Natural Language Queries",
        "",
        "You can ask Claude:",
        "",
        f'- "What does {tool_name.lower()} do?"',
        '- "Show me the available options"',
        '- "Run in auto mode"',
        '- "What happened during the last run?"',
        "",
        "---",
        "",
        "## Tips",
        "",
        f"- Be specific about issue numbers when using {tool_name}",
        "- Use auto mode for unattended operation",
        "- Review the output for errors before proceeding",
        "",
        "---",
        "",
        "## See Also",
        "",
        f"- [{doc_num}c - {tool_name} CLI]({doc_num}c-{filename}-cli.md) - CLI reference",
        f"- [Issue #{issue_number}](https://github.com/issues/{issue_number})",
        "",
    ])

    doc_path.write_text("\n".join(content_parts), encoding="utf-8")
    return doc_path
