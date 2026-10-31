"""One reader of the coverage report, three states (#2637).

The denominator law (#2546/#2552/#2608) had one door left open: a file ABSENT
from the coverage report was rendered as a number. Two consumers read the same
empty report and disagreed, three log lines apart, on boostgauge's
`run-issue331-201554`:

    [N5]  15 passed, 0 failed | Coverage: 0.0%
    [N5]  all 15 test(s) pass; coverage 0.0% < 95% target -- this is a test
          gap, routing to test additions (never to implementation)
    [N4c] coverage report named no uncovered lines; nothing specific to
          target -- returning to verification

Both readings are wrong and they cannot both be right about a measured file:
at a genuine 0% every line is uncovered, so N4c would have had a full target
list. Together they prove the file was never in the report. N5 renders the
absence as a percentage and routes to test additions; N4c renders it as
all-clear and bounces back; the ping-pong ends in a stagnation halt that blames
the LLD and spec -- the two artifacts that had just passed.

## Why the report was empty

`--cov` takes a module name or a directory. Given a path ending in `.py` it
treats the string as a module name, never imports it, and collects nothing:

    --cov=src/pkg/mod.py  -> CoverageWarning: Module ... was never imported
                             CoverageWarning: No data was collected
                             WARNING: Failed to generate report: No data to report

No table is printed at all -- so the percent regex finds nothing and defaults
to 0.0, and the missing-lines parser finds nothing and reports "no uncovered
lines". #2636 fixes the target derivation; this module makes the failure
unmistakable when a target is wrong for any other reason.

## Three states, one accessor

* **measured** -- a TOTAL row exists and the number is real.
* **measured at zero** -- a TOTAL row exists reading 0%, with every line
  uncovered and nameable. A genuine test gap, and it still routes to test
  additions.
* **absent** -- no TOTAL row, or the target file appears nowhere in the table.
  A MEASUREMENT FAILURE, named: what was asked for, and what the report
  actually contained.

Two parsers of one report is the #1698 class, and the N5/N4c contradiction is
the live proof, so both consume this.

## Per-line reports (#4436)

The term-missing table says which lines of a whole file no test reached. The
green phase judges the lines a run changed, so it needs every executable line
of a file and whether it ran: coverage.py's JSON report for pytest, and
Istanbul's `coverage-final.json` for Vitest and Jest (a json-summary carries
totals only). `read_coverage_py_report` and `read_istanbul_report` read them
into one shape, `FileLines`. Each raises `CoverageReportError` naming the path
when the report is missing, does not parse, or is not the shape it should be,
never an empty result: an empty result would read as zero changed lines.
"""

from __future__ import annotations

import json
import os
import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: A `--cov-report=term-missing` data row: `path  Stmts  Miss  Cover  Missing`.
#: `[^\S\n]` is horizontal whitespace, NOT `\s`. `\s` matches newlines, so a
#: `\s`-separated optional Missing column ran past the end of its own row and
#: swallowed the report's `-----` separator as a missing-line range -- a file
#: at 100% then read as having uncovered lines. Rows are line-scoped by
#: construction here, and the Missing column must start with a digit so a
#: separator can never open one.
_ROW_RE = re.compile(
    r"^(?P<path>[^\s|]+\.py)[^\S\n]+(?P<stmts>\d+)[^\S\n]+(?P<miss>\d+)"
    r"[^\S\n]+(?P<cover>\d+)%"
    r"(?:[^\S\n]+(?P<missing>\d[\d,\-\s]*?))?[^\S\n]*$",
    re.MULTILINE,
)

#: The report's footer. Its presence is what separates "measured" from
#: "absent" -- pytest-cov prints no table at all when nothing was collected.
_TOTAL_RE = re.compile(r"^TOTAL\s+\d+\s+\d+\s+(\d+)%", re.MULTILINE)

#: coverage.py's own words when the target named nothing importable. Recorded
#: because they say WHY better than any inference from an empty table.
_NO_DATA_MARKERS = (
    "was never imported",
    "No data was collected",
    "Failed to generate report",
)

MEASURED = "measured"
ABSENT = "absent"


class CoverageReportError(RuntimeError):
    """A run asked to measure coverage whose report cannot be read (#4246).

    Raised, never read as 0%: a percentage no report backs is a measurement
    failure, not a coverage gap. Names the report's path and the cause.
    """


@dataclass(frozen=True)
class FileLines:
    """One file's lines in a per-line coverage report (#4436).

    `hits` holds every line the tool counts as executable, and whether it
    ran. A comment, a blank line, a docstring and a line a project excludes
    are not in it, so they are in no denominator.

    `continuation` is what the tool's own statement spans say about a
    multi-line statement: a later line of it -> the first line, which is the
    line the tool reports. Only Istanbul's report carries this; for Python,
    `changed_lines` reads it from the source.
    """

    hits: dict[int, bool]
    continuation: dict[int, int] = field(default_factory=dict)


