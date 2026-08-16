#!/usr/bin/env python3
"""Audit: every place the pipeline continues after something failed (#2475).

Sibling of #2474, where the N0c requirements gate could not reach the governance
model, printed ``proceeding``, and the run went on to spend drafter budget with
the check skipped. This is the sweep that defect earned: a pipeline which
advances past a gate it could not run is untrustworthy at every stage, because a
green result becomes indistinguishable from a skipped one.

The classification logic lives in ``assemblyzero.core.fail_open_audit`` so the
CI gate in ``tests/unit/test_fail_open_audit.py`` runs the same code this prints.
A check that only exists as a script is one that only runs when somebody
remembers.

Usage
-----
    poetry run python tools/audit_fail_open.py                # ranked report
    poetry run python tools/audit_fail_open.py --format tsv   # one row per site
    poetry run python tools/audit_fail_open.py --undeclared   # only the unruled
    poetry run python tools/audit_fail_open.py --write-baseline
    poetry run python tools/audit_fail_open.py --check        # CI mode

``--check`` exits 1 if any UNDECLARED site exists that is not in the baseline.
It is what the unit test calls, so a newly-introduced fail-open fails the build
at the point it lands.

Clearing a finding means one of two things, and the audit does not care which:
make the site fail closed, or write ``# fail-open: <reason>`` on it and let it
be a decision on record. What it refuses to allow is a third state where nobody
has decided.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# #2367: before anything prints. This report quotes source text verbatim --
# exception expressions and guard conditions straight out of the tree -- so it
# carries whatever characters the codebase does.
from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

from assemblyzero.core.fail_open_audit import (  # noqa: E402
    CATEGORY_HANDLER,
    CATEGORY_UNMET_PRECONDITION,
    CATEGORY_VACUOUS_PASS,
    CATEGORY_WARNED_RETURN,
    DECLARATION_MARKER,
    VISIBILITY_LOUD,
    VISIBILITY_RECORDED,
    VISIBILITY_SILENT,
    Coverage,
    Finding,
    scan,
)

#: What counts as "the pipeline". The package is the pipeline proper; the two
#: launcher entry points under tools/ are included because a fail-open in the
#: thing that decides whether to relaunch is exactly as costly as one inside a
#: node. Overridable so the sweep can be widened without editing this file.
DEFAULT_SUBDIRS = ("assemblyzero",)

BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "fail_open_baseline.json"

_CATEGORY_TITLES = {
    CATEGORY_HANDLER: "exception handlers that continue",
    CATEGORY_WARNED_RETURN: "warned, then returned the all-clear",
    CATEGORY_VACUOUS_PASS: "reported success having examined nothing",
    CATEGORY_UNMET_PRECONDITION: "precondition unmet, all-clear returned anyway",
}


def load_baseline(path: Path = BASELINE_PATH) -> set[str]:
    """The findings already accepted as known. Absent file means empty."""
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return set()
    return set(payload.get("undeclared", []))


def write_baseline(findings: list[Finding], coverage: Coverage,
                   path: Path = BASELINE_PATH) -> int:
    """Freeze today's undeclared findings so CI can catch tomorrow's.

    The counts ride along so a reader can see what the baseline was measured
    against without re-running anything.
    """
    undeclared = sorted(f.key for f in findings if not f.declared)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "_comment": (
                    "Undeclared fail-open sites known at the time this was "
                    "written (#2475). CI fails on any key not listed here. To "
                    "clear one, either make the site fail closed or write "
                    f"'{DECLARATION_MARKER} <reason>' on it, then regenerate "
                    "with tools/audit_fail_open.py --write-baseline. Do not "
                    "add keys by hand: the point is that each removal is a "
                    "decision somebody made in the code."
                ),
                "measured_against": {
                    "files_scanned": coverage.files_scanned,
                    "sites_examined": coverage.sites_examined,
                    "findings_total": len(findings),
                },
                "undeclared": undeclared,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return len(undeclared)


def render_report(findings: list[Finding], coverage: Coverage) -> str:
    """The operator-facing report, ranked most-untrustworthy first."""
    silent = [f for f in findings if f.visibility == VISIBILITY_SILENT]
    undeclared = [f for f in findings if not f.declared]
    silent_undeclared = [f for f in silent if not f.declared]
    spending = [f for f in undeclared if f.spends_after == "yes"]

    lines = [
        "=" * 78,
        "FAIL-OPEN AUDIT (#2475)",
        "=" * 78,
        "",
        "Coverage -- counted, not estimated:",
        f"  Files scanned:        {coverage.files_scanned}",
        f"  Functions scanned:    {coverage.functions_scanned}",
        f"  Sites examined:       {coverage.sites_examined}"
        f"  ({coverage.handlers_examined} handlers,"
        f" {coverage.returns_examined} returns,"
        f" {coverage.branches_examined} branches)",
    ]
    if coverage.files_unparseable:
        lines.append(
            f"  Files that would NOT parse: {len(coverage.files_unparseable)} "
            f"-- {', '.join(coverage.files_unparseable)}"
        )
    else:
        lines.append("  Files that would NOT parse: 0")

    recorded = [f for f in findings if f.visibility == VISIBILITY_RECORDED]
    loud = [f for f in findings if f.visibility == VISIBILITY_LOUD]

    lines += [
        "",
        "Findings:",
        f"  Total fail-open sites:            {len(findings)}",
        f"  Undeclared (nobody has ruled):    {len(undeclared)}",
        f"  Undeclared, on a spending path:   {len(spending)}",
        "",
        "  Can the output be told from a run where the step succeeded?",
        f"    no    (nothing is said at all):   {len(silent)}"
        f"   <-- rank 1, {len(silent_undeclared)} undeclared",
        f"    maybe (filed into a structure):   {len(recorded)}",
        f"    yes   (printed or logged):        {len(loud)}",
        "",
        "That question is the one that matters. A fail-open leaving a visible",
        "mark is a nuisance; one whose output is identical to the success path",
        "is what makes results untrustworthy. 'maybe' is the accumulating",
        "validator -- the failure became an entry, but whether that entry",
        "reaches the operator depends on the caller and is not derivable here.",
        "",
    ]

    if not findings:
        lines.append("No fail-open sites found.")
        return "\n".join(lines)

    for category in (CATEGORY_HANDLER, CATEGORY_WARNED_RETURN,
                     CATEGORY_VACUOUS_PASS, CATEGORY_UNMET_PRECONDITION):
        group = [f for f in findings if f.category == category]
        if not group:
            continue
        lines += [
            "-" * 78,
            f"{_CATEGORY_TITLES[category].upper()}  ({len(group)})",
            "-" * 78,
        ]
        for f in group:
            flag = "RULED " if f.declared else "OPEN  "
            mark = "!" if f.visibility == VISIBILITY_SILENT and not f.declared else " "
            lines += [
                f"{flag}{mark} {f.path}:{f.line}  {f.qualname}",
                f"          fails:        {f.what_fails}",
                f"          instead:      {f.what_happens}",
                f"          outcome:      {f.outcome}",
                f"          spends after: {f.spends_after}",
                f"          output tells you it happened: {f.distinguishable}",
            ]
        lines.append("")

    lines += [
        "=" * 78,
        "Some fall-throughs are correct -- an advisory benchmark should not halt",
        "a run. The job is not to remove them but to make each one a decision on",
        f"record: write '{DECLARATION_MARKER} <reason>' on the site, or make it",
        "fail closed. RULED sites are still fail-open; they are just no longer",
        "accidents.",
        "=" * 78,
    ]
    return "\n".join(lines)


def render_tsv(findings: list[Finding]) -> str:
    header = (
        "path\tline\tqualname\tcategory\toutcome\tvisibility\tspends_after\t"
        "output_distinguishable\tdeclared\twhat_fails\twhat_happens"
    )
    rows = [header]
    for f in findings:
        rows.append(
            f"{f.path}\t{f.line}\t{f.qualname}\t{f.category}\t{f.outcome}\t"
            f"{f.visibility}\t{f.spends_after}\t{f.distinguishable}\t"
            f"{'yes' if f.declared else 'no'}\t{f.what_fails}\t{f.what_happens}"
        )
    return "\n".join(rows)


def check(findings: list[Finding], baseline: set[str]) -> tuple[bool, list[Finding]]:
    """CI mode. Passes only when every undeclared site is one we already knew."""
    fresh = [f for f in findings if not f.declared and f.key not in baseline]
    return (not fresh), fresh


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT,
                        help="repo root to scan (default: this checkout)")
    parser.add_argument("--subdir", action="append", default=None,
                        help="subdirectory to scan; repeatable "
                             f"(default: {', '.join(DEFAULT_SUBDIRS)})")
    parser.add_argument("--format", choices=("report", "tsv", "json"),
                        default="report")
    parser.add_argument("--undeclared", action="store_true",
                        help="only sites nobody has ruled on")
    parser.add_argument("--silent-only", action="store_true",
                        help="only sites whose output looks like success")
    parser.add_argument("--write-baseline", action="store_true",
                        help="freeze today's undeclared findings for CI")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 on any undeclared finding not in the baseline")
    args = parser.parse_args()

    subdirs = tuple(args.subdir) if args.subdir else DEFAULT_SUBDIRS
    findings, coverage = scan(args.root, subdirs)

    if args.write_baseline:
        count = write_baseline(findings, coverage)
        print(f"Baseline written: {count} undeclared site(s) frozen.")
        print(f"  {BASELINE_PATH.relative_to(REPO_ROOT)}")
        return 0

    if args.check:
        ok, fresh = check(findings, load_baseline())
        if ok:
            print(
                f"PASS -- {coverage.files_scanned} files, "
                f"{coverage.sites_examined} sites examined, no new fail-open."
            )
            return 0
        print(f"FAIL -- {len(fresh)} fail-open site(s) not in the baseline:")
        for f in fresh:
            print(f"  {f.path}:{f.line}  {f.qualname}  ({f.category}/{f.outcome})")
            print(f"      instead of halting: {f.what_happens}")
            print(f"      output tells you it happened: {f.distinguishable}")
        print()
        print("Either make the site fail closed, or rule on it in the code with")
        print(f"  {DECLARATION_MARKER} <why continuing is correct here>")
        return 1

    shown = findings
    if args.undeclared:
        shown = [f for f in shown if not f.declared]
    if args.silent_only:
        shown = [f for f in shown if f.visibility == VISIBILITY_SILENT]

    if args.format == "tsv":
        print(render_tsv(shown))
    elif args.format == "json":
        print(json.dumps([f.__dict__ | {"key": f.key} for f in shown], indent=2))
    else:
        print(render_report(shown, coverage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
