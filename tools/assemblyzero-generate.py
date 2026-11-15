#!/usr/bin/env python3
"""
AssemblyZero Config Generator

Reads templates from parent's .claude/templates/ and project's project.json,
outputs concrete configs to the project's .claude/ directory.

Usage:
  python tools/assemblyzero-generate.py --project /path/to/project
  python tools/assemblyzero-generate.py --project Aletheia  # A name, looked up under every Projects root

A name is found under any Projects root (#4773, #4775). A name held under two
roots is refused, and nothing is generated. An absolute path is used as given.

Files processed:
  - commands/*.md.template → commands/*.md
  - hooks/*.sh.template → hooks/*.sh
  - settings.json.template → settings.json

Besides project.json's variables, templates get {{ASSEMBLYZERO_ROOT}}: AssemblyZero's
root, read from project.json's inherit_from on the side this runs on (#4775, #4776).
"""
import json
import os
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from assemblyzero.core.projects_root import locate_repo  # #4775 R3

#: Where Windows names a path on Ubuntu's own disk.
WSL_SHARE = "//wsl.localhost/"


def _drive(value: str) -> tuple[str, str] | None:
    """(letter, rest) when `value` names a Windows drive, else None.

    `value` has forward slashes. The drive spellings are `C:/...`, Git Bash's
    `/c/...` and WSL's `/mnt/c/...`; `rest` is what follows the drive.
    """
    if value[1:2] == ":":
        letter, rest = value[:1], value[2:]
    elif value.startswith("/mnt/"):
        letter, rest = value[5:6], value[6:]
    elif value.startswith("/"):
        letter, rest = value[1:2], value[2:]
    else:
        return None
    if letter.isascii() and letter.isalpha() and rest[:1] in ("", "/"):
        return letter, rest
    return None


def inherit_from_path(value: str, *, windows: bool, mount_root: str = "/mnt",
                      distro: str = "Ubuntu") -> str:
    """AssemblyZero's root from project.json's `inherit_from`, spelled for this side (#4775).

    The file holds whatever spelling the side that created the repository wrote:
    `C:\\...`, `C:/...`, `/c/...`, `/mnt/c/...`, a plain POSIX path, or the WSL
    share `\\\\wsl.localhost\\<distro>\\...` (or `//wsl.localhost/...`).

    On Ubuntu (`windows=False`) a drive path opens through `mount_root`, so
    `C:\\X` is `/mnt/c/X`, and a WSL share path is its POSIX path. On Windows a
    drive path is `C:\\X`, and a POSIX path is on Ubuntu's disk, reached through
    the share for `distro`. A relative value is returned as written, and is read
    against the working directory as it always was.
    """
    text = value.strip().replace("\\", "/")
    if len(text) > 1:
        text = text.rstrip("/") or "/"

    if text.lower().startswith(WSL_SHARE):
        share_distro, _, inner = text[len(WSL_SHARE):].partition("/")
        posix = "/" + inner
        if windows:
            return "\\\\wsl.localhost\\" + share_distro + posix.replace("/", "\\")
        return posix

    drive = _drive(text)
    if drive:
        letter, rest = drive
        if windows:
            return letter.upper() + ":" + (rest or "/").replace("/", "\\")
        return mount_root.rstrip("/") + "/" + letter.lower() + rest

    if text.startswith("/"):
        if windows:
            return "\\\\wsl.localhost\\" + distro + text.replace("/", "\\")
        return text
    return value


def root_variable(root: str, *, windows: bool) -> str:
    """ASSEMBLYZERO_ROOT as templates hold it (#4776): the root with forward slashes.

    Templates put it in bash commands, where an unquoted backslash is lost. On
    Windows `C:/...` and `//wsl.localhost/...` are read by Git Bash and by
    Windows programs alike; on Ubuntu the root is already a POSIX path.
    """
    return (PureWindowsPath(root) if windows else PurePosixPath(root)).as_posix()


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


