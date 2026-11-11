"""The passphrase box names the secret it wants (#4701).

gpg's own pinentry box for a passphrase-only file says only "Please enter the
passphrase for decryption." So every session in _pat_session.py asks
gpg-agent for the passphrase itself (GET_PASSPHRASE), with a box text naming
the secret and its file, and hands it to gpg on a pipe with
`--pinentry-mode loopback --passphrase-fd`. The mechanism is copied from a
working prompt in a private tool.

The real-gpg tests encrypt a throwaway file in the test's own GNUPGHOME with
a dummy passphrase. No test reads, touches or decrypts anything under
~/.secrets.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import _pat_session

DUMMY_PASSPHRASE = "dummy passphrase 4701, tests only"
WRONG_PASSPHRASE = "not the dummy passphrase"
DUMMY_VALUE = "dummy-secret-value-4701"

# Each session, the file name it is opened on here, and the name its box
# must show.
SESSIONS = [
    pytest.param(_pat_session.classic_pat_session, "classic-pat.gpg",
                 _pat_session.SECRET_CLASSIC_PAT, id="classic_pat"),
    pytest.param(_pat_session.cerberus_pem_session, "cerberus-pem.gpg",
                 _pat_session.SECRET_CERBERUS_PEM, id="cerberus_pem"),
    pytest.param(_pat_session.pr_sentinel_app_session, "pr-sentinel-app.gpg",
                 _pat_session.SECRET_PR_SENTINEL_APP, id="pr_sentinel_app"),
    pytest.param(lambda path: _pat_session.gpg_secret_session(path, "read-only CI token"),
                 "token.gpg", "read-only CI token", id="gpg_secret"),
]

requires_real_gpg = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("gpg") is None,
    reason="needs gpg, and a stand-in pinentry and gpg home, which are POSIX here",
)


def _completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _agent_ok(passphrase: str = "typed"):
    """gpg-agent's answer to GET_PASSPHRASE: the passphrase in hex."""
    return _completed(stdout=f"OK {passphrase.encode('utf-8').hex()}\n")


