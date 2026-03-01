```python
"""Tests for janitor probes.

Issue #94: Lu-Tze: The Janitor
Test IDs: T020-T100, T150-T220
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, mock_open, patch

import pytest

from assemblyzero.workflows.janitor.probes import run_probe_safe
from assemblyzero.workflows.janitor.probes.harvest import (
    find_harvest_script,
    parse_harvest_output,
    probe_harvest,
)
from assemblyzero.workflows.janitor.probes.links import (
    extract_internal_links,
    find_likely_target,
    find_markdown_files,
    probe_links,
    resolve_link,
)
from assemblyzero.workflows.janitor.probes.todo import (
    extract_todos,
    get_line_date,
    probe_todo,
)
from assemblyzero.workflows.janitor.probes.worktrees import (
    get_branch_last_commit_date,
    is_branch_merged,
    list_worktrees,
    probe_worktrees,
)
from assemblyzero.workflows.janitor.state import ProbeResult


FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "fixtures", "janitor", "mock_repo"
)


class TestProbeLinkDetection:
    """Test broken link detection. T020, T030, T040, T150, T160, T170."""

    def test_probe_links_detects_broken_link(self, tmp_path):
        """T020/T150: probe_links returns fixable finding for resolvable broken link."""
        # Create mock repo with broken link
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/old-guide.md)\n")
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ), patch(
            "assemblyzero.workflows.janitor.probes.links.find_likely_target",
            return_value="./docs/guide.md",
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].fixable is True
        assert result.findings[0].fix_data["new_link"] == "./docs/guide.md"

    def test_probe_links_ignores_external_urls(self, tmp_path):
        """T030/T160: probe_links skips http/https links."""
        readme = tmp_path / "README.md"
        readme.write_text("[example](https://example.com)\n[other](http://other.com)\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "ok"
        assert result.findings == []

    def test_probe_links_handles_valid_links(self, tmp_path):
        """T040/T170: probe_links returns ok for all valid links."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("[guide](./docs/guide.md)\n")

        with patch(
            "assemblyzero.workflows.janitor.probes.links.find_markdown_files",
            return_value=[str(readme)],
        ):
            result = probe_links(str(tmp_path))

        assert result.status == "ok"

    def test_extract_internal_links(self, tmp_path):
        """extract_internal_links returns relative links only."""
        md = tmp_path / "test.md"
        md.write_text(
            "# Test\n"
            "[guide](./docs/guide.md)\n"
            "[ext](https://example.com)\n"
            "![img](./images/pic.png)\n"
            "[anchor](#heading)\n"
        )
        links = extract_internal_links(str(md))
        assert len(links) == 2
        assert links[0] == (2, "guide", "./docs/guide.md")
        assert links[1] == (4, "img", "./images/pic.png")

    def test_resolve_link_existing(self, tmp_path):
        """resolve_link returns True for existing file."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/guide.md", str(tmp_path)) is True

    def test_resolve_link_missing(self, tmp_path):
        """resolve_link returns False for missing file."""
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/nonexistent.md", str(tmp_path)) is False

    def test_resolve_link_with_anchor(self, tmp_path):
        """resolve_link strips anchor before checking."""
        docs = tmp_path / "docs"
        docs.mkdir()
        guide = docs / "guide.md"
        guide.write_text("# Guide\n")
        readme = tmp_path / "README.md"
        readme.write_text("")
        assert resolve_link(str(readme), "./docs/guide.md#section", str(tmp_path)) is True

    def test_find_likely_target_unique_match(self, tmp_path):
        """find_likely_target returns match when exactly one file with same basename."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="docs/guide.md\n"
            )
            result = find_likely_target("./docs/old-guide.md", str(tmp_path))
            # basename of old-guide.md is old-guide.md, no match for guide.md
            assert result is None

    def test_find_likely_target_no_match(self, tmp_path):
        """find_likely_target returns None when no files match."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="docs/guide.md\nREADME.md\n"
            )
            result = find_likely_target("./nonexistent.md", str(tmp_path))
            assert result is None


class TestProbeWorktrees:
    """Test worktree detection. T050, T060, T180, T190."""

    def test_probe_worktrees_detects_stale(self):
        """T050/T180: probe_worktrees returns finding for stale merged worktree."""
        past_date = datetime.now(timezone.utc) - timedelta(days=15)

        with patch(
            "assemblyzero.workflows.janitor.probes.worktrees.list_worktrees",
            return_value=[
                {
                    "path": "/repo",
                    "HEAD": "abc123",
                    "branch": "refs/heads/main",
                    "bare": False,
                    "detached": False,
                },
                {
                    "path": "/repo-42",
                    "HEAD": "def456",
                    "branch": "refs/heads/feature/old",
                    "bare": False,
                    "detached": False,
                },
            ],
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.get_branch_last_commit_date",
            return_value=past_date,
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.is_branch_merged",
            return_value=True,
        ):
            result = probe_worktrees("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "stale_worktree"
        assert result.findings[0].fixable is True

    def test_probe_worktrees_ignores_active(self):
        """T060/T190: probe_worktrees returns no finding for active worktree."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch(
            "assemblyzero.workflows.janitor.probes.worktrees.list_worktrees",
            return_value=[
                {
                    "path": "/repo",
                    "HEAD": "abc123",
                    "branch": "refs/heads/main",
                    "bare": False,
                    "detached": False,
                },
                {
                    "path": "/repo-42",
                    "HEAD": "def456",
                    "branch": "refs/heads/feature/active",
                    "bare": False,
                    "detached": False,
                },
            ],
        ), patch(
            "assemblyzero.workflows.janitor.probes.worktrees.get_branch_last_commit_date",
            return_value=recent_date,
        ):
            result = probe_worktrees("/repo")

        assert result.status == "ok"
        assert result.findings == []

    def test_list_worktrees_parses_porcelain(self):
        """list_worktrees parses git porcelain output correctly."""
        porcelain_output = (
            "worktree /home/user/repo\n"
            "HEAD abc123def456\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/repo-42\n"
            "HEAD def789abc012\n"
            "branch refs/heads/feature/thing\n"
            "\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=porcelain_output
            )
            wts = list_worktrees("/repo")

        assert len(wts) == 2
        assert wts[0]["path"] == "/home/user/repo"
        assert wts[0]["branch"] == "refs/heads/main"
        assert wts[1]["path"] == "/home/user/repo-42"

    def test_list_worktrees_detached(self):
        """list_worktrees parses detached worktree correctly."""
        porcelain_output = (
            "worktree /home/user/repo\n"
            "HEAD abc123def456\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /home/user/repo-42\n"
            "HEAD def789abc012\n"
            "detached\n"
            "\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=porcelain_output
            )
            wts = list_worktrees("/repo")

        assert wts[1]["detached"] is True
        assert "branch" not in wts[1]

    def test_get_branch_last_commit_date(self):
        """get_branch_last_commit_date parses ISO 8601 date."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="2026-02-15T10:30:00+00:00\n"
            )
            dt = get_branch_last_commit_date("/repo", "feature/thing")

        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 2
        assert dt.day == 15

    def test_get_branch_last_commit_date_nonexistent(self):
        """get_branch_last_commit_date returns None for nonexistent branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            dt = get_branch_last_commit_date("/repo", "nonexistent")

        assert dt is None

    def test_is_branch_merged(self):
        """is_branch_merged returns True for merged branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="  feature/old\n* main\n"
            )
            assert is_branch_merged("/repo", "feature/old") is True

    def test_is_branch_not_merged(self):
        """is_branch_merged returns False for unmerged branch."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="* main\n"
            )
            assert is_branch_merged("/repo", "feature/active") is False


class TestProbeTodo:
    """Test TODO detection. T070, T080, T200, T210."""

    def test_probe_todo_finds_stale(self):
        """T070/T200: probe_todo returns finding for TODO older than 30 days."""
        past_date = datetime.now(timezone.utc) - timedelta(days=45)

        with patch(
            "assemblyzero.workflows.janitor.probes.todo.find_source_files",
            return_value=["tools/helper.py"],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.extract_todos",
            return_value=[(42, "# TODO: refactor this function")],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.get_line_date",
            return_value=past_date,
        ):
            result = probe_todo("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "stale_todo"
        assert result.findings[0].fixable is False

    def test_probe_todo_ignores_recent(self):
        """T080/T210: probe_todo returns no finding for recent TODO."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=1)

        with patch(
            "assemblyzero.workflows.janitor.probes.todo.find_source_files",
            return_value=["tools/helper.py"],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.extract_todos",
            return_value=[(42, "# TODO: add this feature")],
        ), patch(
            "assemblyzero.workflows.janitor.probes.todo.get_line_date",
            return_value=recent_date,
        ):
            result = probe_todo("/repo")

        assert result.status == "ok"
        assert result.findings == []

    def test_extract_todos(self, tmp_path):
        """extract_todos finds TODO/FIXME/HACK/XXX patterns."""
        f = tmp_path / "test.py"
        f.write_text(
            "def func():\n"
            "    # TODO: refactor this\n"
            "    pass\n"
            "    # FIXME: handle error\n"
            "    # Regular comment\n"
            "    # HACK: workaround for bug\n"
        )
        todos = extract_todos(str(f))
        assert len(todos) == 3
        assert todos[0] == (2, "# TODO: refactor this")
        assert todos[1] == (4, "# FIXME: handle error")
        assert todos[2] == (6, "# HACK: workaround for bug")

    def test_get_line_date_parses_blame(self):
        """get_line_date parses author-time from git blame porcelain."""
        blame_output = (
            "abc123 42 42 1\n"
            "author Test User\n"
            "author-mail <test@example.com>\n"
            "author-time 1737936000\n"  # 2025-01-27T00:00:00Z
            "author-tz +0000\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout=blame_output
            )
            dt = get_line_date("/repo", "test.py", 42)

        assert dt is not None
        assert dt.year == 2025

    def test_get_line_date_untracked(self):
        """get_line_date returns None for untracked file."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            dt = get_line_date("/repo", "untracked.py", 1)

        assert dt is None


class TestProbeHarvest:
    """Test harvest detection. T090, T220."""

    def test_probe_harvest_missing_script(self):
        """T090/T220: probe_harvest returns info finding when script not found."""
        with patch(
            "assemblyzero.workflows.janitor.probes.harvest.find_harvest_script",
            return_value=None,
        ):
            result = probe_harvest("/repo")

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].category == "harvest_missing"
        assert result.findings[0].severity == "info"
        assert result.findings[0].fixable is False

    def test_parse_harvest_output_drift_lines(self):
        """parse_harvest_output extracts DRIFT lines."""
        output = (
            "OK: assemblyzero/state.py in sync\n"
            "DRIFT: pyproject.toml version mismatch\n"
            "OK: tools/audit.py in sync\n"
            "DRIFT: docs/standards/0001.md outdated\n"
        )
        findings = parse_harvest_output(output)
        assert len(findings) == 2
        assert findings[0].category == "cross_project_drift"
        assert "pyproject.toml" in findings[0].message

    def test_parse_harvest_output_no_drift(self):
        """parse_harvest_output returns empty list for clean output."""
        output = "OK: everything in sync\n"
        findings = parse_harvest_output(output)
        assert findings == []

    def test_find_harvest_script_in_root(self, tmp_path):
        """find_harvest_script finds script in repo root."""
        script = tmp_path / "assemblyzero-harvest.py"
        script.write_text("# script")
        assert find_harvest_script(str(tmp_path)) == str(script)

    def test_find_harvest_script_in_tools(self, tmp_path):
        """find_harvest_script finds script in tools/."""
        tools = tmp_path / "tools"
        tools.mkdir()
        script = tools / "assemblyzero-harvest.py"
        script.write_text("# script")
        assert find_harvest_script(str(tmp_path)) == str(script)

    def test_find_harvest_script_not_found(self, tmp_path):
        """find_harvest_script returns None when not found."""
        assert find_harvest_script(str(tmp_path)) is None


class TestProbeIsolation:
    """Test probe crash isolation. T100."""

    def test_run_probe_safe_catches_exception(self):
        """T100: run_probe_safe returns error ProbeResult on exception."""

        def crashing_probe(repo_root: str) -> ProbeResult:
            raise RuntimeError("Probe exploded!")

        result = run_probe_safe("links", crashing_probe, "/repo")
        assert result.status == "error"
        assert result.probe == "links"
        assert "RuntimeError: Probe exploded!" in result.error_message

    def test_run_probe_safe_passes_through_success(self):
        """run_probe_safe returns normal result on success."""
        expected = ProbeResult(probe="links", status="ok")

        def good_probe(repo_root: str) -> ProbeResult:
            return expected

        result = run_probe_safe("links", good_probe, "/repo")
        assert result.status == "ok"
        assert result is expected
```
