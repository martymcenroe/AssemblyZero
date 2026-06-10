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
import base64
import json
import logging
import os
import re
import subprocess
import sys
import tomllib
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

# Cerberus secret deploy helpers (used by --cerberus-pem flag)
try:
    from deploy_cerberus_secrets import deploy_to_repo, verify_secrets
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))

# Dependabot enablement (#1331) — runs at step 20, inside the same
# classic_pat_session as steps 13-19 so it shares the in-process PAT.
try:
    from enable_dependabot import enable_dependabot_for_repo
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from enable_dependabot import enable_dependabot_for_repo
    from deploy_cerberus_secrets import deploy_to_repo, verify_secrets

# In-process classic PAT for privileged REST calls (ADR-0216).
# Branch protection PUT and repo settings PATCH used to shell out to
# `gh api` which reads GH_TOKEN from the env block (snoopable by sibling
# same-user processes); the PAT now lives only in the Python heap via
# classic_pat_session(). gh repo create --source . --push still reads
# GH_TOKEN for the workflow-scoped initial push — tracked in #1000.
import requests  # noqa: E402
try:
    from _pat_session import classic_pat_session, cerberus_pem_session
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from _pat_session import classic_pat_session, cerberus_pem_session


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

# Canonical location for the encrypted Cerberus App private key per
# ADR-0216 / runbook 0927. When neither --cerberus-pem nor --cerberus-pem-gpg
# is passed, main() falls back to this path so repeat invocations don't need
# to retype the flag every time. Tests patch this constant to a non-existent
# path to exercise the missing-PEM error branch (#1543).
DEFAULT_CERBERUS_PEM_GPG = Path.home() / ".secrets" / "cerberus-pem.gpg"


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


PROJECT_TYPES = ("minimal", "python", "chrome-extension", "pypi", "cf-worker", "web")


def _project_specific_context(project_type: str, name: str) -> str:
    """Return the "## Project-Specific Context" section for the given project type.

    Each stub:
      - Names the stack concretely so the next agent doesn't have to guess
      - Leaves a TODO for project-specific additions
      - References ADR 0219 explicitly so the boundary stays load-bearing

    Stubs MUST be ADDITIVE only — no restating of universal CLAUDE.md content
    (merge sequence, Closes #N rules, branch protection, banned commands,
    GitHub CLI safety). Verified by tests/test_new_repo_setup.py.

    Per #1291: default 'minimal' on operator silence — better to emit a blank
    that the operator fills in than guess wrong for unrecognized types.
    """
    if project_type == "minimal":
        return (
            "## Project-Specific Context\n"
            "\n"
            "_TODO: Add tech stack, architecture, file map, project-type-specific notes,\n"
            "and any workflow overrides specific to this project. The universal\n"
            "CLAUDE.md (auto-loaded by Claude Code's parent-directory traversal) covers\n"
            "fleet-wide rules -- this file only adds what's true for THIS repo\n"
            "specifically. Restating universal content here creates drift on every\n"
            "universal-CLAUDE.md edit (ADR 0219)._\n"
        )
    if project_type == "python":
        return (
            "## Project-Specific Context\n"
            "\n"
            "**Stack:** Python (Poetry); pytest suite at `tests/`. Layout details in\n"
            "the TODO block below.\n"
            "\n"
            "_TODO: Add source layout (single-package under `src/{name}/`, script\n"
            "collection in `tools/`, or another shape), architecture notes, key modules,\n"
            "project-specific gotchas, and any workflow overrides. The universal CLAUDE.md\n"
            "(auto-loaded) covers fleet-wide rules -- only add what's true for THIS repo\n"
            "specifically (ADR 0219)._\n"
        )
    if project_type == "chrome-extension":
        return (
            "## Project-Specific Context\n"
            "\n"
            "**Stack:** Chrome extension, Manifest V3. Source under `extensions/` (or `src/`).\n"
            "Tests via jest + jsdom. Build/bundle via the project's chosen tooling (esbuild,\n"
            "webpack, or vite -- confirm in `package.json` scripts).\n"
            "\n"
            "_TODO: Add MV3 service-worker entry point, content-script layout,\n"
            "message-passing notes, and the manifest version. The universal CLAUDE.md\n"
            "(auto-loaded) covers fleet-wide rules -- only add what's true for THIS\n"
            "repo specifically (ADR 0219)._\n"
        )
    if project_type == "pypi":
        return (
            "## Project-Specific Context\n"
            "\n"
            f"**Stack:** Python (Poetry), published to PyPI. Source under `src/{name}/`,\n"
            "entry points in `[tool.poetry.scripts]`, release via\n"
            "`.github/workflows/release.yml` on tag push. Pending-publisher registration\n"
            "on PyPI documented in runbook 0934.\n"
            "\n"
            "_TODO: Add public-API stability notes, versioning policy, and any\n"
            "release-time checks the project requires. The universal CLAUDE.md\n"
            "(auto-loaded) covers fleet-wide rules -- only add what's true for THIS\n"
            "repo specifically (ADR 0219)._\n"
        )
    if project_type == "cf-worker":
        return (
            "## Project-Specific Context\n"
            "\n"
            "**Stack:** Cloudflare Worker. Source under `src/`. Deploy via `wrangler`\n"
            "(config in `wrangler.toml`). Local dev: `wrangler dev`. Secrets / env\n"
            "via `wrangler secret put`.\n"
            "\n"
            "_TODO: Add the Worker's route map, KV/D1/R2 bindings, observability\n"
            "notes, and the staging-vs-prod environment split. The universal\n"
            "CLAUDE.md (auto-loaded) covers fleet-wide rules -- only add what's true\n"
            "for THIS repo specifically (ADR 0219)._\n"
        )
    if project_type == "web":
        return (
            "## Project-Specific Context\n"
            "\n"
            "**Stack:** Web (static or SPA). Confirm the framework in `package.json`.\n"
            "Deploy target documented in the project's own README (commonly Cloudflare\n"
            "Pages, GitHub Pages, or Netlify for this fleet).\n"
            "\n"
            "_TODO: Add the routing structure, asset pipeline, and any deploy hooks\n"
            "specific to this repo. The universal CLAUDE.md (auto-loaded) covers\n"
            "fleet-wide rules -- only add what's true for THIS repo specifically\n"
            "(ADR 0219)._\n"
        )
    raise ValueError(
        f"Unknown project_type: {project_type!r}. "
        f"Choose one of: {', '.join(PROJECT_TYPES)}"
    )


def create_claude_md(
    project_path: Path,
    name: str,
    github_user: str,
    project_type: str = "minimal",
) -> None:
    """
    Create the project CLAUDE.md file.

    Emits the lean per-repo template per ADR 0219 (#1258): identifiers plus
    a project-type-specific Project-Specific Context stub (per #1291).
    Everything else (merge sequence, PR rules, branch protection, GitHub CLI
    safety) lives in the universal CLAUDE.md auto-loaded by Claude Code's
    parent-directory traversal -- NOT restated here, to avoid drift on every
    universal-CLAUDE.md edit.

    Args:
        project_path: Path to the project root
        name: Project name
        github_user: GitHub username
        project_type: One of PROJECT_TYPES. Default 'minimal' on operator
            silence -- better to emit a TODO than guess wrong (#1291).

    See: #1266 (minimum-viable slice), #1291 (project-type branching),
    #1292 (test coverage), #1258 (ADR 0219).
    """
    projects_root_unix = config.projects_root_unix()
    context_block = _project_specific_context(project_type, name)

    # Footer: invitation to document workflow overrides explicitly. Pushes
    # the minimal-type emission over the lint stub threshold AND signals to
    # the next agent where overrides belong (per ADR 0219). Cheap content,
    # high signal — "no overrides yet" is itself a useful claim.
    overrides_footer = (
        "## Workflow Overrides\n"
        "\n"
        "_None yet. If this project needs to override any universal CLAUDE.md\n"
        "rule (e.g., a custom merge tool, a special test convention), document\n"
        "the override here with explicit language (\"override\") per ADR 0219._\n"
    )

    content = f"""# CLAUDE.md - {name} Project

You are a team member on the {name} project, not a tool.

## Project Identifiers

- **Repository:** `{github_user}/{name}`
- **Project Root (Windows):** `{project_path}`
- **Project Root (Unix):** `{projects_root_unix}/{name}`
- **Worktree Pattern:** `{name}-{{IssueID}}` (e.g., `{name}-45`)

{context_block}
## Data Directories

- `data/`: ephemeral session artifacts (transcripts, run logs, pickup state). Ignored by the fleet-wide global gitignore; not committed.
- `data-g/`: source-of-truth data the runtime treats as authoritative (rosters, corpora, configs). Git-tracked for durability. See `data-g/README.md`. (AssemblyZero #1563.)

{overrides_footer}"""
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

