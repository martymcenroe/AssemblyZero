"""A process tree that cannot be killed is a failure, not "already dead" (ADR 0236, #3585).

``kill_process_tree`` ends a timed-out model call and every process it spawned,
so the drain that follows does not block on a grandchild holding the pipes (the
#1874 hang). It never checked ``taskkill``'s exit code, and it swallowed every
``OSError`` and a ``taskkill`` timeout as "already dead", so a tree that
survived the kill was reported as killed. Now only a process that is really
gone is quiet: ``ProcessLookupError`` off Windows, and ``taskkill``'s "not
found" exit (128) on Windows. Everything else logs an ERROR line and raises
``ProcessTreeKillError`` naming the pid and the cause.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import errno
import os
import subprocess
import sys

import pytest

from assemblyzero.utils import process


def _kill_error():
    # Looked up per test, so the kept-behaviour tests run against a module that
    # predates the exception.
    return process.ProcessTreeKillError


class _Ran:
    def __init__(self, returncode: int, stderr: bytes = b""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = b""


def _on_windows(monkeypatch, outcome):
    monkeypatch.setattr(sys, "platform", "win32")

    def _run(cmd, **_kwargs):
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(subprocess, "run", _run)


def test_33_a_taskkill_that_fails_raises_with_its_stderr(monkeypatch, capsys, operator_alerts):
    _on_windows(monkeypatch, _Ran(1, b"ERROR: Access is denied."))

    with pytest.raises(_kill_error()) as excinfo:
        process.kill_process_tree(4242)

    assert "4242" in str(excinfo.value)
    assert "Access is denied" in str(excinfo.value)
    assert "ERROR" in capsys.readouterr().err


def test_33_a_taskkill_that_finds_no_process_is_quiet(monkeypatch, capsys, operator_alerts):
    _on_windows(monkeypatch, _Ran(128, b'ERROR: The process "4242" not found.'))

    process.kill_process_tree(4242)

    assert capsys.readouterr().err == ""


def test_33_a_taskkill_that_succeeds_is_quiet(monkeypatch, capsys, operator_alerts):
    _on_windows(monkeypatch, _Ran(0))

    process.kill_process_tree(4242)

    assert capsys.readouterr().err == ""


def test_41_a_taskkill_that_times_out_raises(monkeypatch, capsys, operator_alerts):
    _on_windows(monkeypatch, subprocess.TimeoutExpired(["taskkill"], 10))

    with pytest.raises(_kill_error()):
        process.kill_process_tree(4242)

    assert "ERROR" in capsys.readouterr().err


def test_41_a_kill_the_os_refuses_raises(monkeypatch, capsys, operator_alerts):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os, "getpgid", lambda pid: 777)

    def _refuse(pgid, sig):
        raise PermissionError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(os, "killpg", _refuse)

    with pytest.raises(_kill_error()) as excinfo:
        process.kill_process_tree(4242)

    assert "PermissionError" in str(excinfo.value)
    assert "ERROR" in capsys.readouterr().err


def test_41_a_process_that_is_already_gone_is_quiet(monkeypatch, capsys, operator_alerts):
    monkeypatch.setattr(sys, "platform", "linux")

    def _gone(pid):
        raise ProcessLookupError(errno.ESRCH, "No such process")

    monkeypatch.setattr(os, "getpgid", _gone)

    process.kill_process_tree(4242)

    assert capsys.readouterr().err == ""
