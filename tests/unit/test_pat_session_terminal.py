"""_pat_session.py when the passphrase prompt is a terminal pinentry (#4179).

On Ubuntu, pinentry-curses draws its box in a terminal. These tests live under
tests/unit/ rather than beside tests/tools/test_pat_session.py because no CI
step collects tests/tools/ (#3453).
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import _pat_session

# A stand-in for gpg, found first on PATH, that fails the way gpg does when
# pinentry-curses has no terminal.
_FAKE_GPG_NO_TERMINAL = (
    "import sys\n"
    "sys.stderr.write('gpg: problem with the agent: Inappropriate ioctl for device\\n')\n"
    "sys.exit(2)\n"
)

_REPORT_REFUSAL = (
    "import sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, %r)\n"
    "from _pat_session import PinentryUnavailable, classic_pat_session\n"
    "try:\n"
    "    with classic_pat_session(Path(sys.argv[1])):\n"
    "        pass\n"
    "except PinentryUnavailable as e:\n"
    "    sys.stdout.write(str(e))\n"
)


@pytest.mark.skipif(sys.platform == "win32", reason="terminal pinentry is the Ubuntu side")
class TestNoPromptAdvice:
    """The refusal says why gpg had nowhere to prompt, and never sends a WSL
    user to Git Bash."""

    def test_a_run_with_no_terminal_is_told_so(self, tmp_path):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        gpg = bin_dir / "gpg"
        gpg.write_text(f"#!{sys.executable}\n{_FAKE_GPG_NO_TERMINAL}", encoding="utf-8")
        gpg.chmod(0o755)
        script = tmp_path / "run.py"
        script.write_text(_REPORT_REFUSAL % str(TOOLS_DIR), encoding="utf-8")
        secret = tmp_path / "classic-pat.gpg"
        secret.write_bytes(b"not a gpg blob")
        env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        env.pop("GPG_TTY", None)

        result = subprocess.run(
            [sys.executable, str(script), str(secret)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60, env=env,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "Inappropriate ioctl" in result.stdout, "the fake gpg must have run"
        assert "This run has no terminal" in result.stdout
        assert "Git Bash" not in result.stdout

    def test_a_named_terminal_is_reported_with_the_pinentry_check(self, monkeypatch):
        monkeypatch.setenv("GPG_TTY", "/dev/pts/7")
        advice = _pat_session._no_prompt_advice()
        assert "/dev/pts/7" in advice
        assert "pinentry-program" in advice
        assert "Git Bash" not in advice


class TestGpgOutputStaysOffTheTerminal:
    """While pinentry-curses draws its box, gpg's own messages must not land
    on the same terminal (requirement 4). This module prints nothing during
    the call, which blocks; gpg's stdout and stderr are captured."""

    @pytest.mark.parametrize("session", [
        _pat_session.classic_pat_session,
        _pat_session.cerberus_pem_session,
        _pat_session.pr_sentinel_app_session,
        lambda path: _pat_session.gpg_secret_session(path, "read-only CI token"),
    ])
    def test_every_decrypt_captures_gpg_output(self, tmp_path, monkeypatch, session):
        secret_file = tmp_path / "secret.gpg"
        secret_file.write_bytes(b"fake gpg blob")
        # mock-ok: subprocess boundary; gpg would raise a real pinentry prompt.
        run_mock = mock.Mock(return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="value", stderr=""))
        monkeypatch.setattr(_pat_session.subprocess, "run", run_mock)

        with session(secret_file):
            pass

        assert run_mock.call_count == 1
        assert run_mock.call_args.kwargs["capture_output"] is True