# Agent-parked files (mv $file $file.bak / $file.parked-{timestamp})
# CLAUDE.md "Destroying uncommitted state" principle: the agent uses
# mv-to-bak instead of rm to preserve recoverability. Ignored here so
# the parked artifacts don't pollute git status across the fleet.
*.bak
*.parked-*
"""
    gitignore_path = project_path / ".gitignore"
    gitignore_path.write_text(content, encoding='utf-8')


def create_data_g_readme(project_path: Path) -> None:
    """Create data-g/ with a README documenting the tracked-data split (#1563).

    The fleet-wide global gitignore ignores `data/` so ephemeral session
    artifacts (transcripts, run logs, pickup state) never land in git -- the
    right default for throwaway state. But that ignore silently drops
    authoritative work product too. Source-of-truth data the runtime reads as
    canonical (rosters, corpora, recipient lists, configs) goes in `data-g/`
    (the `-g` reads as "git-tracked"), which the global ignore does NOT match.

    Surfaced in IEEE-LRP-SC5 #19 when a roster JSON under data/ was silently
    dropped from a durability commit and would have been lost on a machine wipe.

    Removes the schema-created .gitkeep -- the README makes the directory
    non-empty and committable on its own.
    """
    data_g = project_path / "data-g"
    data_g.mkdir(parents=True, exist_ok=True)
    gitkeep = data_g / ".gitkeep"
    if gitkeep.exists():
        gitkeep.unlink()
    readme = '''\
# data-g/ -- git-tracked data

Source-of-truth data files that must persist in GitHub live here.

The fleet-wide global gitignore ignores `data/` so ephemeral session artifacts
(transcripts, run logs, pickup state) never land in git. That is the right
default for throwaway state -- but it silently drops authoritative work product
too. Anything the runtime reads as canonical input -- roster files, corpora,
recipient lists, convergence configs -- belongs in `data-g/`, which the global
ignore does NOT match.

| Path | Tracked? | Use for |
|------|----------|---------|
| `data/`   | No (global gitignore) | Session transcripts, pickup state, throwaway run output |
| `data-g/` | Yes                   | Source-of-truth: rosters, corpora, configs the runtime depends on |

Rule of thumb: if losing the file on a machine wipe would hurt, it goes in
`data-g/`. (Convention established in AssemblyZero #1563.)
'''
    (data_g / "README.md").write_text(readme, encoding="utf-8", newline="")


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
├── data/                       # Ephemeral data (git-ignored fleet-wide)
├── data-g/                     # Git-tracked source-of-truth data (see data-g/README.md)
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

    Sets model=claude-opus-4-7[1M], effort=max so unleashed wrappers pass
    the correct CLI flags. Without this file, wrappers fall back to tool
    defaults. The explicit model literal (not the bare "opus" alias) pins
    to 4.7[1M] — the alias would resolve to LATEST in Claude CLI and
    bypass the user's pin.

    `assemblyZero` defaults to True (#1059): repos created by this tool
    are by definition AssemblyZero-managed, so /onboard should load
    AssemblyZero's CLAUDE.md when a session starts here.

    `pickupThresholdMinutes` is intentionally NOT emitted (#1060): the
    /onboard skill is event-ordered now and explicitly ignores this
    field, so writing it just confuses future readers tuning the value.

    Args:
        project_path: Path to the project root.
    """
    content = json.dumps({
        "profile": "default",
        "claude": {
            "model": "claude-opus-4-7[1M]",
            "effort": "max"
        },
        "assemblyZero": True,
        "onboard": {
            "auto": True,
            "guide": None,
            "plan": None
        }
    }, indent=2) + "\n"
    unleashed_path = project_path / ".unleashed.json"
    unleashed_path.write_text(content, encoding='utf-8')


_PYTEST_INI_BLOCK = """
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-ra --strict-markers"
"""

_CONFTEST_BODY = '''"""Project test bootstrap.

Adds `src/` to `sys.path` so test files can import the project's
package without a full Poetry package install. Mirrors the pattern
used across the AssemblyZero fleet.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
'''

# License IDs accepted by `poetry init --license`. Matches the values
# of the existing --license CLI flag.
_POETRY_LICENSE_MAP = {
    "polyform": "PolyForm-Noncommercial-1.0.0",
    "mit": "MIT",
}

# PyPI publishing extension (#1074). Appended to pyproject.toml when
# --no-pypi is NOT passed AND github_user is known. Wires:
#   - poetry packages directive (src-layout — matches conftest's sys.path)
#   - [tool.poetry.scripts] entry point so `pip install <pkg> && <pkg>` runs
#   - [tool.poetry.urls] for the PyPI page
# Placeholders {module} and {github_user_repo} are .format()ed in.
_PYPROJECT_PYPI_BLOCK = """
[tool.poetry.scripts]
{module} = "{module}.__main__:main"

[tool.poetry.urls]
Homepage = "https://github.com/{github_user_repo}"
Source = "https://github.com/{github_user_repo}"
Issues = "https://github.com/{github_user_repo}/issues"
"""

# Package files for the entry-point target. Created at src/<module>/.
_PACKAGE_INIT_BODY = '''"""{module} package."""
'''

_PACKAGE_MAIN_BODY = '''"""Entry point for `python -m {module}` and the {module} CLI script."""
from __future__ import annotations


def main() -> int:
    """Run {module} as a CLI. Returns process exit code."""
    print("{module}: replace this with the real entry point.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


_REQUIRES_PYTHON_CARET = re.compile(
    r'(requires-python\s*=\s*")\^(\d+)\.(\d+)(?:\.\d+)?(")'
)


def _normalize_requires_python(pyproject_text: str) -> str:
    """Rewrite a Poetry-style caret requires-python to valid PEP 440 (#1573).

    `poetry init` writes `requires-python = "^3.10"` into the PEP 621 [project]
    table. The caret is valid Poetry dependency syntax but INVALID PEP 440 for
    this field, so ruff and other strict PEP 621 consumers refuse to parse
    pyproject.toml at all. `^X.Y` means `>=X.Y,<(X+1).0`, so rewrite to that
    faithful, valid form. An already-valid specifier is returned unchanged.
    """
    def _repl(m):
        major = int(m.group(2))
        minor = m.group(3)
        return f'{m.group(1)}>={major}.{minor},<{major + 1}.0{m.group(4)}'

    return _REQUIRES_PYTHON_CARET.sub(_repl, pyproject_text)


def create_python_project(
    project_path: Path,
    name: str,
    license_id: str,
    enable_pypi: bool = True,
    github_user: str = "owner",
) -> bool:
    """Bootstrap a Python project: pyproject.toml, dev deps, pytest config,
    tests/conftest.py, and optional PyPI publishing scaffold.

    Required for repos that will host the AssemblyZero implementation
    workflow (TDD-driven, runs pytest). Without this bootstrap, fresh
    repos fail in the workflow's red phase with "pytest: command not
    found". (#1058)

    Steps:
      1. `poetry init --no-interaction` produces pyproject.toml.
      2. `poetry add --group dev pytest pytest-cov` adds dev deps and
         creates poetry.lock as a side effect.
      3. Append `[tool.pytest.ini_options]` to pyproject.toml for
         deterministic test discovery across the canonical 12 test
         subdirs.
      4. Write `tests/conftest.py` so `from <package> import ...` works
         in test files without a full Poetry install.
      5. (#1074) If enable_pypi: create src/<module>/__init__.py and
         src/<module>/__main__.py with a no-op main() entry point.
      6. (#1074) If enable_pypi: inject `packages = [...]` into
         [tool.poetry] (src-layout) and append [tool.poetry.scripts]
         + [tool.poetry.urls] blocks. Steps 5–6 wire the entry point
         so `pip install <pkg> && <pkg>` runs the app, and populate
         the PyPI page URLs from {github_user}/{repo}. Skipped under
         --no-pypi.

    Best-effort: each step is wrapped in try/except. Failure prints a
    warning but does not abort the overall repo creation. The user can
    re-run `poetry init` / `poetry add` manually if needed.

    Args:
        project_path: Path to the project root.
        name: Project name (used as the Poetry package name).
        license_id: Either "polyform" or "mit"; mapped to a Poetry
                    --license value.
        enable_pypi: When True (default), install the PyPI publishing
                     scaffold (steps 5–6). When False, only steps 1–4
                     run (pure-internal package, no publish target).
        github_user: GitHub username, used to populate [tool.poetry.urls]
                     in step 6. Ignored when enable_pypi is False or
                     when github_user is the placeholder "owner"
                     (which means --no-github mode — caller must hand-
                     edit URLs later).

    Returns:
        True iff all enabled steps succeeded.
    """
    poetry_license = _POETRY_LICENSE_MAP.get(license_id, "MIT")
    package_name = name.lower().replace("_", "-")
    module_name = name.lower().replace("-", "_")

    # Step 1: poetry init
    init_cmd = [
        "poetry", "init",
        "--no-interaction",
        "--name", package_name,
        "--description", "",
        "--python", "^3.10",
        "--license", poetry_license,
    ]
    try:
        r = run_command(init_cmd, cwd=project_path, check=False)
        if r.returncode != 0:
            print(f"  WARNING: poetry init failed: {(r.stderr or '').strip()}")
            return False
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  WARNING: poetry init errored: {e}")
        return False

    # Step 2: poetry add dev deps (also generates poetry.lock)
    add_cmd = ["poetry", "add", "--group", "dev", "pytest", "pytest-cov"]
    try:
        r = run_command(add_cmd, cwd=project_path, check=False)
        if r.returncode != 0:
            print(f"  WARNING: poetry add dev deps failed: "
                  f"{(r.stderr or '').strip()}")
            return False
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"  WARNING: poetry add errored: {e}")
        return False

    # Step 3: append pytest config
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            current = pyproject.read_text(encoding="utf-8")
            if "[tool.pytest.ini_options]" not in current:
                pyproject.write_text(
                    current.rstrip() + "\n" + _PYTEST_INI_BLOCK,
                    encoding="utf-8",
                )
        except OSError as e:
            print(f"  WARNING: could not append pytest config: {e}")
            return False

    # Step 3b: normalize requires-python to valid PEP 440 (#1573). poetry init
    # writes `requires-python = "^3.x"` into [project] -- valid Poetry syntax
    # but invalid PEP 440, which breaks ruff and every strict PEP 621 consumer.
    if pyproject.exists():
        try:
            current = pyproject.read_text(encoding="utf-8")
            fixed = _normalize_requires_python(current)
            if fixed != current:
                pyproject.write_text(fixed, encoding="utf-8")
                print("  Normalized requires-python to valid PEP 440")
        except OSError as e:
            print(f"  WARNING: could not normalize requires-python: {e}")
            return False

    # Step 4: tests/conftest.py
    conftest = project_path / "tests" / "conftest.py"
    try:
        conftest.parent.mkdir(parents=True, exist_ok=True)
        if not conftest.exists():
            conftest.write_text(_CONFTEST_BODY, encoding="utf-8")
    except OSError as e:
        print(f"  WARNING: could not write tests/conftest.py: {e}")
        return False

    # Steps 5–6 are the PyPI publishing scaffold (#1074). They are
    # opt-out: --no-pypi skips them entirely. Without them, repos
    # created here have no entry point and no PyPI URLs — fine for
    # internal-only packages, broken for "pip install <pkg> && <pkg>"
    # workflows like the boostgauge speed-run.
    if not enable_pypi:
        return True

    # Step 5: src/<module>/__init__.py + __main__.py
    package_dir = project_path / "src" / module_name
    try:
        package_dir.mkdir(parents=True, exist_ok=True)
        init_file = package_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text(
                _PACKAGE_INIT_BODY.format(module=module_name),
                encoding="utf-8",
            )
        main_file = package_dir / "__main__.py"
        if not main_file.exists():
            main_file.write_text(
                _PACKAGE_MAIN_BODY.format(module=module_name),
                encoding="utf-8",
            )
    except OSError as e:
        print(f"  WARNING: could not write src/{module_name}/ skeleton: {e}")
        return False

    # Step 6: inject packages directive + append PyPI blocks. Three
    # mutations to the freshly-poetry-init'd pyproject.toml:
    #   (a) inject `packages = [{include = "<module>", from = "src"}]`
    #       into [tool.poetry] so `poetry build` finds the src-layout
    #       package.
    #   (b) append [tool.poetry.scripts] mapping <module> -> main().
    #   (c) append [tool.poetry.urls] populated from {github_user}/{repo}.
    # When github_user == "owner" (--no-github mode), the URLs use the
    # placeholder; the caller must hand-edit them before the first
    # tag push, but the structural scaffold is in place either way.
    try:
        current = pyproject.read_text(encoding="utf-8")

        # (a) Inject packages directive after the description line.
        # poetry init always emits `description = "..."` in [tool.poetry].
        packages_line = (
            f'packages = [{{include = "{module_name}", from = "src"}}]'
        )
        if packages_line not in current:
            new_text, n_subs = re.subn(
                r'(^description\s*=.*$)',
                lambda m: m.group(1) + "\n" + packages_line,
                current,
                count=1,
                flags=re.MULTILINE,
            )
            if n_subs == 0:
                print(
                    "  WARNING: could not find description line to "
                    "anchor packages directive — pyproject.toml may "
                    "have an unusual layout"
                )
                return False
            current = new_text

        # (b) + (c) Append scripts + urls blocks.
        github_user_repo = f"{github_user}/{package_name}"
        block = _PYPROJECT_PYPI_BLOCK.format(
            module=module_name,
            github_user_repo=github_user_repo,
        )
        if "[tool.poetry.scripts]" not in current:
            current = current.rstrip() + "\n" + block

        pyproject.write_text(current, encoding="utf-8")
    except OSError as e:
        print(f"  WARNING: could not write PyPI pyproject.toml additions: {e}")
        return False

    return True


# Canonical auto-reviewer.yml caller content. Single source of truth used
# by both create_github_workflows() (write at creation time) and
# verify_workflow_content_on_origin() (post-setup verification). Lifted
# to module scope so both paths compare against the same bytes — the
# #1193 failure mode was exactly this kind of divergent-template drift.
_CANONICAL_AUTO_REVIEWER_CALLER = '''\
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


def create_github_workflows(project_path: Path, enable_pypi: bool = True) -> None:
    """Create GitHub Actions workflow files for PR governance + PyPI release.

    Deploys two workflows by default:
    - auto-reviewer.yml: calls the reusable auto-reviewer from AssemblyZero
      to approve PRs after pr-sentinel passes (requires Cerberus secrets).
    - release.yml (#1074): tag-triggered, OIDC-auth to PyPI, runs poetry
      build + poetry publish. Skipped when enable_pypi is False.

    pr-sentinel check is posted by the Cloudflare Worker (pr-sentinel-mm
    GitHub App, installed in "All repositories" mode fleet-wide). The
    Worker covers the issue-reference check on every new repo
    automatically — no per-repo Actions workflow needed. Branch protection
    gates on context "pr-sentinel / issue-reference" (the Worker's check
    name), set by configure_branch_protection().

    Args:
        project_path: Path to the project root.
        enable_pypi: When True (default), also deploy release.yml. When
                     False, only auto-reviewer.yml is written. Mirrors the
                     --no-pypi flag wired through main().
    """
    workflows_dir = project_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # newline="" disables Python's Windows LF→CRLF translation. The
    # workflow file lands on disk with LF — same as every other repo
    # in the fleet, and matches what the Contents API upload sends.
    (workflows_dir / "auto-reviewer.yml").write_text(
        _CANONICAL_AUTO_REVIEWER_CALLER, encoding="utf-8", newline="",
    )

    # release.yml (#1074): tag-triggered PyPI publish via OIDC Trusted
    # Publisher. The first tag push only succeeds AFTER the human runs
    # runbook 0934 to register the pending publisher on PyPI's side
    # (browser-only step, not automatable). Skipped under --no-pypi.
    if enable_pypi:
        release_yml = '''\
name: Release to PyPI

# Tag-triggered publish to PyPI via OIDC Trusted Publisher (no token in
# secrets). Configure the publisher per runbook 0934 BEFORE the first
# tag push — pre-#0934 tag pushes will fail at the publish step with a
# "no pending publisher" error from PyPI.

on:
  push:
    tags:
      - "v*.*.*"

permissions:
  id-token: write  # Required for OIDC trust handshake with PyPI.
  contents: read

jobs:
  release:
    runs-on: ubuntu-latest
    environment: pypi  # Must match the environment registered on PyPI.
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"

      - name: Install Poetry
        run: pipx install poetry

      - name: Build distributions
        run: poetry build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # No password / token — OIDC Trusted Publisher handles auth.
'''
        (workflows_dir / "release.yml").write_text(
            release_yml, encoding="utf-8", newline="",
        )


# Dependabot version-update ecosystems, detected by marker-file presence.
# (marker filename, package-ecosystem, ecosystem label). github-actions is
# always added on top -- every scaffolded repo ships at least one workflow.
_DEPENDABOT_ECOSYSTEMS: list[tuple[str, str, str]] = [
    ("pyproject.toml", "pip", "python"),
    ("package.json", "npm", "javascript"),
    ("Dockerfile", "docker", "docker"),
]


def detect_dependabot_ecosystems(project_path: Path) -> list[tuple[str, str]]:
    """Return the (package-ecosystem, label) pairs that apply to project_path.

    Detection is by marker-file presence (pyproject.toml -> pip, package.json
    -> npm, Dockerfile -> docker). github-actions is always appended last
    because every scaffolded repo ships at least the auto-reviewer workflow.
    Keeping detection file-based (not arg-based) lets the fleet-backfill
    follow-up reuse this helper unchanged against existing repos.
    """
    ecosystems = [
        (eco, label)
        for marker, eco, label in _DEPENDABOT_ECOSYSTEMS
        if (project_path / marker).exists()
    ]
    ecosystems.append(("github-actions", "github-actions"))
    return ecosystems


def _dependabot_block(package_ecosystem: str, label: str) -> str:
    """Render one `updates:` block in the fleet-standard format.

    Weekly Monday 09:00 America/Chicago, grouped minor+patch to cut PR noise,
    chore(deps) commit prefix, open-pull-requests-limit 5, dependencies +
    per-ecosystem label. Mirrors the working Aletheia config.
    """
    return f'''\
  - package-ecosystem: "{package_ecosystem}"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "America/Chicago"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "{label}"
    commit-message:
      prefix: "chore(deps)"
    groups:
      {label}-minor:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"
'''


def render_dependabot_yml(ecosystems: list[tuple[str, str]]) -> str:
    """Render a complete .github/dependabot.yml for the given ecosystems."""
    header = (
        "# Dependabot version-update configuration.\n"
        "# https://docs.github.com/code-security/dependabot/dependabot-version-updates\n"
        "# Generated by AssemblyZero new_repo_setup.py (#1334). Repo-level\n"
        "# Dependabot alerts + security updates are enabled separately by\n"
        "# enable_dependabot.py; this file is what makes version-update PRs fire.\n"
        "version: 2\n"
        "updates:\n"
    )
    return header + "\n".join(
        _dependabot_block(eco, label) for eco, label in ecosystems
    )


def create_dependabot_config(project_path: Path) -> list[str]:
    """Write .github/dependabot.yml with version-update config (#1334).

    Without this file a repo emits only Dependabot *security* PRs (after
    enable_dependabot.py flips the API toggles) -- never *version-update* PRs.
    Detects ecosystems by marker-file presence; github-actions is always
    included. Returns the package-ecosystems written.

    The file lands under .github/ (NOT .github/workflows/), so it needs no
    `workflow` PAT scope and rides the normal initial commit -- unlike the
    workflow files, which require the Contents API (step 16).
    """
    ecosystems = detect_dependabot_ecosystems(project_path)
    github_dir = project_path / ".github"
    github_dir.mkdir(parents=True, exist_ok=True)
    # newline="" keeps LF on Windows, matching the rest of the fleet.
    (github_dir / "dependabot.yml").write_text(
        render_dependabot_yml(ecosystems), encoding="utf-8", newline="",
    )
    return [eco for eco, _label in ecosystems]


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


_GH_API = "https://api.github.com"

# Shared retry helper (#1052). Imported as _request_with_retry to keep
# existing call-sites unchanged. Loud-failure variant: retry exhaustion
# raises requests.HTTPError / ConnectionError / Timeout (all
# RequestException subclasses, so existing except handlers still catch).
try:
    from _gh_retry import request_with_retry as _request_with_retry
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from _gh_retry import request_with_retry as _request_with_retry  # noqa: F401


def configure_branch_protection(github_user: str, repo_name: str, pat: str) -> bool:
    """
    Configure branch protection on the main branch via GitHub REST API.

    The privileged PUT is issued via `requests` using an in-process classic
    PAT (ADR-0216) so the token never enters the subprocess argv or env block.
    The branch-existence pre-check stays on `gh api` (read-only, fine-grained
    PAT suffices and keeps a single source of truth for gh-CLI auth state).

    Sets: require PR, block force push, block deletion, enforce_admins,
    pr-sentinel / issue-reference required check.

    Args:
        github_user: GitHub username
        repo_name: Repository name
        pat: Classic PAT obtained via classic_pat_session().

    Returns:
        True if protection was configured, False if it failed.
    """
    # Branch protection requires at least one commit on main.
    # Verify remote branch exists before attempting. Read-only — no classic PAT needed.
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

    body = {
        "required_status_checks": {
            "strict": False,
            "contexts": ["pr-sentinel / issue-reference"],
        },
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": False,
            "require_code_owner_reviews": False,
            "required_approving_review_count": 1,
        },
        "restrictions": None,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    try:
        resp = _request_with_retry(
            "PUT",
            f"{_GH_API}/repos/{github_user}/{repo_name}/branches/main/protection",
            pat,
            json=body,
        )
        return resp.status_code < 300
    except requests.RequestException:
        return False


def configure_repo_settings(github_user: str, repo_name: str, pat: str) -> bool:
    """
    Configure GitHub repo settings to match fleet standards via REST API
    using an in-process classic PAT (ADR-0216).

    Sets: wiki disabled, projects disabled, squash-only merge, delete branch on merge.

    Args:
        github_user: GitHub username
        repo_name: Repository name
        pat: Classic PAT obtained via classic_pat_session().

    Returns:
        True if settings were applied, False if it failed.
    """
    body = {
        "has_wiki": False,
        "has_projects": False,
        "delete_branch_on_merge": True,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
    }
    try:
        resp = _request_with_retry(
            "PATCH",
            f"{_GH_API}/repos/{github_user}/{repo_name}",
            pat,
            json=body,
        )
        return resp.status_code < 300
    except requests.RequestException:
        return False


def _deploy_workflows_via_contents_api(
    project_path: Path,
    github_user: str,
    repo_name: str,
    pat: str,
    branch: str = "main",
) -> tuple[bool, int]:
    """Upload all files under .github/workflows/ via the GitHub Contents API.

    Each PUT creates one commit on the remote. Fine-grained PATs cannot
    push workflow-file changes via git (they lack the `workflow` scope),
    so this path uses classic-PAT REST calls instead. Invoked after the
    non-workflow initial commit is already on the remote. (#1000 / ADR-0216.)

    Args:
        project_path: Local repo root.
        github_user: GitHub username (owner).
        repo_name: Lowercased repository name.
        pat: Classic PAT from classic_pat_session().
        branch: Target branch (default "main").

    Returns:
        (success, count) — success is True iff every workflow file was
        uploaded (HTTP < 300). count is the number of files uploaded.
        If the workflows directory is missing or empty, returns (True, 0).
    """
    import base64
    workflows_dir = project_path / ".github" / "workflows"
    if not workflows_dir.exists():
        return True, 0
    files = sorted(p for p in workflows_dir.iterdir() if p.is_file())
    if not files:
        return True, 0

    uploaded = 0
    for wf in files:
        rel_path = f".github/workflows/{wf.name}"
        # CRLF normalize before base64 — Path.write_text on Windows
        # writes CRLF, and the Contents API stores bytes verbatim, so
        # without this the workflow lands on origin with CRLF where the
        # rest of the fleet uses LF. Per root CLAUDE.md gotcha (2026-04-30 #3).
        content_bytes = wf.read_bytes().replace(b"\r\n", b"\n")
        payload = {
            "message": f"chore: add {rel_path}",
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": branch,
        }
        try:
            resp = _request_with_retry(
                "PUT",
                f"{_GH_API}/repos/{github_user}/{repo_name}/contents/{rel_path}",
                pat,
                json=payload,
            )
        except requests.RequestException as e:
            print(f"  Contents API PUT errored for {rel_path}: {e}")
            return False, uploaded
        if resp.status_code >= 300:
            print(f"  Contents API PUT failed for {rel_path}: HTTP {resp.status_code} — {resp.text[:200]}")
            return False, uploaded
        uploaded += 1
    return True, uploaded


# Canonical AZ labels (#1061). The metrics_aggregator counts the
# `implementation` label as the in-implementation classifier; `lld`
# is convention for issues with an approved LLD ready for the
# implementation workflow. Kept deliberately small — workflow
# CONFIG names like `lld-standard` belong in code, not GitHub labels.
_CANONICAL_LABELS: list[tuple[str, str, str]] = [
    ("implementation", "0E8A16",
     "Issue is in implementation or has a paired implementation PR"),
    ("lld", "5319E7",
     "Issue has an approved LLD in docs/lld/active/LLD-NNN.md"),
]


def create_canonical_labels(github_user: str, repo_name: str) -> tuple[int, int]:
    """Create canonical AssemblyZero labels on the new repo.

    Idempotent via `gh label create --force` — pre-existing labels
    get updated to the canonical color/description rather than failing.

    Args:
        github_user: GitHub username (owner).
        repo_name: Lowercased repository name.

    Returns:
        (created, total) — count of labels successfully created/updated
        and total attempted.
    """
    repo = f"{github_user}/{repo_name}"
    created = 0
    for name, color, description in _CANONICAL_LABELS:
        cmd = [
            "gh", "label", "create", name,
            "--color", color,
            "--description", description,
            "--force",
            "--repo", repo,
        ]
        try:
            r = run_command(cmd, check=False)
            if r.returncode == 0:
                created += 1
            else:
                print(f"  WARNING: failed to create label '{name}': "
                      f"{(r.stderr or '').strip()}")
        except (subprocess.TimeoutExpired, OSError) as e:
            print(f"  WARNING: error creating label '{name}': {e}")
    return created, len(_CANONICAL_LABELS)


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


# ---------------------------------------------------------------------------
# Post-setup verification helpers (#1200, #1202)
#
# The pre-#1200 verification block only checked LOCAL filesystem state — same
# blind spot as the boostgauge #1193 incident, where file presence was OK
# but file CONTENT was wrong on origin. These helpers verify GitHub-side
# state end-to-end. Each returns (passed: bool, message: str) so the caller
# can decide how to format output.
# ---------------------------------------------------------------------------


def verify_branch_protection_on_origin(
    github_user: str, repo_name: str, pat: str,
) -> tuple[bool, str]:
    """Verify branch protection on origin matches fleet standard.

    Required for parity with configure_branch_protection(): enforce_admins
    enabled, required_approving_review_count == 1, pr-sentinel/issue-reference
    in required checks. Reading classic Branch Protection needs Admin scope
    so this requires the classic PAT, not the fine-grained one.
    """
    try:
        resp = _request_with_retry(
            "GET",
            f"{_GH_API}/repos/{github_user}/{repo_name}/branches/main/protection",
            pat,
        )
    except requests.RequestException as e:
        return False, f"network: {e}"
    if resp.status_code == 404:
        return False, "no branch protection set on origin"
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    p = resp.json()
    failures: list[str] = []
    if not (p.get("enforce_admins") or {}).get("enabled"):
        failures.append("enforce_admins not enabled")
    reviews = p.get("required_pull_request_reviews") or {}
    if reviews.get("required_approving_review_count") != 1:
        actual = reviews.get("required_approving_review_count")
        failures.append(f"required_approving_review_count={actual!r}, want 1")
    checks = (p.get("required_status_checks") or {}).get("contexts") or []
    if "pr-sentinel / issue-reference" not in checks:
        failures.append(
            f"'pr-sentinel / issue-reference' not in required checks ({checks!r})"
        )
    if failures:
        return False, "; ".join(failures)
    return True, "enforce_admins=on, 1 review, pr-sentinel check"


def verify_repo_settings_on_origin(
    github_user: str, repo_name: str, pat: str,
) -> tuple[bool, str]:
    """Verify repo settings match fleet standard (squash-only, no wiki/projects)."""
    try:
        resp = _request_with_retry(
            "GET",
            f"{_GH_API}/repos/{github_user}/{repo_name}",
            pat,
        )
    except requests.RequestException as e:
        return False, f"network: {e}"
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    r = resp.json()
    expected = {
        "has_wiki": False,
        "has_projects": False,
        "allow_merge_commit": False,
        "allow_rebase_merge": False,
        "allow_squash_merge": True,
        "delete_branch_on_merge": True,
    }
    failures = [
        f"{k}={r.get(k)!r}, want {v!r}"
        for k, v in expected.items()
        if r.get(k) is not v
    ]
    if failures:
        return False, "; ".join(failures)
    return True, "squash-only, no wiki/projects, delete-branch-on-merge"


def verify_workflow_content_on_origin(
    github_user: str, repo_name: str, pat: str,
) -> tuple[bool, str]:
    """Verify .github/workflows/auto-reviewer.yml on origin matches canonical.

    Catches the #1193 failure mode: file exists but content is wrong (e.g.,
    the OLD caller format that triggers startup_failure). Byte-for-byte
    compare against the same constant that create_github_workflows() writes,
    after CRLF normalization (Contents API stores bytes verbatim).
    """
    try:
        resp = _request_with_retry(
            "GET",
            f"{_GH_API}/repos/{github_user}/{repo_name}/contents/.github/workflows/auto-reviewer.yml",
            pat,
        )
    except requests.RequestException as e:
        return False, f"network: {e}"
    if resp.status_code == 404:
        return False, "auto-reviewer.yml not present on origin"
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    encoded = (resp.json().get("content") or "").replace("\n", "")
    try:
        content = base64.b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as e:
        return False, f"could not decode content: {e}"
    if content.replace("\r\n", "\n") == _CANONICAL_AUTO_REVIEWER_CALLER:
        return True, "content matches canonical NEW format"
    return False, "content differs from canonical (#1193 failure mode)"


def verify_pr_sentinel_installation(
    github_user: str, repo_name: str, pat: str,
) -> tuple[bool, str]:
    """Best-effort check that pr-sentinel-mm Cloudflare Worker covers this repo.

    The Worker delivers the `pr-sentinel / issue-reference` check that branch
    protection requires. If the Worker's GitHub App installation scope has
    drifted from 'All repositories', the check never fires and every PR sits
    blocked. Catches that at creation time instead of when the first PR opens.

    Uses the in-process classic PAT per ADR-0216 (#1274). The
    /user/installations endpoint requires elevated scope that the
    fine-grained PAT deliberately lacks; prior versions of this function
    shelled out via gh and reliably 403'd on every run.

    Args:
        github_user: GitHub username (org or user account that owns the repo).
        repo_name: Repository name (no owner prefix).
        pat: Classic PAT from classic_pat_session(). Passed in the
            Authorization header; never reaches env or argv.
    """
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Step 1: find the pr-sentinel-mm installation id on the user account.
    try:
        r = requests.get(
            "https://api.github.com/user/installations",
            headers=headers, timeout=30,
        )
    except requests.RequestException as e:
        return False, f"could not query /user/installations: {e}"
    if r.status_code != 200:
        return False, (
            f"GET /user/installations failed: {r.status_code} "
            f"{r.text[:200]}"
        )
    try:
        installations = r.json().get("installations", [])
    except ValueError as e:
        return False, f"could not parse /user/installations: {e}"
    sentinel = next(
        (inst for inst in installations if inst.get("app_slug") == "pr-sentinel-mm"),
        None,
    )
    if sentinel is None:
        return False, "pr-sentinel-mm not found in /user/installations"
    installation_id = sentinel.get("id")
    if installation_id is None:
        return False, "pr-sentinel-mm installation has no id field"

    # Step 2: list repositories covered by this installation; confirm the
    # new repo is in the list. GitHub paginates installation repositories
    # at 100 per page; loop until exhausted.
    full_name = f"{github_user}/{repo_name}"
    page = 1
    while True:
        try:
            r = requests.get(
                f"https://api.github.com/user/installations/{installation_id}/repositories",
                headers=headers,
                params={"per_page": 100, "page": page},
                timeout=30,
            )
        except requests.RequestException as e:
            return False, f"could not query installation repos: {e}"
        if r.status_code != 200:
            return False, (
                f"GET /user/installations/{installation_id}/repositories "
                f"failed: {r.status_code} {r.text[:200]}"
            )
        try:
            repos = r.json().get("repositories", [])
        except ValueError as e:
            return False, f"could not parse installation repos: {e}"
        for repo in repos:
            if repo.get("full_name") == full_name:
                return True, f"installation {installation_id} covers this repo"
        if len(repos) < 100:
            break  # last page
        page += 1
    return False, (
        f"installation {installation_id} does NOT cover {full_name} -- "
        "App scope may have drifted from 'All repositories'"
    )


def _deploy_cerberus(
    repo_name: str,
    pem_content: str,
    pat: str,
    *,
    source_path: Path | None = None,
) -> str:
    """Deploy Cerberus secrets to a single repo.

    Deploys REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY to the specified
    repo via in-process classic PAT (sealed-box encrypted per GitHub's
    secrets API), then verifies they landed. (#1007)

    Args:
        repo_name: The new repo name (lowercased, owner-less).
        pem_content: PEM contents as a string. Already loaded from
            disk (--cerberus-pem flow) or decrypted in-process via
            cerberus_pem_session() (--cerberus-pem-gpg flow).
        pat: Classic PAT from classic_pat_session() — consumed by
            deploy_to_repo / verify_secrets, never placed in env.
        source_path: If provided, the plaintext file at this path is
            unlinked after successful verification (legacy
            --cerberus-pem flow). If None, no file is unlinked --
            used by --cerberus-pem-gpg, which has nothing plaintext
            on disk to delete (#1254).

    Returns a short status string for the summary table.
    """
    print("\n" + "=" * 60)
    print("CERBERUS SECRETS DEPLOY")
    print("=" * 60)

    if "PRIVATE KEY" not in pem_content:
        print("  ERROR: PEM contents do not look like a private key.")
        return "INVALID_PEM"

    print(f"  Target repo: {repo_name}")
    if source_path is not None:
        print(f"  Source:      {source_path.name} (plaintext, "
              f"will be deleted after deploy)")
    else:
        print("  Source:      gpg-decrypted in-process "
              "(no plaintext on disk; encrypted blob preserved)")
    print(f"  Key length:  {len(pem_content)} chars")

    ok, failed = deploy_to_repo(repo_name, pem_content, pat)
    if not ok:
        print(f"  FAILED to deploy: {', '.join(failed)}")
        if source_path is not None:
            print(f"  .pem file NOT deleted -- retry manually:")
            print(f"    poetry run python tools/deploy_cerberus_secrets.py {source_path}")
        return f"FAILED: {', '.join(failed)}"
    print("  Secrets set.")

    ok, missing = verify_secrets(repo_name, pat)
    if not ok:
        print(f"  WARNING: verification failed; missing {missing}")
        if source_path is not None:
            print(f"  .pem file NOT deleted -- investigate before deleting.")
        return f"UNVERIFIED: {', '.join(missing)}"
    print("  Secrets verified on GitHub (both REVIEWER_APP_ID and REVIEWER_APP_PRIVATE_KEY present).")

    if source_path is not None:
        try:
            source_path.unlink()
            print(f"  .pem file deleted: {source_path}")
        except OSError as e:
            print(f"  WARNING: could not delete .pem file: {e}")
            print(f"  DELETE MANUALLY: {source_path}")
    else:
        print("  (gpg-encrypted PEM preserved at "
              "the path you provided; reuse it for additional repos.)")

    print()
    print("  NEXT STEP (browser-only, cannot be automated):")
    print("    Revoke the key you just used in the GitHub App UI:")
    print("    https://github.com/settings/apps/cerberus-az > Private keys > Revoke")

    return "OK"


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
    parser.add_argument(
        "--cerberus-pem",
        metavar="PATH",
        default=None,
        help="Path to PLAINTEXT Cerberus App .pem file. After deploy the "
             "script DELETES this file. Single-use; for repeat/multi-repo "
             "creation, use --cerberus-pem-gpg instead (encrypted at rest, "
             "decrypted in-process per ADR-0216, no plaintext on disk). "
             "When omitted, runbook 0927 step 4 is printed as manual fallback."
    )
    parser.add_argument(
        "--cerberus-pem-gpg",
        metavar="PATH",
        default=None,
        help="Path to GPG-ENCRYPTED Cerberus App .pem file (typically "
             "~/.secrets/cerberus-pem.gpg per ADR-0216 / runbook 0927). "
             "Decrypted in-process via cerberus_pem_session(); never written "
             "to plaintext disk. Pinentry prompts per gpg-agent TTL. The "
             "encrypted blob is NOT deleted -- reuse it across as many "
             "new-repo invocations as you need, then revoke the key in the "
             "browser when done (#1254)."
    )
    parser.add_argument(
        "--lang",
        choices=["python", "none"],
        default="python",
        help="Project language bootstrap. 'python' (default) initializes "
             "a Poetry project (pyproject.toml + dev deps + pytest config + "
             "tests/conftest.py). 'none' skips language bootstrap — useful "
             "for non-Python projects. (#1058)"
    )
    parser.add_argument(
        "--project-type",
        choices=list(PROJECT_TYPES),
        default="minimal",
        help="Project-type-specific stub for the scaffolded CLAUDE.md's "
             "Project-Specific Context section. 'minimal' (default) emits a "
             "TODO block. Other choices ('python', 'chrome-extension', 'pypi', "
             "'cf-worker', 'web') emit a one-paragraph stack note plus a "
             "type-specific TODO. Default is intentionally 'minimal' -- "
             "better to leave a TODO than guess wrong for an unrecognized "
             "type. (#1291; ADR 0219)"
    )
    parser.add_argument(
        "--pypi",
        action="store_true",
        default=False,
        help="Include the PyPI publishing scaffold (entry point, src/<pkg>/ "
             "skeleton, [tool.poetry.scripts]/[urls] blocks, release.yml). "
             "Default: OMITTED. Runbook 0934 describes the one-time "
             "pending-publisher registration on PyPI that release.yml "
             "expects. Pass this flag ONLY for repos you intend to "
             "publish to PyPI. (#1269)"
    )
    parser.add_argument(
        "--no-pypi",
        action="store_true",
        default=False,
        help="DEPRECATED -- this is now the default. Accepted as a no-op "
             "for backward compatibility; will print a deprecation warning. "
             "Use --pypi to opt INTO the PyPI scaffold. (#1269)"
    )

    args = parser.parse_args()

    # --cerberus-pem and --cerberus-pem-gpg are mutually exclusive
    if args.cerberus_pem and args.cerberus_pem_gpg:
        print("ERROR: --cerberus-pem and --cerberus-pem-gpg are mutually exclusive.")
        print("Pick one: --cerberus-pem PATH (plaintext, deleted after) OR "
              "--cerberus-pem-gpg PATH (encrypted at rest, reusable).")
        sys.exit(1)

    # --pypi and --no-pypi are mutually exclusive (#1269)
    if args.pypi and args.no_pypi:
        print("ERROR: --pypi and --no-pypi are mutually exclusive.")
        sys.exit(1)

    # --no-pypi is now the default; emit deprecation notice if it's used
    if args.no_pypi:
        print("NOTE: --no-pypi is deprecated -- this is now the default. "
              "The flag is a no-op; remove it from your invocation. (#1269)")

    # Cerberus deploy requires --no-github not set (need the repo to deploy to)
    if (args.cerberus_pem or args.cerberus_pem_gpg) and args.no_github:
        print("ERROR: --cerberus-pem / --cerberus-pem-gpg requires GitHub repo "
              "creation (cannot be combined with --no-github)")
        sys.exit(1)

    # A Cerberus PEM source is REQUIRED when creating a GitHub repo (#1206).
    # Without Cerberus secrets the new repo's PRs sit blocked indefinitely
    # because branch protection requires 1 approving review and the
    # auto-reviewer workflow can't authenticate without the App secrets.
    # Catching this at the CLI gate keeps the failure loud and pre-creation,
    # not silent and only-visible-on-first-PR. Audit mode is exempt — it
    # only inspects an existing project, never creates anything.
    #
    # When neither flag was passed, fall back to the canonical encrypted-PEM
    # location (#1543). Repeat invocations don't need to retype the flag.
    # The default is only applied when neither flag was explicitly passed,
    # so the mutual-exclusion check above still catches both-flags-passed.
    if (not args.cerberus_pem and not args.cerberus_pem_gpg
            and not args.no_github and not args.audit
            and DEFAULT_CERBERUS_PEM_GPG.exists()):
        args.cerberus_pem_gpg = str(DEFAULT_CERBERUS_PEM_GPG)
        print(f"Using Cerberus PEM: {DEFAULT_CERBERUS_PEM_GPG} "
              "(encrypted, in-process decryption)")

    if (not args.cerberus_pem and not args.cerberus_pem_gpg
            and not args.no_github and not args.audit):
        print(f"ERROR: Cerberus encrypted PEM not found at {DEFAULT_CERBERUS_PEM_GPG}")
        print()
        print("The new-repo workflow needs a Cerberus App key to wire up auto-approval.")
        print("Without it, every PR on the new repo sits blocked waiting for a review.")
        print()
        print("Options:")
        print("  - Encrypted key elsewhere?  --cerberus-pem-gpg /path/to/cerberus-pem.gpg")
        print("  - One-shot plaintext?       --cerberus-pem /path/to/cerberus.pem")
        print("  - First-time setup?         See docs/runbooks/0927-new-repo-human-checklist.md#4")
        print()
        print("Override: --no-github (skip GitHub repo entirely; local scaffold only).")
        sys.exit(1)

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


def _diagnose_existing_path(project_path: Path) -> tuple[str, list[str]]:
    """Classify what's at project_path when it already exists.

    Pre-flight helper for _create_repo. Returns (kind, recovery_lines)
    where `kind` is one of:
        'file'           — path exists as a regular file, not a directory
        'stale_worktree' — directory has a `.git` FILE pointing at a
                            worktree registration (the #935 case — usually
                            a leftover from a prior worktree-based session)
        'live_repo'      — directory has a `.git` DIRECTORY (real local repo)
        'unknown_dir'    — directory exists, no `.git` of any kind

    `recovery_lines` is a list of human-readable strings the caller prints
    to help the user clean up and retry. No side effects performed —
    callers must not auto-delete; the user decides.
    """
    if project_path.is_file():
        return ("file", [
            f"Path is a regular file, not a directory.",
            f"Remove it: rm '{project_path}'",
            f"Then re-run.",
        ])

    git_path = project_path / ".git"

    if git_path.is_file():
        registration = ""
        try:
            registration = git_path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            pass
        return ("stale_worktree", [
            f"Directory contains a `.git` FILE — looks like a stale git-worktree leftover (#935).",
            f"  .git contents: {registration or '(unreadable)'}",
            "Recovery options (try in this order):",
            f"  1. cd '{project_path}' && poetry env remove --all  # release venv file locks",
            f"  2. rm -rf '{project_path}'                          # may still fail if other locks remain",
            f"  3. powershell -c \"Get-Process | Where-Object {{ \\$_.Path -like '*{project_path.name}*' }}\"  # find lock-holder",
            f"  4. If a stale Python process holds the lock: powershell -c \"Get-Process python | Stop-Process\" (carefully)",
            f"  5. Reboot is the nuclear option.",
        ])

    if git_path.is_dir():
        return ("live_repo", [
            f"Directory is an existing git repo (has a `.git` directory).",
            f"This is NOT a leftover. Refusing to overwrite.",
            f"Pick a different name for your new repo, or move/rename the existing repo first.",
        ])

    try:
        entry_count = sum(1 for _ in project_path.iterdir())
    except OSError:
        entry_count = -1
    return ("unknown_dir", [
        f"Directory exists with {entry_count} entries but no `.git` of any kind.",
        f"Either remove it (if not yours) or pick a different name:",
        f"  rm -rf '{project_path}'  # if you confirm you don't need it",
    ])


def validate_scaffold(project_path: Path) -> tuple[list[str], list[str]]:
    """Structural validation of a freshly scaffolded repo (#1575).

    Returns (blocking, advisory) lists of human-readable failure messages.

    Blocking = structural invalidity that must not ship: a config file that
    does not parse, or a requires-python that is not a valid PEP 440 specifier.
    Advisory = checks that could not be run fully (an optional validator's
    dependency is unavailable).

    Operates on local files only, so the caller can run it BEFORE creating any
    GitHub state -- a blocking failure then aborts with nothing to roll back.
    """
    blocking: list[str] = []
    advisory: list[str] = []

    # pyproject.toml: must parse, and [project].requires-python (if present)
    # must be a valid PEP 440 specifier -- the #1571 / #1573 failure class.
    pp = project_path / "pyproject.toml"
    if pp.exists():
        data = None
        try:
            data = tomllib.loads(pp.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError) as e:
            blocking.append(f"pyproject.toml does not parse: {e}")
        if data is not None:
            rp = data.get("project", {}).get("requires-python")
            if rp is not None:
                try:
                    from packaging.specifiers import (
                        InvalidSpecifier,
                        SpecifierSet,
                    )
                    try:
                        SpecifierSet(rp)
                    except InvalidSpecifier as e:
                        blocking.append(
                            f"[project].requires-python is not valid PEP 440: "
                            f"{rp!r} ({e})"
                        )
                except ImportError:
                    # packaging unavailable: fall back to the known-bad forms.
                    if rp.lstrip().startswith(("^", "~")):
                        blocking.append(
                            f"[project].requires-python uses non-PEP-440 "
                            f"syntax: {rp!r}"
                        )
                    else:
                        advisory.append(
                            "packaging unavailable; requires-python only "
                            "shallow-checked"
                        )

    # .github/dependabot.yml: must be valid YAML (the #1334 file).
    db = project_path / ".github" / "dependabot.yml"
    if db.exists():
        try:
            import yaml
            try:
                yaml.safe_load(db.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                blocking.append(f".github/dependabot.yml is not valid YAML: {e}")
        except ImportError:
            advisory.append("PyYAML unavailable; dependabot.yml not validated")

    # JSON config files must parse.
    for rel in (".claude/project.json", ".claude/settings.json", ".unleashed.json"):
        f = project_path / rel
        if f.exists():
            try:
                json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                blocking.append(f"{rel} is not valid JSON: {e}")

    return blocking, advisory


def _create_repo(project_path: Path, args: argparse.Namespace, github_user: str) -> None:
    """Internal repo creation logic, separated for error handling."""
    # Pre-flight: refuse to proceed if anything already exists at project_path.
    # No GitHub state should be created when there's a local collision; the
    # user resolves it and re-runs. Covers the #935 stale-worktree case
    # plus typos and accidental name reuse.
    if project_path.exists():
        kind, recovery_lines = _diagnose_existing_path(project_path)
        print("\n" + "=" * 60)
        print(f"[PRE-FLIGHT] Refusing to proceed: target path already exists")
        print("=" * 60)
        print(f"Path: {project_path}")
        print(f"Kind: {kind}")
        for line in recovery_lines:
            print(f"  {line}")
        print()
        print("No local files written, no GitHub repo created. Resolve the collision and re-run.")
        sys.exit(1)

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
    create_claude_md(project_path, args.name, github_user, args.project_type)
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

    # Step 11a: Create data-g/ (git-tracked source-of-truth data) (#1563).
    # The global gitignore ignores data/; data-g/ is the durable counterpart
    # the ignore does not match. README explains the split.
    print("\n11a. Creating data-g/ (git-tracked data convention)...")
    create_data_g_readme(project_path)
    print("  Created data-g/README.md")

    # Step 11b: Create .unleashed.json (wrapper configuration)
    print("\n11b. Creating .unleashed.json...")
    create_unleashed_json(project_path)
    print("  Created .unleashed.json (model=claude-opus-4-7[1M], effort=max)")

    # Step 11b2: Bootstrap Python project (#1058) — pyproject.toml,
    # pytest, pytest-cov, conftest.py. Required for AZ implementation
    # workflow's red/green TDD phases. Skippable via --lang none.
    # PyPI publishing scaffold (#1074) is OPT-IN via --pypi (#1269 --
    # inverted from earlier opt-out via --no-pypi).
    enable_pypi = (args.lang == "python") and args.pypi
    if args.lang == "python":
        if enable_pypi:
            print("\n11b2. Bootstrapping Python project (poetry init + pytest + PyPI scaffold)...")
        else:
            print("\n11b2. Bootstrapping Python project (poetry init + pytest)...")
        if create_python_project(
            project_path,
            args.name,
            args.license,
            enable_pypi=enable_pypi,
            github_user=github_user,
        ):
            tail = " + src/{m}/__main__:main + URLs".format(
                m=args.name.lower().replace("-", "_"),
            ) if enable_pypi else ""
            print("  Created pyproject.toml, poetry.lock, dev deps "
                  "(pytest, pytest-cov), tests/conftest.py" + tail)
        else:
            print("  WARNING: Python bootstrap incomplete. Run manually:")
            print(f"    cd {project_path}")
            print("    poetry init --no-interaction")
            print("    poetry add --group dev pytest pytest-cov")
    else:
        print("\n11b2. SKIPPED Python bootstrap (--lang none)")

    # Step 11c: Create GitHub Actions workflows (PR governance + release)
    print("\n11c. Creating GitHub Actions workflows...")
    create_github_workflows(project_path, enable_pypi=enable_pypi)
    if enable_pypi:
        print("  Created auto-reviewer.yml + release.yml (PyPI publish on tag)")
    else:
        print("  Created auto-reviewer.yml (Cerberus auto-approval caller)")

    # Step 11c2: Create .github/dependabot.yml (#1334). Step 20 enables
    # Dependabot at the API level (alerts + security updates); without this
    # file no *version-update* PRs ever fire. Runs after the Python bootstrap
    # so pyproject.toml is present for ecosystem detection. Lands in the
    # initial commit (not under .github/workflows/, so no workflow scope).
    print("\n11c2. Creating .github/dependabot.yml...")
    db_ecos = create_dependabot_config(project_path)
    print(f"  Created dependabot.yml (ecosystems: {', '.join(db_ecos)})")

    # Step 12: Initial commit — non-workflow files only.
    # Workflow files (.github/workflows/*) require the `workflow` scope on
    # push, which fine-grained PATs lack. Instead of requiring env-scoped
    # classic PAT for the initial push, we commit non-workflow files here,
    # push via normal git, then upload workflows via Contents API using an
    # in-process classic PAT (ADR-0216, #1000).
    print("\n12. Creating initial commit (non-workflow files)...")
    run_command(
        ["git", "add", "--", ".", ":!.github/workflows"],
        cwd=project_path,
    )
    run_command(
        ["git", "commit", "-m", "chore: initialize project with AssemblyZero\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"],
        cwd=project_path
    )
    print("  Created initial commit (workflows deferred — go via Contents API)")

    # Step 12b: If skipping GitHub, commit workflows locally as a second
    # commit so the local repo is complete. With GitHub in play, workflow
    # files stay untracked locally until `git pull` brings them back after
    # the Contents API upload (step 16 below).
    if args.no_github:
        run_command(["git", "add", ".github/workflows"], cwd=project_path)
        run_command(
            ["git", "commit", "-m", "chore: add GitHub Actions workflows"],
            cwd=project_path,
        )
        print("  Created workflow commit (local-only mode)")

    github_created = False
    push_succeeded = False
    workflows_deployed = False
    repo_settings_ok = False
    protection_ok = False
    cerberus_status: str | None = None
    gh_checks_passed = 0
    gh_checks_total = 0

    # Local post-setup verification (no PAT required, runs BEFORE the
    # GitHub-side elevated batch so scaffold problems surface before any
    # pinentry prompt).
    print("\n" + "=" * 60)
    print("POST-SETUP VERIFICATION (local)")
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

    # Verify .gitignore has agent-parked-file patterns (#1425)
    checks_total += 1
    if gitignore.exists():
        gi_content = gitignore.read_text(encoding="utf-8")
        parked_missing = [p for p in ["*.bak", "*.parked-*"]
                          if p not in gi_content]
        if not parked_missing:
            print("  [PASS] .gitignore agent-parked-file patterns present")
            checks_passed += 1
        else:
            print(f"  [FAIL] .gitignore missing agent-parked patterns: {parked_missing}")

    # Verify .github/dependabot.yml present with version-update config (#1334)
    checks_total += 1
    dependabot_yml = project_path / ".github" / "dependabot.yml"
    if dependabot_yml.exists() and "package-ecosystem" in dependabot_yml.read_text(encoding="utf-8"):
        print("  [PASS] .github/dependabot.yml present (version updates)")
        checks_passed += 1
    else:
        print("  [FAIL] .github/dependabot.yml missing or has no ecosystems")

    # Verify data-g/ tracked-data directory present with README (#1563)
    checks_total += 1
    data_g_readme = project_path / "data-g" / "README.md"
    if data_g_readme.exists():
        print("  [PASS] data-g/ present (git-tracked data convention)")
        checks_passed += 1
    else:
        print("  [FAIL] data-g/README.md missing")

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

    print(f"\nLocal verification: {checks_passed}/{checks_total} checks passed")

    if checks_passed < checks_total:
        print("\nWARNING: Some local checks failed. Review and fix before starting work!")

    # Scaffold validation gate (#1575). Structural validity is checked on local
    # files BEFORE any GitHub state exists, so a malformed scaffold aborts with
    # nothing to roll back. Blocking failures abort; advisory ones only warn.
    print("\n" + "=" * 60)
    print("SCAFFOLD VALIDATION GATE")
    print("=" * 60)
    gate_blocking, gate_advisory = validate_scaffold(project_path)
    for msg in gate_advisory:
        print(f"  [WARN] {msg}")
    if gate_blocking:
        print("\n  BLOCKING -- scaffold is structurally invalid:")
        for msg in gate_blocking:
            print(f"    [FAIL] {msg}")
        print("\n  Aborting BEFORE any GitHub repo is created. Nothing was pushed.")
        print(f"  Local scaffold left for inspection at: {project_path}")
        print("  Fix the scaffolder defect, delete that directory, then re-run.")
        sys.exit(1)
    print("  [PASS] Scaffold structurally valid.")

    if not args.no_github:
        # Closes #1533: the GitHub repo name preserves the operator's input
        # case verbatim. Prior code unconditionally lowercased here, which
        # produced `martymcenroe/chiron` from `Chiron` input. GitHub's REST
        # API is case-insensitive for lookup and case-preserved for display,
        # so passing the verbatim case is correct in both directions.
        # (The Python package name at line ~1252 stays lowercased — that is
        # the separate PEP 503 packaging convention, not GitHub-side.)

        print("\n" + "=" * 60)
        print("GITHUB REMOTE (single classic-PAT session per ADR-0216)")
        print("=" * 60)
        print("\n  All elevated operations -- repo create, workflow upload,")
        print("  repo settings, branch protection, Cerberus deploy, and")
        print("  GitHub-side verification -- run inside ONE classic_pat_session().")
        print("  Single pinentry prompt; the PAT lives only in this Python")
        print("  process's heap and is removed programmatically when the block")
        print("  exits. No env vars, no subprocess argv. (#1268)\n")

        try:
            with classic_pat_session() as pat:
                _api_headers = {
                    "Authorization": f"token {pat}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }

                # Step 13: Create the GitHub repo via REST API.
                # Replaces `gh repo create --source . --push` which fails for
                # fine-grained PATs that lack Administration: write (per
                # ADR-0216 the fine-grained PAT is intentionally lean; admin
                # operations use the in-process classic PAT). (#1268)
                print(f"\n13. Creating GitHub repository ({args.name})...")
                create_resp = requests.post(
                    "https://api.github.com/user/repos",
                    headers=_api_headers,
                    json={
                        "name": args.name,
                        "private": not args.public,
                        "description": f"{args.name} project",
                    },
                    timeout=30,
                )
                if create_resp.status_code == 201:
                    print(f"  Created: https://github.com/{github_user}/{args.name}")
                    github_created = True
                elif create_resp.status_code == 422:
                    # 422 typically means "name already exists" -- check
                    # whether it's THIS user's repo (rerun mode) before failing.
                    check_resp = requests.get(
                        f"https://api.github.com/repos/{github_user}/{args.name}",
                        headers=_api_headers, timeout=30,
                    )
                    if check_resp.status_code == 200:
                        print(f"  Already exists: https://github.com/{github_user}/{args.name}")
                        print("  Proceeding in rerun mode against existing repo.")
                        github_created = True
                    else:
                        print(f"  ERROR: 422 from POST /user/repos but repo not found")
                        print(f"  Response: {create_resp.text[:300]}")
                else:
                    print(f"  ERROR: POST /user/repos returned {create_resp.status_code}")
                    print(f"  Response: {create_resp.text[:400]}")

                # Step 13b: Set remote + push the initial (non-workflow) commit.
                # The initial commit excludes .github/workflows (step 12), so
                # this push goes through git's credential helper (typically
                # `gh` with the fine-grained PAT) and works WITHOUT needing
                # the workflow scope.
                if github_created:
                    print("\n13b. Setting remote and pushing initial commit...")
                    remote_check = subprocess.run(
                        ["git", "remote", "get-url", "origin"],
                        cwd=str(project_path),
                        capture_output=True, text=True,
                    )
                    if remote_check.returncode != 0:
                        try:
                            run_command(
                                ["git", "remote", "add", "origin",
                                 f"https://github.com/{github_user}/{args.name}.git"],
                                cwd=project_path,
                            )
                        except Exception as e:
                            print(f"  WARNING: git remote add failed: {e}")
                    try:
                        run_command(
                            ["git", "push", "-u", "origin", "main"],
                            cwd=project_path,
                        )
                        push_succeeded = True
                        print("  Pushed initial commit (workflows uploaded separately via Contents API).")
                    except Exception as e:
                        print(f"  WARNING: git push failed: {e}")
                        print("  Diagnose: `gh auth status` + `git remote -v`.")
                        print("  Re-run the script after fixing -- it will resume against this repo.")

                # Step 14: Star the repo (non-fatal, uses pat via REST).
                if github_created:
                    print("\n14. Starring repository...")
                    star_resp = requests.put(
                        f"https://api.github.com/user/starred/{github_user}/{args.name}",
                        headers=_api_headers, timeout=30,
                    )
                    if star_resp.status_code in (204, 304):
                        print("  Starred repository")
                    else:
                        print(f"  (star non-fatal: {star_resp.status_code})")

                # Step 15: Upload workflow files via Contents API.
                if github_created and push_succeeded:
                    print("\n15. Uploading workflow files via Contents API...")
                    success, count = _deploy_workflows_via_contents_api(
                        project_path, github_user, args.name, pat,
                    )
                    if success:
                        workflows_deployed = True
                        if count > 0:
                            print(f"  Uploaded {count} workflow file(s) to main")
                        else:
                            print("  No workflow files to upload (skipped)")
                    else:
                        print("  WARNING: Workflow upload failed.")

                    # Step 16: Sync local repo with the Contents API commits.
                    if workflows_deployed and count > 0:
                        print("\n16. Syncing local repo with remote workflow commits...")
                        import shutil as _shutil
                        workflows_dir = project_path / ".github" / "workflows"
                        if workflows_dir.exists():
                            _shutil.rmtree(workflows_dir)
                        pull = subprocess.run(
                            ["git", "pull", "--rebase", "origin", "main"],
                            cwd=str(project_path), capture_output=True, text=True, timeout=60,
                        )
                        if pull.returncode == 0:
                            print("  Synced -- local is now at remote HEAD with workflows tracked.")
                        else:
                            print(f"  WARNING: git pull failed: {pull.stderr.strip()}")

                    # Step 17: Configure repo settings.
                    print("\n17. Configuring repo settings...")
                    if configure_repo_settings(github_user, args.name, pat):
                        print("  Repo settings configured:")
                        print("    - Wiki: disabled")
                        print("    - Projects: disabled")
                        print("    - Merge strategy: squash only")
                        print("    - Delete branch on merge: enabled")
                        repo_settings_ok = True
                    else:
                        print("  WARNING: Could not configure repo settings.")

                    # Step 18: Configure branch protection.
                    print("\n18. Configuring branch protection...")
                    if configure_branch_protection(github_user, args.name, pat):
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

                    # Step 19: Create canonical AZ workflow labels (#1061).
                    print("\n19. Creating canonical labels...")
                    created, total = create_canonical_labels(
                        github_user, args.name
                    )
                    print(f"  {created}/{total} labels created or updated "
                          f"({', '.join(n for n, _, _ in _CANONICAL_LABELS)})")

                    # Step 20: Enable Dependabot (#1331).
                    # Private repos default to Dependabot DISABLED at the
                    # repo settings level. Without this step, .github/
                    # dependabot.yml is inert -- no PRs emit, wedge starves.
                    # Confirmed defect 2026-05-26 on dependabot-honeypot.
                    print("\n20. Enabling Dependabot (security updates, alerts, "
                          "automated fixes)...")
                    db_result = enable_dependabot_for_repo(
                        github_user, args.name, pat, apply=True,
                    )
                    for endpoint, status in db_result.actions.items():
                        print(f"  {endpoint}: {status}")
                    if not db_result.ok:
                        print("  WARNING: Dependabot enablement had errors. "
                              "Re-run `tools/enable_dependabot.py --repo "
                              f"{github_user}/{args.name} --apply` "
                              "after diagnosing.")

                # Cerberus secrets deploy. Inside the same with-block so it
                # shares `pat` -- no extra pinentry. cerberus_pem_session
                # (if --cerberus-pem-gpg) is nested separately because it
                # decrypts a different encrypted blob with a different
                # passphrase.
                if (github_created and push_succeeded
                        and (args.cerberus_pem or args.cerberus_pem_gpg)):
                    if args.cerberus_pem:
                        pem_source_path = Path(args.cerberus_pem)
                        try:
                            pem_content = pem_source_path.read_text(
                                encoding="utf-8"
                            ).strip()
                            cerberus_status = _deploy_cerberus(
                                args.name, pem_content, pat,
                                source_path=pem_source_path,
                            )
                        except FileNotFoundError as e:
                            print(f"\n  WARNING: source PEM file not found: {e}")
                            cerberus_status = "PEM_NOT_FOUND"
                    else:  # args.cerberus_pem_gpg
                        pem_gpg_path = Path(args.cerberus_pem_gpg)
                        try:
                            with cerberus_pem_session(pem_gpg_path) as pem_content:
                                cerberus_status = _deploy_cerberus(
                                    args.name, pem_content, pat,
                                    source_path=None,
                                )
                        except FileNotFoundError as e:
                            print(f"\n  WARNING: encrypted PEM not configured: {e}")
                            cerberus_status = "PEM_GPG_NOT_CONFIGURED"
                        except RuntimeError as e:
                            print(f"\n  WARNING: PEM gpg decrypt failed: {e}")
                            cerberus_status = "PEM_GPG_FAILED"

                # GitHub-side verification. Also inside the with-block --
                # shares `pat`, no extra pinentry. (#1200, #1202)
                if github_created:
                    print("\n" + "=" * 60)
                    print("GITHUB-SIDE VERIFICATION")
                    print("=" * 60)

                    gh_checks_total += 1
                    ok, msg = verify_branch_protection_on_origin(
                        github_user, args.name, pat,
                    )
                    if ok:
                        print(f"  [PASS] Branch protection: {msg}")
                        gh_checks_passed += 1
                    else:
                        print(f"  [FAIL] Branch protection: {msg}")

                    gh_checks_total += 1
                    ok, msg = verify_repo_settings_on_origin(
                        github_user, args.name, pat,
                    )
                    if ok:
                        print(f"  [PASS] Repo settings: {msg}")
                        gh_checks_passed += 1
                    else:
                        print(f"  [FAIL] Repo settings: {msg}")

                    gh_checks_total += 1
                    ok, msg = verify_workflow_content_on_origin(
                        github_user, args.name, pat,
                    )
                    if ok:
                        print(f"  [PASS] auto-reviewer.yml: {msg}")
                        gh_checks_passed += 1
                    else:
                        print(f"  [FAIL] auto-reviewer.yml: {msg}")

                    if args.cerberus_pem or args.cerberus_pem_gpg:
                        gh_checks_total += 1
                        secrets_ok, missing = verify_secrets(
                            args.name, pat,
                        )
                        if secrets_ok:
                            print("  [PASS] Cerberus secrets present "
                                  "(REVIEWER_APP_ID, REVIEWER_APP_PRIVATE_KEY)")
                            gh_checks_passed += 1
                        else:
                            print(f"  [FAIL] Cerberus secrets missing: {missing}")

                    # pr-sentinel installation check -- elevated; needs the
                    # classic PAT (the /user/installations endpoint is NOT
                    # accessible to the fine-grained PAT). Inside the
                    # with-block, shares pat -- no extra pinentry. (#1274)
                    gh_checks_total += 1
                    ok, msg = verify_pr_sentinel_installation(
                        github_user, args.name, pat,
                    )
                    if ok:
                        print(f"  [PASS] pr-sentinel-mm Worker: {msg}")
                        gh_checks_passed += 1
                    else:
                        print(f"  [WARN] pr-sentinel-mm Worker: {msg}")
                        print("         If pr-sentinel checks don't appear on the first PR,")
                        print("         the App's installation scope likely drifted from "
                              "'All repositories'.")

        except FileNotFoundError as e:
            print(f"\n  ERROR: classic PAT not configured: {e}")
            print("  Local scaffold preserved. Set up classic PAT per ADR-0216 /")
            print("  runbook 0927, then re-run this script (it will resume against")
            print("  the existing scaffold and against the existing GitHub repo if")
            print("  one was created before the failure).")
        except RuntimeError as e:
            print(f"\n  ERROR: gpg decrypt failed: {e}")
            print("  Re-enter passphrase carefully and re-run.")

        if github_created:
            print(f"\nGitHub-side verification: {gh_checks_passed}/{gh_checks_total} checks passed")

            if gh_checks_passed < gh_checks_total:
                print("\nWARNING: GitHub-side checks failed. Investigate before opening PRs!")

    # Final summary
    if not args.no_github:
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        # Closes #1535: do NOT lowercase args.name here. The GitHub repo
        # was created with the verbatim case (#1533); the summary must
        # display the same value, not a mutated lowercased form.
        print("  Local scaffold:     OK")
        print(f"  GitHub repo:        {'OK' if github_created else 'FAILED'}")
        print(f"  Push:               {'OK' if push_succeeded else 'FAILED'}")
        print(f"  Repo settings:      {'OK' if repo_settings_ok else 'FAILED — configure manually'}")
        print(f"  Branch protection:  {'OK' if protection_ok else 'FAILED — configure manually or re-run with classic PAT'}")
        if cerberus_status is not None:
            print(f"  Cerberus secrets:   {cerberus_status}")

    print("\n" + "=" * 60)
    print(f"[SUCCESS] Repository '{args.name}' created!")
    print("\nNext steps:")
    print(f"  cd {project_path}")
    if not args.no_github:
        # Closes #1535: print the verbatim case-preserved repo name, not
        # a mutated lowercased form. The local dir on the `cd` line above
        # and this URL must agree, both matching the actual GitHub repo.
        print(f"  # Repository: https://github.com/{github_user}/{args.name}")
        if not push_succeeded:
            print("  # IMPORTANT: Initial push failed.")
            print("  # Diagnose first -- the push uses git's credential helper")
            print("  # (typically `gh` with the fine-grained PAT), and the initial")
            print("  # commit contains NO workflow files so the fine-grained PAT")
            print("  # has sufficient scope. Common causes:")
            print("  #   - gh auth not configured: `gh auth status`")
            print("  #   - remote URL wrong: `git remote -v`")
            print("  #   - network / proxy issue")
            print("  # Then re-run the script; it will resume against this repo.")
            print("  # DO NOT escalate to env GH_TOKEN or `gh auth login` swap --")
            print("  # those violate ADR-0216 (PAT in env block / globally-")
            print("  # visible gh storage). The fine-grained PAT is sufficient")
            print("  # for this push; if it isn't, the problem is elsewhere.")
    if (args.cerberus_pem is None and args.cerberus_pem_gpg is None
            and not args.no_github):
        print()
        print("  # Cerberus secrets (manual):")
        print("  #   Without secrets, PRs pass pr-sentinel but are never auto-approved.")
        print("  #   1. https://github.com/settings/apps/cerberus-az > Private keys > Generate")
        print("  #   2. poetry run python tools/deploy_cerberus_secrets.py /path/to/downloaded.pem")
        print("  #   3. Delete the .pem, revoke the key in the app UI")
        print("  #   See runbook 0927 step 4 for full procedure.")
        print("  #   OR re-run this script with --cerberus-pem PATH (single-shot)")
        print("  #   or --cerberus-pem-gpg PATH (reusable, encrypted at rest).")
    elif cerberus_status == "OK":
        # Closes #1536: the post-deploy advice depends on which Cerberus
        # flow ran. The plaintext flow (--cerberus-pem) deletes the .pem
        # after deploy, so revoking the GitHub-side key as belt-and-
        # suspenders is correct — no on-disk credential survives this run.
        # The encrypted-reusable flow (--cerberus-pem-gpg) intentionally
        # keeps the encrypted blob for subsequent new-repo invocations;
        # revoking the key would invalidate that blob — catastrophic for
        # the documented design intent of the flag.
        print()
        print("  # Cerberus secrets deployed and verified.")
        if args.cerberus_pem is not None:
            print("  # The plaintext .pem was deleted by the script.")
            print("  # REMEMBER to revoke the key in the app UI (browser-only step) —")
            print("  # there is no on-disk credential to retire otherwise.")
        else:  # args.cerberus_pem_gpg is not None
            print(f"  # Encrypted PEM preserved at {args.cerberus_pem_gpg} for reuse.")
            print("  # DO NOT revoke the key in the app UI — that would invalidate")
            print("  # the encrypted blob you just kept. Revoke only when you want")
            print("  # to retire this credential entirely (e.g., rotation per")
            print("  # runbook 0930, AZ #1017).")

    # The internal function uses `no_pypi` (legacy parameter name); compute
    # it as "did the operator OPT IN via --pypi?" -- false = no_pypi=True =
    # reminder suppressed; true = no_pypi=False = reminder fires. (#1269)
    _maybe_print_pypi_reminder(
        lang=args.lang,
        no_pypi=not args.pypi,
        no_github=args.no_github,
        github_user=github_user,
        # Closes #1535: pass the case-preserved repo name. PyPI itself
        # canonicalizes the PEP 503 form internally; the displayed URL
        # in the reminder should match the actual GitHub repo name.
        repo_name=args.name,
    )


def _maybe_print_pypi_reminder(
    *,
    lang: str,
    no_pypi: bool,
    no_github: bool,
    github_user: str,
    repo_name: str,
) -> None:
    """Print the PyPI 0934 reminder if release.yml shipped on this repo.

    release.yml is deployed by create_github_workflows() when
    enable_pypi == (lang == "python") and (not no_pypi). The first
    `git push origin v0.1.0` tag will fail at the publish step unless
    the user has done the one-time PyPI pending-publisher registration
    first — runbook 0934 covers the browser step. Surface here so the
    user can't miss it. (#1201)

    No-op when:
    - --no-github was passed (no remote to release from)
    - --lang none was passed (no Python project, no release.yml shipped)
    - --no-pypi was passed (explicit opt-out, release.yml suppressed)

    Keyword-only args so callers must be explicit about the flag state.
    """
    if no_github or lang != "python" or no_pypi:
        return
    print()
    print("  # PyPI publish needs ONE-TIME pending-publisher registration")
    print("  # BEFORE the first tag push (otherwise release.yml fails):")
    print("  #   1. https://pypi.org/manage/account/publishing/")
    print("  #   2. Add new pending publisher:")
    print(f"  #        Project name:     {repo_name}")
    print(f"  #        Owner:            {github_user}")
    print(f"  #        Repository name:  {repo_name}")
    print("  #        Workflow filename: release.yml")
    print("  #        Environment name:  pypi")
    print("  #   3. Click Add. Then `git tag v0.1.0 && git push origin v0.1.0`.")
    print("  # Full procedure: docs/runbooks/0934-pypi-trusted-publisher-setup.md")
    print("  # Not publishing to PyPI? Delete .github/workflows/release.yml.")


if __name__ == "__main__":
    main()
