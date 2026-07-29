#!/usr/bin/env python3
"""Land a staged workflow file into .github/workflows/ via the in-process classic PAT.

Issue #1882. Generic replacement for the per-repo one-shot landers. The target
repository, file paths, and issue number are RUN-TIME arguments, so no target
name is written into this repo -- which matters because this repo is public and
some targets are not (universal CLAUDE.md, "Private-Repo Names Stay Off Public
Surfaces").

## Why a lander exists at all

The fine-grained PAT every agent session uses cannot push files under
`.github/workflows/` -- it lacks the `workflow` scope, and that exclusion is
load-bearing (ADR-0216 section 1: without it an agent could edit its own
pr-sentinel workflow to disable governance). So a workflow file is staged
somewhere pushable (conventionally `docs/ci/`) and moved into place here,
through the GitHub Contents API, using the admin-scope classic PAT that this
process gpg-decrypts in-heap per ADR-0216 (#959). The PAT lives only as a local
variable inside the `with classic_pat_session()` block, is consumed by
`requests` directly, and never reaches env, argv, disk, or a log.

## What it does (idempotent -- safe to re-run)

  1. If the destination already exists on main -> report + exit 0.
  2. Read the staged file from the target repo over the Contents API. Read from
     GitHub, never from a local working tree: bytes on GitHub are already
     LF-normalized, which sidesteps the CRLF hazard entirely (root CLAUDE.md
     gotcha 3 -- the Contents API stores bytes verbatim, so submitting a
     CRLF-checked-out file flips the whole file's line endings on origin).
  3. Create the branch from main.
  4. PUT the workflow file at its destination on that branch.
  5. DELETE the staged copy on the same branch, so the repo does not carry two
     versions that can drift (--keep-staged opts out).
  6. Open a PR ("Closes #<issue>"), WAIT for the named check to CONCLUDE, and
     report it.
  7. Squash-merge, then delete the remote branch. Local git is never touched.

Step 6 deliberately waits rather than merging as soon as GitHub reports
`unstable`. A PR that *installs* a check is the first real exercise of that
check -- for `pull_request` events GitHub evaluates the workflow from the merge
ref -- so merging without reading the result installs an instrument and never
looks at it. Refuses to merge on red unless --merge-on-red is given.

## Usage

RUN THIS YOURSELF in your own Git Bash -- never via an agent's Bash tool, per
the _pat_session operational rule: a Python process spawned by an agent is the
agent's child, and its heap is theoretically readable while the PAT is in scope.

    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_staged_workflow.py \
        --repo <REPO> --issue <N> \
        --staged docs/ci/tests.yml \
        --workflow .github/workflows/tests.yml

Add --dry-run to print the plan without credentials or writes.

Requires ~/.secrets/classic-pat.gpg (one-time setup in the _pat_session
docstring) and gpg-agent default-cache-ttl 0, so a sibling's silent decrypt
attempt surfaces pinentry.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GH_API = "https://api.github.com"
DEFAULT_OWNER = "martymcenroe"
DEFAULT_CHECK = "tests"
HTTP_TIMEOUT_S = 30
MERGE_POLL_ATTEMPTS = 30
MERGE_POLL_SLEEP_S = 10
CHECK_POLL_ATTEMPTS = 40
CHECK_POLL_SLEEP_S = 15


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo_url(cfg: argparse.Namespace, suffix: str) -> str:
    return f"{GH_API}/repos/{cfg.owner}/{cfg.repo}/{suffix}"


def get_file(pat: str, cfg: argparse.Namespace, path: str, ref: str) -> dict | None:
    """Return the Contents-API record for `path` at `ref`, or None if absent."""
    r = requests.get(
        _repo_url(cfg, f"contents/{path}"),
        params={"ref": ref},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def strip_header_comment(text: str) -> str:
    """Drop leading `#` comment lines and any blank lines that follow them.

    A staged workflow typically opens with a comment explaining why it lives in
    the staging directory. That explanation stops being true the moment the file
    lands, so it should not travel with it.
    """
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith("#"):
        i += 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    return "".join(lines[i:])


def read_staged(pat: str, cfg: argparse.Namespace) -> str:
    rec = get_file(pat, cfg, cfg.staged, "main")
    if rec is None:
        raise SystemExit(
            f"staged file {cfg.staged} not found on {cfg.owner}/{cfg.repo}@main -- "
            f"nothing to land"
        )
    text = base64.b64decode(rec["content"]).decode("utf-8")
    if cfg.strip_header_comment:
        text = strip_header_comment(text)
    return text


def main_sha(pat: str, cfg: argparse.Namespace) -> str:
    r = requests.get(
        _repo_url(cfg, "git/ref/heads/main"), headers=_headers(pat), timeout=HTTP_TIMEOUT_S
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def ensure_branch(pat: str, cfg: argparse.Namespace, sha: str) -> None:
    r = requests.post(
        _repo_url(cfg, "git/refs"),
        headers=_headers(pat),
        json={"ref": f"refs/heads/{cfg.branch}", "sha": sha},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 422 and "already exists" in r.text.lower():
        print(f"  branch {cfg.branch} already exists -- reusing")
        return
    r.raise_for_status()
    print(f"  created branch {cfg.branch} @ {sha[:8]}")


def put_workflow(pat: str, cfg: argparse.Namespace, content: str) -> None:
    existing = get_file(pat, cfg, cfg.workflow, cfg.branch)
    payload: dict[str, object] = {
        "message": f"ci: add {Path(cfg.workflow).name} (Closes #{cfg.issue})",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": cfg.branch,
    }
    if existing:
        payload["sha"] = existing["sha"]  # re-run against a half-finished branch
    r = requests.put(
        _repo_url(cfg, f"contents/{cfg.workflow}"),
        headers=_headers(pat),
        json=payload,
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  committed {cfg.workflow} on {cfg.branch}")


def delete_staged(pat: str, cfg: argparse.Namespace) -> None:
    staged = get_file(pat, cfg, cfg.staged, cfg.branch)
    if staged is None:
        print(f"  {cfg.staged} already absent on {cfg.branch} -- nothing to remove")
        return
    r = requests.delete(
        _repo_url(cfg, f"contents/{cfg.staged}"),
        headers=_headers(pat),
        json={
            "message": f"chore: drop staged copy now that it is live (Closes #{cfg.issue})",
            "sha": staged["sha"],
            "branch": cfg.branch,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  removed staged {cfg.staged} on {cfg.branch}")


def open_pr(pat: str, cfg: argparse.Namespace) -> int:
    r = requests.get(
        _repo_url(cfg, "pulls"),
        params={"head": f"{cfg.owner}:{cfg.branch}", "state": "open"},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    if r.json():
        num = r.json()[0]["number"]
        print(f"  reusing open PR #{num}")
        return num

    body = (
        f"Closes #{cfg.issue}\n\n"
        f"Moves the workflow staged at `{cfg.staged}` into `{cfg.workflow}`"
        + ("" if cfg.keep_staged else ", and removes the staged copy so the repo "
           "does not carry two versions that can drift")
        + ".\n\n"
        "Landed via the classic-PAT Contents API (ADR-0216) because the "
        "fine-grained PAT every agent session uses cannot push under "
        "`.github/workflows/` -- it lacks the `workflow` scope, and that "
        "exclusion is load-bearing.\n\n"
        f"This PR is itself the first exercise of the `{cfg.check}` check it "
        "installs: for `pull_request` events the workflow is evaluated from the "
        "merge ref, so it runs here before the merge.\n"
    )
    r = requests.post(
        _repo_url(cfg, "pulls"),
        headers=_headers(pat),
        json={
            "title": f"ci: add {Path(cfg.workflow).name} (Closes #{cfg.issue})",
            "head": cfg.branch,
            "base": "main",
            "body": body,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    num = r.json()["number"]
    print(f"  opened PR #{num}")
    return num


def head_sha(pat: str, cfg: argparse.Namespace, num: int) -> str:
    r = requests.get(_repo_url(cfg, f"pulls/{num}"), headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return r.json()["head"]["sha"]


def wait_for_check(pat: str, cfg: argparse.Namespace, sha: str) -> str:
    """Wait for the named check and return its conclusion.

    Returns the conclusion string, or "absent" if it never registered within the
    poll budget. Never raises on a red check -- a failing result is information
    the caller acts on, not an error in this script.
    """
    for i in range(1, CHECK_POLL_ATTEMPTS + 1):
        r = requests.get(
            _repo_url(cfg, f"commits/{sha}/check-runs"),
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        run = {c["name"]: c for c in r.json().get("check_runs", [])}.get(cfg.check)
        if run is None:
            print(f"  [{i}/{CHECK_POLL_ATTEMPTS}] {cfg.check}: not registered yet")
        elif run["status"] == "completed":
            print(f"  [{i}/{CHECK_POLL_ATTEMPTS}] {cfg.check}: {run['conclusion']}")
            return run["conclusion"] or "unknown"
        else:
            print(f"  [{i}/{CHECK_POLL_ATTEMPTS}] {cfg.check}: {run['status']}")
        time.sleep(CHECK_POLL_SLEEP_S)
    return "absent"


def wait_mergeable(pat: str, cfg: argparse.Namespace, num: int) -> bool:
    for i in range(1, MERGE_POLL_ATTEMPTS + 1):
        r = requests.get(
            _repo_url(cfg, f"pulls/{num}"), headers=_headers(pat), timeout=HTTP_TIMEOUT_S
        )
        r.raise_for_status()
        state = r.json().get("mergeable_state")
        print(f"  [{i}/{MERGE_POLL_ATTEMPTS}] mergeable_state={state}")
        if state in ("clean", "unstable"):
            # `unstable` = mergeable, but a NON-required check is pending or
            # failing. A newly installed check is not yet required, so it parks
            # the PR here. Required review and pr-sentinel are already satisfied
            # by this point, and the caller has separately inspected the check's
            # own conclusion.
            return True
        if state == "dirty":
            return False
        time.sleep(MERGE_POLL_SLEEP_S)
    return False


def merge_pr(pat: str, cfg: argparse.Namespace, num: int) -> None:
    r = requests.put(
        _repo_url(cfg, f"pulls/{num}/merge"),
        headers=_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    print(f"  merged PR #{num}")


def delete_branch(pat: str, cfg: argparse.Namespace) -> None:
    r = requests.delete(
        _repo_url(cfg, f"git/refs/heads/{cfg.branch}"),
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code in (204, 422, 404):
        print(f"  cleaned up remote branch {cfg.branch}")
        return
    r.raise_for_status()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True, help="Target repository name.")
    ap.add_argument("--issue", required=True, type=int, help="Issue the PR closes.")
    ap.add_argument("--staged", required=True, help="Staged path, e.g. docs/ci/tests.yml")
    ap.add_argument("--workflow", required=True, help="Destination under .github/workflows/")
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--branch", default=None, help="Default: ci/staged-workflow-<issue>")
    ap.add_argument("--check", default=DEFAULT_CHECK, help="Check to wait for.")
    ap.add_argument(
        "--strip-header-comment",
        action="store_true",
        help="Drop leading # comments (a staging preamble that stops being true once landed).",
    )
    ap.add_argument("--keep-staged", action="store_true", help="Do not remove the staged copy.")
    ap.add_argument(
        "--merge-on-red",
        action="store_true",
        help="Merge even if the installed check fails. Default is to stop and report.",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print the plan; no credentials, no writes.")
    cfg = ap.parse_args(argv)
    if cfg.branch is None:
        cfg.branch = f"ci/staged-workflow-{cfg.issue}"
    return cfg


def main() -> int:
    cfg = parse_args()
    target = f"{cfg.owner}/{cfg.repo}"

    if cfg.dry_run:
        print("DRY-RUN -- no credentials requested, no writes performed.\n")
        print(f"  target   : {target}")
        print(f"  read     : {cfg.staged} @ main")
        print(f"  write    : {cfg.workflow} on branch {cfg.branch}")
        print(f"  staged   : {'kept' if cfg.keep_staged else 'removed in the same PR'}")
        print(f"  header   : {'stripped' if cfg.strip_header_comment else 'preserved'}")
        print(f"  PR       : Closes #{cfg.issue}, waits for check `{cfg.check}`")
        print(f"  on red   : {'merge anyway' if cfg.merge_on_red else 'stop and report'}")
        return 0

    with classic_pat_session(reason=f"land {cfg.workflow} in {target}") as pat:
        if get_file(pat, cfg, cfg.workflow, "main"):
            print(f"{cfg.workflow} already exists on {target}@main -- nothing to do.")
            return 0

        print(f"Landing {cfg.workflow} in {target} ...")
        content = read_staged(pat, cfg)
        print(f"  read {cfg.staged} ({len(content):,} chars)")
        ensure_branch(pat, cfg, main_sha(pat, cfg))
        put_workflow(pat, cfg, content)
        if not cfg.keep_staged:
            delete_staged(pat, cfg)
        num = open_pr(pat, cfg)

        print(f"Waiting for `{cfg.check}` on PR #{num} ...")
        conclusion = wait_for_check(pat, cfg, head_sha(pat, cfg, num))

        if conclusion == "success":
            print("  green on its first run.")
        elif conclusion == "absent":
            print(
                f"  `{cfg.check}` never registered within the poll budget. The branch "
                f"and PR exist; inspect PR #{num} on GitHub.",
                file=sys.stderr,
            )
            return 1
        elif not cfg.merge_on_red:
            print(
                f"  `{cfg.check}` concluded `{conclusion}`. NOT merging.\n"
                f"  The workflow landed on the branch and PR #{num} is open, so the "
                f"failure is visible and fixable there. Re-run with --merge-on-red "
                f"to override.",
                file=sys.stderr,
            )
            return 1

        if not wait_mergeable(pat, cfg, num):
            print(
                f"PR #{num} did not reach a mergeable state. Inspect it on GitHub; "
                f"the branch and file are committed.",
                file=sys.stderr,
            )
            return 1
        merge_pr(pat, cfg, num)
        delete_branch(pat, cfg)
        print(f"Done. CI is live on {target}; #{cfg.issue} closed by the merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
