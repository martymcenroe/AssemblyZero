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


def _run_main(tmp_path: Path, hook_list: Path, name: str, hook_runner: mock.Mock | None,
              sentinel_bundle: Path | None = None, real_pat_session: bool = False) -> int:
    """Run new_repo.main() through the GitHub path, reading its hook list from
    `hook_list` and running hooks through `hook_runner`. Returns the exit code.

    Every GitHub boundary is replaced, as in test_cerberus_after_auto_review,
    and the home is a tmp directory. With a runner (a mock), no listed hook's
    post_create ever runs, whichever list the run reads; with None, the real
    runner calls each hook (#4786).

    The classic PAT's file is a placeholder in that home, never the real one
    (#4786). The session is faked unless `real_pat_session`; a test that runs
    the real one fakes _pat_session's prompt and gpg itself.

    With no `sentinel_bundle` the pr-sentinel check is faked as a pass, and its
    key file is a placeholder in that home. With one, the real check runs
    against that key file (#4785); a test that lets it reach gpg fakes
    _pat_session's subprocess boundary itself.
    """
    home = tmp_path / "home"
    secrets = home / ".secrets"
    secrets.mkdir(parents=True, exist_ok=True)
    pat_file = secrets / "classic-pat.gpg"
    pat_file.write_bytes(b"placeholder, never decrypted for real")
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
        mock.patch("new_repo.DEFAULT_PAT_PATH", pat_file),
        mock.patch.object(new_repo, "requests", fake_requests),
        mock.patch("new_repo._deploy_workflows_via_contents_api", return_value=(True, 0)),
        mock.patch("new_repo.configure_repo_settings", return_value=True),
        mock.patch("new_repo.configure_branch_protection", return_value=True),
        mock.patch("new_repo.create_canonical_labels", return_value=(2, 2)),
        mock.patch("new_repo.enable_dependabot_for_repo",
                   return_value=SimpleNamespace(actions={}, ok=True)),
        mock.patch("new_repo.DEFAULT_POST_CREATE_HOOKS", hook_list),
        mock.patch("new_repo.verify_branch_protection_on_origin", return_value=(True, "ok")),
        mock.patch("new_repo.verify_repo_settings_on_origin", return_value=(True, "ok")),
        mock.patch("sys.argv", ["new_repo.py", name]),
    ]
    if not real_pat_session:
        patches.append(mock.patch("new_repo.classic_pat_session", _fake_pat_session))
    if hook_runner is not None:
        patches.append(mock.patch("new_repo.run_post_create_hooks", hook_runner))
    if sentinel_bundle is None:
        placeholder = secrets / "pr-sentinel-app.gpg"
        placeholder.write_bytes(b"placeholder, never decrypted")
        patches.append(mock.patch("new_repo.DEFAULT_PR_SENTINEL_APP_GPG", placeholder))
        patches.append(mock.patch(
            "new_repo.run_pr_sentinel_check",
            return_value=("pass", "App installation covers this repo (faked in a test)"),
        ))
    else:
        patches.append(mock.patch("new_repo.DEFAULT_PR_SENTINEL_APP_GPG", sentinel_bundle))
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
        it reports missing or empty is the list it read. Since #4786 the run
        loads the listed hooks before its first prompt and hands the stage
        those loaded hooks."""
        listing = tmp_path / "hooks.txt"
        hook = _hook(tmp_path, "deploy", "def post_create(*, owner, repo, pat):\n    return 'OK'\n")
        listing.write_text(f"{hook}\n", encoding="utf-8")
        runner = mock.Mock(return_value=[(hook, "OK")])
        code = _run_main(tmp_path, listing, "OneHook", runner)
        out, err = capsys.readouterr()

        assert code == 0, out[-2000:] + err[-2000:]
        runner.assert_called_once()
        [loaded], owner, repo, pat = runner.call_args.args
        assert (loaded.path, loaded.error, owner, repo, pat) == (hook, None, "owner", "OneHook", FAKE_PAT)
        assert callable(loaded.module.post_create)
        assert (f"  Not counted: the hook {hook} declares no passphrases; "
                "it may still ask\n") in out
        assert f"  {hook}: OK" in out
        assert "[SUCCESS] Repository 'OneHook' created!" in out
        assert operator_alerts == []


# ---------------------------------------------------------------------------
# #4785: the pr-sentinel check in a GitHub run, driven through main()
# ---------------------------------------------------------------------------


def _empty_hook_list(tmp_path: Path) -> Path:
    listing = tmp_path / "hooks.txt"
    listing.write_text("", encoding="utf-8")
    return listing


def _agent_cancels(cmd, *args, **kwargs):
    """gpg-agent's answer when the operator presses Cancel in the box."""
    assert cmd == ["gpg-connect-agent"], f"a test reached an unexpected command: {cmd}"
    return subprocess.CompletedProcess(
        cmd, 0, stdout="ERR 83886179 Operation cancelled <Pinentry>\n", stderr="",
    )


