#!/usr/bin/env python3
"""Which repos' .gitignore have drifted from the scaffolder template, and how (#1618).

    poetry run python tools/audit_gitignore_drift.py
    poetry run python tools/audit_gitignore_drift.py --apply

WHY THIS EXISTS
---------------
`new_repo.py` emits a canonical `.gitignore`. Every repo scaffolded before a
given pattern was added never receives it, and nothing detects the gap. The
patterns arrive one incident at a time -- `node_modules/` after build tooling
littered a repo root, `*.bak` and `*.parked-*` after the mv-to-bak convention
started polluting `git status`, `data-dl/` after downloaded material spent months
landing in the one data directory that is committed.

Each of those was found by a human noticing. This makes it a check.

WHAT DRIFT MEANS HERE, AND WHAT IT DOES NOT
-------------------------------------------
Drift is **a pattern in the template that the repo lacks**. It is deliberately
one-directional: a repo having extra patterns of its own is normal and correct,
not a finding. Repos carry local rules the template will never know about, and an
audit that flagged them would cry wolf on every repo it inspected.

So this reports what is MISSING and never what is EXTRA.

WHY IT COMPARES PATTERNS AND NOT TEXT
-------------------------------------
The template's comments are prose and get rewritten; its blank lines move.
Diffing raw text reports every repo as drifted the first time a comment is
reworded, which trains the reader to ignore the output. Only non-comment,
non-blank lines are compared, and each is normalised for a trailing slash so
`node_modules/` and `node_modules` are one pattern rather than two.

THE data-g TRAP
---------------
Do not "simplify" the template's `data-dl/*` rule into a `data-*/` glob. That
glob matches `data-g/`, which exists specifically to be tracked, and the failure
is silent -- nothing stops being committed, new files just quietly never get
added. This tool therefore reports a repo that ignores `data-g/` as a FINDING in
its own right, separate from drift.

SAFETY
------
Default is read-only: it reports and writes nothing. `--apply` appends missing
patterns to each repo's `.gitignore` under a dated, labelled section, and does
nothing else -- it never removes a line, never reorders, never touches a file
other than `.gitignore`, and never commits. Committing is a per-repo decision
with a per-repo issue, which is what the umbrella tracks.

Skips any repo whose working tree is dirty, unless --include-dirty. Appending to
a file in a tree someone is mid-edit in is how an unrelated change gets swept
into somebody's commit.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from new_repo import GITIGNORE_TEMPLATE  # noqa: E402

PROJECTS_ROOT = Path(r"C:\Users\mcwiz\Projects")

# Repos whose .gitignore is deliberately its own thing.
SKIP_REPOS = {"AssemblyZero"}


def patterns(text: str) -> list[str]:
    """Meaningful ignore patterns, in order, comments and blanks dropped.

    Trailing slashes are normalised away: git treats `foo/` as directory-only and
    `foo` as either, but for drift purposes a repo that has one has the intent of
    the other, and reporting it as missing would be a false alarm.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.rstrip("/"))
    return out


