"""context.py under standard 0034 (ADR 0236), the #3585 sweep.

``summarize_file_for_context`` gives the later files of a run a signature
summary of each earlier one. A Python file that does not parse used to be
summarized by its first fifty lines with nothing said. It still is -- the
summary is context, not a gate -- but now with an ERROR line naming the file
and the syntax error. A file that is not Python is summarized by its head as
an answer, quietly. The test name carries ledger 0908's line number at its
base ``79e18ad1``.
"""

from __future__ import annotations

from assemblyzero.workflows.testing.nodes.implementation.context import (
    summarize_file_for_context,
)


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


def test_40_a_python_file_that_does_not_parse_is_an_error_line(capsys):
    summary = summarize_file_for_context("def broken(:\n    pass\n", filepath="src/x.py")

    assert "def broken(:" in summary
    assert _loud(capsys.readouterr().err, "src/x.py", "does not parse")


def test_a_file_that_is_not_python_is_summarized_by_its_head_quietly(capsys):
    """Kept: a TypeScript file is not a Python file that failed to parse."""
    summary = summarize_file_for_context("export const x = 1;\n", filepath="src/x.ts")

    assert "export const x = 1;" in summary
    assert capsys.readouterr().err == ""


def test_a_python_file_that_parses_is_summarized(capsys):
    """Kept: signatures, no error."""
    summary = summarize_file_for_context("def f(a):\n    return a\n")

    assert "def f(a)" in summary
    assert capsys.readouterr().err == ""