class TestPrSentinelStage:
    """The run of 2026-11-14 had no key file, printed [SKIP], and then
    "GitHub-side verification: 2/2 checks passed" (#4785)."""

    def test_a_missing_key_file_fails_the_run_and_names_the_file(self, tmp_path, capsys,
                                                                operator_alerts):
        absent = tmp_path / "home" / ".secrets" / "pr-sentinel-app.gpg"
        code = _run_main(tmp_path, _empty_hook_list(tmp_path), "NoSentinelKey",
                         mock.Mock(return_value=[]), sentinel_bundle=absent)
        out, err = capsys.readouterr()

        msg = (f"key file not found: {absent}; create it with "
               "tools/store_pr_sentinel_app_key.py. The check did not run")
        assert code == 1, out[-2000:] + err[-2000:]
        assert f"  [FAIL] pr-sentinel-mm Worker: {msg}\n" in out
        assert "pinentry will prompt" not in out
        assert "[SKIP]" not in out
        assert "GitHub-side verification: 2/3 checks passed\n" in out
        assert f"  pr-sentinel check:  FAILED: {msg}\n" in out
        assert "[SUCCESS]" not in out + err
        assert "[FAILED] Repository 'NoSentinelKey' is incomplete" in err
        assert f"pr-sentinel check ({msg})" in err
        assert len(operator_alerts) == 1
        assert not absent.exists(), "the run must not create the key file it lacked"

    def test_a_cancelled_prompt_is_declined_and_named_on_the_count_line(self, tmp_path,
                                                                       capsys,
                                                                       operator_alerts):
        bundle = tmp_path / "pr-sentinel-app.gpg"
        bundle.write_bytes(b"not a real bundle")
        pat_session = sys.modules[new_repo.pr_sentinel_app_session.__module__]
        # mock-ok: subprocess boundary of the session module only; git in the
        # scaffold still runs for real. The answer is the agent's on Cancel.
        with mock.patch.object(pat_session, "subprocess", SimpleNamespace(run=_agent_cancels)):
            code = _run_main(tmp_path, _empty_hook_list(tmp_path), "DeclinedSentinel",
                             mock.Mock(return_value=[]), sentinel_bundle=bundle)
        out, err = capsys.readouterr()

        assert code == 0, out[-2000:] + err[-2000:]
        assert ("  pr-sentinel check: pinentry will prompt to decrypt the App "
                "credential (cancel to decline this check).") in out
        assert ("  [DECLINED] pr-sentinel-mm Worker: you cancelled its passphrase "
                "prompt; the check did not run\n") in out
        assert "GitHub-side verification: 2/2 checks passed, 1 declined\n" in out
        assert "  pr-sentinel check:  declined\n" in out
        assert "[SUCCESS] Repository 'DeclinedSentinel' created!" in out
        assert operator_alerts == []

    def test_a_passing_check_is_counted(self, tmp_path, capsys, operator_alerts):
        code = _run_main(tmp_path, _empty_hook_list(tmp_path), "PassingSentinel",
                         mock.Mock(return_value=[]))
        out, err = capsys.readouterr()

        assert code == 0, out[-2000:] + err[-2000:]
        assert ("  [PASS] pr-sentinel-mm Worker: App installation covers this repo "
                "(faked in a test)\n") in out
        assert "GitHub-side verification: 3/3 checks passed\n" in out
        assert "declined" not in out
        assert "  pr-sentinel check:  passed\n" in out
        assert operator_alerts == []


# ---------------------------------------------------------------------------
# #4786: every passphrase the run will ask for, listed before the first
# ---------------------------------------------------------------------------

_ASKING_HOOK = (
    "from pathlib import Path\n"
    "from _pat_session import gpg_secret_session\n"
    "with open({marker!r}, 'a', encoding='utf-8') as f:\n"
    "    f.write('executed\\n')\n"
    "PASSPHRASES = ({secret!r},)\n"
    "def post_create(*, owner, repo, pat):\n"
    "    with gpg_secret_session(Path({token!r}), {secret!r}) as value:\n"
    "        return f'OK {{len(value)}}'\n"
)
SECRET_HOOK = "test CI token"
BUNDLE = "12345\n-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n"


