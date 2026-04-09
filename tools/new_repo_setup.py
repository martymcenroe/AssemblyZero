#!/usr/bin/env python3
"""
New Repository Setup Script

Scaffolds a complete new repository with the canonical AssemblyZero structure,
creates it on GitHub, and configures it for agent-driven development.

Usage:
    # Basic usage (private repo)
    python tools/new_repo_setup.py MyNewProject

    # Public repo
    python tools/new_repo_setup.py MyNewProject --public

    # Audit existing structure (no creation)
    python tools/new_repo_setup.py MyNewProject --audit

    # Local only (skip GitHub creation)
    python tools/new_repo_setup.py MyNewProject --no-github

See: docs/standards/0009-canonical-project-structure.md
"""

import argparse
import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Import AssemblyZero config for path resolution
try:
    from assemblyzero_config import config
except ImportError:
    # Fallback if running from a different directory
    sys.path.insert(0, str(Path(__file__).parent))
    from assemblyzero_config import config


# ---------------------------------------------------------------------------
# Schema types and exceptions
# ---------------------------------------------------------------------------

class SchemaValidationError(Exception):
    """Raised when schema structure is invalid."""
    pass


# ---------------------------------------------------------------------------
# Schema-driven structure functions (Issue #99 / LLD-099)
# ---------------------------------------------------------------------------

# Default schema location: co-located with standard 0009
_DEFAULT_SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "standards" / "0009-structure-schema.json"


def load_structure_schema(schema_path: Path | None = None) -> dict:
    """Load and validate the project structure schema from JSON file.

    Args:
        schema_path: Path to schema file. Defaults to standard location.

    Returns:
        Parsed and validated schema dictionary.

    Raises:
        FileNotFoundError: If schema file doesn't exist.
        json.JSONDecodeError: If schema is invalid JSON.
        SchemaValidationError: If schema structure is invalid.
    """
    path = schema_path or _DEFAULT_SCHEMA_PATH
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    text = path.read_text(encoding="utf-8")
    schema = json.loads(text)

    # Validate required top-level keys
    for key in ("version", "directories", "files"):
        if key not in schema:
            raise SchemaValidationError(
                f"Schema missing required key: '{key}'"
            )

    # Security validation
    validate_paths_no_traversal(schema)

    return schema


def _flatten_dirs_recursive(
    entries: dict, prefix: str = "", required_only: bool = False
) -> list[str]:
    """Recursively flatten nested directory entries into path list."""
    result = []
    for name, entry in entries.items():
        path = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"
        if required_only and not entry.get("required", True):
            continue
        result.append(path)
        children = entry.get("children")
        if children:
            result.extend(
                _flatten_dirs_recursive(children, path, required_only)
            )
    return result


def flatten_directories(
    schema: dict, required_only: bool = False
) -> list[str]:
    """Flatten nested directory structure into list of paths.

    Args:
        schema: The loaded project structure schema.
        required_only: If True, only return required directories.

    Returns:
        List of directory paths relative to project root.
    """
    return _flatten_dirs_recursive(
        schema.get("directories", {}), "", required_only
    )


def flatten_files(
    schema: dict, required_only: bool = False
) -> list[dict[str, Any]]:
    """Flatten file definitions into list of file configs.

    Args:
        schema: The loaded project structure schema.
        required_only: If True, only return required files.

    Returns:
        List of file configurations with path and metadata.
    """
    result = []
    for path, entry in schema.get("files", {}).items():
        if required_only and not entry.get("required", True):
            continue
        result.append({"path": path, **entry})
    return result


def validate_paths_no_traversal(schema: dict) -> None:
    """Validate that no paths in schema contain traversal sequences.

    Raises:
        SchemaValidationError: If any path contains '..' or is absolute.
    """
    all_paths = flatten_directories(schema) + [
        f["path"] for f in flatten_files(schema)
    ]
    for p in all_paths:
        if ".." in p:
            raise SchemaValidationError(
                f"Path traversal detected in schema path: '{p}'"
            )
        if p.startswith("/") or p.startswith("\\"):
            raise SchemaValidationError(
                f"Absolute path detected in schema path: '{p}'"
            )


def validate_template_files_exist(
    schema: dict, template_dir: Path
) -> None:
    """Validate that all referenced template files exist.

    Raises:
        SchemaValidationError: If any referenced template file doesn't exist.
    """
    for path, entry in schema.get("files", {}).items():
        template = entry.get("template")
        if template:
            template_path = template_dir / template
            if not template_path.exists():
                raise SchemaValidationError(
                    f"Referenced template file not found: '{template}' "
                    f"(for file '{path}', looked in {template_dir})"
                )


def create_structure(
    root: Path,
    schema: dict,
    force: bool = False,
    logger: logging.Logger | None = None,
) -> dict:
    """Create project directory structure from schema.

    Args:
        root: Root directory where structure should be created.
        schema: The loaded project structure schema.
        force: If True, overwrite existing files. If False, skip existing.
        logger: Optional logger for progress output.

    Returns:
        Dict with created_dirs, created_files, skipped_files lists.
    """
    result = {"created_dirs": [], "created_files": [], "skipped_files": []}

    # Create directories
    for dir_path in flatten_directories(schema):
        full = root / dir_path
        full.mkdir(parents=True, exist_ok=True)
        result["created_dirs"].append(dir_path)
        if logger:
            logger.info("Created directory: %s", dir_path)

    # Create files (empty placeholders unless template specified)
    for file_info in flatten_files(schema):
        path = file_info["path"]
        full = root / path
        full.parent.mkdir(parents=True, exist_ok=True)

        if full.exists() and not force:
            result["skipped_files"].append(path)
            if logger:
                logger.info("Skipped (exists): %s", path)
            continue

        # Create empty file (templates handled by the main workflow,
        # not the schema create_structure — the main() function writes
        # actual content for CLAUDE.md, README.md, etc.)
        full.touch()
        result["created_files"].append(path)
        if logger:
            logger.info("Created file: %s", path)

    return result


