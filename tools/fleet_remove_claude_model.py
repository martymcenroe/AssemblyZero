#!/usr/bin/env python3
"""Fleet-wide removal of the inert `.unleashed.json` `claude.model` key.

AssemblyZero #1730.

The Claude wrapper no longer reads `claude.model` — model choice belongs to
Claude Code's native settings hierarchy (the operator's /model default in
user settings; a committed `.claude/settings.json` for a deliberate per-repo
pin). Any `claude.model` left in a repo's `.unleashed.json` is dead config
that misleads readers into thinking it decides something. The scaffolder
stopped minting the key in #1727; this tool sweeps the existing fleet.

For each named repo this tool:

  1. Skips if the repo or its `.unleashed.json` does not exist on origin.
  2. Skips if `claude.model` is absent (idempotent re-runs).
  3. Skips if an open PR from a prior run exists (idempotent).
  4. Files a per-repo issue describing the change.
  5. Creates a branch from the default-branch HEAD.
  6. Removes ONLY the `claude.model` key via the Contents API — key order,
     sibling fields, 2-space indent, LF endings, trailing newline preserved.
  7. Opens a PR carrying `Closes #N` for that repo's issue.
  8. Polls `mergeable_state` until clean/unstable, then squash-merges.
  9. Verifies the merge actually landed before reporting success.

All GitHub access goes through the ambient `gh` CLI auth: `.unleashed.json`
is a plain contents path, so no elevated scopes are needed (contrast
`fleet_set_permission_mode.py`, which predates that distinction and uses the
classic-PAT session). Every `gh` call goes through an injectable runner so
the logic is unit-testable with a scripted fake — no live GitHub required.

Generated issue/PR bodies carry no cross-repo references: each repo's
artifacts describe the change in that repo only.

Usage:
    poetry run python tools/fleet_remove_claude_model.py --repos a,b,c
    poetry run python tools/fleet_remove_claude_model.py --repos a,b,c --apply

Dry-run is the default: prints the per-repo plan and the exact resulting
JSON, takes no action. `--apply` mutates.
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from typing import Any, Callable, Optional

GITHUB_USER = "martymcenroe"
TARGET_PATH = ".unleashed.json"
BRANCH_SUFFIX = "remove-claude-model"
HTTP_TIMEOUT_S = 60
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 300
MAX_REPOS_PER_RUN = 100

# Mergeable states that never resolve by waiting (mirrors tracked_pr_land).
TERMINAL_BAD_STATES = {"dirty", "draft"}
# States good enough to merge: `unstable` means non-required checks are still
# running; required ones passed (fleet merges gate on a single required check).
MERGEABLE_OK_STATES = {"clean", "unstable"}

ISSUE_TITLE = "Remove inert claude.model from .unleashed.json"

ISSUE_BODY = """## Context

The Claude wrapper no longer reads `claude.model` from `.unleashed.json` —
model choice belongs to Claude Code's native settings hierarchy (the
operator's `/model` default; a committed `.claude/settings.json` for a
deliberate per-repo pin). This repo's `.unleashed.json` still carries the
key, where it is dead config that misleads readers.

## Scope

Remove ONLY `claude.model`. Sibling fields (`effort`, `permissionMode`,
`onboard`, etc.) are preserved, as are key order, indent, and line endings.
No behavior change: the wrapper ignores the key at every version still in
service.

Filed and processed automatically by `tools/fleet_remove_claude_model.py`
in AssemblyZero.
"""

PR_BODY_TEMPLATE = """## Summary

Removes the inert `claude.model` key from `.unleashed.json`. The Claude
wrapper no longer reads it; model choice belongs to Claude Code's native
settings hierarchy. Sibling fields, key order, indent, and line endings are
preserved. No behavior change.

Filed and processed automatically by `tools/fleet_remove_claude_model.py`
in AssemblyZero.

