#!/usr/bin/env python3
"""Audit: identify code that writes to repo-tracked log paths (#1151).

A file written to a tracked path inside a git repo dirties every worktree
of that repo the moment the writer fires. `git worktree remove` (no
--force, per policy) refuses to remove a dirty worktree, so any tool
that creates worktrees and tries to clean them up silently leaks state.

This audit script surfaces the writers programmatically by scanning the
codebase for path constants that resolve to TRACKED paths. The pattern
that bit us in #1134 (relative path constant -> dirty worktree at every
firing) recurs anywhere a module defines `Path("rel/path.ext")` or
similar string constants that aren't absolute.

What it does:

  1. Scan the codebase (Python source files) for path-like string and
     Path constants -- module-level assignments matching patterns like:
       NAME: str = "rel/sub/file.ext"
       NAME = Path("rel/sub/file.ext")
  2. For each candidate, check if the path is RELATIVE (the bug shape)
     and whether the path is currently TRACKED in the repo via
     `git ls-files`.
  3. Emit a TSV: source_file:line, constant_name, target_path,
     is_relative, is_tracked, classification.
  4. Print a summary: candidates flagged as relative+tracked are the
     #1134-pattern bugs that need relocation.

Run from the AssemblyZero checkout root. Usage:

    poetry run python tools/audit_tracked_log_writers.py
    poetry run python tools/audit_tracked_log_writers.py --root /c/Users/.../AssemblyZero
    poetry run python tools/audit_tracked_log_writers.py --output /tmp/writers.tsv

Issue: #1151 | Pattern: #1134 (first instance)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUTPUT = Path("audit_tracked_log_writers_results.tsv")

# Captures things like:
#   NAME = "rel/path.ext"
#   NAME: type = "rel/path.ext"
#   NAME = Path("rel/path.ext")
#   NAME: Path = Path("rel/path.ext")
PATH_CONSTANT_RE = re.compile(
    r"""
    ^(?P<indent>[ \t]*)               # leading whitespace
    (?P<name>[_A-Z][_A-Z0-9]+)        # ALL_CAPS const
    (?:\s*:\s*[^=]+)?                 # optional type annotation
    \s*=\s*
    (?:Path\(\s*)?                    # optional Path( wrapper
    (?P<quote>['"])                   # opening quote
    (?P<path>[^'"]+)                  # the path string
    (?P=quote)                        # matching quote
    """,
    re.VERBOSE,
)

# Filter to paths that LOOK LIKE log/data targets the bug applies to.
# We deliberately do NOT match every string constant (test fixture paths,
# template names, etc.) -- only those that resemble outputs.
LOG_PATH_HINTS = re.compile(
    r"""
    (?:
        \.jsonl$
        | \.json$
        | \.log$
        | \.tsv$
        | history\.json$
        | -log$
        | _log$
        | /audit
        | /telemetry
        | /history
        | hourglass
        | logs?/
        | tmp/
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class Finding:
    source_file: str
    line_no: int
    name: str
    target_path: str
    is_relative: bool
    is_tracked: bool

    @property
    def is_bug_shape(self) -> bool:
        """The #1134 bug shape: relative path + tracked target = guaranteed
        dirty-worktree on every firing."""
        return self.is_relative and self.is_tracked

    def tsv_row(self) -> str:
        return "\t".join([
            self.source_file,
            str(self.line_no),
            self.name,
            self.target_path,
            "yes" if self.is_relative else "no",
            "yes" if self.is_tracked else "no",
            "BUG" if self.is_bug_shape else (
                "RELATIVE_BUT_UNTRACKED" if self.is_relative else "OK"
            ),
        ])


TSV_HEADER = "\t".join([
    "source_file", "line_no", "constant_name", "target_path",
    "is_relative", "is_tracked", "classification",
])


def find_path_constants(source: Path) -> list[tuple[int, str, str]]:
    """Return [(line_no, name, target_path), ...] for path-like constants
    matched in the file. Filter to ones whose path matches LOG_PATH_HINTS."""
    try:
        text = source.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[tuple[int, str, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        m = PATH_CONSTANT_RE.match(line)
        if not m:
            continue
        path = m.group("path")
        if not LOG_PATH_HINTS.search(path):
            continue
        out.append((line_no, m.group("name"), path))
    return out


def is_path_relative(target_path: str) -> bool:
    """A path is the bug-shape relative if it does NOT start with / or
    a Windows drive letter or `~`."""
    p = target_path.lstrip()
    if not p:
        return False
    if p.startswith("/") or p.startswith("\\"):
        return False
    if len(p) >= 2 and p[1] == ":":  # Windows drive
        return False
    if p.startswith("~"):
        return False
    return True


def tracked_paths(root: Path) -> set[str]:
    """Return the set of paths tracked by `git ls-files` (normalized
    to forward slashes)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if result.returncode != 0:
        return set()
    return {line.replace("\\", "/").strip() for line in result.stdout.splitlines() if line.strip()}


def iter_python_sources(root: Path) -> list[Path]:
    """All .py files under root, excluding venvs / caches / done-lineage."""
    out: list[Path] = []
    skip_dir_names = {
        "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache",
        ".pytest_cache", ".ruff_cache", "build", "dist",
    }
    for candidate in root.rglob("*.py"):
        if any(part in skip_dir_names for part in candidate.parts):
            continue
        if "lineage/done" in candidate.as_posix():
            continue
        out.append(candidate)
    return out


def audit(root: Path) -> list[Finding]:
    tracked = tracked_paths(root)
    findings: list[Finding] = []
    for src in iter_python_sources(root):
        for line_no, name, path in find_path_constants(src):
            rel = is_path_relative(path)
            norm = path.replace("\\", "/")
            tracked_match = norm in tracked
            rel_to_root = str(src.relative_to(root)).replace("\\", "/")
            findings.append(Finding(
                source_file=rel_to_root,
                line_no=line_no,
                name=name,
                target_path=path,
                is_relative=rel,
                is_tracked=tracked_match,
            ))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--root", type=Path, default=Path.cwd(),
                        help="Repo root to audit (default: cwd)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"TSV output path (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not (root / ".git").exists():
        sys.exit(f"Not a git repo: {root}")

    print(f"Auditing path constants under {root}...")
    findings = audit(root)
    print(f"Scanned {len(findings)} path-like constants.\n")

    args.output.write_text(
        TSV_HEADER + "\n" + "\n".join(f.tsv_row() for f in findings) + "\n",
        encoding="utf-8",
    )
    print(f"TSV written: {args.output.resolve()}")

    bugs = [f for f in findings if f.is_bug_shape]
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total candidates: {len(findings)}")
    print(f"  Bug shape (relative + tracked): {len(bugs)}")
    if bugs:
        print("\nWRITERS DIRTYING WORKTREES (relative path + tracked target):")
        for b in bugs:
            print(f"  {b.source_file}:{b.line_no}  {b.name} -> {b.target_path}")
        return 2
    print("\nNo bug-shape writers detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
