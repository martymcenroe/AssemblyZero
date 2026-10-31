"""utf8_console.py under standard 0034, one test per sweep site (#3800).

``widen`` makes a stream carry any text, trying UTF-8 and then
``errors="replace"``. When a stream refused both it returned False in silence,
and the first character its encoding lacks then killed the report with no word
about why. That is now an ERROR line on stderr and in the log, naming the
stream and both refusals. A stream with no ``reconfigure`` is still left
alone quietly. Line numbers in the names are ledger 0908's, at its base
``79e18ad1``.
"""
from __future__ import annotations

import io

from assemblyzero.core import utf8_console


def _closed_stream() -> io.TextIOWrapper:
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    stream.close()
    return stream


def test_83_a_stream_that_refuses_both_tiers_is_an_error_line(capsys, caplog):
    stream = _closed_stream()

    assert utf8_console.widen(stream) is False

    err = capsys.readouterr().err
    assert "ERROR [CONSOLE]" in err
    assert "TextIOWrapper" in err
    assert err.count("ValueError") == 2, "both refusals are named"
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_a_refused_first_tier_that_falls_back_is_quiet(capsys):
    """Kept: tier 2 is the designed fallback (ledger line 76, compliant)."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    calls: list[dict] = []

    def reconfigure(**kwargs):
        calls.append(kwargs)
        if "encoding" in kwargs:
            raise LookupError("this stream's encoding is fixed")

    stream.reconfigure = reconfigure  # type: ignore[method-assign]

    assert utf8_console.widen(stream) is True
    assert len(calls) == 2
    assert capsys.readouterr().err == ""


def test_a_stream_without_reconfigure_is_left_alone_quietly(capsys):
    """Kept: a StringIO or a capture object is not ours to reach into."""
    assert utf8_console.widen(io.StringIO()) is False
    assert capsys.readouterr().err == ""
