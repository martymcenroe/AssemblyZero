"""
Safety guards for new_repo.py.

Two failure modes, both diagnosed from real runs on 2026-07-25/26:

- #1805: scaffolding a fresh local history against a name whose GitHub repo
  already exists. The push is rejected, and every step gated on that push --
  workflow upload, repo settings, the Cerberus secret deploy -- silently
  skips. The visible symptom (a missing second pinentry prompt) reads as a
  broken security flow when the real fault is scaffolding over a live repo.
- #1806: a passphrase typed while pinentry lacks focus must land nowhere.
  This process, and the children it spawns, must not be able to read it.

Issues: #1805, #1806
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from new_repo import (
    _create_repo,
    check_remote_repo_exists,
    detach_stdin,
    get_github_username,
    main,
    run_command,
)

TOOLS_DIR = Path(__file__).parent.parent.parent / "tools"


def _completed(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


# ===========================================================================
# #1805 — the existence oracle
# ===========================================================================


class TestCheckRemoteRepoExists:

    def test_returns_metadata_when_repo_exists(self):
        payload = '{"full_name": "u/r", "created_at": "2026-07-04T10:00:00Z", "private": true}'
        with patch("new_repo.subprocess.run", return_value=_completed(0, payload)):
            result = check_remote_repo_exists("u", "r")
        assert result["full_name"] == "u/r"
        assert result["created_at"] == "2026-07-04T10:00:00Z"

    def test_returns_none_on_404(self):
        """A 404 is the good case -- the name is free."""
        with patch("new_repo.subprocess.run",
                   return_value=_completed(1, stderr="gh: Not Found (HTTP 404)")):
            assert check_remote_repo_exists("u", "r") is None

    def test_auth_failure_raises_rather_than_reporting_absent(self):
        """
        The #1805 trap. An error that is NOT a 404 must never be read as
        "repo does not exist" -- that would let the caller scaffold over a
        live repo, which is the whole defect.
        """
        with patch("new_repo.subprocess.run",
                   return_value=_completed(1, stderr="gh: Bad credentials (HTTP 401)")):
            with pytest.raises(RuntimeError, match="401"):
                check_remote_repo_exists("u", "r")

    def test_missing_gh_cli_raises(self):
        with patch("new_repo.subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError, match="gh"):
                check_remote_repo_exists("u", "r")

    def test_timeout_raises(self):
        with patch("new_repo.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("gh", 30)):
            with pytest.raises(RuntimeError, match="timed out"):
                check_remote_repo_exists("u", "r")

    def test_unparseable_response_raises(self):
        with patch("new_repo.subprocess.run", return_value=_completed(0, "<html>")):
            with pytest.raises(RuntimeError, match="unparseable"):
                check_remote_repo_exists("u", "r")

    def test_query_does_not_inherit_stdin(self):
        with patch("new_repo.subprocess.run", return_value=_completed(0, "{}")) as run:
            check_remote_repo_exists("u", "r")
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL


# ===========================================================================
# #1805 — the refusal, which must precede any local write
# ===========================================================================


class TestCreateRepoRemotePreflight:

    def _args(self, name="brandnew", no_github=False):
        args = MagicMock()
        args.name = name
        args.no_github = no_github
        return args

    def test_refuses_and_writes_nothing_when_repo_exists(self, tmp_path, capsys):
        target = tmp_path / "brandnew"
        existing = {
            "full_name": "u/brandnew",
            "html_url": "https://github.com/u/brandnew",
            "created_at": "2026-07-04T10:00:00Z",
            "private": True,
        }
        with patch("new_repo.check_remote_repo_exists", return_value=existing):
            with pytest.raises(SystemExit) as exc:
                _create_repo(target, self._args(), "u")

        assert exc.value.code == 1
        assert not target.exists(), "no scaffold directory may be created"
        out = capsys.readouterr().out
        assert "already exists" in out
        assert "2026-07-04" in out, "operator needs the creation date to recognize the repo"
        assert "gh repo clone u/brandnew" in out, "refusal must name the safe alternative"

    def test_refuses_when_existence_cannot_be_determined(self, tmp_path, capsys):
        """Unknown is not absent. Refuse rather than scaffold on an unverified name."""
        target = tmp_path / "brandnew"
        with patch("new_repo.check_remote_repo_exists",
                   side_effect=RuntimeError("Bad credentials")):
            with pytest.raises(SystemExit) as exc:
                _create_repo(target, self._args(), "u")

        assert exc.value.code == 1
        assert not target.exists()
        out = capsys.readouterr().out
        assert "Cannot determine" in out
        assert "Bad credentials" in out

    def test_no_github_skips_the_remote_check(self, tmp_path):
        """--no-github never contacts GitHub, so there is nothing to pre-flight."""
        target = tmp_path / "brandnew"
        with patch("new_repo.check_remote_repo_exists") as check:
            # Scaffolding proceeds past the guard and fails later for unrelated
            # reasons (MagicMock args); we assert only that the guard abstained.
            with pytest.raises(BaseException):
                _create_repo(target, self._args(no_github=True), "u")
        check.assert_not_called()


# ===========================================================================
# #1806 — a stray passphrase must land nowhere
# ===========================================================================


class TestDetachStdin:

    def test_detached_stdin_reads_empty_and_never_echoes_input(self, tmp_path):
        """
        End-to-end proof in a real subprocess: fd 0 is what is under test,
        and pytest owns fd 0 in-process.
        """
        script = tmp_path / "probe.py"
        script.write_text(
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "from new_repo import detach_stdin\n"
            "detach_stdin()\n"
            "sys.stdout.write('READ=' + repr(sys.stdin.read()))\n" % str(TOOLS_DIR),
            encoding="utf-8",
        )
        result = subprocess.run(
            [sys.executable, str(script)],
            input="hunter2-not-a-real-passphrase\n",
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert "READ=''" in result.stdout, "detached stdin must read as empty"
        assert "hunter2" not in result.stdout, "typed input must never be echoed"

    def test_returns_false_when_there_is_no_real_stdin(self):
        fake = MagicMock()
        fake.fileno.side_effect = ValueError("no fileno")
        with patch("new_repo.sys.stdin", fake):
            assert detach_stdin() is False

    def test_main_detaches_stdin_before_parsing_arguments(self):
        """A guard that runs after the risky work is not a guard."""
        with patch("new_repo.detach_stdin") as detach:
            with patch("new_repo.argparse.ArgumentParser.parse_args",
                       side_effect=SystemExit(2)) as parse:
                with pytest.raises(SystemExit):
                    main()
        assert detach.call_count == 1, "main() must detach stdin exactly once"
        assert parse.called


class TestSubprocessStdinIsolation:
    """No child may inherit a terminal that a passphrase could land in."""

    def test_run_command_passes_devnull(self):
        completed = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="", stderr=""
        )
        with patch("new_repo.subprocess.run", return_value=completed) as run:
            run_command(["git", "status"])
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_get_github_username_passes_devnull(self):
        completed = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout="octocat\n", stderr=""
        )
        with patch("new_repo.subprocess.run", return_value=completed) as run:
            assert get_github_username() == "octocat"
        assert run.call_args.kwargs["stdin"] is subprocess.DEVNULL

    def test_no_new_repo_code_path_reads_stdin(self):
        """
        Belt and braces: assert the module never reads stdin directly.
        The recon for #1806 found no such path; this keeps it that way.
        """
        source = (TOOLS_DIR / "new_repo.py").read_text(encoding="utf-8")
        assert "input(" not in source.replace("_input(", ""), "new_repo must not call input()"
        assert "sys.stdin.read" not in source
