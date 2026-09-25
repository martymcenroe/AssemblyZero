"""The archival step CLAUDE.md prescribes runs as written (#3558).

`tools/archive_worktree_lineage.py` carried `shutil.rmtree` (and `unlink`)
in `clean_ephemeral`, and the shell guard reads a script for deletion calls
before it lets an agent run it: on 2026-09-24 the command CLAUDE.md tells an
agent to run before every PR was refused for every PR of the day. The
function deleted gitignored caches that `git worktree remove`, the last step
of the same sequence, deletes anyway.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "archive_worktree_lineage.py"
GUARD_SHIM = Path.home() / ".claude" / "hooks" / "shell-guard.sh"
#: The command CLAUDE.md ("Merging PRs") prescribes, with an issue number.
CLAUDE_MD_COMMAND = (
    "poetry run python tools/archive_worktree_lineage.py "
    "--worktree . --issue 3558 --main-repo ."
)


class TestTheToolDeletesNothing:
    def test_no_deletion_call_remains(self):
        """Requirement 1: no rmtree, unlink or remove call, and no
        `from shutil import rmtree`, anywhere in the tool."""
        tree = ast.parse(TOOL.read_text(encoding="utf-8"))
        imported = [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "shutil"
            for alias in node.names
            if alias.name == "rmtree"
        ]
        deleting = {"rmtree", "unlink", "remove", "removedirs", "rmdir"}
        calls = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr in deleting)
                or (isinstance(node.func, ast.Name) and node.func.id in deleting)
            )
        ]

        assert imported == []
        assert calls == [], f"deletion calls at lines {calls}"

    def test_clean_ephemeral_is_gone(self):
        import tools.archive_worktree_lineage as awl

        assert not hasattr(awl, "clean_ephemeral")

    def test_claude_md_prescribes_the_same_command(self):
        """The fix is in the tool, not the procedure."""
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")

        assert (
            "tools/archive_worktree_lineage.py --worktree . --issue {ID} --main-repo ."
            in text
        )


class TestMainRunsTheThreeStepsAndNothingElse:
    def test_main_archives_stages_and_evicts_in_order(self, tmp_path, monkeypatch):
        """Requirement 2: the three collaborators, in the same order as before,
        and no cleaning step between archive and stage."""
        import tools.archive_worktree_lineage as awl

        calls: list[str] = []
        monkeypatch.setattr(awl, "require_linked_worktree", lambda p: calls.append("require"))

        def archive(wt, issue, main):
            calls.append("archive")
            return [tmp_path / "archived"]

        monkeypatch.setattr(awl, "archive_lineage", archive)
        monkeypatch.setattr(awl, "stage_archived", lambda main, issue: calls.append("stage"))
        monkeypatch.setattr(awl, "evict_poetry_venv", lambda wt: calls.append("evict"))

        argv = ["prog", "--worktree", str(tmp_path), "--issue", "3558", "--main-repo", str(tmp_path)]
        with patch("sys.argv", argv):
            awl.main()
        # #3626: eviction is opt-in, so the default run stops after staging.
        assert calls == ["require", "archive", "stage"]

        calls.clear()
        with patch("sys.argv", argv + ["--evict-venv"]):
            awl.main()
        assert calls == ["require", "archive", "stage", "evict"]


@pytest.mark.skipif(
    not GUARD_SHIM.exists(),
    reason="the shell guard is installed on the operator's machine only",
)
class TestTheGuardLetsTheCommandThrough:
    def test_the_claude_md_command_is_not_denied(self):
        """Exit 2 is the guard's deny (its shim says so; every other code is
        permission). Run from this checkout, so the script path in the
        command resolves to the tool under test."""
        payload = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": CLAUDE_MD_COMMAND},
        })

        result = subprocess.run(
            ["bash", str(GUARD_SHIM)],
            input=payload, capture_output=True, text=True,
            encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=120,
        )

        assert result.returncode != 2, result.stderr