def _asking_hook(tmp_path: Path) -> tuple[Path, Path]:
    token = tmp_path / "token.gpg"
    token.write_bytes(b"placeholder")
    marker = tmp_path / "executions.txt"
    hook = _hook(tmp_path, "asks", _ASKING_HOOK.format(
        marker=str(marker), secret=SECRET_HOOK, token=str(token)))
    return hook, marker


def _run_counting_prompts(tmp_path, monkeypatch, capsys, hooks, name, sentinel):
    """main() with the real PAT session, hook runner and pr-sentinel check.
    Every prompt goes through _pat_session._ask_passphrase, faked here to
    count; gpg is faked to succeed. Returns (code, prompts, out before the
    first prompt, all out)."""
    listing = tmp_path / "hooks.txt"
    listing.write_text("".join(f"{h}\n" for h in hooks), encoding="utf-8")
    pat_session = sys.modules[new_repo.pr_sentinel_app_session.__module__]
    prompts: list[str] = []
    before_first: list[str] = []

    def ask(text, error, secret_name):
        if not prompts:
            before_first.append(capsys.readouterr().out)
        prompts.append(secret_name)
        return b"typed"

    def gpg(path, passphrase):
        out = {"classic-pat.gpg": FAKE_PAT, "pr-sentinel-app.gpg": BUNDLE}.get(path.name, FAKE_SECRET)
        return subprocess.CompletedProcess([], 0, stdout=out, stderr="")

    monkeypatch.setattr(pat_session, "_ask_passphrase", ask)
    monkeypatch.setattr(pat_session, "_run_gpg", gpg)
    monkeypatch.setattr(new_repo._github_app_jwt, "mint_app_jwt", lambda app_id, pem: "fake.jwt")
    monkeypatch.setattr(new_repo, "verify_pr_sentinel_installation",
                        lambda user, repo, jwt: (True, "installed (faked in a test)"))
    code = _run_main(tmp_path, listing, name, None, sentinel_bundle=sentinel,
                     real_pat_session=True)
    rest = capsys.readouterr().out
    return code, prompts, (before_first or [""])[0], (before_first or [""])[0] + rest


def _printed_count(out: str) -> int:
    [line] = [x for x in out.splitlines() if x.startswith("PASSPHRASES THIS RUN WILL ASK FOR: ")]
    return int(line.rsplit(" ", 1)[1])