def audit_project_structure(
    project_root: Path, schema: dict
) -> dict:
    """Validate project structure against schema.

    Args:
        project_root: Root directory of project to audit.
        schema: The loaded project structure schema.

    Returns:
        Dict with missing_required_dirs, missing_required_files,
        missing_optional_dirs, missing_optional_files, and valid flag.
    """
    result = {
        "missing_required_dirs": [],
        "missing_required_files": [],
        "missing_optional_dirs": [],
        "missing_optional_files": [],
        "valid": True,
    }

    # Check all directories
    all_dirs = flatten_directories(schema)
    required_dirs = set(flatten_directories(schema, required_only=True))

    for d in all_dirs:
        if not (project_root / d).exists():
            if d in required_dirs:
                result["missing_required_dirs"].append(d)
                result["valid"] = False
            else:
                result["missing_optional_dirs"].append(d)

    # Check all files
    all_files = flatten_files(schema)
    required_file_paths = {
        f["path"] for f in flatten_files(schema, required_only=True)
    }

    for f in all_files:
        path = f["path"]
        if not (project_root / path).exists():
            if path in required_file_paths:
                result["missing_required_files"].append(path)
                result["valid"] = False
            else:
                result["missing_optional_files"].append(path)

    return result


def validate_name(name: str) -> tuple[bool, str]:
    """
    Validate repository name.

    Args:
        name: The proposed repository name

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, "Name cannot be empty"

    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', name):
        return False, "Name must start with a letter and contain only letters, numbers, hyphens, and underscores"

    if len(name) > 100:
        return False, "Name cannot exceed 100 characters"

    return True, ""


def get_github_username() -> str:
    """Get the authenticated GitHub username."""
    result = subprocess.run(
        ["gh", "api", "user", "-q", ".login"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return result.stdout.strip()


def run_command(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """
    Run a shell command.

    Args:
        cmd: Command as list of strings
        cwd: Working directory
        check: Whether to raise on non-zero exit

    Returns:
        CompletedProcess result
    """
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check, timeout=60)


def create_directory_structure(project_path: Path) -> list[str]:
    """
    Create the canonical directory structure from schema.

    Args:
        project_path: Path to the project root

    Returns:
        List of created directories
    """
    schema = load_structure_schema()
    all_dirs = flatten_directories(schema)
    created = []

    for dir_path in all_dirs:
        full_path = project_path / dir_path
        full_path.mkdir(parents=True, exist_ok=True)

        # Add .gitkeep to empty directories
        gitkeep = full_path / ".gitkeep"
        if not any(full_path.iterdir()):
            gitkeep.touch()

        created.append(str(dir_path))

    return created


def create_project_json(project_path: Path, name: str, github_user: str) -> None:
    """
    Create the .claude/project.json file.

    Args:
        project_path: Path to the project root
        name: Project name
        github_user: GitHub username
    """
    # Get path formats from config
    projects_root_unix = config.projects_root_unix()
    assemblyzero_root_windows = config.assemblyzero_root()

    project_json = {
        "variables": {
            "PROJECT_ROOT": f"{projects_root_unix}/{name}",
            "PROJECT_ROOT_WINDOWS": str(project_path),
            "PROJECT_NAME": name,
            "GITHUB_REPO": f"{github_user}/{name}",
            "TOOLS_DIR": f"{projects_root_unix}/{name}/tools",
            "WORKTREE_PATTERN": f"{name}-{{ID}}"
        },
        "inherit_from": assemblyzero_root_windows
    }

    project_json_path = project_path / ".claude" / "project.json"
    project_json_path.write_text(json.dumps(project_json, indent=2) + "\n", encoding='utf-8')


def create_claude_md(project_path: Path, name: str, github_user: str) -> None:
    """
    Create the project CLAUDE.md file.

    Args:
        project_path: Path to the project root
        name: Project name
        github_user: GitHub username
    """
    assemblyzero_root_windows = config.assemblyzero_root()
    projects_root_unix = config.projects_root_unix()

    content = f"""# CLAUDE.md - {name} Project

You are a team member on the {name} project, not a tool.

## FIRST: Read AssemblyZero Core Rules

**Before doing any work, read the AssemblyZero core rules:**
`{assemblyzero_root_windows}\\CLAUDE.md`

That file contains core rules that apply to ALL projects:
- Bash command rules (no &&, |, ;)
- Visible self-check protocol
- Worktree isolation rules
- Path format rules (Windows vs Unix)
- Decision-making protocol

**This file adds {name}-specific rules ON TOP of those core rules.**

---

## Project Identifiers

- **Repository:** `{github_user}/{name}`
- **Project Root (Windows):** `{project_path}`
- **Project Root (Unix):** `{projects_root_unix}/{name}`
- **Worktree Pattern:** `{name}-{{IssueID}}` (e.g., `{name}-45`)

---

## Project-Specific Workflow Rules

### Required Workflow

- **Docs before Code:** Write the LLD (`docs/lld/active/`) before writing code
- **Worktree before code:** `git worktree add ../{name}-{{ID}} -b {{ID}}-short-desc`
- **Push immediately:** `git push -u origin HEAD`

### Reports Before Merge (PRE-MERGE GATE)

**Before ANY PR merge, you MUST:**

1. Create `docs/reports/active/1{{IssueID}}-implementation-report.md`
2. Create `docs/reports/active/1{{IssueID}}-test-report.md`
3. Wait for orchestrator review

---

## Documentation Structure

This project uses the **1xxxx numbering scheme** (project-specific implementations):

| Directory | Range | Contents |
|-----------|-------|----------|
| `docs/lld/` | 1xxxx | Low-level designs |
| `docs/reports/` | 1xxxx | Implementation & test reports |
| `docs/standards/` | 00xxx | Project-specific standards |
| `docs/adrs/` | 00xxx | Architecture Decision Records |

