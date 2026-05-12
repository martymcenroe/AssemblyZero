"""validate_skill.py — static checks for slash-command skill files.

Scans a .md skill file for content patterns known or suspected to trigger
Claude Code's "empty content blocks" API error (the 2026-05-12 outage class).
Designed to run as a pre-commit hook on `.claude/skills/*.md`.

Rules currently checked:
  E001  Empty code fence (```\n``` with no body)
  E003  Trailing whitespace-only content after the final horizontal rule (---)
  E004  Frontmatter missing required `scope:` field
  E005  Unclosed code fence (odd count of ``` lines)

More rules will be added as Part 4 (root-cause investigation) identifies
specific markdown shapes that trigger the empty-block bug. The current rule
set is intentionally conservative — only patterns clearly known to cause
content-block issues, not speculative ones (e.g., consecutive headers with
blank lines between are valid markdown and not flagged).

Usage:
    poetry run python tools/validate_skill.py path/to/skill.md
    poetry run python tools/validate_skill.py path/to/skill1.md path/to/skill2.md

Exit codes:
    0 — all files clean
    1 — one or more files have validation errors
    2 — invocation error (missing file, etc.)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


SCOPE_RE = re.compile(r"^scope:\s*(\w+)", re.MULTILINE)


class Finding:
    __slots__ = ("rule", "line", "col", "message")

    def __init__(self, rule: str, line: int, col: int, message: str):
        self.rule = rule
        self.line = line
        self.col = col
        self.message = message

    def __str__(self) -> str:
        return f"{self.rule} L{self.line}:C{self.col}  {self.message}"


def check_empty_code_fences(lines: list[str]) -> list[Finding]:
    findings = []
    i = 0
    n = len(lines)
    while i < n:
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            # Find matching close
            j = i + 1
            while j < n and not lines[j].strip().startswith("```"):
                j += 1
            if j < n:
                # Check body is all blank
                body = lines[i + 1:j]
                if all(not line.strip() for line in body):
                    findings.append(Finding("E001", i + 1, 1,
                        f"empty code fence (lines {i + 1}-{j + 1})"))
                i = j + 1
            else:
                # Unclosed — handled by E005
                break
        else:
            i += 1
    return findings


def check_trailing_after_hr(lines: list[str], raw: str) -> list[Finding]:
    findings = []
    # Find last `---` line that is NOT YAML frontmatter close
    hr_indices = [i for i, ln in enumerate(lines) if ln.strip() == "---"]
    if len(hr_indices) < 3:  # frontmatter open + close, plus at least one body
        return findings
    # frontmatter close is hr_indices[1]; body horizontal rules start at hr_indices[2]
    last_hr = hr_indices[-1]
    if last_hr < 2:
        return findings
    tail = lines[last_hr + 1:]
    if tail and all(not line.strip() for line in tail):
        findings.append(Finding("E003", last_hr + 1, 1,
            f"trailing whitespace-only content after final horizontal rule (L{last_hr + 1})"))
    return findings


def check_frontmatter_scope(raw: str) -> list[Finding]:
    if not raw.startswith("---\n"):
        return [Finding("E004", 1, 1, "missing YAML frontmatter (must start with ---)")]
    # Find closing ---
    end = raw.find("\n---\n", 4)
    if end == -1:
        return [Finding("E004", 1, 1, "unclosed YAML frontmatter")]
    fm = raw[4:end]
    if not SCOPE_RE.search(fm):
        return [Finding("E004", 1, 1, "frontmatter missing `scope:` field")]
    return []


def check_balanced_code_fences(lines: list[str]) -> list[Finding]:
    count = sum(1 for ln in lines if ln.strip().startswith("```"))
    if count % 2 != 0:
        # Find the last unmatched fence
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip().startswith("```"):
                return [Finding("E005", i + 1, 1,
                    f"unbalanced code fences (odd count of ``` lines = {count})")]
    return []


def validate(path: Path) -> tuple[bool, list[Finding]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return False, [Finding("E000", 0, 0, f"could not read file: {e}")]
    except UnicodeDecodeError as e:
        return False, [Finding("E000", 0, 0, f"file is not valid UTF-8: {e}")]

    lines = raw.split("\n")
    findings = []
    findings += check_frontmatter_scope(raw)
    findings += check_balanced_code_fences(lines)
    findings += check_empty_code_fences(lines)
    findings += check_trailing_after_hr(lines, raw)
    return len(findings) == 0, findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate slash-command skill .md files.")
    parser.add_argument("files", nargs="+", help="One or more .md files to validate.")
    parser.add_argument("--quiet", action="store_true", help="Only print failures, not OK lines.")
    args = parser.parse_args()

    any_fail = False
    for arg in args.files:
        path = Path(arg)
        if not path.is_file():
            print(f"ERROR: {arg}: not a file", file=sys.stderr)
            any_fail = True
            continue
        ok, findings = validate(path)
        if ok:
            if not args.quiet:
                print(f"OK    {path}")
        else:
            any_fail = True
            print(f"FAIL  {path}")
            for f in findings:
                print(f"  {f}")

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
