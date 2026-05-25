"""Nightly backup of the universal CLAUDE.md to a versioned canonical path.

The universal CLAUDE.md lives at C:\\Users\\mcwiz\\Projects\\CLAUDE.md --
auto-loaded by Claude Code into every session's context, but not in any
git repo. This script snapshots it nightly into AssemblyZero/docs/canonical/
and opens a PR if drift is detected. **Never auto-merges** -- the operator
reviews any change to the universal rules before it lands.

Scheduled task: Claude-UniversalClaudeMdBackup, daily 5:55 AM local
(per runbook 0903 silent-task pattern).

Detection / PR-open uses a worktree so the operator's main AssemblyZero
working tree is never disturbed.

Issue: martymcenroe/AssemblyZero#1262
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

UNIVERSAL_CLAUDE_MD = Path("C:/Users/mcwiz/Projects/CLAUDE.md")
AZ_ROOT = Path("C:/Users/mcwiz/Projects/AssemblyZero")
CANONICAL_REL = "docs/canonical/universal-CLAUDE.md"
REPO = "martymcenroe/AssemblyZero"
LOG_FILE = Path("C:/Users/mcwiz/Projects/.universal-claude-md-backup.jsonl")


def log(status: str, **details) -> None:
    """Append a JSONL entry to the heartbeat-style log file."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "status": status,
        **details,
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _gh(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["gh", *args],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=check,
    )


def _git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=check,
    )


def fetch_canonical_from_origin() -> bytes | None:
    """Return the current canonical file bytes from origin/main, or None
    if it doesn't exist on origin yet (first-snapshot case).
    """
    result = _gh(
        "api",
        f"repos/{REPO}/contents/{CANONICAL_REL}?ref=main",
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
        return base64.b64decode(data["content"])
    except (json.JSONDecodeError, KeyError):
        return None


def find_existing_backup_pr() -> int | None:
    """Return PR number of an open backup PR (if any), else None."""
    result = _gh(
        "pr", "list", "--repo", REPO, "--state", "open",
        "--search", "in:title backup universal CLAUDE.md",
        "--json", "number,title", check=False,
    )
    if result.returncode != 0:
        return None
    try:
        prs = json.loads(result.stdout)
        return prs[0]["number"] if prs else None
    except (json.JSONDecodeError, KeyError, IndexError):
        return None


def open_backup_pr(source_bytes: bytes, prior_canonical_len: int | None) -> tuple[int | None, str]:
    """Worktree-based commit + PR. Returns (pr_number, branch_name)."""
    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    branch = f"backup-universal-claude-md-{date_tag}"
    worktree = Path(f"C:/Users/mcwiz/Projects/AssemblyZero-backup-{date_tag}")

    if worktree.exists():
        # Leftover from a previous failed run; remove it
        _git("worktree", "remove", "--force", str(worktree), cwd=AZ_ROOT, check=False)

    _git("fetch", "origin", "main", cwd=AZ_ROOT)
    _git("worktree", "add", str(worktree), "-b", branch, "origin/main", cwd=AZ_ROOT)

    try:
        target = worktree / CANONICAL_REL
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_bytes)

        _git("add", CANONICAL_REL, cwd=worktree)
        commit_msg = (
            f"chore: nightly backup of universal CLAUDE.md\n"
            f"\n"
            f"No-Issue: scheduled nightly backup (tracking #1262)\n"
            f"\n"
            f"Source: {UNIVERSAL_CLAUDE_MD}\n"
            f"Canonical: {CANONICAL_REL}\n"
            f"Source length: {len(source_bytes)} bytes\n"
        )
        _git("commit", "-m", commit_msg, cwd=worktree)
        _git("push", "-u", "origin", branch, cwd=worktree)

        body = (
            f"No-Issue: scheduled nightly backup (tracking #1262)\n\n"
            f"## Drift detected\n\n"
            f"The universal CLAUDE.md at `{UNIVERSAL_CLAUDE_MD}` has changed since the last canonical snapshot on origin/main.\n\n"
            f"| Field | Value |\n"
            f"|---|---|\n"
            f"| Source path | `{UNIVERSAL_CLAUDE_MD}` |\n"
            f"| Canonical path | `{CANONICAL_REL}` |\n"
            f"| Source length | {len(source_bytes)} bytes |\n"
            f"| Prior canonical length | "
            f"{prior_canonical_len if prior_canonical_len is not None else 'N/A (first snapshot)'} bytes |\n\n"
            f"## Review checklist\n\n"
            f"- [ ] Diff is an intentional rule change (not corruption or accidental edit)\n"
            f"- [ ] No secrets / operator-private content slipped in\n"
            f"- [ ] If the change affects PR handling, dependabot review, or any fleet workflow, it lands BEFORE the next 6:00 AM dependabot sweep\n\n"
            f"After merging, this canonical snapshot becomes the new baseline; the next nightly run will diff against it.\n\n"
            f"## Related\n\n"
            f"- Tool: `tools/backup_universal_claude_md.py`\n"
            f"- Scheduled task: `Claude-UniversalClaudeMdBackup` (daily 5:55 AM local)\n"
            f"- Tracking: #1262\n"
            f"- Runbook: `docs/runbooks/0903-windows-scheduled-tasks.md`\n"
        )
        result = _gh(
            "pr", "create", "--repo", REPO,
            "--head", branch, "--base", "main",
            "--title", f"chore: nightly backup of universal CLAUDE.md ({date_tag})",
            "--body", body,
            check=False,
        )
        if result.returncode != 0:
            return None, branch
        # gh returns the URL on the last line
        for line in result.stdout.strip().splitlines():
            if "/pull/" in line:
                return int(line.rstrip("/").rsplit("/", 1)[-1]), branch
        return None, branch
    finally:
        # Always remove the worktree; the branch lives on origin
        _git("worktree", "remove", "--force", str(worktree), cwd=AZ_ROOT, check=False)


def main() -> int:
    if not UNIVERSAL_CLAUDE_MD.exists():
        log("error", reason="universal CLAUDE.md not found",
            path=str(UNIVERSAL_CLAUDE_MD))
        return 1

    # Normalize CRLF -> LF before any comparison (gh Contents API returns LF;
    # local file may be CRLF if edited with a Windows tool)
    source_bytes = UNIVERSAL_CLAUDE_MD.read_bytes().replace(b"\r\n", b"\n")

    canonical_bytes = fetch_canonical_from_origin()
    if canonical_bytes is not None and canonical_bytes.replace(b"\r\n", b"\n") == source_bytes:
        log("no_drift", source_len=len(source_bytes))
        return 0

    existing_pr = find_existing_backup_pr()
    if existing_pr is not None:
        log("pr_exists", existing_pr=existing_pr, source_len=len(source_bytes))
        return 0

    pr_number, branch = open_backup_pr(
        source_bytes,
        prior_canonical_len=len(canonical_bytes) if canonical_bytes else None,
    )
    if pr_number is None:
        log("pr_open_failed", branch=branch, source_len=len(source_bytes))
        return 1

    log("pr_opened", pr_number=pr_number, branch=branch,
        source_len=len(source_bytes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