def git(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=cwd, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout.strip()


def is_repo(path: Path) -> bool:
    """True for a real repository, False for a linked worktree of one.

    A worktree has `.git` as a FILE containing a `gitdir:` pointer; a repository
    has it as a directory. Both "exist", so a naive check counts every worktree
    as another repo -- and since a worktree checks out the same tracked
    `.gitignore`, it reports the parent's drift a second time under a different
    name. On this machine that inflated the first run by a double-digit count and
    listed the audit's own worktree as a drifted repo.

    Duplicate rows are worse than merely untidy here: the whole output is a
    to-do list, and a to-do list with phantom entries gets worked twice or
    distrusted.
    """
    return (path / ".git").is_dir()


def is_dirty(path: Path) -> bool:
    code, out = git(["status", "--porcelain"], path)
    return code != 0 or bool(out)


def ignores_data_g(path: Path) -> bool:
    """Does this repo ignore data-g/ -- the directory meant to be tracked?

    Asked of git rather than by reading .gitignore, because the rule can arrive
    from a glob, an exclude file, or the machine's global config, and only git
    knows the answer for all three.
    """
    code, _ = git(["check-ignore", "-q", "data-g/probe"], path)
    return code == 0


def audit_repo(path: Path, wanted: list[str]) -> dict:
    gitignore = path / ".gitignore"
    row = {
        "repo": path.name,
        "has_gitignore": gitignore.exists(),
        "missing": [],
        "ignores_data_g": ignores_data_g(path),
        "dirty": is_dirty(path),
    }
    have = set(patterns(gitignore.read_text(encoding="utf-8", errors="replace"))) if gitignore.exists() else set()
    row["missing"] = [p for p in wanted if p not in have]
    return row


def backfill(path: Path, missing: list[str], today: str) -> None:
    """Append the missing patterns. Never removes, never reorders."""
    gitignore = path / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8", errors="replace") if gitignore.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    block = [
        "",
        f"# --- backfilled from new_repo.py template ({today}) ---",
        "# Patterns this repo predates. Appended by tools/audit_gitignore_drift.py;",
        "# nothing above this line was changed.",
    ]
    block.extend(missing)
    gitignore.write_text(existing + "\n".join(block) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=PROJECTS_ROOT)
    ap.add_argument("--apply", action="store_true", help="append missing patterns (default: report only)")
    ap.add_argument("--include-dirty", action="store_true", help="do not skip repos with a dirty working tree")
    args = ap.parse_args()

    wanted = patterns(GITIGNORE_TEMPLATE)
    today = dt.date.today().isoformat()

    if not args.root.is_dir():
        print(f"ERROR: {args.root} is not a directory", file=sys.stderr)
        return 2

    rows = []
    for child in sorted(args.root.iterdir()):
        if not child.is_dir() or child.name in SKIP_REPOS or not is_repo(child):
            continue
        try:
            rows.append(audit_repo(child, wanted))
        except OSError as exc:
            rows.append({"repo": child.name, "error": str(exc)[:80], "missing": [],
                         "has_gitignore": False, "ignores_data_g": False, "dirty": True})

    drifted = [r for r in rows if r["missing"] or not r["has_gitignore"]]
    data_g_broken = [r for r in rows if r["ignores_data_g"]]

    print(f"repos inspected: {len(rows)}   drifted: {len(drifted)}   clean: {len(rows) - len(drifted)}")
    print()

    if data_g_broken:
        print("FINDING -- data-g/ is IGNORED in these repos. It is meant to be tracked;")
        print("anything added there is silently never committed:")
        for r in data_g_broken:
            print(f"  {r['repo']}")
        print()

    if not drifted:
        print("No drift.")
    else:
        print("MISSING PATTERNS (template has them, repo does not):")
        for r in sorted(drifted, key=lambda r: -len(r["missing"])):
            if not r["has_gitignore"]:
                print(f"  {r['repo']}: NO .gitignore AT ALL")
                continue
            flag = " [dirty]" if r["dirty"] else ""
            print(f"  {r['repo']}{flag}: {len(r['missing'])} missing")
            for p in r["missing"]:
                print(f"      {p}")

    if args.apply:
        print()
        applied = skipped = 0
        for r in drifted:
            path = args.root / r["repo"]
            if r["dirty"] and not args.include_dirty:
                print(f"  SKIP {r['repo']}: working tree dirty")
                skipped += 1
                continue
            if not r["missing"]:
                continue
            backfill(path, r["missing"], today)
            print(f"  APPLIED {r['repo']}: {len(r['missing'])} patterns appended")
            applied += 1
        print(f"\napplied: {applied}   skipped: {skipped}")
        print("Nothing was committed. Each repo needs its own issue and PR.")
    elif drifted:
        print("\nRead-only. Re-run with --apply to append. Nothing was changed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
