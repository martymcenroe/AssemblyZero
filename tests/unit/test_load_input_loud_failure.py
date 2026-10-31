"""The requirements input node (N0) under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (lines at 79e18ad1). An issue
with no body halts before anything drafts from it. The repo provenance
written into the lineage is looked up or the run stops: a failed lookup used
to write "unknown/unknown" into the frontmatter without a word. A mock run is
an offline rehearsal and looks nothing up.
"""
from __future__ import annotations

import importlib
import json
import subprocess
from unittest.mock import patch

import pytest

from assemblyzero.workflows.requirements.graph import route_after_load_input

li = importlib.import_module("assemblyzero.workflows.requirements.nodes.load_input")


def _done(stdout: str = "", stderr: str = "", rc: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def _commands(issue: dict, remote: subprocess.CompletedProcess):
    """gh answers with `issue`; git answers the remote lookup with `remote`."""
    def run(args, **kwargs):
        if args[0] == "gh":
            return _done(stdout=json.dumps(issue))
        if args[0] == "git":
            return remote
        raise AssertionError(f"unexpected command {args}")
    return run


GITHUB_REMOTE = _done(stdout="https://github.com/o/r.git\n")


def _state(tmp_path, **overrides) -> dict:
    state = {"workflow_type": "lld", "issue_number": 42, "target_repo": str(tmp_path)}
    state.update(overrides)
    return state


def _halts(out: dict) -> bool:
    return bool(out.get("error_message")) and route_after_load_input(out) == "HALT"


class TestIssueBody:
    @pytest.mark.parametrize("body", ["", "   \n", None])
    def test_207_an_issue_with_no_body_halts_naming_it(self, tmp_path, capsys, body):
        with patch.object(li, "run_command", side_effect=_commands({"title": "T", "body": body}, GITHUB_REMOTE)):
            out = li.load_input(_state(tmp_path))

        assert _halts(out)
        assert "#42" in out["error_message"]
        assert "body" in out["error_message"]
        assert "ERROR" in capsys.readouterr().err

    def test_207_kept_an_issue_with_a_body_loads(self, tmp_path):
        with patch.object(li, "run_command", side_effect=_commands({"title": "T", "body": "Do it."}, GITHUB_REMOTE)):
            out = li.load_input(_state(tmp_path))

        assert out["error_message"] == ""
        assert out["issue_body"] == "Do it."


class TestProvenance:
    def test_334_a_remote_lookup_that_fails_raises_with_its_stderr(self, tmp_path, capsys):
        remote = _done(stderr="error: No such remote 'origin'", rc=2)
        with patch.object(li, "run_command", return_value=remote), \
             pytest.raises(li.RepoNameError, match="No such remote 'origin'"):
            li._get_repo_name(str(tmp_path))
        assert "ERROR" in capsys.readouterr().err

    def test_334_and_the_node_halts_rather_than_write_unknown(self, tmp_path):
        remote = _done(stderr="fatal: not a git repository", rc=128)
        with patch.object(li, "run_command", side_effect=_commands({"title": "T", "body": "Do it."}, remote)):
            out = li.load_input(_state(tmp_path))

        assert _halts(out)
        assert "not a git repository" in out["error_message"]
        assert not list(tmp_path.rglob("*issue.md")), "no lineage written with unknown provenance"

    def test_340_a_lookup_that_raises_is_said_and_raised(self, tmp_path, capsys):
        with patch.object(li, "run_command", side_effect=subprocess.TimeoutExpired(["git"], 10)), \
             pytest.raises(li.RepoNameError, match="TimeoutExpired"):
            li._get_repo_name(str(tmp_path))
        assert "ERROR" in capsys.readouterr().err

    def test_340_kept_a_github_remote_names_the_repo(self, tmp_path):
        with patch.object(li, "run_command", return_value=_done(stdout="git@github.com:o/r.git\n")):
            assert li._get_repo_name(str(tmp_path)) == "o/r"

    def test_kept_a_mock_run_looks_nothing_up(self, tmp_path):
        with patch.object(li, "run_command", side_effect=AssertionError("a mock run ran a command")):
            out = li.load_input(_state(tmp_path, config_mock_mode=True))

        assert out["error_message"] == ""
        [issue] = list((tmp_path / "data").rglob("*issue.md"))
        assert "repo: mock/" in issue.read_text(encoding="utf-8")
