"""Unit tests for tools/dependabot_review.py.

Issue #957: Regression test for the Windows CreateProcess argv-size limit.
The tool used to pass full PR bodies via `gh pr edit --body "<string>"`,
which crashed on Windows with WinError 206 when bodies exceeded ~32KB
(common for multi-package dependabot group bumps with embedded release
notes). The fix routes large bodies through `--body-file <tempfile>`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import dependabot_review  # noqa: E402


# 30KB is well above the empirically-observed Windows CreateProcess limit
# (~32K total including the rest of the command). Real PR #953 body was ~19KB.
LARGE_BODY = "x" * 30_000


def _stub_run(captured: dict) -> mock.MagicMock:
    """Replace the module's `run` with a stub that records args and returns success."""
    stub = mock.MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    )

    def _capture(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        return stub.return_value

    stub.side_effect = _capture
    return stub


class TestRunGhWithBody:
    """Direct tests for the new helper introduced by #957."""

    def test_uses_body_file_flag_not_body(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        dependabot_review.run_gh_with_body(
            ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
            "hello world",
        )

        assert "--body-file" in captured["cmd"]
        assert "--body" not in captured["cmd"], (
            "Helper must NOT pass body via --body argv (the bug it fixes)."
        )

    def test_body_file_contents_match_body(self, monkeypatch):
        captured: dict = {}
        body_seen: dict = {}

        def _capture(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            # Read the file before the helper deletes it
            tmp_path = cmd[cmd.index("--body-file") + 1]
            body_seen["text"] = Path(tmp_path).read_text(encoding="utf-8")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)

        dependabot_review.run_gh_with_body(
            ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
            "exact body content",
        )
        assert body_seen["text"] == "exact body content"

    def test_tempfile_cleaned_up_after_call(self, monkeypatch):
        tmp_paths: list[str] = []

        def _capture(cmd, *args, **kwargs):
            tmp_paths.append(cmd[cmd.index("--body-file") + 1])
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)

        dependabot_review.run_gh_with_body(
            ["gh", "pr", "comment", "1", "--repo", "owner/repo"],
            "some comment",
        )
        assert tmp_paths, "subprocess should have been invoked"
        assert not Path(tmp_paths[0]).exists(), "tempfile should be cleaned up after call"

    def test_tempfile_cleaned_up_on_exception(self, monkeypatch):
        tmp_paths: list[str] = []

        def _capture_then_raise(cmd, *args, **kwargs):
            tmp_paths.append(cmd[cmd.index("--body-file") + 1])
            raise RuntimeError("simulated subprocess failure")

        monkeypatch.setattr(dependabot_review, "run", _capture_then_raise)

        with pytest.raises(RuntimeError):
            dependabot_review.run_gh_with_body(
                ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
                "body",
            )
        assert tmp_paths, "subprocess should have been invoked"
        assert not Path(tmp_paths[0]).exists(), (
            "tempfile must be cleaned up even when the subprocess raises."
        )

    def test_handles_30kb_body_without_winerror(self, monkeypatch):
        """REGRESSION: 30KB body must not raise FileNotFoundError (WinError 206)."""
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        result = dependabot_review.run_gh_with_body(
            ["gh", "pr", "edit", "1", "--repo", "owner/repo"],
            LARGE_BODY,
        )
        assert result.returncode == 0


class TestInjectNoIssue:
    """Tests for inject_no_issue, the original failure site."""

    def test_inject_no_issue_does_not_use_body_argv(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        pr = dependabot_review.PRInfo(
            number=42,
            title="t",
            author_login="app/dependabot",
            body=LARGE_BODY,
            head_ref="dependabot/pip/x-1",
        )
        dependabot_review.inject_no_issue(pr, "owner/repo")

        assert "--body" not in captured["cmd"], (
            "inject_no_issue must use --body-file, never --body (#957 fix)."
        )
        assert "--body-file" in captured["cmd"]

    def test_inject_no_issue_writes_full_tagged_body(self, monkeypatch):
        body_seen: dict = {}

        def _capture(cmd, *args, **kwargs):
            tmp_path = cmd[cmd.index("--body-file") + 1]
            body_seen["text"] = Path(tmp_path).read_text(encoding="utf-8")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(dependabot_review, "run", _capture)

        pr = dependabot_review.PRInfo(
            number=42,
            title="bump foo",
            author_login="app/dependabot",
            body="Bumps `foo` from 1.0 to 2.0.",
            head_ref="dependabot/pip/foo-2",
        )
        dependabot_review.inject_no_issue(pr, "owner/repo")

        assert "Bumps `foo` from 1.0 to 2.0." in body_seen["text"]
        assert "No-Issue:" in body_seen["text"]


class TestCommentOnPr:
    """comment_on_pr also routes through run_gh_with_body for consistency."""

    def test_uses_body_file(self, monkeypatch):
        captured: dict = {}
        monkeypatch.setattr(dependabot_review, "run", _stub_run(captured))

        dependabot_review.comment_on_pr(99, "owner/repo", "comment text")

        assert "--body-file" in captured["cmd"]
        assert "--body" not in captured["cmd"]
        assert "gh" in captured["cmd"][0]
        assert "comment" in captured["cmd"]
