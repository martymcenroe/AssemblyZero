"""Post-create hooks for new_repo.py (#3588, ADR-0216 section 8).

A hook is a Python module listed in the operator's hook file. new_repo.py
calls its post_create(owner=, repo=, pat=) in-process, inside the classic-PAT
session, and every failure is reported by path rather than skipped.

A run with no hook list on its side fails (#4186): the list exists on one
side only, so a missing file is a run that skipped every hook, never a run
that meant none. An empty list is how a side runs no hooks on purpose.
"""

import contextlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

import _pat_session  # noqa: E402
import new_repo
from new_repo import read_post_create_hooks, run_post_create_hooks  # noqa: E402

FAKE_PAT = "ghp_fake_classic_pat_for_testing_only"
FAKE_SECRET = "github_pat_fake_read_only_token_for_testing"


def _hook(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return path


class TestReadPostCreateHooks:
    def test_missing_file_reads_as_an_empty_list(self, tmp_path):
        """The reader returns no paths; the run, not the reader, reports the
        missing list as a failure (#4186, TestHookListStage)."""
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
        monkeypatch.setattr(_pat_session, "_ask_passphrase", lambda text, error, name: b"typed")
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


# ---------------------------------------------------------------------------
# #4186 Test 1: the hook stage of a GitHub run, driven through main()
# ---------------------------------------------------------------------------


def _git_init_really(cmd, cwd=None, check=True):
    """run_command that really runs `git init` (the scaffold's own checks ask
    real git) and answers everything else as a success."""
    if cmd[:2] == ["git", "init"]:
        subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


@contextlib.contextmanager
def _fake_pat_session(*args, **kwargs):
    yield FAKE_PAT


def _run_main(tmp_path: Path, hook_list: Path, name: str, hook_runner: mock.Mock) -> int:
    """Run new_repo.main() through the GitHub path, reading its hook list from
    `hook_list` and running hooks through `hook_runner`. Returns the exit code.

    Every GitHub boundary is replaced, as in test_cerberus_after_auto_review,
    and the home is a tmp directory. The runner is a mock, so no listed hook
    ever runs, whichever list the run reads.
    """
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    fake_requests = mock.MagicMock()
    for method, status in (("post", 201), ("put", 204), ("get", 200)):
        getattr(fake_requests, method).return_value = SimpleNamespace(
            status_code=status, text="", json=dict,
        )
    patches = [
        mock.patch("new_repo.config"),
        mock.patch("new_repo.run_command", side_effect=_git_init_really),
        mock.patch("new_repo.Path.home", return_value=home),
        mock.patch("new_repo.get_github_username", return_value="owner"),
        mock.patch("new_repo.check_remote_repo_exists", return_value=None),
        mock.patch("new_repo.classic_pat_session", _fake_pat_session),
        mock.patch.object(new_repo, "requests", fake_requests),
        mock.patch("new_repo._deploy_workflows_via_contents_api", return_value=(True, 0)),
        mock.patch("new_repo.configure_repo_settings", return_value=True),
        mock.patch("new_repo.configure_branch_protection", return_value=True),
        mock.patch("new_repo.create_canonical_labels", return_value=(2, 2)),
        mock.patch("new_repo.enable_dependabot_for_repo",
                   return_value=SimpleNamespace(actions={}, ok=True)),
        mock.patch("new_repo.DEFAULT_POST_CREATE_HOOKS", hook_list),
        mock.patch("new_repo.run_post_create_hooks", hook_runner),
        mock.patch("new_repo.verify_branch_protection_on_origin", return_value=(True, "ok")),
        mock.patch("new_repo.verify_repo_settings_on_origin", return_value=(True, "ok")),
        mock.patch("new_repo.run_pr_sentinel_check", return_value=("skip", "not in a test")),
        mock.patch("sys.argv", ["new_repo.py", name]),
    ]
    with contextlib.ExitStack() as stack:
        cfg = stack.enter_context(patches[0])
        for p in patches[1:]:
            stack.enter_context(p)
        cfg.load_error = None
        cfg.new_repo_root.return_value = str(tmp_path)
        cfg.assemblyzero_root.return_value = str(tmp_path / "AssemblyZero")
        try:
            new_repo.main()
        except SystemExit as e:
            return e.code or 0
        return 0


class TestHookListStage:
    """Test 1 (#4186). A run from the side with no hook list used to print
    "None listed", skip every hook and end in [SUCCESS]."""

    def test_a_missing_list_fails_the_run_and_runs_no_hook(self, tmp_path, capsys,
                                                           operator_alerts):
        absent = tmp_path / "home" / ".claude" / "new-repo-post-create-hooks.txt"
        runner = mock.Mock(return_value=[])
        code = _run_main(tmp_path, absent, "NoHookList", runner)
        out, err = capsys.readouterr()

        assert code == 1, out[-2000:] + err[-2000:]
        assert (f"  FAILED: no post-create hook list at {absent}. Create it; "
                "an empty file runs no hooks on purpose (#4186).") in out
        assert "None listed" not in out
        runner.assert_not_called()
        assert "[SUCCESS]" not in out + err
        assert "[FAILED] Repository 'NoHookList' is incomplete" in err
        assert f"post-create hook list (missing: {absent})" in err
        assert len(operator_alerts) == 1
        assert f"post-create hook list (missing: {absent})" in operator_alerts[0]["consequence"]
        assert not absent.exists(), "the run must not create the list it lacked"

    @pytest.mark.parametrize("content", ["", "# no hooks on this side, on purpose\n\n"],
                             ids=["empty", "comments-only"])
    def test_an_empty_list_runs_no_hook_and_is_not_a_failure(self, tmp_path, capsys,
                                                             operator_alerts, content):
        listing = tmp_path / "hooks.txt"
        listing.write_text(content, encoding="utf-8")
        runner = mock.Mock(return_value=[])
        code = _run_main(tmp_path, listing, "EmptyHookList", runner)
        out, err = capsys.readouterr()

        assert code == 0, out[-2000:] + err[-2000:]
        assert f"  None listed in {listing}." in out
        assert "no post-create hook list" not in out + err
        runner.assert_called_once_with([], "owner", "EmptyHookList", FAKE_PAT)
        assert "[SUCCESS] Repository 'EmptyHookList' created!" in out
        assert operator_alerts == []

    def test_the_run_reads_the_list_it_names(self, tmp_path, capsys, operator_alerts):
        """The stage reads DEFAULT_POST_CREATE_HOOKS when it runs, so the list
        it reports missing or empty is the list it read."""
        listing = tmp_path / "hooks.txt"
        hook = tmp_path / "deploy.py"
        listing.write_text(f"{hook}\n", encoding="utf-8")
        runner = mock.Mock(return_value=[(hook, "OK")])
        code = _run_main(tmp_path, listing, "OneHook", runner)
        out, err = capsys.readouterr()

        assert code == 0, out[-2000:] + err[-2000:]
        runner.assert_called_once_with([hook], "owner", "OneHook", FAKE_PAT)
        assert f"  {hook}: OK" in out
        assert "[SUCCESS] Repository 'OneHook' created!" in out
        assert operator_alerts == []