---

## Session Logging

At end of session, append a summary to `docs/session-logs/YYYY-MM-DD.md`.

---

## GitHub CLI Safety

- ALWAYS use `--repo {github_user}/{name}` explicitly
- NEVER rely on default repo inference

---

## You Are Not Alone

Other agents may work on this project. Check `docs/session-logs/` for recent context.
"""
    claude_md_path = project_path / "CLAUDE.md"
    claude_md_path.write_text(content, encoding='utf-8')


def create_gemini_md(project_path: Path, name: str, github_user: str) -> None:
    """
    Create the project GEMINI.md file.

    Args:
        project_path: Path to the project root
        name: Project name
        github_user: GitHub username
    """
    assemblyzero_root_windows = config.assemblyzero_root()
    projects_root_unix = config.projects_root_unix()

    content = f"""# Gemini Operational Protocols

## FIRST: Read Core Rules

**Before doing any work, read the AssemblyZero core rules:**
`{assemblyzero_root_windows}\\CLAUDE.md`

That file contains core rules that apply to ALL projects and ALL agents:
- Bash command rules (no &&, |, ;)
- Path format rules
- Worktree isolation rules
- Decision-making protocol

---

## 1. Session Initialization (The Handshake)

**CRITICAL:** When a session begins:
1. **Analyze:** Silently parse the provided `git status` or issue context.
2. **Halt & Ask:** Your **FIRST** output must be exactly:
   > "ACK. State determination complete. Please identify my model version."
3. **Wait:** Do not proceed until the user replies (e.g., "3.0 Pro").
4. **Update Identity:** Incorporate the version into your Metadata Tag for all future turns.

---

## 2. Execution Rules

- **Authority:** `AssemblyZero:standards/0002-coding-standards` is the law for Git workflows.
- **One Step Per Turn:** Provide one distinct step, then wait for confirmation.
- **Check First:** Verify paths/content before changing them.
- **Copy-Paste Ready:** No placeholders. Use heredocs for new files.

---

## 3. Project-Specific Context

**Project:** {name}
**Repository:** {github_user}/{name}
**Project Root (Windows):** {project_path}
**Project Root (Unix):** {projects_root_unix}/{name}

---

## 4. Session Logging

At session end, append a summary to `docs/session-logs/YYYY-MM-DD.md`:
- **Day boundary:** 3:00 AM CT to following day 2:59 AM CT
- **Include:** date/time, model name (from handshake), summary, files touched, state on exit

---

## 5. You Are Not Alone

Other agents (Claude, human orchestrators) work on this project. Check `docs/session-logs/` for recent context before starting work.
"""
    gemini_md_path = project_path / "GEMINI.md"
    gemini_md_path.write_text(content, encoding='utf-8')


def create_readme(project_path: Path, name: str) -> None:
    """
    Create the README.md file.

    Args:
        project_path: Path to the project root
        name: Project name
    """
    content = f"""# {name}

> One-line description of what this project does.

## Overview

Brief (2-3 sentence) description of the project's purpose and value.

## Status

| Aspect | Status |
|--------|--------|
| Development | Active |
| Documentation | In Progress |
| Tests | None |

## Quick Start

```bash
# Installation
poetry install  # or npm install

# Run
poetry run python src/main.py  # or npm start
```

## Project Structure

```
{name}/
├── src/            # Application source code
├── tests/          # Test suites
├── docs/           # Documentation
└── tools/          # Development utilities
```

## Documentation

- [Architecture](docs/adrs/) - Architecture Decision Records
- [Standards](docs/standards/) - Coding and process standards
- [Runbooks](docs/runbooks/) - Operational procedures

## Development

