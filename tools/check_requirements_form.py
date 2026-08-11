#!/usr/bin/env python3
"""Check an issue against the ADR 0226 requirement form. Free and instant.

Issue #2219. Fully deterministic: no model calls, no network beyond reading
the issue, and the same answer every time for the same input.

    poetry run python tools/check_requirements_form.py \\
        --repo /c/Users/mcwiz/Projects/boostgauge --issue 7

    poetry run python tools/check_requirements_form.py --file draft.md

It verifies EARS conformance of the bullets under a ``## Requirements``
heading, that a decision table of n binary conditions carries 2^n rows with no
combination repeated, and that every table row appears as its own acceptance
criterion. Acceptance criteria are never EARS-validated -- a row criterion is
a row's projection into the test list, and its terse form is mandated by
ADR 0226 section 3.2.

It cannot report correctness. A table can enumerate every combination and
state the wrong outcome in every row. The report names what it verified and
what it did not, and never lets the weaker row-join mode read as the stronger.

This is the first of the two pre-roll checks. It is free, so it runs first;
tools/check_requirements.py then spends one model call on the semantic gate
(#2221), and only then is it worth rolling.

Exit codes:
    0  the form holds
    1  at least one violation, each named with its location
    2  the check could not run, so nothing was verified
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from assemblyzero.workflows.requirements.form_check import (  # noqa: E402
    check_form,
    render_report,
)
from assemblyzero.workflows.requirements.precheck import (  # noqa: E402
    PrecheckError,
    fetch_issue,
)

EXIT_PASS = 0
EXIT_VIOLATIONS = 1
EXIT_ERROR = 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an issue against the checkable requirement form of "
            "ADR 0226. Deterministic; no model calls."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue", type=int, help="issue number to read via gh")
    source.add_argument("--file", help="a local draft body to check instead")
    parser.add_argument(
        "--repo",
        default=".",
        help="target repository checkout, for --issue (default: cwd)",
    )
    args = parser.parse_args(argv)

    try:
        if args.file:
            path = Path(args.file)
            if not path.is_file():
                raise PrecheckError(f"--file is not a file: {path}")
            body = path.read_text(encoding="utf-8")
            label = path.name
        else:
            repo = Path(args.repo).resolve()
            _, body = fetch_issue(repo, args.issue)
            label = f"{repo.name} #{args.issue}"
        if not body.strip():
            raise PrecheckError("the body is empty; there is nothing to check")
    except PrecheckError as exc:
        print(f"ERROR -- the form check could not run: {exc}", file=sys.stderr)
        print("Nothing about this issue's form has been verified.", file=sys.stderr)
        return EXIT_ERROR

    report = check_form(body)
    print(render_report(report, label), end="", flush=True)
    return EXIT_PASS if report.ok else EXIT_VIOLATIONS


if __name__ == "__main__":
    raise SystemExit(main())
