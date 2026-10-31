"""The AST sentinel raises when it cannot run (ADR 0236, #3585).

The sentinel answers one question about an existing file: does it use a name it
never defines? A file that will not parse, or cannot be read, gets no answer.
Returning that as an undefined-symbol finding let its only caller file it as an
advisory warning ("symbol '<syntax>' may not be imported"), so a check that never
ran read as a check that found something minor. Both now raise
``SentinelCannotRun`` naming the file and the cause.

One test per ledger site, named for the line the ledger gives at ``79e18ad1``.
"""

from __future__ import annotations

import pytest

from assemblyzero.utils import ast_sentinel
from assemblyzero.utils.ast_sentinel import analyze_file, analyze_source


def _cannot_run():
    # Looked up per test, so the kept-behaviour tests still run against a
    # module that predates the exception.
    return ast_sentinel.SentinelCannotRun


def test_472_a_source_that_does_not_parse_raises(operator_alerts):
    with pytest.raises(_cannot_run()) as excinfo:
        analyze_source("if x:\n", filename="pkg/broken.py")

    message = str(excinfo.value)
    assert "pkg/broken.py" in message
    assert "SyntaxError" in message
    assert isinstance(excinfo.value.__cause__, SyntaxError)


def test_472_a_file_that_does_not_parse_raises_naming_the_file(tmp_path, operator_alerts):
    target = tmp_path / "broken.py"
    target.write_text("def f(:\n    pass\n", encoding="utf-8")

    with pytest.raises(_cannot_run()) as excinfo:
        analyze_file(target)

    assert str(target) in str(excinfo.value)


def test_498_a_file_that_cannot_be_read_raises(tmp_path, operator_alerts):
    missing = tmp_path / "absent.py"

    with pytest.raises(_cannot_run()) as excinfo:
        analyze_file(missing)

    assert str(missing) in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, OSError)


def test_498_a_file_that_is_not_utf8_raises(tmp_path, operator_alerts):
    target = tmp_path / "latin.py"
    target.write_bytes(b"x = '\xff\xfe'\n")

    with pytest.raises(_cannot_run()) as excinfo:
        analyze_file(target)

    assert isinstance(excinfo.value.__cause__, UnicodeDecodeError)


def test_an_undefined_name_is_still_a_finding_not_a_raise(tmp_path, operator_alerts):
    """The sentinel's real answer is unchanged: a result with the finding."""
    target = tmp_path / "uses.py"
    target.write_text("def f():\n    return json.dumps({})\n", encoding="utf-8")

    result = analyze_file(target)

    assert not result.ok
    assert [e.name for e in result.errors] == ["json"]


def test_a_clean_file_is_ok(tmp_path, operator_alerts):
    target = tmp_path / "clean.py"
    target.write_text("import json\n\ndef f():\n    return json.dumps({})\n", encoding="utf-8")

    assert analyze_file(target).ok