class TestPassphraseList:
    def test_three_secrets_are_listed_counted_and_asked(self, tmp_path, monkeypatch, capsys,
                                                        operator_alerts):
        hook, marker = _asking_hook(tmp_path)
        bundle = tmp_path / "pr-sentinel-app.gpg"
        bundle.write_bytes(b"placeholder")
        code, prompts, before, out = _run_counting_prompts(
            tmp_path, monkeypatch, capsys, [hook], "ThreeSecrets", bundle)
        pat_file = tmp_path / "home" / ".secrets" / "classic-pat.gpg"

        block = (
            "PASSPHRASES THIS RUN WILL ASK FOR: 3\n" + "=" * 60 + "\n"
            f"  1. GitHub classic PAT (admin scope): file {pat_file}\n"
            f"  2. {SECRET_HOOK}: asked by the hook {hook}\n"
            f"  3. pr-sentinel App credential (App ID + PEM): file {bundle}\n"
            "  A wrong passphrase is asked for again; a step that fails before its "
            "prompt asks for nothing.\n"
        )
        assert block in before, before[-3000:]
        assert "NOT asked" not in out
        assert "Single pinentry prompt" not in out
        assert prompts == [_pat_session.SECRET_CLASSIC_PAT, SECRET_HOOK,
                           _pat_session.SECRET_PR_SENTINEL_APP]
        assert _printed_count(out) == len(prompts)  # AC1
        assert marker.read_text(encoding="utf-8") == "executed\n"
        assert code == 0, out[-3000:]
        assert f"  {hook}: OK {len(FAKE_SECRET)}" in out

    def test_a_missing_key_and_an_unloadable_hook_are_named_with_reasons(
            self, tmp_path, monkeypatch, capsys, operator_alerts):
        hook, marker = _asking_hook(tmp_path)
        broken = _hook(tmp_path, "broken", "import no_such_module_4786\n")
        absent = tmp_path / "home" / ".secrets" / "pr-sentinel-app.gpg"
        code, prompts, before, out = _run_counting_prompts(
            tmp_path, monkeypatch, capsys, [hook, broken], "TwoMissing", absent)

        assert "PASSPHRASES THIS RUN WILL ASK FOR: 2\n" in before
        assert f"  2. {SECRET_HOOK}: asked by the hook {hook}\n" in before
        assert (
            "  Expected and NOT asked: 2\n"
            f"    - the hook {broken} cannot load: ModuleNotFoundError: "
            "No module named 'no_such_module_4786'\n"
            f"    - pr-sentinel App credential (App ID + PEM): its file {absent} is "
            "missing; create it with tools/store_pr_sentinel_app_key.py\n"
        ) in before
        assert prompts == [_pat_session.SECRET_CLASSIC_PAT, SECRET_HOOK]
        assert _printed_count(out) == len(prompts)  # AC1
        assert marker.read_text(encoding="utf-8") == "executed\n"
        assert code == 1
        assert f"  {broken}: FAILED: ModuleNotFoundError" in out

    def test_a_hook_without_passphrases_is_listed_as_declaring_none(self, tmp_path):
        hook = _hook(tmp_path, "quiet", "def post_create(*, owner, repo, pat):\n    return 'OK'\n")
        [loaded] = new_repo.load_post_create_hooks([hook])
        assert loaded.passphrases is None and loaded.error is None
        asked, _, uncounted = new_repo.passphrase_plan(
            hook, tmp_path / "hooks.txt", [loaded], tmp_path / "absent.gpg")
        assert len(asked) == 1
        assert uncounted == [f"the hook {hook} declares no passphrases; it may still ask"]

    @pytest.mark.parametrize("declared, error", [
        ("'token'", "PASSPHRASES must be a tuple of non-empty strings, not a str"),
        ("('',)", "PASSPHRASES must be a tuple of non-empty strings; item 0 is empty"),
        ("('ok', 3)", "PASSPHRASES must be a tuple of non-empty strings; item 1 is a int"),
    ], ids=["str", "empty", "int"])
    def test_a_malformed_passphrases_is_a_load_error_naming_the_hook(self, tmp_path, declared,
                                                                    error):
        hook = _hook(tmp_path, "malformed",
                     f"PASSPHRASES = {declared}\n"
                     "def post_create(*, owner, repo, pat):\n    raise AssertionError('ran')\n")
        [loaded] = new_repo.load_post_create_hooks([hook])
        assert (loaded.module, loaded.error) == (None, error)
        block = new_repo.passphrase_block(hook, tmp_path / "h.txt", [loaded], tmp_path / "a.gpg")
        assert f"    - the hook {hook} cannot load: {error}\n" in block
        assert new_repo.run_post_create_hooks([loaded], "o", "r", FAKE_PAT) == [
            (hook, f"FAILED: {error}")]

    def test_a_hook_module_executes_once_when_loaded_then_run(self, tmp_path, monkeypatch):
        hook, marker = _asking_hook(tmp_path)
        pat_session = sys.modules[new_repo.pr_sentinel_app_session.__module__]
        monkeypatch.setattr(pat_session, "_ask_passphrase", lambda text, error, name: b"typed")
        monkeypatch.setattr(pat_session, "_run_gpg", lambda path, passphrase:
                            subprocess.CompletedProcess([], 0, stdout=FAKE_SECRET, stderr=""))
        loaded = new_repo.load_post_create_hooks([hook])
        assert new_repo.run_post_create_hooks(loaded, "o", "r", FAKE_PAT) == [
            (hook, f"OK {len(FAKE_SECRET)}")]
        assert marker.read_text(encoding="utf-8") == "executed\n"

    def test_a_missing_classic_pat_file_means_nothing_is_asked(self, tmp_path):
        absent = tmp_path / "classic-pat.gpg"
        bundle = tmp_path / "pr-sentinel-app.gpg"
        bundle.write_bytes(b"placeholder")
        asked, not_asked, _ = new_repo.passphrase_plan(absent, tmp_path / "h.txt", [], bundle)
        assert asked == []
        assert not_asked[0] == (f"GitHub classic PAT (admin scope): its file {absent} is "
                                "missing, so no GitHub step runs")
        assert not_asked[1].endswith("(not reached)")