Closes #{issue_number}
"""


class GhError(RuntimeError):
    """A gh api call failed in a way the caller did not expect."""


Runner = Callable[..., subprocess.CompletedProcess]


def run(cmd: list[str], *, timeout: int = HTTP_TIMEOUT_S,
        input: Optional[str] = None) -> subprocess.CompletedProcess:
    """Default runner. UTF-8 + replace-errors so gh output never crashes on
    the Windows cp1252 default console encoding."""
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False, timeout=timeout, input=input,
    )


def gh_api(runner: Runner, path: str, *, method: str = "GET",
           payload: Optional[dict] = None, ok_404: bool = False) -> Optional[Any]:
    """One gh api call. Returns parsed JSON, or None on 404 when ok_404."""
    cmd = ["gh", "api", path]
    if method != "GET":
        cmd += ["-X", method]
    kwargs: dict[str, Any] = {}
    if payload is not None:
        cmd += ["--input", "-"]
        kwargs["input"] = json.dumps(payload)
    proc = runner(cmd, timeout=HTTP_TIMEOUT_S, **kwargs)
    if proc.returncode != 0:
        if ok_404 and "404" in (proc.stderr or ""):
            return None
        raise GhError(f"gh api {method} {path} failed: {proc.stderr.strip()[:300]}")
    out = (proc.stdout or "").strip()
    return json.loads(out) if out else {}


def compute_new_content(current_b64: str) -> Optional[str]:
    """New `.unleashed.json` text with `claude.model` removed.

    Returns None when there is nothing to do (no claude block / no model
    key). Preserves key order and sibling fields; emits the fleet house
    style: 2-space indent, LF-only, trailing newline, non-ASCII unescaped.
    """
    raw = base64.b64decode(current_b64).decode("utf-8")
    cfg = json.loads(raw)
    claude = cfg.get("claude")
    if not isinstance(claude, dict) or "model" not in claude:
        return None
    del claude["model"]
    return json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"


def find_existing_pr(runner: Runner, repo: str) -> Optional[int]:
    """Open PR from a prior run of this tool, if any."""
    prs = gh_api(runner, f"repos/{GITHUB_USER}/{repo}/pulls?state=open&per_page=50")
    for pr in prs or []:
        if pr.get("head", {}).get("ref", "").endswith(BRANCH_SUFFIX):
            return pr["number"]
    return None


def wait_for_mergeable(runner: Runner, repo: str, pr_number: int,
                       *, timeout_s: int = MERGEABLE_TIMEOUT_S,
                       interval_s: int = POLL_INTERVAL_S,
                       sleep: Callable[[float], None] = time.sleep,
                       clock: Callable[[], float] = time.monotonic) -> str:
    """Poll mergeable_state until an OK state, a terminal-bad state, or timeout."""
    deadline = clock() + timeout_s
    state = "unknown"
    while clock() < deadline:
        pr = gh_api(runner, f"repos/{GITHUB_USER}/{repo}/pulls/{pr_number}")
        state = pr.get("mergeable_state") or "unknown"
        if state in MERGEABLE_OK_STATES:
            return state
        if state in TERMINAL_BAD_STATES:
            return state
        print(f"  PR #{pr_number} mergeable_state={state} -> wait")
        sleep(interval_s)
    return f"timeout:{state}"


def process_repo(runner: Runner, repo: str, apply: bool) -> str:
    """Run the full cycle for one repo. Returns a one-line outcome."""
    print(f"\n=== {repo} ===")

    meta = gh_api(runner, f"repos/{GITHUB_USER}/{repo}", ok_404=True)
    if meta is None:
        return "skip: repo not found on origin"
    default_branch = meta.get("default_branch", "main")

    info = gh_api(
        runner,
        f"repos/{GITHUB_USER}/{repo}/contents/{TARGET_PATH}?ref={default_branch}",
        ok_404=True,
    )
    if info is None:
        return f"skip: no {TARGET_PATH} on {default_branch}"

    new_content = compute_new_content(info["content"])
    if new_content is None:
        return "skip: claude.model already absent"

    existing = find_existing_pr(runner, repo)
    if existing is not None:
        return f"skip: open PR #{existing} from a prior run"

    if not apply:
        print(new_content, end="")
        return "dry-run: would file issue, branch, edit, PR, merge"

    issue = gh_api(
        runner, f"repos/{GITHUB_USER}/{repo}/issues", method="POST",
        payload={"title": ISSUE_TITLE, "body": ISSUE_BODY},
    )
    issue_number = issue["number"]
    print(f"  issue #{issue_number}")

    head = gh_api(runner, f"repos/{GITHUB_USER}/{repo}/git/ref/heads/{default_branch}")
    head_sha = head["object"]["sha"]
    branch = f"{issue_number}-{BRANCH_SUFFIX}"
    gh_api(
        runner, f"repos/{GITHUB_USER}/{repo}/git/refs", method="POST",
        payload={"ref": f"refs/heads/{branch}", "sha": head_sha},
    )
    print(f"  branch {branch} @ {head_sha[:8]}")

    title = f"chore: remove inert claude.model from .unleashed.json (Closes #{issue_number})"
    gh_api(
        runner, f"repos/{GITHUB_USER}/{repo}/contents/{TARGET_PATH}", method="PUT",
        payload={
            "message": title,
            "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
            "sha": info["sha"],
            "branch": branch,
        },
    )
    print(f"  {TARGET_PATH} updated on {branch}")

    pr = gh_api(
        runner, f"repos/{GITHUB_USER}/{repo}/pulls", method="POST",
        payload={
            "title": title,
            "head": branch,
            "base": default_branch,
            "body": PR_BODY_TEMPLATE.format(issue_number=issue_number),
        },
    )
    pr_number = pr["number"]
    print(f"  PR #{pr_number}")

    state = wait_for_mergeable(runner, repo, pr_number)
    if state not in MERGEABLE_OK_STATES:
        return (f"STUCK: PR #{pr_number} mergeable_state={state} -- "
                f"branch + issue retained for human review")

    gh_api(
        runner, f"repos/{GITHUB_USER}/{repo}/pulls/{pr_number}/merge", method="PUT",
        payload={"merge_method": "squash"},
    )

    merged = gh_api(runner, f"repos/{GITHUB_USER}/{repo}/pulls/{pr_number}")
    if not merged.get("merged"):
        return f"STUCK: PR #{pr_number} merge reported but merged=false -- verify by hand"
    sha = (merged.get("merge_commit_sha") or "")[:8]
    return f"merged: issue #{issue_number}, PR #{pr_number}, squash {sha}"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repos", required=True,
                        help="Comma-separated owner-less repo names to sweep")
    parser.add_argument("--apply", action="store_true",
                        help="Mutate. Default is dry-run: print plan, take no action.")
    parser.add_argument("--limit", type=int, default=MAX_REPOS_PER_RUN)
    args = parser.parse_args(argv)

    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    if not repos:
        print("no repos given", file=sys.stderr)
        return 2
    repos = repos[: args.limit]

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"fleet_remove_claude_model [{mode}] over {len(repos)} repo(s)")

    outcomes: dict[str, str] = {}
    for repo in repos:
        try:
            outcomes[repo] = process_repo(run, repo, args.apply)
        except (GhError, KeyError, json.JSONDecodeError) as exc:
            outcomes[repo] = f"ERROR: {exc}"
        print(f"  -> {outcomes[repo]}")

    print("\n===== summary =====")
    stuck = 0
    for repo, outcome in outcomes.items():
        print(f"{repo}: {outcome}")
        if outcome.startswith(("STUCK", "ERROR")):
            stuck += 1
    return 1 if stuck else 0


if __name__ == "__main__":
    sys.exit(main())
