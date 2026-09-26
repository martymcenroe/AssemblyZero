"""No AssemblyZero code prunes worktrees (#3649).

On a machine running agents on both Windows and WSL, each side's git reads the
other side's worktrees as stale (measured 2026-09-26), so `git worktree prune`
from either side deletes the other side's live worktrees. A single worktree is
removed by name with `git worktree remove <path>`, which also clears the
registration of one whose directory is gone.

The closed set checked here is the two spellings of the call a tool can make:
an argv list with "worktree" then "prune", and the command as one string.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARGV_FORM = re.compile(r"""["']worktree["']\s*,\s*["']prune["']""")
STRING_FORM = re.compile(r"git\s+(?:-C\s+\S+\s+)?worktree\s+prune")


def offenders() -> list[str]:
    found = []
    for base in ("tools", "assemblyzero"):
        for path in sorted((ROOT / base).rglob("*.py")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for n, line in enumerate(text.splitlines(), 1):
                if ARGV_FORM.search(line) or STRING_FORM.search(line):
                    found.append(f"{path.relative_to(ROOT).as_posix()}:{n}: {line.strip()}")
    return found


def test_no_tool_prunes_worktrees():
    assert offenders() == []


def test_the_check_sees_both_forms():
    assert ARGV_FORM.search('_run(["git", "worktree", "prune"], cwd=r)')
    assert STRING_FORM.search("git -C /x worktree prune")
    assert not ARGV_FORM.search('["git", "worktree", "remove", p]')
