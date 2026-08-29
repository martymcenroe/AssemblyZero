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
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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
