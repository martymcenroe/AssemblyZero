"""Unit tests for tools/_pat_session.py.

Issue #959. The PAT must:
  1. Be yielded only inside the with-block.
  2. Never appear in os.environ at any point.
  3. Surface a helpful error when the encrypted file is missing.
  4. Surface gpg's stderr verbatim when decryption fails.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import _pat_session  # noqa: E402

FAKE_PAT = "ghp_fake_classic_pat_for_testing_only"


def _make_completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestClassicPatSession:
    def test_yields_decrypted_pat(self, tmp_path, monkeypatch):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")

        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stdout=FAKE_PAT + "\n")),
        )

        with _pat_session.classic_pat_session(pat_file) as pat:
            assert pat == FAKE_PAT

    def test_strips_trailing_newline(self, tmp_path, monkeypatch):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")

        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stdout="  " + FAKE_PAT + "  \n\n")),
        )

        with _pat_session.classic_pat_session(pat_file) as pat:
            assert pat == FAKE_PAT
            assert "\n" not in pat

    def test_invokes_gpg_decrypt_with_path(self, tmp_path, monkeypatch):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")

        run_mock = mock.Mock(return_value=_make_completed_process(stdout=FAKE_PAT))
        monkeypatch.setattr(_pat_session.subprocess, "run", run_mock)

        with _pat_session.classic_pat_session(pat_file):
            pass

        cmd = run_mock.call_args.args[0]
        assert cmd[0] == "gpg"
        assert "--quiet" in cmd
        assert "--decrypt" in cmd
        assert str(pat_file) in cmd

    def test_missing_file_raises_with_setup_hint(self, tmp_path):
        missing = tmp_path / "does_not_exist.gpg"
        with pytest.raises(FileNotFoundError) as excinfo:
            with _pat_session.classic_pat_session(missing):
                pass
        msg = str(excinfo.value)
        assert "One-time setup" in msg, "error must guide user to create the file"
        assert str(missing) in msg

    def test_setup_hint_uses_clipboard_not_echo(self, tmp_path):
        """Issue #968: hint must NOT suggest `echo '<pat>' | gpg ...` —
        that pattern puts the secret in shell history and process argv."""
        missing = tmp_path / "does_not_exist.gpg"
        with pytest.raises(FileNotFoundError) as excinfo:
            with _pat_session.classic_pat_session(missing):
                pass
        msg = str(excinfo.value)
        assert "echo '<classic-pat>'" not in msg, (
            "must not suggest the echo pattern — it leaks via shell history + argv"
        )
        assert "/dev/clipboard" in msg or "pbpaste" in msg or "xclip" in msg, (
            "must suggest a clipboard-pipe pattern instead"
        )

    def test_gpg_failure_raises_runtimeerror_with_stderr(self, tmp_path, monkeypatch):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")

        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(
                stderr="gpg: decryption failed: Bad session key\n",
                returncode=2,
            )),
        )

        with pytest.raises(RuntimeError) as excinfo:
            with _pat_session.classic_pat_session(pat_file):
                pass
        msg = str(excinfo.value)
        assert "gpg decrypt failed" in msg
        assert "Bad session key" in msg, "must surface gpg stderr so user can diagnose"

    def test_pat_not_in_environ_during_block(self, tmp_path, monkeypatch):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")

        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stdout=FAKE_PAT)),
        )

        with _pat_session.classic_pat_session(pat_file) as pat:
            for env_value in os.environ.values():
                assert pat not in env_value, (
                    "the PAT must never leak into os.environ — "
                    "the whole point of this module"
                )

    def test_pat_not_in_environ_after_block(self, tmp_path, monkeypatch):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")

        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stdout=FAKE_PAT)),
        )

        with _pat_session.classic_pat_session(pat_file):
            pass

        for env_value in os.environ.values():
            assert FAKE_PAT not in env_value

    def test_default_path_is_secrets_dir(self):
        assert _pat_session.DEFAULT_PAT_PATH.name == "classic-pat.gpg"
        assert _pat_session.DEFAULT_PAT_PATH.parent.name == ".secrets"


class TestDecryptAnnouncement:
    """Issue #1853. The operator holds several distinct passphrases and
    pinentry's dialog names neither the secret nor the operation, so each
    decrypt must announce itself on the console FIRST."""

    def test_announce_names_secret_path_and_reason(self, capsys):
        _pat_session._announce_decrypt(
            _pat_session.SECRET_CLASSIC_PAT,
            Path("/x/classic-pat.gpg"),
            "land Seshat CI workflow",
            1,
            5,
        )
        err = capsys.readouterr().err
        assert _pat_session.SECRET_CLASSIC_PAT in err
        assert "classic-pat.gpg" in err
        assert "land Seshat CI workflow" in err
        assert "1 of 5" in err

    def test_announce_omits_reason_line_when_unstated(self, capsys):
        _pat_session._announce_decrypt(
            _pat_session.SECRET_CLASSIC_PAT, Path("/x/a.gpg"), None, 1, 5
        )
        assert "used for" not in capsys.readouterr().err

    def test_announce_is_ascii_only(self, capsys):
        """Prints into Git Bash, cmd, and Windows Terminal — box-drawing
        characters do not survive all three."""
        _pat_session._announce_decrypt(
            _pat_session.SECRET_CERBERUS_PEM, Path("/x/a.gpg"), "rotate", 2, 5
        )
        capsys.readouterr().err.encode("ascii")  # raises if non-ASCII

    def test_announce_goes_to_stderr_not_stdout(self, capsys):
        _pat_session._announce_decrypt(
            _pat_session.SECRET_CLASSIC_PAT, Path("/x/a.gpg"), "r", 1, 5
        )
        captured = capsys.readouterr()
        assert captured.out == "", "banner must not pollute stdout — callers pipe it"
        assert _pat_session.SECRET_CLASSIC_PAT in captured.err

    def test_announce_happens_before_gpg_runs(self, tmp_path, monkeypatch):
        """The whole point: the operator must know which passphrase is wanted
        BEFORE pinentry appears, not after."""
        order: list[str] = []
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")

        monkeypatch.setattr(
            _pat_session,
            "_announce_decrypt",
            lambda *a, **k: order.append("announce"),
        )
        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            lambda *a, **k: (
                order.append("gpg"),
                _make_completed_process(stdout=FAKE_PAT),
            )[1],
        )

        with _pat_session.classic_pat_session(pat_file):
            pass

        assert order == ["announce", "gpg"]

    def test_banner_never_contains_the_secret(self, tmp_path, monkeypatch, capsys):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")
        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stdout=FAKE_PAT)),
        )

        with _pat_session.classic_pat_session(pat_file, reason="a run"):
            pass

        captured = capsys.readouterr()
        assert FAKE_PAT not in captured.err
        assert FAKE_PAT not in captured.out

    def test_retry_announces_each_attempt_with_counter(self, tmp_path, monkeypatch, capsys):
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")
        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stderr="bad passphrase", returncode=2)),
        )

        with pytest.raises(RuntimeError):
            with _pat_session.classic_pat_session(pat_file):
                pass

        err = capsys.readouterr().err
        for n in range(1, _pat_session.MAX_GPG_ATTEMPTS + 1):
            assert f"{n} of {_pat_session.MAX_GPG_ATTEMPTS}" in err

    def test_each_session_names_its_own_secret(self, tmp_path, monkeypatch, capsys):
        """A shared banner that always said 'PAT' would defeat the purpose."""
        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stdout="payload")),
        )
        cases = [
            (_pat_session.cerberus_pem_session, "cerberus-pem.gpg", _pat_session.SECRET_CERBERUS_PEM),
            (_pat_session.pr_sentinel_app_session, "pr-sentinel-app.gpg", _pat_session.SECRET_PR_SENTINEL_APP),
        ]
        for fn, filename, expected in cases:
            f = tmp_path / filename
            f.write_bytes(b"fake gpg blob")
            with fn(f):
                pass
            err = capsys.readouterr().err
            assert expected in err
            assert _pat_session.SECRET_CLASSIC_PAT not in err

    def test_reason_is_backward_compatible_keyword(self, tmp_path, monkeypatch):
        """Existing callers pass only the path positionally; adding `reason`
        must not break them."""
        monkeypatch.setattr(
            _pat_session.subprocess,
            "run",
            mock.Mock(return_value=_make_completed_process(stdout=FAKE_PAT)),
        )
        pat_file = tmp_path / "classic-pat.gpg"
        pat_file.write_bytes(b"fake gpg blob")
        with _pat_session.classic_pat_session(pat_file) as pat:
            assert pat == FAKE_PAT
