#!/usr/bin/env python3
"""Enumerate everything a stash holds before you drop it (#2364).

`git stash drop` removes the last named reference to every path in the stash,
and `git stash show` does not list all of them. A stash made with
`--include-untracked` keeps its untracked files in a **third parent**, which the
ordinary listing never mentions:

    $ git stash show --name-only stash@{0}
    tracked.txt
    $ git show --name-only --format="" stash@{0}^3
    mine_wip.py
    other_lane.py

One of three paths. That gap is the whole of #2364. During the 2026-08-14
doctrine batch a `git stash push -u` swept eight one-shot landing scripts left
in `tools/` by other sessions -- a shared checkout cannot tell whose untracked
files are whose -- and the stash was dropped after verifying that *this
session's* two files had landed. The other eight had not landed anywhere and
never would. They survived because nothing had garbage-collected the dropped
commit yet, which is luck, not design.

The failure was not carelessness. It was scoping: a check that looks for what
you expect finds nothing you did not expect. So this tool takes the enumeration
out of memory and does it mechanically -- every path in both halves, each one
compared against a reference the work was supposed to land on.

Read-only. It runs no destructive command and takes no `--apply`, because there
is nothing here to apply; the drop stays a human decision made with the full
list in hand.

    poetry run python tools/stash_audit.py
    poetry run python tools/stash_audit.py --stash 'stash@{2}' --ref origin/main

Exit codes:
    0  every path in the stash is present and identical on the reference
    1  at least one path is missing or differs, so the drop would lose it
    2  the audit could not run, so nothing was verified
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# #2367: before anything prints. Stashed paths and diffs carry arbitrary text.
from assemblyzero.core.utf8_console import install as _install_utf8_console  # noqa: E402

_install_utf8_console()

EXIT_ACCOUNTED = 0
EXIT_UNACCOUNTED = 1
EXIT_ERROR = 2

LANDED = "landed"
DIFFERS = "differs"
ABSENT = "absent"


class AuditError(RuntimeError):
    """The audit could not run. Never raised to mean 'a path is unaccounted'."""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise AuditError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or 'no detail'}"
        )
    return result.stdout


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def tracked_paths(repo: Path, stash: str) -> list[str]:
    """The modifications to files git was already tracking."""
    return _lines(git(repo, "stash", "show", "--name-only", stash))


def untracked_paths(repo: Path, stash: str) -> list[str]:
    """The files swept in by --include-untracked, from the third parent.

    A stash made without -u has no third parent, and that is not an error --
    it means the stash never swept anything, which is the good case.
    """
    try:
        git(repo, "rev-parse", "--verify", "--quiet", f"{stash}^3")
    except AuditError:
        return []
    return _lines(git(repo, "show", "--name-only", "--format=", f"{stash}^3"))


def blob(repo: Path, rev: str, path: str) -> bytes | None:
    """One file's stored bytes at a revision, or None if it is not there.

    Both sides of every comparison in this tool are git blobs, so no line-ending
    normalisation belongs here and adding some would be a bug. The CRLF trap
    documented in the root CLAUDE.md applies to git content compared against a
    file on disk; a blob is already LF whatever the working tree looks like.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{rev}:{path}"],
        capture_output=True,
    )
    return result.stdout if result.returncode == 0 else None


def classify(repo: Path, stash_rev: str, ref: str, path: str) -> str:
    stashed = blob(repo, stash_rev, path)
    if stashed is None:
        raise AuditError(f"{path} is listed in the stash but has no blob there")
    landed = blob(repo, ref, path)
    if landed is None:
        return ABSENT
    return LANDED if landed == stashed else DIFFERS


def audit(repo: Path, stash: str, ref: str) -> list[dict]:
    """One record per path the stash holds, both halves, in a stable order."""
    findings = []
    for path in tracked_paths(repo, stash):
        findings.append(
            {
                "path": path,
                "half": "tracked",
                "status": classify(repo, stash, ref, path),
            }
        )
    for path in untracked_paths(repo, stash):
        findings.append(
            {
                "path": path,
                "half": "untracked",
                "status": classify(repo, f"{stash}^3", ref, path),
            }
        )
    return findings


def render(findings: list[dict], stash: str, ref: str) -> str:
    rule = "=" * 70
    out = [rule, f"Stash audit -- {stash} against {ref}", rule, ""]

    if not findings:
        out += [
            "The stash holds no paths at all. Nothing to lose by dropping it,",
            "and nothing was verified because there was nothing to verify.",
            "",
            rule,
            "",
        ]
        return "\n".join(out)

    for half in ("tracked", "untracked"):
        rows = [f for f in findings if f["half"] == half]
        if not rows:
            continue
        label = {
            "tracked": "Tracked modifications (git stash show)",
            "untracked": "Swept in by --include-untracked (the third parent)",
        }[half]
        out.append(f"{label}: {len(rows)}")
        for row in rows:
            out.append(f"  [{row['status']:>8}] {row['path']}")
        out.append("")

    unaccounted = [f for f in findings if f["status"] != LANDED]
    out.append(f"{len(findings)} path(s) examined, {len(unaccounted)} unaccounted.")
    out.append("")

    if unaccounted:
        out += [
            "DO NOT DROP. These paths are not on the reference, so the stash is",
            "the last named handle on them:",
            "",
        ]
        out += [f"  {f['path']} ({f['status']})" for f in unaccounted]
        out += [
            "",
            "A path can be absent because it was another session's work that was",
            "never going to land here at all -- that is exactly what happened in",
            "#2364. Find its owner before dropping, or copy it out first.",
            "",
        ]
    else:
        out += [
            "Every path is present and byte-identical on the reference.",
            "",
            "Not verified: whether the reference is the right place for this work",
            "to have landed. A path that landed somewhere else, or that belongs to",
            "another session entirely, reads exactly the same as one that landed",
            "here. This tool checks presence, not ownership.",
            "",
        ]

    out += [rule, ""]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "List every path a stash holds, including the untracked files "
            "`git stash show` omits, and check each against a reference "
            "before you drop it. Read-only."
        )
    )
    parser.add_argument("--repo", default=".", help="repository (default: cwd)")
    parser.add_argument(
        "--stash", default="stash@{0}", help="stash to audit (default: stash@{0})"
    )
    parser.add_argument(
        "--ref",
        default="origin/main",
        help="where the work should have landed (default: origin/main)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    try:
        git(repo, "rev-parse", "--verify", "--quiet", args.stash)
        git(repo, "rev-parse", "--verify", "--quiet", args.ref)
        findings = audit(repo, args.stash, args.ref)
    except AuditError as exc:
        print(f"ERROR -- the stash audit could not run: {exc}", file=sys.stderr)
        print("Nothing about this stash has been verified.", file=sys.stderr)
        return EXIT_ERROR

    print(render(findings, args.stash, args.ref), end="", flush=True)
    unaccounted = [f for f in findings if f["status"] != LANDED]
    return EXIT_UNACCOUNTED if unaccounted else EXIT_ACCOUNTED


if __name__ == "__main__":
    raise SystemExit(main())