class _Box:
    """Stands in for the operator at the box: records each box's text and
    error line, types the next answer."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.asked: list[tuple[str, str | None]] = []

    def __call__(self, text, error, secret_name):
        self.asked.append((text, error))
        return self.answers.pop(0).encode("utf-8")


# ---------------------------------------------------------------------------
# The box text
# ---------------------------------------------------------------------------

class TestBoxText:

    def test_classic_pat_box_says_classic_pat_and_its_file(self):
        """The exact words in his box for the classic PAT. Built from the
        default path; the file itself is never opened."""
        text = _pat_session._box_text(
            _pat_session.SECRET_CLASSIC_PAT, _pat_session.DEFAULT_PAT_PATH, None)
        assert "classic PAT" in text
        assert str(_pat_session.DEFAULT_PAT_PATH) in text
        assert text == (
            "GitHub classic PAT (admin scope)\n\n"
            f"The passphrase for the file {_pat_session.DEFAULT_PAT_PATH}."
        )

    def test_the_reason_follows_the_name_and_file(self):
        text = _pat_session._box_text("read-only CI token", Path("/x/token.gpg"), "deploy it.")
        assert text.endswith("\n\nFor: deploy it.")

    @pytest.mark.parametrize("session, filename, name", SESSIONS)
    def test_every_session_asks_the_agent_with_its_name_and_file(
            self, tmp_path, monkeypatch, session, filename, name):
        secret_file = tmp_path / filename
        secret_file.write_bytes(b"fake gpg blob")
        # mock-ok: subprocess boundary; a real agent would open a real box.
        run_mock = mock.Mock(side_effect=[_agent_ok(), _completed(stdout="value")])
        monkeypatch.setattr(_pat_session.subprocess, "run", run_mock)

        with session(secret_file) as value:
            assert value == "value"

        (agent_cmd,), agent_kwargs = run_mock.call_args_list[0]
        assert agent_cmd == ["gpg-connect-agent"]
        box = _pat_session._box_text(name, secret_file, None)
        assert f"GET_PASSPHRASE X X {_pat_session._assuan('Passphrase:')} " \
               f"{_pat_session._assuan(box)}\n" in agent_kwargs["input"]
        (gpg_cmd,), _ = run_mock.call_args_list[1]
        assert gpg_cmd[:2] == ["gpg", "--batch"]
        assert gpg_cmd[gpg_cmd.index("--pinentry-mode") + 1] == "loopback"
        assert "--passphrase-fd" in gpg_cmd and "--no-symkey-cache" in gpg_cmd
        assert "typed" not in " ".join(gpg_cmd)

    def test_a_retry_box_says_the_passphrase_did_not_open_it(self, tmp_path, monkeypatch):
        secret_file = tmp_path / "classic-pat.gpg"
        secret_file.write_bytes(b"fake gpg blob")
        box = _Box("wrong", "right")
        monkeypatch.setattr(_pat_session, "_ask_passphrase", box)
        # mock-ok: subprocess boundary; gpg's wrong-passphrase failure, then success.
        monkeypatch.setattr(_pat_session.subprocess, "run", mock.Mock(side_effect=[
            _completed(stderr="gpg: decryption failed: Bad session key\n", returncode=2),
            _completed(stdout="value"),
        ]))

        with _pat_session.classic_pat_session(secret_file):
            pass

        (_, first), (text, second) = box.asked
        assert first is None
        assert second == f"That passphrase did not open it (try 1 of {_pat_session.MAX_GPG_ATTEMPTS})."
        assert "classic PAT" in text and str(secret_file) in text

    def test_cancel_in_the_box_stops_before_gpg(self, tmp_path, monkeypatch):
        secret_file = tmp_path / "classic-pat.gpg"
        secret_file.write_bytes(b"fake gpg blob")
        # mock-ok: subprocess boundary; the agent's answer when he presses Cancel.
        run_mock = mock.Mock(return_value=_completed(
            stdout="ERR 83886179 Operation cancelled <Pinentry>\n"))
        monkeypatch.setattr(_pat_session.subprocess, "run", run_mock)

        with pytest.raises(RuntimeError, match="declined"), \
                _pat_session.classic_pat_session(secret_file):
            pass
        assert run_mock.call_count == 1, "gpg must not run after a cancel"


# ---------------------------------------------------------------------------
# The real gpg, in the test's own home
# ---------------------------------------------------------------------------

# A stand-in pinentry. gpg-agent runs it only if gpg itself opens a box; it
# leaves a mark and refuses, so a box gpg opened would show.
_FAKE_PINENTRY = (
    "import sys\n"
    "open(%r, 'a').write('pinentry was called\\n')\n"
    "print('OK stand-in pinentry', flush=True)\n"
    "for line in sys.stdin:\n"
    "    if line.startswith('BYE'):\n"
    "        print('OK', flush=True)\n"
    "        break\n"
    "    print('ERR 83886179 Operation cancelled', flush=True)\n"
)


@pytest.fixture
def pinentry_marker(tmp_path, monkeypatch):
    """A gpg home of the test's own, whose agent's pinentry is the stand-in.

    Yields the file the stand-in marks if it is ever called. Stops the
    test's agent afterwards.
    """
    home = tmp_path / "g"
    home.mkdir(mode=0o700)
    marker = tmp_path / "pinentry-was-called"
    pinentry = tmp_path / "fake-pinentry"
    pinentry.write_text(f"#!{sys.executable}\n{_FAKE_PINENTRY % str(marker)}", encoding="utf-8")
    pinentry.chmod(0o755)
    (home / "gpg-agent.conf").write_text(f"pinentry-program {pinentry}\n", encoding="utf-8")
    monkeypatch.setenv("GNUPGHOME", str(home))
    yield marker
    subprocess.run(
        ["gpgconf", "--kill", "gpg-agent"],
        env={**os.environ, "GNUPGHOME": str(home)},
        capture_output=True, timeout=30, check=False,
    )


def _encrypt(tmp_path: Path, filename: str) -> Path:
    """A throwaway file holding DUMMY_VALUE, encrypted with DUMMY_PASSPHRASE."""
    plain = tmp_path / (filename + ".plain")
    plain.write_text(DUMMY_VALUE + "\n", encoding="utf-8")
    out = tmp_path / filename
    read_fd, write_fd = os.pipe()
    os.write(write_fd, (DUMMY_PASSPHRASE + "\n").encode("utf-8"))
    os.close(write_fd)
    try:
        result = subprocess.run(
            ["gpg", "--batch", "--quiet", "--no-symkey-cache", "--pinentry-mode", "loopback",
             "--passphrase-fd", "0", "--symmetric", "-o", str(out), str(plain)],
            stdin=read_fd, capture_output=True, text=True, timeout=60, check=False,
        )
    finally:
        os.close(read_fd)
    assert result.returncode == 0, result.stderr
    plain.unlink()
    return out


@requires_real_gpg
class TestRealGpg:
    """The box is the stand-in (_Box); gpg is real. It decrypts with what was
    typed, opens no box of its own, and the passphrase stays out of argv,
    the environment, output and errors."""

    @pytest.mark.parametrize("session, filename, name", SESSIONS)
    def test_the_right_passphrase_decrypts_with_no_box_from_gpg(
            self, tmp_path, monkeypatch, pinentry_marker, session, filename, name):
        secret_file = _encrypt(tmp_path, filename)
        box = _Box(DUMMY_PASSPHRASE)
        monkeypatch.setattr(_pat_session, "_ask_passphrase", box)

        with session(secret_file) as value:
            assert value == DUMMY_VALUE

        [(text, _)] = box.asked
        assert name in text and str(secret_file) in text
        assert not pinentry_marker.exists(), "gpg opened a box of its own"

    def test_a_wrong_passphrase_fails_cleanly(self, tmp_path, monkeypatch, pinentry_marker, capsys):
        secret_file = _encrypt(tmp_path, "cerberus-pem.gpg")
        box = _Box(*[WRONG_PASSPHRASE] * _pat_session.MAX_GPG_ATTEMPTS)
        monkeypatch.setattr(_pat_session, "_ask_passphrase", box)

        with pytest.raises(RuntimeError) as excinfo, _pat_session.cerberus_pem_session(secret_file):
            pass

        assert len(box.asked) == _pat_session.MAX_GPG_ATTEMPTS
        assert not isinstance(excinfo.value, _pat_session.PinentryUnavailable)
        assert WRONG_PASSPHRASE not in str(excinfo.value)
        captured = capsys.readouterr()
        assert WRONG_PASSPHRASE not in captured.out + captured.err
        assert not pinentry_marker.exists(), "gpg opened a box of its own"

    def test_the_passphrase_is_never_in_argv_env_output_or_errors(
            self, tmp_path, monkeypatch, pinentry_marker, capsys):
        secret_file = _encrypt(tmp_path, "classic-pat.gpg")
        calls: list[tuple[list[str], dict]] = []
        real_run = subprocess.run

        def spy(cmd, **kwargs):
            calls.append((list(cmd), dict(kwargs)))
            return real_run(cmd, **kwargs)

        monkeypatch.setattr(_pat_session.subprocess, "run", spy)
        monkeypatch.setattr(_pat_session, "_ask_passphrase", _Box(WRONG_PASSPHRASE, DUMMY_PASSPHRASE))

        with _pat_session.classic_pat_session(secret_file) as value:
            assert value == DUMMY_VALUE
            for env_value in os.environ.values():
                assert DUMMY_PASSPHRASE not in env_value
                assert WRONG_PASSPHRASE not in env_value

        assert len(calls) == 2
        for cmd, kwargs in calls:
            joined = "\0".join(cmd)
            assert DUMMY_PASSPHRASE not in joined and WRONG_PASSPHRASE not in joined
            assert "--passphrase-fd" in cmd
            assert "--passphrase" not in cmd and "--passphrase-file" not in cmd
            assert "env" not in kwargs and "input" not in kwargs
        captured = capsys.readouterr()
        for text in (captured.out, captured.err):
            assert DUMMY_PASSPHRASE not in text and WRONG_PASSPHRASE not in text
        assert not pinentry_marker.exists(), "gpg opened a box of its own"