def setup_ideas_folder(project_path: Path, encrypt: bool = True) -> None:
    """
    Create ideas folder with optional encryption setup.

    Args:
        project_path: Root of the project
        encrypt: Whether to set up git-crypt encryption
    """
    ideas_path = project_path / "ideas"
    ideas_path.mkdir(exist_ok=True)

    # Create README placeholder
    readme = ideas_path / "README.md"
    readme.write_text("""# Ideas

This folder contains pre-issue ideation - half-formed thoughts,
patent concepts, exploratory ideas not ready for the issue tracker.

**Encrypted:** This folder's contents are encrypted in git.
Only authorized users with the key can read these files.

## Naming Convention

- `YYYY-MM-slug.md` - Dated ideas
- `someday/` - "Maybe never" concepts
- Freeform names for evergreen ideas

## Security

**NEVER** use `echo "KEY" | base64 -d > file` - this leaks the key to shell history.

Use clipboard methods or save directly from your password manager.
""", encoding='utf-8')

    # Create someday subfolder
    someday_path = ideas_path / "someday"
    someday_path.mkdir(exist_ok=True)
    (someday_path / ".gitkeep").touch()

    if encrypt:
        # Add encryption rules to root .gitattributes
        gitattributes = project_path / ".gitattributes"
        rules = """
# Encrypt ideas folder (git-crypt)
ideas/** filter=git-crypt diff=git-crypt
ideas/**/* filter=git-crypt diff=git-crypt
"""
        if gitattributes.exists():
            content = gitattributes.read_text(encoding='utf-8')
            if "ideas/**" not in content:
                gitattributes.write_text(content.rstrip() + "\n" + rules, encoding='utf-8')
        else:
            gitattributes.write_text(rules.strip() + "\n", encoding='utf-8')

        print(f"Created ideas/ folder with encryption rules at {ideas_path}")
        print("Next steps:")
        print("  1. git-crypt init")
        print("  2. git-crypt export-key ../your-project-ideas.key")
        print("  3. Store key in 1Password, then DELETE the .key file")
        print("  4. git add .gitattributes ideas/")
        print("  5. git commit -m 'feat: add encrypted ideas folder'")
    else:
        print(f"Created ideas/ folder (no encryption) at {ideas_path}")


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
        description="Generate AssemblyZero configs from templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/assemblyzero-generate.py --project /path/to/Aletheia
  python tools/assemblyzero-generate.py --project Aletheia
  python tools/assemblyzero-generate.py --project Aletheia --templates /path/to/.claude/templates
        """
    )
    parser.add_argument(
        "--project", "-p",
        required=True,
        help=("Project directory: an absolute path, used as given, or a name, "
              "looked up under every Projects root (a name under two roots is refused)")
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
    parser.add_argument(
        "--ideas",
        action="store_true",
        help="Create ideas/ folder with git-crypt encryption setup"
    )
    parser.add_argument(
        "--no-encrypt",
        action="store_true",
        help="With --ideas: skip encryption setup (not recommended for public repos)"
    )

    args = parser.parse_args()

    # Resolve project path. A name is looked up under every Projects root
    # (#4773, #4775): one copy is used, a name under two roots is refused, and a
    # name under none is the first root's path, which the check below reports.
    project_path = Path(args.project)
    if not project_path.is_absolute():
        try:
            project_path = locate_repo(args.project)
        except RuntimeError as e:
            print(f"ERROR: {e}")
            sys.exit(1)

    if not project_path.exists():
        print(f"ERROR: Project directory not found: {project_path}")
        sys.exit(1)

    # Handle --ideas standalone (no project.json required)
    if args.ideas:
        print(f"Project: {project_path}")
        setup_ideas_folder(project_path, encrypt=not args.no_encrypt)
        if not (project_path / ".claude" / "project.json").exists():
            # No project.json, just created ideas folder, we're done
            return

    # Load project configuration (required for template generation)
    config = load_project_config(project_path)
    variables = dict(config.get("variables", {}))

    # AssemblyZero's root, from inherit_from in whatever spelling the file holds
    # (#4775).
    windows = os.name == "nt"
    if "inherit_from" in config:
        assemblyzero_root = Path(inherit_from_path(config["inherit_from"], windows=windows))
        default_templates = assemblyzero_root / ".claude" / "templates"
    else:
        # Default: parent directory's templates
        default_templates = project_path.parent / ".claude" / "templates"

    # Resolve templates path
    templates_path = Path(args.templates) if args.templates else default_templates
    if "inherit_from" not in config:
        # The AssemblyZero whose .claude/templates these are.
        assemblyzero_root = templates_path.resolve().parent.parent

    # Templates reach AssemblyZero through this, never as a sibling of the
    # project (#4776). project.json does not hold it: inherit_from is its one source.
    variables["ASSEMBLYZERO_ROOT"] = root_variable(str(assemblyzero_root), windows=windows)

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
