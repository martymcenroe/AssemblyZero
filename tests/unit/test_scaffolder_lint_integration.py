"""Integration test — the scaffolder's CLAUDE.md emission must pass the fleet lint.

#1305 — without this test, `tools/new_repo_setup.py:create_claude_md` and
`tools/lint_per_repo_claude_md.py:detect_drift` can drift apart silently.
Yesterday's incident: scaffolder shipped a TODO block whose explanatory text
mentioned "merge sequence" and "banned commands"; the lint detector (shipped
hours later) flagged that exact phrase as drift. Three real repos shipped
broken because no test ran the scaffolder and ran the lint against its output.

This test closes that loop. Any future edit to either the scaffolder template
or the lint detector that breaks their agreement fails CI.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from new_repo_setup import PROJECT_TYPES, create_claude_md  # noqa: E402
from lint_per_repo_claude_md import detect_drift  # noqa: E402


@pytest.mark.parametrize("project_type", PROJECT_TYPES)
def test_scaffolder_emission_passes_lint(tmp_path: Path, project_type: str) -> None:
    """For each project type, the scaffolder's CLAUDE.md emission must pass lint.

    Catches: any template edit that re-introduces drift phrases, drops content
    below the stub threshold, or otherwise produces content the fleet lint
    would reject. The whole point is to fail in CI BEFORE a real repo is
    created with broken content.
    """
    repo = tmp_path / f"test-{project_type}"
    repo.mkdir()
    create_claude_md(repo, f"test-{project_type}", "alice", project_type)
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert result.status == "PASS", (
        f"Scaffolder emission for project_type={project_type!r} tripped lint:\n"
        + "\n".join(
            f"  - marker {f.marker} ({f.severity}): {f.description}"
            for f in result.findings
        )
    )


def test_scaffolder_emission_default_project_type_passes_lint(tmp_path: Path) -> None:
    """The default (no project_type arg) emission must also pass lint."""
    repo = tmp_path / "test-default"
    repo.mkdir()
    create_claude_md(repo, "test-default", "alice")  # default project_type=minimal
    result = detect_drift(repo / "CLAUDE.md", repo)
    assert result.status == "PASS", (
        "Scaffolder default emission tripped lint:\n"
        + "\n".join(
            f"  - marker {f.marker} ({f.severity}): {f.description}"
            for f in result.findings
        )
    )
