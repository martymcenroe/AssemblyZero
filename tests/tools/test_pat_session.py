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