This project follows [AssemblyZero](https://github.com/martymcenroe/AssemblyZero) conventions:
- Worktree isolation for all code changes
- Pre-merge gates (implementation + test reports)
- Session logging for agent continuity

## License

PolyForm Noncommercial 1.0.0 - See LICENSE file.

---

*Managed under [AssemblyZero](https://github.com/martymcenroe/AssemblyZero) governance.*
"""
    readme_path = project_path / "README.md"
    readme_path.write_text(content, encoding='utf-8')


def create_license(project_path: Path, github_user: str) -> None:
    """
    Create the PolyForm Noncommercial LICENSE file.

    Args:
        project_path: Path to the project root
        github_user: GitHub username for copyright notice
    """
    year = datetime.now().year
    content = f"""# PolyForm Noncommercial License 1.0.0

<https://polyformproject.org/licenses/noncommercial/1.0.0>

## Acceptance

In order to get any license under these terms, you must agree
to them as both strict obligations and conditions to all
your licenses.

## Copyright License

The licensor grants you a copyright license for the
software to do everything you might do with the software
that would otherwise infringe the licensor's copyright
in it for any permitted purpose.  However, you may
only distribute the software according to [Distribution
License](#distribution-license) and make changes or new works
based on the software according to [Changes and New Works
License](#changes-and-new-works-license).

## Distribution License

The licensor grants you an additional copyright license
to distribute copies of the software.  Your license
to distribute covers distributing the software with
changes and new works permitted by [Changes and New Works
License](#changes-and-new-works-license).

## Notices

You must ensure that anyone who gets a copy of any part of
the software from you also gets a copy of these terms or the
URL for them above, as well as copies of any plain-text lines
beginning with `Required Notice:` that the licensor provided
with the software.  For example:

> Required Notice: Copyright {github_user} (https://github.com/{github_user})

## Changes and New Works License

The licensor grants you an additional copyright license to
make changes and new works based on the software for any
permitted purpose.

## Patent License

The licensor grants you a patent license for the software that
covers patent claims the licensor can license, or becomes able
to license, that you would infringe by using the software.

## Noncommercial Purposes

Any noncommercial purpose is a permitted purpose.

## Personal Uses

Personal use for research, experiment, and testing for
the benefit of public knowledge, personal study, private
entertainment, hobby projects, amateur pursuits, or religious
observance, without any anticipated commercial application,
is use for a permitted purpose.

## Noncommercial Organizations

Use by any charitable organization, educational institution,
public research organization, public safety or health
organization, environmental protection organization,
or government institution is use for a permitted purpose
regardless of the source of funding or obligations resulting
from the funding.

## Fair Use

You may have "fair use" rights for the software under the
law. These terms do not limit them.

## No Other Rights

These terms do not allow you to sublicense or transfer any of
your licenses to anyone else, or prevent the licensor from
granting licenses to anyone else.  These terms do not imply
any other licenses.

## Patent Defense

If you make any written claim that the software infringes or
contributes to infringement of any patent, your patent license
for the software granted under these terms ends immediately. If
your company makes such a claim, your patent license ends
immediately for work on behalf of your company.

## Violations

The first time you are notified in writing that you have
violated any of these terms, or done anything with the software
not covered by your licenses, your licenses can nonetheless
continue if you come into full compliance with these terms,
and take practical steps to correct past violations, within
32 days of receiving notice.  Otherwise, all your licenses
end immediately.

## No Liability

***As far as the law allows, the software comes as is, without
any warranty or condition, and the licensor will not be liable
to you for any damages arising out of these terms or the use
or nature of the software, under any kind of legal claim.***

## Definitions

The **licensor** is the individual or entity offering these
terms, and the **software** is the software the licensor makes
available under these terms.

**You** refers to the individual or entity agreeing to these
terms.

**Your company** is any legal entity, sole proprietorship,
or other kind of organization that you work for, plus all
organizations that have control over, are under the control of,
or are under common control with that organization.  **Control**
means ownership of substantially all the assets of an entity,
or the power to direct its management and policies by vote,
contract, or otherwise.  Control can be direct or indirect.

**Your licenses** are all the licenses granted to you for the
software under these terms.

**Use** means anything you do with the software requiring one
of your licenses.

---

Required Notice: Copyright (c) {year} {github_user} (https://github.com/{github_user})
"""
    license_path = project_path / "LICENSE"
    license_path.write_text(content, encoding='utf-8')


def create_mit_license(project_path: Path, github_user: str) -> None:
    """Create MIT LICENSE file.

    Issue #755: Alternative license for open-source projects.
    """
    year = datetime.now().year
    content = f"""MIT License

Copyright (c) {year} {github_user}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
    license_path = project_path / "LICENSE"
    license_path.write_text(content, encoding='utf-8')


def create_gitignore(project_path: Path) -> None:
    """
    Create the .gitignore file.

    Args:
        project_path: Path to the project root
    """
    content = """# Claude Code local settings (machine-specific)
.claude/settings.local.json

# Claude Code temporary files
tmpclaude-*

# Python
__pycache__/
*.pyc
*.pyo
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
ENV/

# Node.js
node_modules/
npm-debug.log
yarn-error.log

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment & Secrets
.env
.env.*
.dev.vars
*.pem
*.key
credentials.json
secrets.json

# Logs
*.log
logs/

# Coverage
.coverage
htmlcov/
coverage.xml

# Test artifacts
.pytest_cache/
.tox/

# Build artifacts
*.generated.json

# Unleashed session transcripts (auto-generated, untracked)
data/unleashed/
"""
    gitignore_path = project_path / ".gitignore"
    gitignore_path.write_text(content, encoding='utf-8')


def create_file_inventory(project_path: Path, name: str) -> None:
    """
    Create the docs/00003-file-inventory.md file.

    Per 0009 standard, this file is REQUIRED for all projects.

    Args:
        project_path: Path to the project root
        name: Project name
    """
    content = f"""# 00003 - {name} File Inventory

**Status:** Active
**Created:** {datetime.now().strftime('%Y-%m-%d')}
**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}

---

## Purpose

This document provides a complete inventory of files in the {name} project, organized by directory. It serves as a quick reference for agents and developers to understand the project structure.

---

## Directory Structure

```
{name}/
├── .claude/                    # Claude Code configuration
├── data/                       # App data: examples, templates, seeds
├── docs/                       # All documentation
│   ├── adrs/                   # Architecture Decision Records
│   ├── standards/              # Project-specific standards
│   ├── templates/              # Document templates
│   ├── lld/                    # Low-Level Designs
│   │   ├── active/             # In-progress LLDs
│   │   └── done/               # Completed LLDs
│   ├── reports/                # Implementation & test reports
│   │   ├── active/             # In-progress reports
│   │   └── done/               # Completed reports
│   ├── runbooks/               # Operational procedures
│   ├── session-logs/           # Agent session context
│   ├── audit-results/          # Historical audit outputs
│   ├── media/                  # Artwork, videos, tutorials
│   ├── legal/                  # ToS, privacy policy, regulatory
│   └── design/                 # UI mockups, style guides
├── src/                        # Application source code
├── tests/                      # Test suites
│   ├── unit/                   # Fast, isolated tests
│   ├── integration/            # Multiple components together
│   ├── e2e/                    # End-to-end tests
│   ├── smoke/                  # Quick sanity/environment tests
│   ├── contract/               # API contract tests
│   ├── visual/                 # Visual regression tests
│   ├── benchmark/              # Performance tests
│   ├── security/               # Security tests
│   ├── accessibility/          # Accessibility tests
│   ├── compliance/             # Compliance tests
│   ├── fixtures/               # Test data
│   └── harness/                # Test utilities
├── tools/                      # Development utilities
├── CLAUDE.md                   # Claude agent instructions
├── GEMINI.md                   # Gemini agent instructions
├── README.md                   # Project overview
├── LICENSE                     # PolyForm Noncommercial 1.0.0
├── .gitignore                  # Git ignore rules
└── .unleashed.json             # Unleashed wrapper config (model, effort)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Instructions for Claude agents working on this project |
| `GEMINI.md` | Instructions for Gemini agents working on this project |
| `README.md` | Project overview and quick start guide |
| `.claude/project.json` | Project variables for AssemblyZero template generation |

---

## Documentation Numbering

This project uses the AssemblyZero numbering scheme:

| Range | Category | Location |
|-------|----------|----------|
| `0xxxx` | Foundational (ADRs, standards) | `docs/adrs/`, `docs/standards/` |
| `1xxxx` | Issue-specific (LLDs, reports) | `docs/lld/`, `docs/reports/` |
| `3xxxx` | Runbooks | `docs/runbooks/` |
| `4xxxx` | Media | `docs/media/` |

---

## Maintenance

This inventory should be updated when:
- New directories are added
- Significant new files are created
- Project structure changes

Use `/audit` to verify structure compliance with AssemblyZero standards.
"""
    inventory_path = project_path / "docs" / "00003-file-inventory.md"
    inventory_path.write_text(content, encoding='utf-8')


def create_unleashed_json(project_path: Path) -> None:
    """Create .unleashed.json with standard wrapper configuration.

    Sets model=opus, effort=max so unleashed wrappers pass the correct
    CLI flags. Without this file, wrappers fall back to tool defaults.

    Args:
        project_path: Path to the project root.
    """
    content = json.dumps({
        "profile": "default",
        "claude": {
            "model": "opus",
            "effort": "max"
        },
        "assemblyZero": False,
        "onboard": {
            "auto": True,
            "pickupThresholdMinutes": 10,
            "guide": None,
            "plan": None
        }
    }, indent=2) + "\n"
    unleashed_path = project_path / ".unleashed.json"
    unleashed_path.write_text(content, encoding='utf-8')


def create_github_workflows(project_path: Path) -> None:
    """Create GitHub Actions workflow files for PR governance.

    Deploys two workflows:
    - pr-sentinel.yml: validates issue references in PR title/body/commits
    - auto-reviewer.yml: calls the reusable auto-reviewer from AssemblyZero
      to approve PRs after pr-sentinel passes (requires Cerberus secrets)

    These workflows make the merge gate work on new repos immediately
    (once Cerberus secrets are deployed fleet-wide).
    """
    workflows_dir = project_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # pr-sentinel: local issue reference check
    pr_sentinel = '''\
name: pr-sentinel

on:
  pull_request:
    branches: [main]
    types: [opened, edited, synchronize, reopened]

permissions:
  checks: write
  statuses: write
  pull-requests: read
  contents: read

jobs:
  issue-reference:
    runs-on: ubuntu-latest
    steps:
      - name: Check for issue reference
        env:
          PR_TITLE: ${{ github.event.pull_request.title }}
          PR_BODY: ${{ github.event.pull_request.body }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          GH_TOKEN: ${{ github.token }}
        run: |
          PATTERN='([Cc]loses #[0-9]+)'

          PR_COMMITS=$(gh pr view $PR_NUMBER --repo ${{ github.repository }} --json commits --jq '.commits[].messageHeadline, .commits[].messageBody')
          if echo "$PR_COMMITS" | grep -qE "$PATTERN"; then
            echo "Issue reference found in commit messages"
            exit 0
          fi

          if echo "$PR_TITLE" | grep -qE "$PATTERN"; then
            echo "Issue reference found in PR title"
            exit 0
          fi

          if echo "$PR_BODY" | grep -qE "$PATTERN"; then
            echo "Issue reference found in PR body"
            exit 0
          fi

          echo "No issue reference found."
          echo ""
          echo "PR title, body, or commit message must close a GitHub issue."
          echo "Required Format: 'Closes #123'"
          exit 1
'''
    (workflows_dir / "pr-sentinel.yml").write_text(pr_sentinel, encoding="utf-8")

    # auto-reviewer caller: invokes AssemblyZero's reusable workflow
    auto_reviewer = '''\
name: Auto Review

# Caller workflow: invokes the reusable auto-reviewer from AssemblyZero.
# Requires Cerberus secrets (REVIEWER_APP_ID, REVIEWER_APP_PRIVATE_KEY).
# Deploy secrets fleet-wide: poetry run python tools/deploy_cerberus_secrets.py

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]

permissions:
  pull-requests: write
  checks: read

jobs:
  auto-review:
    uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main
    with:
      required_checks: "issue-reference"
    secrets:
      REVIEWER_APP_ID: ${{ secrets.REVIEWER_APP_ID }}
      REVIEWER_APP_PRIVATE_KEY: ${{ secrets.REVIEWER_APP_PRIVATE_KEY }}
'''
    (workflows_dir / "auto-reviewer.yml").write_text(auto_reviewer, encoding="utf-8")


def create_settings_json(project_path: Path) -> None:
    """
    Create .claude/settings.json with per-repo hooks.

    Only deploys secret-file-guard.sh per-repo. Security hooks (secret-guard.sh,
    bash-gate.sh) are registered globally in ~/.claude/settings.json and do not
    need per-repo copies. See AssemblyZero #872.

    Args:
        project_path: Path to the project root
    """
    projects_root_unix = config.projects_root_unix()
    project_name = project_path.name

    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Read|Write|Edit|Grep|NotebookEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f"bash {projects_root_unix}/{project_name}/.claude/hooks/secret-file-guard.sh",
                            "timeout": 5,
                            "description": "Secret File Guard (blocks file tools on .env, credentials)"
                        }
                    ]
                }
            ],
            "PostToolUse": []
        }
    }

    settings_path = project_path / ".claude" / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding='utf-8')


