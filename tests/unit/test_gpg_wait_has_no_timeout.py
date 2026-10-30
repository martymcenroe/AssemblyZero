"""The operator's passphrase wait has no time limit (#4204).

gpg waits inside pinentry for the operator. A 180-second timeout killed a
new_repo.py run under him at the classic-PAT prompt on 2026-10-22, after the
local scaffold and before the GitHub repository existed. A prompt that never
reaches him already fails at once (PinentryUnavailable, #4135).
"""

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import _pat_session  # noqa: E402
import verify_encrypted_secret  # noqa: E402


def _fake_gpg():
    # mock-ok: subprocess boundary; gpg would raise a real pinentry prompt.
    return mock.Mock(return_value=subprocess.CompletedProcess(
        args=[], returncode=0, stdout="value", stderr=""))


@pytest.mark.parametrize("session", [
    _pat_session.classic_pat_session,
    _pat_session.cerberus_pem_session,
    _pat_session.pr_sentinel_app_session,
    lambda path: _pat_session.gpg_secret_session(path, "read-only CI token"),
])
def test_t1_every_session_waits_for_the_passphrase_without_a_limit(tmp_path, monkeypatch, session):
    secret_file = tmp_path / "secret.gpg"
    secret_file.write_bytes(b"fake gpg blob")
    run_mock = _fake_gpg()
    monkeypatch.setattr(_pat_session.subprocess, "run", run_mock)

    with session(secret_file):
        pass

    assert run_mock.call_count == 1
    assert run_mock.call_args.kwargs["timeout"] is None


def test_t2_verify_encrypted_secret_waits_without_a_limit(tmp_path, monkeypatch):
    secret_file = tmp_path / "secret.gpg"
    secret_file.write_bytes(b"fake gpg blob")
    run_mock = _fake_gpg()
    monkeypatch.setattr(verify_encrypted_secret.subprocess, "run", run_mock)

    assert verify_encrypted_secret._decrypt(secret_file) == "value"
    assert run_mock.call_args.kwargs["timeout"] is None
