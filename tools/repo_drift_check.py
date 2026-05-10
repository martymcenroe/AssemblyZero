#!/usr/bin/env python3
"""
tools/repo_drift_check.py - Detect local-vs-origin drift in repos referenced by a handoff

Surfaced by #1077: when /onboard imports a handoff that touched multiple repos,
the agent inherits a stale assumption about each of those repos' local-vs-origin
state. Drift is silent until the agent tries to merge or push, by which point
recovery is more expensive.

This tool:
  1. Reads a handoff file (a single handoff body OR a handoff-log.md)
  2. Extracts repo references from path patterns
  3. For each unique repo: git fetch (timeout-bounded), then count drift commits
  4. Reports per-repo drift behind/ahead of origin

Output formats:
  - Default: human-readable text (one line per repo with drift)
  - --json:  machine-readable JSON for skill consumption
  - --quiet: only emit if drift is non-zero (text mode only)

Exit codes:
  0 -- ran successfully (regardless of whether drift was found)
  1 -- argument or file error
  2 -- one or more repos errored during fetch/check (drift state partial)

Usage:
  poetry run python tools/repo_drift_check.py --handoff /path/to/handoff-log.md
  poetry run python tools/repo_drift_check.py --handoff /path/to/handoff-body.md --json
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Match repo references in handoff bodies. Two path families to cover:
#   /c/Users/mcwiz/Projects/<repo>      (Bash / Git Bash)
#   C:\Users\mcwiz\Projects\<repo>      (Windows native, with or without trailing slash)
# We also match bare "Projects/<repo>" since handoffs sometimes use shorthand.
# The capture group is the repo name only. We deliberately exclude "." from the
# character class because real repo directory names don't contain dots, and
# admitting "." causes "Projects/CLAUDE.md" -> "CLAUDE.md" false positives.
_PATH_PATTERNS = [
    re.compile(r"/c/Users/mcwiz/Projects/([A-Za-z0-9_-]+)", re.IGNORECASE),
    re.compile(r"C:\\Users\\mcwiz\\Projects\\([A-Za-z0-9_-]+)", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_-])Projects/([A-Za-z0-9_-]+)"),
]

# Marker delimiters for the most-recent handoff inside a handoff-log.md.
_HANDOFF_START_RE = re.compile(r"<!--\s*handoff-start\s*-->")
_HANDOFF_END_RE = re.compile(r"<!--\s*handoff-end\s*-->")

# Repo names we never want to count as a real repo (worktree paths, build artifacts).
_REPO_DENYLIST = {
    "node_modules",
    "__pycache__",
    ".git",
    "AppData",
    "OneDrive",
}

# Hard timeout for any git subprocess call (seconds). Network ops should never block /onboard.
_GIT_TIMEOUT = 30

PROJECTS_ROOT = Path("C:/Users/mcwiz/Projects")


def extract_handoff_body(text: str) -> str:
    """
    If the input contains <!-- handoff-start --> ... <!-- handoff-end --> markers,
    return only the LAST such block. Otherwise return the input unchanged.

    This lets the same code path consume a full handoff-log.md or a single
    handoff body the caller already extracted.
    """
    end_matches = list(_HANDOFF_END_RE.finditer(text))
    if not end_matches:
        return text
    last_end = end_matches[-1]

    # Find the start marker preceding this end marker.
    start_match = None
    for m in _HANDOFF_START_RE.finditer(text):
        if m.end() <= last_end.start():
            start_match = m
        else:
            break

    if start_match is None:
        return text
    return text[start_match.end():last_end.start()]


def parse_repo_names(text: str) -> list[str]:
    """
    Pure regex extraction of repo-like names from text. Does NOT validate
    that the names correspond to real directories -- callers that want a
    filesystem-validated list should use `extract_repo_names`.

    Returns unique names, preserving first-seen order.
    """
    seen: dict[str, None] = {}
    for pattern in _PATH_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1)
            if not name or name in _REPO_DENYLIST:
                continue
            seen.setdefault(name, None)
    return list(seen.keys())


def extract_repo_names(text: str) -> list[str]:
    """
    Return unique repo names from text that correspond to real directories
    under PROJECTS_ROOT. Preserves first-seen order.

    Worktree-style names (e.g., "AssemblyZero-1077") are normalised to their
    parent repo when the parent exists; otherwise kept as-is so we don't
    silently drop genuinely-named repos that happen to end in -NNNN.
    """
    candidates = parse_repo_names(text)
    seen: dict[str, None] = {}
    for name in candidates:
        # Worktree normalisation: try stripping a "-NNNN" suffix.
        stripped = re.sub(r"-\d+$", "", name)
        if stripped != name and (PROJECTS_ROOT / stripped).is_dir():
            candidate = stripped
        elif (PROJECTS_ROOT / name).is_dir():
            candidate = name
        else:
            # Not a real repo directory -- skip silently. (Common case: file
            # names like "CLAUDE" extracted from "Projects/CLAUDE.md" after
            # the dot was already stripped by the regex char class.)
            continue
        seen.setdefault(candidate, None)
    return list(seen.keys())


def _run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a git command, return (returncode, stdout, stderr). Never raises on timeout/error."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {_GIT_TIMEOUT}s"
    except FileNotFoundError:
        return 127, "", "git executable not found"


def detect_default_branch(repo: Path) -> str:
    """
    Resolve the repo's default branch via origin/HEAD. Falls back to 'main', then
    'master' if origin/HEAD isn't set (rare, but happens on shallow clones).
    """
    rc, stdout, _ = _run_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], repo)
    if rc == 0 and stdout.startswith("origin/"):
        return stdout[len("origin/"):]

    for candidate in ("main", "master"):
        rc, _, _ = _run_git(["rev-parse", "--verify", f"refs/heads/{candidate}"], repo)
        if rc == 0:
            return candidate

    return "main"


def check_repo_drift(name: str) -> dict:
    """Return a dict describing drift state for one repo. Always returns a dict; never raises."""
    path = PROJECTS_ROOT / name
    result: dict = {"name": name, "path": str(path)}

    if not path.is_dir():
        result["status"] = "missing"
        result["error"] = "path does not exist"
        return result
    if not (path / ".git").exists():
        result["status"] = "not_git"
        result["error"] = ".git not present"
        return result

    branch = detect_default_branch(path)
    result["branch"] = branch

    rc, _, stderr = _run_git(["fetch", "origin", "--quiet"], path)
    if rc != 0:
        result["status"] = "fetch_error"
        result["error"] = stderr or f"git fetch returned {rc}"
        return result

    rc_b, behind, _ = _run_git(["rev-list", "--count", f"{branch}..origin/{branch}"], path)
    rc_a, ahead, _ = _run_git(["rev-list", "--count", f"origin/{branch}..{branch}"], path)
    if rc_b != 0 or rc_a != 0:
        result["status"] = "rev_list_error"
        result["error"] = f"rev-list failed (behind rc={rc_b}, ahead rc={rc_a})"
        return result

    behind_n = int(behind or "0")
    ahead_n = int(ahead or "0")
    result["behind"] = behind_n
    result["ahead"] = ahead_n
    if behind_n == 0 and ahead_n == 0:
        result["status"] = "in_sync"
    else:
        result["status"] = "drift"
    return result


def format_text_report(report: dict, quiet: bool) -> str:
    lines = []
    drift_repos = [r for r in report["repos"] if r["status"] == "drift"]
    error_repos = [r for r in report["repos"] if r["status"] not in ("in_sync", "drift")]

    if quiet and not drift_repos and not error_repos:
        return ""

    if not report["repos"]:
        return "No repo references found in handoff body."

    if drift_repos:
        lines.append("Drift detected in handoff-referenced repos:")
        for r in drift_repos:
            parts = []
            if r["behind"]:
                parts.append(f"{r['behind']} behind origin/{r['branch']}")
            if r["ahead"]:
                parts.append(f"{r['ahead']} ahead of origin/{r['branch']}")
            lines.append(f"  {r['name']}: {' / '.join(parts)} -- pull before any local work")

    if error_repos:
        if lines:
            lines.append("")
        lines.append("Repos that could not be checked:")
        for r in error_repos:
            lines.append(f"  {r['name']}: {r['status']} ({r.get('error', 'no detail')})")

    if not quiet:
        in_sync = [r for r in report["repos"] if r["status"] == "in_sync"]
        if in_sync:
            if lines:
                lines.append("")
            lines.append(f"In sync ({len(in_sync)}): {', '.join(r['name'] for r in in_sync)}")

    return "\n".join(lines)


def build_report(handoff_text: str) -> dict:
    body = extract_handoff_body(handoff_text)
    names = extract_repo_names(body)
    repos = [check_repo_drift(name) for name in names]
    return {"repos": repos, "names_extracted": names}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--handoff", required=True, help="Path to handoff-log.md or a handoff body file")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--quiet", action="store_true", help="Text mode: only print if drift or errors")
    args = parser.parse_args(argv)

    handoff_path = Path(args.handoff)
    if not handoff_path.is_file():
        print(f"ERROR: handoff file not found: {handoff_path}", file=sys.stderr)
        return 1

    handoff_text = handoff_path.read_text(encoding="utf-8", errors="replace")
    report = build_report(handoff_text)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        text = format_text_report(report, quiet=args.quiet)
        if text:
            print(text)

    has_errors = any(r["status"] not in ("in_sync", "drift") for r in report["repos"])
    return 2 if has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