def deploy_canonical_hooks(project_path: Path) -> None:
    """
    Copy per-repo hooks from AssemblyZero to the new project.

    Only deploys secret-file-guard.sh per-repo. Security hooks (secret-guard.sh,
    bash-gate.sh) are registered globally in ~/.claude/settings.json and do not
    need per-repo copies. See AssemblyZero #872.

    Args:
        project_path: Path to the project root

    Raises:
        FileNotFoundError: If AssemblyZero hook source files don't exist.
    """
    import shutil

    assemblyzero_root = Path(config.assemblyzero_root())
    source_hooks_dir = assemblyzero_root / ".claude" / "hooks"
    target_hooks_dir = project_path / ".claude" / "hooks"
    target_hooks_dir.mkdir(parents=True, exist_ok=True)

    per_repo_hooks = ["secret-file-guard.sh"]
    for hook_name in per_repo_hooks:
        source = source_hooks_dir / hook_name
        if not source.exists():
            raise FileNotFoundError(
                f"Canonical hook not found: {source}\n"
                f"AssemblyZero hooks must exist before creating new repos."
            )
        target = target_hooks_dir / hook_name
        shutil.copy2(str(source), str(target))


def configure_branch_protection(github_user: str, repo_name: str) -> bool:
    """
    Configure branch protection on the main branch via GitHub API.

    Sets: require PR, block force push, block deletion.
    Does NOT set required status checks (repo needs at least one push first).

    Args:
        github_user: GitHub username
        repo_name: Repository name

    Returns:
        True if protection was configured, False if it failed.
    """
    # Branch protection requires at least one commit on main.
    # Verify remote branch exists before attempting.
    try:
        check = subprocess.run(
            ["gh", "api", f"/repos/{github_user}/{repo_name}/branches/main"],
            capture_output=True, text=True, timeout=15,
        )
        if check.returncode != 0:
            print("    Remote branch 'main' not found — skipping branch protection.")
            print("    Push to main first, then re-run or configure manually.")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

    try:
        result = subprocess.run(
            ["gh", "api", "-X", "PUT",
             f"/repos/{github_user}/{repo_name}/branches/main/protection",
             "-F", "required_pull_request_reviews[dismiss_stale_reviews]=false",
             "-F", "required_pull_request_reviews[require_code_owner_reviews]=false",
             "-F", "required_pull_request_reviews[required_approving_review_count]=1",
             "-F", "enforce_admins=true",
             "-F", "restrictions=null",
             "-F", "required_status_checks[strict]=false",
             "-f", "required_status_checks[contexts][]=pr-sentinel / issue-reference",
             "-F", "allow_force_pushes=false",
             "-F", "allow_deletions=false",
             ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def configure_repo_settings(github_user: str, repo_name: str) -> bool:
    """
    Configure GitHub repo settings to match fleet standards.

    Sets: wiki disabled, projects disabled, squash-only merge, delete branch on merge.

    Args:
        github_user: GitHub username
        repo_name: Repository name

    Returns:
        True if settings were applied, False if it failed.
    """
    try:
        result = subprocess.run(
            ["gh", "api", "-X", "PATCH",
             f"/repos/{github_user}/{repo_name}",
             "-F", "has_wiki=false",
             "-F", "has_projects=false",
             "-F", "delete_branch_on_merge=true",
             "-F", "allow_merge_commit=false",
             "-F", "allow_rebase_merge=false"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def audit_structure(project_path: Path, name: str) -> int:
    """
    Audit an existing project structure against the canonical schema.

    Uses the schema as primary source of truth, supplemented by 0011
    audit decisions for allowed-missing exemptions.

    Args:
        project_path: Path to the project root
        name: Project name

    Returns:
        Exit code (0 = pass, 1 = fail)
    """
    print(f"\nAuditing structure for: {project_path}")
    print("=" * 60)

    # Load schema
    schema = load_structure_schema()

    # Load audit decisions (allowed exceptions) from 0011
    assemblyzero_root = Path(config.assemblyzero_root())
    decisions_file = assemblyzero_root / "docs" / "standards" / "0011-audit-decisions.md"
    allowed_missing = set()

    if decisions_file.exists():
        content = decisions_file.read_text(encoding='utf-8')
        if "## Allowed Missing Directories" in content:
            section = content.split("## Allowed Missing Directories")[1].split("##")[0]
            for line in section.splitlines():
                if line.strip().startswith("- `"):
                    pattern = line.split("`")[1].rstrip("/")
                    allowed_missing.add(pattern)

    # Run schema-based audit
    audit_result = audit_project_structure(project_path, schema)

    # Filter out allowed-missing dirs from the required list
    missing = []
    for dir_path in audit_result["missing_required_dirs"]:
        is_allowed = dir_path in allowed_missing
        if not is_allowed:
            for pattern in allowed_missing:
                if pattern.endswith("/*"):
                    prefix = pattern[:-2]
                    if dir_path.startswith(prefix + "/") or dir_path == prefix:
                        is_allowed = True
                        break
        if not is_allowed:
            missing.append(dir_path)

    # Add missing required files
    missing.extend(audit_result["missing_required_files"])

    # Report results
    if missing:
        print("\nMISSING (required):")
        for item in sorted(missing):
            print(f"  - {item}")

    if not missing:
        print("\n[PASS] All required directories and files present")
        return 0
    else:
        print(f"\n[FAIL] Audit failed: {len(missing)} missing items")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold a new repository with AssemblyZero structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Create a new private repository
    python tools/new_repo_setup.py MyNewProject

    # Create a public repository
    python tools/new_repo_setup.py MyNewProject --public

    # Audit an existing project
    python tools/new_repo_setup.py MyExistingProject --audit

    # Create local only (no GitHub)
    python tools/new_repo_setup.py MyNewProject --no-github
        """
    )
    parser.add_argument(
        "name",
        help="Repository name"
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Create public repository (default: private)"
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Audit existing structure, don't create"
    )
    parser.add_argument(
        "--no-github",
        action="store_true",
        help="Skip GitHub repository creation (local only)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files when creating structure (default: skip)"
    )
    parser.add_argument(
        "--license",
        choices=["polyform", "mit"],
        default="polyform",
        help="License type (default: polyform)"
    )

    args = parser.parse_args()

    # Validate name
    valid, error = validate_name(args.name)
    if not valid:
        print(f"ERROR: Invalid repository name: {error}")
        sys.exit(1)

    # Resolve project path
    projects_root = Path(config.projects_root())
    project_path = projects_root / args.name

    # Handle audit mode
    if args.audit:
        if not project_path.exists():
            print(f"ERROR: Project directory not found: {project_path}")
            sys.exit(1)
        exit_code = audit_structure(project_path, args.name)
        sys.exit(exit_code)

    # Check if directory already exists
    if project_path.exists():
        print(f"ERROR: Directory already exists: {project_path}")
        print("Use --audit to check an existing project's structure")
        sys.exit(1)

    # Get GitHub username (unless --no-github)
    github_user = "owner"
    if not args.no_github:
        try:
            github_user = get_github_username()
            print(f"GitHub user: {github_user}")
        except subprocess.CalledProcessError:
            print("ERROR: Could not get GitHub username. Is gh CLI authenticated?")
            print("Run: gh auth login")
            sys.exit(1)

    print(f"\nCreating repository: {args.name}")
    print(f"Location: {project_path}")
    print(f"Visibility: {'public' if args.public else 'private'}")
    print("=" * 60)

    # Wrap in try/except for cleanup on failure
    try:
        _create_repo(project_path, args, github_user)
    except Exception as e:
        print(f"\n{'=' * 60}")
        print(f"[ERROR] Repository creation failed: {e}")
        print(f"{'=' * 60}")
        print(f"\nPartial state may exist at: {project_path}")
        print(f"Review and clean up manually if needed.")
        sys.exit(1)


def _create_repo(project_path: Path, args: argparse.Namespace, github_user: str) -> None:
    """Internal repo creation logic, separated for error handling."""
    # Step 1: Create directory
    print("\n1. Creating directory...")
    project_path.mkdir(parents=True)
    print(f"  Created: {project_path}")

    # Step 2: Initialize git
    print("\n2. Initializing git...")
    run_command(["git", "init"], cwd=project_path)
    run_command(["git", "config", "pull.rebase", "true"], cwd=project_path)
    print("  Initialized git repository (pull.rebase=true)")

    # Step 3: Create directory structure
    print("\n3. Creating directory structure...")
    dirs = create_directory_structure(project_path)
    print(f"  Created {len(dirs)} directories")

    # Step 4: Create .claude/project.json
    print("\n4. Creating .claude/project.json...")
    create_project_json(project_path, args.name, github_user)
    print("  Created project.json")

    # Step 5: Create .claude/settings.json (with canonical hooks)
    print("\n5. Creating .claude/settings.json (with security hooks)...")
    create_settings_json(project_path)
    print("  Created settings.json with secret-file-guard.sh hook (security hooks are global)")

    # Step 5b: Deploy canonical hook scripts
    print("\n5b. Deploying canonical security hooks...")
    try:
        deploy_canonical_hooks(project_path)
        print("  Deployed: secret-file-guard.sh (security hooks are global)")
    except FileNotFoundError as e:
        print(f"  WARNING: {e}")
        print("  Hooks not deployed — repo will start unprotected!")

    # Step 6: Create CLAUDE.md
    print("\n6. Creating CLAUDE.md...")
    create_claude_md(project_path, args.name, github_user)
    print("  Created CLAUDE.md")

    # Step 7: Create GEMINI.md
    print("\n7. Creating GEMINI.md...")
    create_gemini_md(project_path, args.name, github_user)
    print("  Created GEMINI.md")

    # Step 8: Create README.md
    print("\n8. Creating README.md...")
    create_readme(project_path, args.name)
    print("  Created README.md")

    # Step 9: Create LICENSE
    print("\n9. Creating LICENSE...")
    if args.license == "mit":
        create_mit_license(project_path, github_user)
        print("  Created LICENSE (MIT)")
    else:
        create_license(project_path, github_user)
        print("  Created LICENSE (PolyForm Noncommercial 1.0.0)")

    # Step 10: Create .gitignore
    print("\n10. Creating .gitignore...")
    create_gitignore(project_path)
    print("  Created .gitignore")

    # Step 11: Create file inventory (required per 0009 standard)
    print("\n11. Creating docs/00003-file-inventory.md...")
    create_file_inventory(project_path, args.name)
    print("  Created file inventory")

    # Step 11b: Create .unleashed.json (wrapper configuration)
    print("\n11b. Creating .unleashed.json...")
    create_unleashed_json(project_path)
    print("  Created .unleashed.json (model=opus, effort=max)")

    # Step 11c: Create GitHub Actions workflows (PR governance)
    print("\n11c. Creating GitHub Actions workflows...")
    create_github_workflows(project_path)
    print("  Created pr-sentinel.yml (issue reference check)")
    print("  Created auto-reviewer.yml (Cerberus auto-approval caller)")

    # Step 12: Initial commit
    print("\n12. Creating initial commit...")
    run_command(["git", "add", "."], cwd=project_path)
    run_command(
        ["git", "commit", "-m", "chore: initialize project with AssemblyZero\n\nCo-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"],
        cwd=project_path
    )
    print("  Created initial commit")

    github_created = False
    push_succeeded = False
    repo_settings_ok = False
    protection_ok = False

    if not args.no_github:
        print("\n" + "=" * 60)
        print("GITHUB REMOTE")
        print("=" * 60)

        # Detect PAT type and warn about workflow scope
        try:
            auth_result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True, text=True, timeout=15,
            )
            auth_output = auth_result.stdout + auth_result.stderr
            if "github_pat_" in auth_output:
                print("\n  NOTE: Fine-grained PAT detected.")
                print("  Workflow files (.github/workflows/) require 'workflow' scope.")
                print("  If push fails, switch to classic PAT:")
                print("    gh auth login -h github.com -p https")
                print("  Then push manually: git push -u origin main")
                print("  Then switch back to fine-grained PAT.\n")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Step 13: Create GitHub repo
        repo_name_lower = args.name.lower()
        print(f"\n13. Creating GitHub repository ({repo_name_lower})...")
        visibility = "--public" if args.public else "--private"
        try:
            run_command(
                ["gh", "repo", "create", f"{github_user}/{repo_name_lower}", visibility, "--source", ".", "--push"],
                cwd=project_path
            )
            print(f"  Created: https://github.com/{github_user}/{repo_name_lower}")
            github_created = True
            push_succeeded = True
        except Exception as e:
            print(f"  WARNING: gh repo create failed: {e}")
            print("  Your PAT may lack 'create repository' or 'workflow' scope.")
            print("  The local repo is fully valid. To finish manually:")
            print("    1. Create repo at https://github.com/new")
            print(f"    2. git remote add origin https://github.com/{github_user}/{repo_name_lower}.git")
            print("    3. gh auth login -h github.com -p https  # classic PAT with workflow scope")
            print("    4. git push -u origin main")
            print("    5. gh auth login -h github.com -p https  # back to fine-grained PAT")

        if github_created:
            # Step 14: Star the repo
            print("\n14. Starring repository...")
            run_command(
                ["gh", "api", "-X", "PUT", f"/user/starred/{github_user}/{repo_name_lower}"],
                cwd=project_path,
                check=False  # Don't fail if starring fails
            )
            print("  Starred repository")

            # Step 15: Configure repo settings (wiki, projects, merge strategy)
            print("\n15. Configuring repo settings...")
            if configure_repo_settings(github_user, repo_name_lower):
                print("  Repo settings configured:")
                print("    - Wiki: disabled")
                print("    - Projects: disabled")
                print("    - Merge strategy: squash only")
                print("    - Delete branch on merge: enabled")
                repo_settings_ok = True
            else:
                print("  WARNING: Could not configure repo settings.")

            # Step 16: Configure branch protection
            print("\n16. Configuring branch protection...")
            if push_succeeded:
                if configure_branch_protection(github_user, repo_name_lower):
                    print("  Branch protection configured:")
                    print("    - Force push: blocked")
                    print("    - Deletion: blocked")
                    print("    - enforce_admins: enabled")
                    print("    - Required reviews: 1 (Cerberus auto-approves)")
                    print("    - Required check: pr-sentinel / issue-reference")
                    print("    - strict: false")
                    protection_ok = True
                else:
                    print("  WARNING: Could not configure branch protection.")
                    print("  This may fail if the token lacks admin scope.")
                    print("  Configure manually or re-run with a classic token.")
            else:
                print("  SKIPPED: Push failed — no remote branch to protect.")
                print("  After pushing, configure branch protection manually.")

    # Post-setup verification
    print("\n" + "=" * 60)
    print("POST-SETUP VERIFICATION")
    print("=" * 60)

    checks_passed = 0
    checks_total = 0

    # Verify per-repo hook exists (security hooks are global since #872)
    checks_total += 1
    sfg = project_path / ".claude" / "hooks" / "secret-file-guard.sh"
    if sfg.exists():
        print("  [PASS] Per-repo hook deployed (secret-file-guard)")
        checks_passed += 1
    else:
        print("  [FAIL] Per-repo hook missing: secret-file-guard.sh")

    # Verify .gitignore has security patterns
    checks_total += 1
    gitignore = project_path / ".gitignore"
    if gitignore.exists():
        gi_content = gitignore.read_text(encoding="utf-8")
        missing = [p for p in [".env", "*.pem", "*.key", ".dev.vars"]
                   if p not in gi_content]
        if not missing:
            print("  [PASS] .gitignore security patterns present")
            checks_passed += 1
        else:
            print(f"  [FAIL] .gitignore missing patterns: {missing}")
    else:
        print("  [FAIL] .gitignore not found!")

    # Verify settings.json has hooks configured
    checks_total += 1
    settings_file = project_path / ".claude" / "settings.json"
    if settings_file.exists():
        s_content = settings_file.read_text(encoding="utf-8")
        if "secret-file-guard" in s_content:
            print("  [PASS] Hook configuration in settings.json (secret-file-guard)")
            checks_passed += 1
        else:
            print("  [FAIL] settings.json missing hook configuration!")

    print(f"\nVerification: {checks_passed}/{checks_total} checks passed")

    if checks_passed < checks_total:
        print("\nWARNING: Some checks failed. Review and fix before starting work!")

    # Final summary
    if not args.no_github:
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        repo_name_lower = args.name.lower()
        print("  Local scaffold:     OK")
        print(f"  GitHub repo:        {'OK' if github_created else 'FAILED'}")
        print(f"  Push:               {'OK' if push_succeeded else 'FAILED'}")
        print(f"  Repo settings:      {'OK' if repo_settings_ok else 'FAILED — configure manually'}")
        print(f"  Branch protection:  {'OK' if protection_ok else 'FAILED — configure manually or re-run with classic PAT'}")

    print("\n" + "=" * 60)
    print(f"[SUCCESS] Repository '{args.name}' created!")
    print("\nNext steps:")
    print(f"  cd {project_path}")
    if not args.no_github:
        repo_name_lower = args.name.lower()
        print(f"  # Repository: https://github.com/{github_user}/{repo_name_lower}")
        if not push_succeeded:
            print("  # IMPORTANT: Push failed. Switch to classic PAT and push:")
            print("  #   gh auth login -h github.com -p https  # classic PAT")
            print("  #   git push -u origin main")
            print("  #   gh auth login -h github.com -p https  # fine-grained PAT")
    print("  # Deploy Cerberus secrets: see runbook 0927")


if __name__ == "__main__":
    main()
