#!/usr/bin/env python3
"""
AgentOS Config Generator

Reads templates from parent's .claude/templates/ and project's project.json,
outputs concrete configs to the project's .claude/ directory.

Usage:
  python tools/agentos-generate.py --project /path/to/project
  python tools/agentos-generate.py --project Aletheia  # Relative to Projects dir

Files processed:
  - commands/*.md.template → commands/*.md
  - hooks/*.sh.template → hooks/*.sh
  - settings.json.template → settings.json
"""
import json
import sys
from pathlib import Path
import argparse


def load_project_config(project_path: Path) -> dict:
    """Load project.json from the project's .claude directory."""
    project_json = project_path / ".claude" / "project.json"
    if not project_json.exists():
        print(f"ERROR: No project.json found at {project_json}")
        print("Create one based on .claude/project.json.example")
        sys.exit(1)
    return json.loads(project_json.read_text())


def substitute(content: str, variables: dict) -> str:
    """Replace {{VAR}} placeholders with actual values."""
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        content = content.replace(placeholder, value)
    return content


def find_unsubstituted(content: str) -> list:
    """Find any remaining {{VAR}} placeholders that weren't substituted."""
    import re
    return re.findall(r'\{\{[A-Z_]+\}\}', content)


def generate_configs(project_path: Path, templates_path: Path, variables: dict):
    """Generate concrete configs from templates."""
    generated = []
    warnings = []

    # Process each template file
    for template in templates_path.rglob("*.template"):
        # Calculate output path relative to project's .claude/
        rel_path = template.relative_to(templates_path)
        # Remove .template extension
        output_name = str(rel_path)[:-9]  # Remove ".template"
        output_path = project_path / ".claude" / output_name

        # Read and substitute
        content = template.read_text(encoding='utf-8')
        concrete = substitute(content, variables)

        # Check for unsubstituted placeholders
        remaining = find_unsubstituted(concrete)
        if remaining:
            warnings.append(f"  {output_path}: Unsubstituted placeholders: {remaining}")

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(concrete, encoding='utf-8')
        generated.append(str(output_path))

    return generated, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Generate AgentOS configs from templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/agentos-generate.py --project /c/Users/mcwiz/Projects/Aletheia
  python tools/agentos-generate.py --project Aletheia
  python tools/agentos-generate.py --project . --templates /c/Users/mcwiz/Projects/.claude/templates
        """
    )
    parser.add_argument(
        "--project", "-p",
        required=True,
        help="Path to project directory (absolute or relative to Projects dir)"
    )
    parser.add_argument(
        "--templates", "-t",
        default=None,
        help="Path to templates directory (default: parent's .claude/templates/)"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be generated without writing files"
    )

    args = parser.parse_args()

    # Resolve project path
    project_path = Path(args.project)
    if not project_path.is_absolute():
        # Assume relative to Projects directory
        # Use Windows-native path that works in both cmd and Git Bash
        projects_dir = Path.home() / "Projects"
        project_path = projects_dir / args.project

    if not project_path.exists():
        print(f"ERROR: Project directory not found: {project_path}")
        sys.exit(1)

    # Load project configuration
    config = load_project_config(project_path)
    variables = config.get("variables", {})

    # Resolve templates path
    if args.templates:
        templates_path = Path(args.templates)
    elif "inherit_from" in config:
        templates_path = Path(config["inherit_from"]) / ".claude" / "templates"
    else:
        # Default: parent directory's templates
        templates_path = project_path.parent / ".claude" / "templates"

    if not templates_path.exists():
        print(f"ERROR: Templates directory not found: {templates_path}")
        sys.exit(1)

    print(f"Project:   {project_path}")
    print(f"Templates: {templates_path}")
    print(f"Variables: {list(variables.keys())}")
    print()

    if args.dry_run:
        print("DRY RUN - would generate:")
        for template in templates_path.rglob("*.template"):
            rel_path = template.relative_to(templates_path)
            output_name = str(rel_path)[:-9]
            print(f"  {project_path / '.claude' / output_name}")
        return

    # Generate configs
    generated, warnings = generate_configs(project_path, templates_path, variables)

    print("Generated files:")
    for f in generated:
        print(f"  {f}")

    if warnings:
        print()
        print("WARNINGS:")
        for w in warnings:
            print(w)

    print()
    print(f"Done! Generated {len(generated)} files.")


if __name__ == "__main__":
    main()
