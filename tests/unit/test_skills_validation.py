"""Validates every .claude/skills/*.md against known empty-content-block triggers.

Backs the 2026-05-12 outage class — a malformed onboard.md got deployed and
stuck a live Claude Code session on a cached broken slash command. The static
validator (tools/validate_skill.py) checks for conservative rule patterns:
E001 empty code fence, E003 trailing whitespace after final HR, E004 missing
scope frontmatter, E005 unbalanced code fences. All 22 currently-deployed AZ
skills pass clean.

The validator is mirrored from martymcenroe/unleashed/tools/validate_skill.py
because the unleashed tools/ dir isn't available in GitHub Actions runners
without a separate checkout (which requires workflow-scope PAT auth). When
the unleashed canonical changes, manually re-copy via:
    cp ~/Projects/unleashed/tools/validate_skill.py tools/validate_skill.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_skills_validation_runs():
    """All .claude/skills/*.md files pass validate_skill.py's static rules."""
    repo_root = Path(__file__).resolve().parents[2]
    skills_dir = repo_root / ".claude" / "skills"
    if not skills_dir.is_dir():
        pytest.skip(f"skills dir {skills_dir} does not exist")

    skill_files = sorted(skills_dir.glob("*.md"))
    if not skill_files:
        pytest.skip(f"no .md files in {skills_dir}")

    validator = repo_root / "tools" / "validate_skill.py"
    assert validator.is_file(), f"validator missing: {validator}"

    cmd = [sys.executable, str(validator), *[str(p) for p in skill_files]]
    result = subprocess.run(cmd, capture_output=True, text=True)

    assert result.returncode == 0, (
        f"validate_skill.py failed (rc={result.returncode}).\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
        "Fix the flagged skills or update tools/validate_skill.py."
    )
