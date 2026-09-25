"""Post-create hooks for new_repo.py (#3588, ADR-0216 section 8).

A hook is a Python module listed in the operator's hook file. new_repo.py
calls its post_create(owner=, repo=, pat=) in-process, inside the classic-PAT
session, and every failure is reported by path rather than skipped.
"""

import subprocess
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

import _pat_session  # noqa: E402
from new_repo import read_post_create_hooks, run_post_create_hooks  # noqa: E402

FAKE_PAT = "ghp_fake_classic_pat_for_testing_only"
FAKE_SECRET = "github_pat_fake_read_only_token_for_testing"


def _hook(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return path


class TestReadPostCreateHooks:
    def test_missing_file_means_no_hooks(self, tmp_path):
        assert read_post_create_hooks(tmp_path / "absent.txt") == []

    def test_comments_and_blank_lines_are_ignored(self, tmp_path):
        listing = tmp_path / "hooks.txt"
        listing.write_text(
            "# a comment\n\n/abs/one.py\n   \n/abs/two.py  # trailing comment\n",
            encoding="utf-8",
        )
        assert read_post_create_hooks(listing) == [Path("/abs/one.py"), Path("/abs/two.py")]


class TestRunPostCreateHooks:
    def test_hook_receives_owner_repo_and_pat_and_its_status_is_returned(self, tmp_path):
        hook = _hook(
            tmp_path, "records",
            "def post_create(*, owner, repo, pat):\n"
            "    return f'OK {owner}/{repo} {len(pat)}'\n",
        )
        results = run_post_create_hooks([hook], "someone", "newrepo", FAKE_PAT)
        assert results == [(hook, f"OK someone/newrepo {len(FAKE_PAT)}")]

    def test_missing_hook_file_fails_by_path(self, tmp_path):
        missing = tmp_path / "gone.py"
        [(path, status)] = run_post_create_hooks([missing], "o", "r", FAKE_PAT)
        assert path == missing
        assert status.startswith("FAILED") and "not found" in status

    def test_module_without_post_create_fails(self, tmp_path):
        hook = _hook(tmp_path, "empty", "X = 1\n")
        [(_, status)] = run_post_create_hooks([hook], "o", "r", FAKE_PAT)
        assert status == "FAILED: no post_create function"

    def test_hook_exception_fails_and_later_hooks_still_run(self, tmp_path):
        bad = _hook(
            tmp_path, "bad",
            "def post_create(*, owner, repo, pat):\n    raise ValueError('boom')\n",
        )
        good = _hook(
            tmp_path, "good",
            "def post_create(*, owner, repo, pat):\n    return 'OK'\n",
        )
        results = run_post_create_hooks([bad, good], "o", "r", FAKE_PAT)
        assert results[0] == (bad, "FAILED: ValueError: boom")
        assert results[1] == (good, "OK")

    def test_failure_status_never_carries_the_pat(self, tmp_path):
        bad = _hook(
            tmp_path, "leaky",
            "def post_create(*, owner, repo, pat):\n    raise RuntimeError('no')\n",
        )
        [(_, status)] = run_post_create_hooks([bad], "o", "r", FAKE_PAT)
        assert FAKE_PAT not in status


class TestGpgSecretSession:
    def test_yields_value_and_announces_the_callers_name(self, tmp_path, monkeypatch, capsys):
        blob = tmp_path / "token.gpg"
        blob.write_bytes(b"fake gpg blob")
        monkeypatch.setattr(
            _pat_session.subprocess, "run",
            mock.Mock(return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout=FAKE_SECRET + "\n", stderr="")),
        )
        with _pat_session.gpg_secret_session(blob, "read-only CI token", reason="test") as value:
            assert value == FAKE_SECRET
        err = capsys.readouterr().err
        assert "read-only CI token" in err
        assert FAKE_SECRET not in err

    def test_missing_file_names_the_secret_and_path(self, tmp_path):
        missing = tmp_path / "absent.gpg"
        try:
            with _pat_session.gpg_secret_session(missing, "read-only CI token"):
                raise AssertionError("must not yield")
        except FileNotFoundError as e:
            assert "read-only CI token" in str(e) and str(missing) in str(e)
