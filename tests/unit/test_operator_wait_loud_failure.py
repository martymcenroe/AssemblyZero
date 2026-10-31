"""operator_wait.py under standard 0034, one test per sweep site (#3784).

``wants_color`` decides whether a line is painted amber. A closed stream, or
one with no ``isatty``, is not a terminal: that is an answer, and it is quiet.
An ``isatty`` that fails on an open stream raises its own error; it used to
read as "not a terminal", so a broken stream went unnamed. Line numbers in the
names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import inspect
import io

import pytest

from assemblyzero.core import operator_wait


class _BrokenTty:
    closed = False

    def isatty(self) -> bool:
        raise OSError(9, "Bad file descriptor")


class _DetachedTty:
    closed = False

    def isatty(self) -> bool:
        raise ValueError("underlying buffer has been detached")


def test_41_an_isatty_that_fails_on_an_open_stream_raises():
    with pytest.raises(OSError, match="Bad file descriptor"):
        operator_wait.wants_color(_BrokenTty())


def test_41_a_detached_stream_raises():
    with pytest.raises(ValueError, match="detached"):
        operator_wait.paint("hello", stream=_DetachedTty())


def test_a_closed_stream_is_not_a_terminal_and_is_quiet(capsys):
    """Kept: a closed stream is not a terminal. The write meant for it raises
    on its own, so the colour decision has nothing to add."""
    stream = io.StringIO()
    stream.close()

    assert operator_wait.wants_color(stream) is False
    assert capsys.readouterr().err == ""


def test_a_stream_without_isatty_is_not_a_terminal():
    """Kept: no isatty means no terminal."""
    assert operator_wait.paint("hello", stream=object()) == "hello"


def test_42_no_fail_open_tag_remains():
    assert "fail-open" not in inspect.getsource(operator_wait)
