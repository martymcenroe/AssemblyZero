"""Fleet sweep: banned-command landmines in rendered agent-facing files (#1808).

Templates get fixed; already-rendered per-repo copies keep the banned form
until someone looks. That is where a banned command survives longest —
#1381's rendered ``branch -D`` instructions sat live for two months after
the template was corrected, with no visible symptom to trigger discovery.

Scans each repo's ``.claude/commands/*.md`` and ``.claude/skills/*.md``
(fixed globs at fixed depth — never a recursive repo walk, never a cloud
mount) for banned-command tokens, then classifies every hit by the 0901
taxonomy line heuristic:

- **GUARD/DOC** — the line *prohibits* the command ("never", "banned",
  "do not"...). These are the wall; they are counted but NOT findings.
- **INSTRUCTOR** — the line tells the agent to run it. An instructed ban
  is an executed ban. These are the findings.

A naive grep flags the guards and buries the instructions — exactly
backwards (docs/audits/0901 §"How to sweep"). The classification is the
tool.

Read-only: no ``--apply`` needed. Exit 0 = no findings, 1 = findings
present, 2 = usage error.

Usage:
    poetry run python tools/banned_command_sweep.py
    poetry run python tools/banned_command_sweep.py --json
    poetry run python tools/banned_command_sweep.py --root <projects-root>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECTS_ROOT = Path(r"C:\Users\mcwiz\Projects")

# Fixed relative globs per repo. Deliberately NOT a recursive walk: the
# hazard class lives in rendered agent-facing command/skill files, and a
# bounded scan can never wander into a cloud-mounted or oversized tree.
SCAN_GLOBS = (".claude/commands/*.md", ".claude/skills/*.md")

# Banned-command tokens, from the root CLAUDE.md "Banned commands (ALWAYS)"
# table. Named so reports read in plain language.
BANNED_PATTERNS: dict[str, re.Pattern] = {
    "git branch -D": re.compile(r"\bbranch\s+-D\b"),
    "force push": re.compile(r"\bpush\b[^\n]*--force"),
    "git reset --hard": re.compile(r"\breset\s+--hard\b"),
    "git clean -fd": re.compile(r"\bclean\s+-fdx?\b"),
    "checkout/merge --theirs": re.compile(r"--theirs\b"),
    "worktree remove --force": re.compile(r"\bworktree\s+remove\b[^\n]*--force"),
    "gh --admin": re.compile(r"--admin\b"),
    "--no-verify": re.compile(r"--no-verify\b"),
    "--no-gpg-sign": re.compile(r"--no-gpg-sign\b"),
}

# A line that PROHIBITS the command is a guard, not a landmine. Marker set
# from the wording used across CLAUDE.md, ADR-0217, and the 0901 audit.
GUARD_MARKERS = re.compile(
    r"(?i)\b(never|banned|ban list|do not|don'?t|not use|must not|"
    r"refus\w+|forbidden|prohibit\w*|instead of|rather than|"
    r"escalat\w+ to|without|avoid)\b"
)


def classify_line(line: str, prev_line: str = "") -> str:
    """Classify one token-bearing line: 'guard' or 'instructor'.

    The previous line participates because prohibition sentences wrap:
    "Do NOT escalate to `--admin` /" on one line, "`--no-verify` /
    `branch -D`." on the next. Judged alone, the continuation line reads
    as an instruction — the real fleet's only false positive on the
    tool's first run.
    """
    if GUARD_MARKERS.search(line) or GUARD_MARKERS.search(prev_line):
        return "guard"
    return "instructor"


def scan_file(path: Path, repo_name: str) -> list[dict]:
    """Return one hit record per banned-token occurrence in the file."""
    hits: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"WARNING: cannot read {path}: {e}", file=sys.stderr)
        return hits

    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        prev_line = lines[lineno - 2] if lineno >= 2 else ""
        for token, pattern in BANNED_PATTERNS.items():
            if pattern.search(line):
                hits.append({
                    "repo": repo_name,
                    "file": path.name,
                    "path": str(path),
                    "line": lineno,
                    "token": token,
                    "class": classify_line(line, prev_line),
                    "text": line.strip()[:160],
                })
    return hits


def sweep(root: Path) -> list[dict]:
    """Scan every repo under root. Returns all hits, both classes."""
    hits: list[dict] = []
    for repo_dir in sorted(root.iterdir()):
        if not repo_dir.is_dir() or repo_dir.name.startswith("."):
            continue
        for rel_glob in SCAN_GLOBS:
            base, _, pattern = rel_glob.rpartition("/")
            target_dir = repo_dir / base
            if not target_dir.is_dir():
                continue
            for md in sorted(target_dir.glob(pattern)):
                hits.extend(scan_file(md, repo_dir.name))
    return hits


def format_report(hits: list[dict]) -> str:
    findings = [h for h in hits if h["class"] == "instructor"]
    guards = [h for h in hits if h["class"] == "guard"]

    lines: list[str] = []
    if findings:
        lines.append(
            f"FINDINGS — {len(findings)} banned-command INSTRUCTION(s) "
            "in rendered agent-facing files:"
        )
        for h in findings:
            lines.append(
                f"  {h['repo']}/{h['file']}:{h['line']}  [{h['token']}]"
            )
            lines.append(f"    {h['text']}")
    else:
        lines.append("No banned-command instructions found.")
    lines.append(
        f"(guards/prohibition text correctly excluded: {len(guards)} line(s) "
        f"across {len({h['path'] for h in guards})} file(s))"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sweep rendered per-repo command/skill files for banned-command instructions",
    )
    parser.add_argument(
        "--root", type=Path, default=PROJECTS_ROOT,
        help="Projects root to scan (default: the fleet root)",
    )
    parser.add_argument("--json", action="store_true", help="Emit all hits as JSON")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print(f"ERROR: root is not a directory: {args.root}", file=sys.stderr)
        return 2

    hits = sweep(args.root)
    findings = [h for h in hits if h["class"] == "instructor"]

    if args.json:
        print(json.dumps({"hits": hits, "finding_count": len(findings)}, indent=2))
    else:
        print(format_report(hits))

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