def _read_json_report(path: str | Path) -> Any:
    """A JSON coverage report's content, or CoverageReportError naming it."""
    if not os.path.isfile(path):
        raise CoverageReportError(
            f"no coverage report at {path}: the run's tests passed and it "
            f"wrote none"
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise CoverageReportError(
            f"the coverage report at {path} cannot be read: "
            f"{type(e).__name__}: {e}"
        ) from e


def _repo_relative(name: str, repo_root: str | Path, base: str | Path) -> str:
    """A report's file name as a POSIX path relative to the repository.

    coverage.py names a file relative to where it ran, and Istanbul
    absolutely. A file outside the repository keeps its own name, which
    matches nothing the run changed. Resolved, so a worktree reached through
    a link compares equal to the path git reports.
    """
    absolute = os.path.realpath(os.path.join(base, name))
    relative = os.path.relpath(absolute, os.path.realpath(repo_root))
    if relative == ".." or relative.startswith(".." + os.sep):
        return name.replace("\\", "/")
    return relative.replace("\\", "/")


def _is_line_list(value: Any) -> bool:
    return isinstance(value, list) and all(
        isinstance(n, int) and not isinstance(n, bool) for n in value
    )


def read_coverage_py_report(path: str | Path, repo_root: str | Path) -> dict[str, FileLines]:
    """Every file in a coverage.py JSON report, by its repository path (#4436).

    `executed_lines` and `missing_lines` together are the executable lines:
    the tool's own statements, which leave out comments, blank lines,
    docstrings and anything the project excludes. `pytest-cov` writes no
    report at all when no data was collected, so that case is a missing
    report and not an empty one (#2637).
    """
    report = _read_json_report(path)
    files = report.get("files") if isinstance(report, dict) else None
    if not isinstance(files, dict):
        raise CoverageReportError(
            f"the coverage report at {path} carries no `files` table, so no "
            f"line in it can be read"
        )
    lines: dict[str, FileLines] = {}
    for name, entry in files.items():
        executed = entry.get("executed_lines") if isinstance(entry, dict) else None
        missing = entry.get("missing_lines") if isinstance(entry, dict) else None
        if not _is_line_list(executed) or not _is_line_list(missing):
            raise CoverageReportError(
                f"the coverage report at {path} does not list {name}'s "
                f"executed_lines and missing_lines as line numbers"
            )
        hits = {number: True for number in executed}
        hits.update({number: False for number in missing})
        lines[_repo_relative(name, repo_root, repo_root)] = FileLines(hits)
    return lines


def read_istanbul_report(
    path: str | Path, repo_root: str | Path, project_dir: str | Path,
) -> dict[str, FileLines]:
    """Every file in an Istanbul `coverage-final.json`, by its repository
    path (#4436). Vitest and Jest both write this shape.

    A line is executable when a statement starts on it, and it ran when any
    statement starting on it ran: Istanbul's own line coverage
    (`getLineCoverage`), which is what `total.lines.pct` counts. The types
    TypeScript erases are in no statement. A statement a source map could not
    place has no line, so it is passed over, as Istanbul passes it over.

    A statement holding no other statement is a simple one, and its later
    lines go in `continuation`. An `if` holds its body, so its later lines do
    not: a comment inside a block belongs to no statement.
    """
    report = _read_json_report(path)
    if not isinstance(report, dict):
        raise CoverageReportError(
            f"the coverage report at {path} is not a table of files"
        )
    lines: dict[str, FileLines] = {}
    for name, entry in report.items():
        statements = entry.get("statementMap") if isinstance(entry, dict) else None
        counts = entry.get("s") if isinstance(entry, dict) else None
        if not isinstance(statements, dict) or not isinstance(counts, dict):
            raise CoverageReportError(
                f"the coverage report at {path} carries no statementMap and "
                f"counts for {name}"
            )
        hits: dict[int, bool] = {}
        spans: list[tuple[int, int]] = []
        for statement, span in statements.items():
            start = _statement_line(span, "start")
            if start is None:
                continue
            count = counts.get(statement)
            if isinstance(count, bool) or not isinstance(count, int):
                raise CoverageReportError(
                    f"the coverage report at {path} has no count for "
                    f"statement {statement} of {name}"
                )
            hits[start] = hits.get(start, False) or count > 0
            end = _statement_line(span, "end")
            spans.append((start, end if end is not None else start))
        lines[_repo_relative(str(entry.get("path") or name), repo_root, project_dir)] = (
            FileLines(hits, _simple_statement_lines(spans))
        )
    return lines


def _statement_line(span: Any, edge: str) -> int | None:
    location = span.get(edge) if isinstance(span, dict) else None
    line = location.get("line") if isinstance(location, dict) else None
    return line if isinstance(line, int) and not isinstance(line, bool) else None


def _simple_statement_lines(spans: list[tuple[int, int]]) -> dict[int, int]:
    """Each later line of a multi-line statement that holds no other
    statement -> its first line."""
    starts = sorted({start for start, _ in spans})
    continuation: dict[int, int] = {}
    for start, end in spans:
        following = bisect_right(starts, start)
        if end <= start or (following < len(starts) and starts[following] <= end):
            continue
        for line in range(start + 1, end + 1):
            continuation[line] = start
    return continuation


@dataclass(frozen=True)
class CoverageReading:
    """What the coverage report actually says. Never a guess."""

    state: str
    #: None when absent -- deliberately not 0.0, so a caller that forgets to
    #: check `state` gets a TypeError rather than a plausible wrong number.
    percent: float | None
    uncovered: dict[str, list[str]] = field(default_factory=dict)
    files: list[str] = field(default_factory=list)
    target: str = ""
    reasons: list[str] = field(default_factory=list)

    @property
    def measured(self) -> bool:
        return self.state == MEASURED

    @property
    def at_zero(self) -> bool:
        return self.measured and (self.percent or 0.0) <= 0.0

    def failure_message(self) -> str:
        """Why the measurement failed, naming what was sought and what was found.

        Never a percentage and never a test gap: nothing was measured, so
        there is no coverage arithmetic to report and no conclusion to draw
        about the tests or about the LLD and spec.
        """
        sought = f"`{self.target}`" if self.target else "the coverage target"
        if self.files:
            found = f"the report covers: {', '.join(self.files[:8])}"
            if len(self.files) > 8:
                found += f" (and {len(self.files) - 8} more)"
        else:
            found = "the report contains no files at all"
        why = f" coverage said: {'; '.join(self.reasons)}." if self.reasons else ""
        return (
            f"COVERAGE MEASUREMENT FAILED: {sought} does not appear in the "
            f"coverage report, so no percentage exists to judge -- {found}.{why} "
            f"This is a harness/measurement defect, not a test gap and not a "
            f"defect in the LLD or spec."
        )


def read_coverage(output: str, target: str = "") -> CoverageReading:
    """The single reading of a pytest-cov term-missing report (#2637)."""
    text = output or ""
    reasons = [m for m in _NO_DATA_MARKERS if m in text]

    rows = list(_ROW_RE.finditer(text))
    files = [m.group("path").replace("\\", "/") for m in rows]
    total = _TOTAL_RE.search(text)

    if total is None:
        return CoverageReading(
            state=ABSENT, percent=None, files=files, target=target,
            reasons=reasons,
        )

    if target and files and not _target_in(target, files):
        # A table exists, listing files, and ours is not among them: coverage
        # measured something, just not the thing under test.
        #
        # `files` must be non-empty for this branch. A TOTAL row with no
        # parseable data rows means coverage RAN -- an abbreviated or
        # unusually formatted report is not a measurement failure, and calling
        # it one would fail runs whose only sin is a layout this regex does
        # not recognise. Absence is claimed only on positive evidence: no
        # TOTAL at all, or a file list that demonstrably excludes the target.
        return CoverageReading(
            state=ABSENT, percent=None, files=files, target=target,
            reasons=reasons,
        )

    uncovered: dict[str, list[str]] = {}
    for match in rows:
        missing = (match.group("missing") or "").strip()
        if not missing:
            continue
        uncovered[match.group("path").replace("\\", "/")] = [
            part.strip() for part in missing.split(",") if part.strip()
        ]

    return CoverageReading(
        state=MEASURED,
        percent=float(total.group(1)),
        uncovered=uncovered,
        files=files,
        target=target,
        reasons=reasons,
    )


def _target_in(target: str, files: list[str]) -> bool:
    """Does the report contain the file the target names?

    A target is a module (`pkg.mod`), a directory (`tools`) or, before #2636,
    a path (`src/pkg/mod.py`). All three are matched against the report's
    file paths by their dotted-or-slashed stem, so the accessor does not need
    to know which form the caller used.
    """
    normalised = target.replace("\\", "/")
    if normalised.endswith(".py"):
        normalised = normalised[:-3]
    as_path = normalised.replace(".", "/")
    for path in files:
        stem = path[:-3] if path.endswith(".py") else path
        if stem == as_path or stem.endswith("/" + as_path) or as_path in stem:
            return True
    return False
