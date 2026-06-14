#!/usr/bin/env python3
"""Fleet cleanup: strip the blocking session-handshake/ACK from every GEMINI.md.

GEMINI.md historically carried a "## Session Initialization (The Handshake)"
section instructing the agent to emit `ACK. State determination complete.
Please identify my model version.` and to HALT ("do not proceed until the user
replies"). When the Antigravity CLI (`agy`) auto-loads GEMINI.md, that handshake
fires and blocks non-interactive / governance use. The fleet is inconsistent --
some repos carry the full ACK, some a variant, some none -- which is why `agy`
prompts the ACK in one repo and not another (operator-confirmed by direct test).

This removes the entire handshake section from each repo's GEMINI.md. The
scaffolder template fix (so new repos stop carrying it) is a separate change in
new_repo_setup.py.

Auth: the `gh` CLI's fine-grained PAT throughout (GEMINI.md is a regular file --
no `workflow` scope, no classic PAT). Cerberus auto-approves each PR after
pr-sentinel passes (No-Issue exemption, operator-authorized fleet cleanup).

Dry-run by default. Mutating the fleet requires --apply. Operator-run.

Usage:
    poetry run python tools/fix_gemini_ack.py --fleet            # preview
    poetry run python tools/fix_gemini_ack.py --repo NAME        # preview one
    poetry run python tools/fix_gemini_ack.py --fleet --apply    # do it
"""
import argparse
import base64
import re
import subprocess
import tempfile
import time
from pathlib import Path

import requests

GH_API = "https://api.github.com"
GITHUB_USER = "martymcenroe"
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 300
BRANCH = "strip-gemini-handshake-ack"
PR_TITLE = "chore(GEMINI.md): remove blocking session-handshake/ACK"
NO_ISSUE = (
    "No-Issue: remove the blocking Gemini session-handshake/ACK from GEMINI.md -- "
    "it halts Antigravity CLI (agy) on auto-load. Operator-confirmed by direct "
    "test that agy prompts the ACK in repos that still carry it. Fleet consistency "
    "cleanup."
)

# Matches the handshake section from its header (e.g. "## 1. Session
# Initialization (The Handshake)") up to the next markdown header or EOF.
HANDSHAKE_RE = re.compile(
    r"(?ms)^#{1,6}[ \t]*\d*\.?[ \t]*Session Initialization.*?(?=^#{1,6}[ \t]|\Z)"
)


def strip_handshake(text: str) -> str:
    """Remove the GEMINI.md session-handshake/ACK section. Idempotent."""
    out = HANDSHAKE_RE.sub("", text)
    out = re.sub(r"\n{3,}", "\n\n", out)  # collapse the gap the cut leaves
    return out


def needs_fix(text: str | None) -> bool:
    """True iff GEMINI.md exists and still carries the handshake section."""
    return text is not None and HANDSHAKE_RE.search(text) is not None


def _gh_token() -> str:
    out = subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"command failed ({r.returncode}): {' '.join(cmd)}\n{r.stderr.strip()}"
        )
    return r


def get_gemini_md(repo: str, token: str) -> str | None:
    """Return a repo's root GEMINI.md text, or None if it has none."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/GEMINI.md",
        params={"ref": "main"},
        headers=_headers(token),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return base64.b64decode(r.json()["content"]).decode("utf-8")


def discover_targets(token: str) -> list[str]:
    """All user-owned non-fork non-archived repos whose GEMINI.md still carries
    the handshake. Returns sorted repo names."""
    names: list[str] = []
    page = 1
    while True:
        r = requests.get(
            f"{GH_API}/user/repos",
            params={"per_page": 100, "page": page, "affiliation": "owner"},
            headers=_headers(token),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for repo in batch:
            if not repo.get("fork") and not repo.get("archived"):
                names.append(repo["name"])
        page += 1

    targets = []
    for name in sorted(set(names)):
        if needs_fix(get_gemini_md(name, token)):
            targets.append(name)
    return targets


def _wait_mergeable(repo: str, pr_number: str, token: str) -> str:
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    last = "unknown"
    while time.time() < deadline:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls/{pr_number}",
            headers=_headers(token),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        last = r.json().get("mergeable_state") or "unknown"
        if last in ("clean", "unstable", "dirty"):
            return last
        time.sleep(POLL_INTERVAL_S)
    return last


def fix_repo(repo: str, token: str, apply: bool) -> str:
    """Strip the handshake from one repo's GEMINI.md. Returns a status line."""
    if not apply:
        return f"{repo}: WOULD strip handshake/ACK from GEMINI.md"

    full = f"{GITHUB_USER}/{repo}"
    with tempfile.TemporaryDirectory() as td:
        _run(["gh", "repo", "clone", full, td, "--", "--depth", "1"])
        gm = Path(td) / "GEMINI.md"
        if not gm.exists():
            return f"{repo}: no GEMINI.md (skipped)"
        text = gm.read_text(encoding="utf-8")
        fixed = strip_handshake(text)
        if fixed == text:
            return f"{repo}: no handshake section (skipped)"
        gm.write_text(fixed, encoding="utf-8")

        _run(["git", "-C", td, "checkout", "-b", BRANCH])
        _run(["git", "-C", td, "add", "GEMINI.md"])
        _run([
            "git", "-C", td, "commit", "-m",
            f"{PR_TITLE}\n\n{NO_ISSUE}",
        ])
        _run(["git", "-C", td, "push", "-u", "origin", BRANCH])

        pr_body = (
            "Removes the `## Session Initialization (The Handshake)` section from "
            "GEMINI.md. It instructs the agent to emit an `ACK` and HALT until the "
            "user replies, which blocks the Antigravity CLI (`agy`) on auto-load. "
            f"Operator-confirmed by direct test.\n\n{NO_ISSUE}"
        )
        pr_url = _run([
            "gh", "pr", "create", "--repo", full, "--head", BRANCH,
            "--base", "main", "--title", PR_TITLE, "--body", pr_body,
        ]).stdout.strip()

    pr_number = pr_url.rstrip("/").rsplit("/", 1)[-1]
    state = _wait_mergeable(repo, pr_number, token)
    if state not in ("clean", "unstable"):
        return f"{repo}: PR {pr_url} stuck at {state!r}; left open for review"
    _run(["gh", "pr", "merge", pr_number, "--repo", full, "--squash"])
    return f"{repo}: fixed via {pr_url}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo", help="single repo NAME (without owner)")
    g.add_argument("--fleet", action="store_true", help="all user-owned repos")
    ap.add_argument(
        "--apply", action="store_true",
        help="actually clone/edit/PR/merge (default: dry-run preview)",
    )
    args = ap.parse_args()
    token = _gh_token()

    if args.repo:
        if not needs_fix(get_gemini_md(args.repo, token)):
            print(f"{args.repo}: GEMINI.md has no handshake section -- nothing to do.")
            return 0
        targets = [args.repo]
    else:
        print("Scanning fleet for GEMINI.md handshake/ACK sections...")
        targets = discover_targets(token)

    if not targets:
        print("No repos need fixing.")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n[{mode}] {len(targets)} repo(s) with a GEMINI.md handshake/ACK:\n")
    failures = 0
    for repo in targets:
        try:
            print("  " + fix_repo(repo, token, args.apply))
        except Exception as e:  # noqa: BLE001 -- isolate per-repo failures
            failures += 1
            print(f"  {repo}: ERROR -- {e}")

    if not args.apply:
        print(f"\nDry-run only. Re-run with --apply to land {len(targets)} PR(s).")
    print(f"\nDone. {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
