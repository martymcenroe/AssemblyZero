#!/usr/bin/env python3
"""Land the auto-reviewer Dependabot skip (#1251) via the Contents API.

Why this script exists instead of `git push`
--------------------------------------------
The change touches `.github/workflows/auto-reviewer.yml`. The fine-grained PAT
deliberately has no `workflow` scope (ADR-0216 section 1 -- agents must not be
able to rewrite their own guardrails), so `git push` is refused by GitHub:

    refusing to allow a Personal Access Token to create or update workflow
    `.github/workflows/auto-reviewer.yml` without `workflow` scope

The sanctioned path is the GitHub Contents API using the in-process classic-PAT
context manager. The PAT is gpg-decrypted inside THIS process, lives only as a
local heap variable inside the `with` block, and is consumed by `requests`
directly -- never via `gh`, never via env, never via argv.

WHO RUNS THIS
-------------
The OPERATOR runs this, not an agent. When an agent runs it, the Python process
is the agent's child and the "PAT lives only in this process's heap" guarantee
no longer holds (ADR-0216 gotcha 1).

What it does
------------
1. Reads the already-committed local copy of the workflow file, CRLF-normalized.
2. Refuses if that copy does not actually contain the skip (guard against
   landing a no-op), or if `main` already has it (idempotent re-run).
3. Creates branch `1251-dependabot-skip` from `main` on origin.
4. PUTs the file onto that branch.
5. Opens a PR carrying `Closes #1251`.
6. Waits for a mergeable state (accepts `clean` AND `unstable`), then squash-merges.
7. Verifies `main` now carries the skip, and prints the post-merge checks.

Usage
-----
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_dependabot_skip_1251.py            # dry run
    poetry run python tools/land_dependabot_skip_1251.py --apply    # live

Dry run makes only GET calls and prints the plan.
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = "AssemblyZero"
GH_API = "https://api.github.com"
FILE_PATH = ".github/workflows/auto-reviewer.yml"
BRANCH = "1251-dependabot-skip"
ISSUE = 1251
HTTP_TIMEOUT_S = 30

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_FILE = REPO_ROOT / FILE_PATH

# The substring that proves the skip is present. Kept narrow so a reformat of
# the surrounding condition does not silently defeat the guard.
SKIP_MARKER = "github.event.pull_request.user.login != 'dependabot[bot]'"

PR_TITLE = "fix(cerberus): skip Dependabot PRs in auto-reviewer — Cerberus is the agent fence (Closes #1251)"

PR_BODY = """\
Cerberus is the agent fence, not the Dependabot enabler.

On an agent PR the author is the repo owner, so GitHub's no-self-approval rule leaves no
eligible reviewer and Cerberus has to manufacture one. On a Dependabot PR the author is
Dependabot: the owner already is an eligible third-party reviewer, so there is nothing at
that gate to guard.

Because the job ran anyway, it reached for an App token from secrets that do not exist in
the Dependabot secrets store — runs triggered by `dependabot[bot]` resolve secrets from
that store, not the Actions store — exited in seconds with `Input required and not
supplied: app-id`, and left a failed required check behind. Nine Dependabot PRs sit blocked
in this repo today: #2096, #2097, #2099, #2100, #2101, #2102, #2103, #2111, #2112.

The decision dates to 2026-05-12 and the exact one-line procedure to #1251. Neither landed.

## The change

`.github/workflows/auto-reviewer.yml`, the `auto-review` job condition:

```yaml
if: (github.event_name == 'pull_request' || github.event_name == 'workflow_call') && github.event.pull_request.user.login != 'dependabot[bot]'
```

The purpose is written into the file beside the condition. Standard 0025's principle applies
here too: a countermeasure has to be something the reader consumes structurally, and the
original ruling asked for the purpose to live where the machinery lives.

## Blast radius

This is a reusable workflow consumed via `@main` across the fleet. Agent PRs are unaffected —
their author is never `dependabot[bot]`, so the condition is unchanged for them. It does not
touch pr-sentinel, branch protection, or any other workflow.

## Rollback

Revert this PR. Single commit, single file, one condition.

## Verification after merge

The next Dependabot PR should show no `auto-review` check at all, rather than a failed one.
The nine already-open PRs keep their existing failed check until their head SHA changes,
since a job that never runs cannot retract a conclusion recorded days ago — they need a
Dependabot rebase, or to be handled by `tools/dependabot_review.py`.

Landed via the Contents API per ADR-0216: the fine-grained PAT has no `workflow` scope by
design, so `git push` is refused on this path.

Closes #1251
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(url: str, pat: str, **kw: Any) -> requests.Response:
    return requests.get(url, headers=_headers(pat), timeout=HTTP_TIMEOUT_S, **kw)


def read_local_content() -> bytes:
    """Return the local workflow bytes, LF-normalized.

    `core.autocrlf=true` keeps CRLF in the Windows working tree while blobs stay
    LF. A normal commit normalizes; the Contents API stores bytes verbatim, so
    without this the whole file's line endings flip on origin and the diff
    becomes a whole-file rewrite (ADR-0216 gotcha 3).
    """
    return LOCAL_FILE.read_bytes().replace(b"\r\n", b"\n")


def remote_file(pat: str, ref: str) -> dict[str, Any]:
    r = _get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}",
        pat,
        params={"ref": ref},
    )
    r.raise_for_status()
    return r.json()


def wait_for_mergeable(pat: str, number: int, timeout_s: int = 900) -> str:
    """Poll until the PR is mergeable, accepting `clean` or `unstable`.

    `unstable` is accepted because a PR can legitimately carry a non-required
    check that is still running or has failed while every required check has
    passed. Strict `clean`-only polling waits forever in that case
    (ADR-0216 gotcha 4).
    """
    deadline = time.time() + timeout_s
    last = "?"
    while time.time() < deadline:
        r = _get(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{number}", pat)
        r.raise_for_status()
        last = r.json().get("mergeable_state", "?")
        if last in ("clean", "unstable"):
            return last
        print(f"  mergeable_state={last} ...")
        time.sleep(15)
    raise RuntimeError(f"PR #{number} never became mergeable (last state: {last})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="actually create the branch, PR and merge. Default is a dry run.",
    )
    args = ap.parse_args()

    local = read_local_content()
    if SKIP_MARKER not in local.decode("utf-8"):
        print(
            f"REFUSING: {LOCAL_FILE} does not contain the skip marker.\n"
            f"  expected substring: {SKIP_MARKER}\n"
            "Check out the branch carrying the change before running this.",
            file=sys.stderr,
        )
        return 2

    print(f"Local file OK — {len(local)} bytes, LF-normalized, skip marker present.")
    print(f"Target: {GITHUB_USER}/{REPO}  file: {FILE_PATH}  branch: {BRANCH}")
    print()
    print("BLAST RADIUS: this is a reusable workflow consumed via @main across the")
    print("fleet. Agent PRs are unaffected; Dependabot PRs stop triggering auto-review.")
    print()

    reason = f"land the auto-reviewer Dependabot skip (#{ISSUE}) in {GITHUB_USER}/{REPO}"

    with classic_pat_session(reason=reason) as pat:
        main_file = remote_file(pat, "main")
        if SKIP_MARKER in base64.b64decode(main_file["content"]).decode("utf-8"):
            print("main already carries the skip — nothing to do.")
            return 0

        main_ref = _get(f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/ref/heads/main", pat)
        main_ref.raise_for_status()
        base_sha = main_ref.json()["object"]["sha"]
        print(f"main is at {base_sha[:8]}; file blob is {main_file['sha'][:8]}")

        if not args.apply:
            print()
            print("DRY RUN — would now:")
            print(f"  1. create refs/heads/{BRANCH} at {base_sha[:8]}")
            print(f"  2. PUT {FILE_PATH} ({len(local)} bytes) onto {BRANCH}")
            print(f"  3. open a PR titled: {PR_TITLE}")
            print("  4. wait for mergeable (clean|unstable), then squash-merge")
            print("  5. verify main carries the skip")
            print()
            print("Re-run with --apply to execute.")
            return 0

        # 1. branch
        r = requests.post(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs",
            headers=_headers(pat),
            json={"ref": f"refs/heads/{BRANCH}", "sha": base_sha},
            timeout=HTTP_TIMEOUT_S,
        )
        if r.status_code == 422:
            print(f"branch {BRANCH} already exists on origin — reusing it")
        else:
            r.raise_for_status()
            print(f"created refs/heads/{BRANCH}")

        # 2. file
        branch_file = remote_file(pat, BRANCH)
        r = requests.put(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{FILE_PATH}",
            headers=_headers(pat),
            json={
                "message": (
                    "fix(cerberus): skip Dependabot PRs in auto-reviewer\n\n"
                    "Cerberus is the agent fence, not the Dependabot enabler.\n\n"
                    f"Closes #{ISSUE}"
                ),
                "content": base64.b64encode(local).decode("ascii"),
                "sha": branch_file["sha"],
                "branch": BRANCH,
            },
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        print(f"PUT {FILE_PATH} -> commit {r.json()['commit']['sha'][:8]}")

        # 3. PR
        r = requests.post(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
            headers=_headers(pat),
            json={"title": PR_TITLE, "head": BRANCH, "base": "main", "body": PR_BODY},
            timeout=HTTP_TIMEOUT_S,
        )
        if r.status_code == 422 and "already exists" in r.text:
            existing = _get(
                f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
                pat,
                params={"head": f"{GITHUB_USER}:{BRANCH}", "state": "open"},
            )
            existing.raise_for_status()
            number = existing.json()[0]["number"]
            print(f"PR already open: #{number}")
        else:
            r.raise_for_status()
            number = r.json()["number"]
            print(f"opened PR #{number}")

        # 4. merge
        print(f"waiting for PR #{number} to become mergeable ...")
        state = wait_for_mergeable(pat, number)
        print(f"mergeable_state={state} — squash-merging")
        r = requests.put(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{number}/merge",
            headers=_headers(pat),
            json={"merge_method": "squash"},
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        print(f"merged: {r.json().get('sha', '?')[:8]}")

        # 5. verify
        after = remote_file(pat, "main")
        if SKIP_MARKER in base64.b64decode(after["content"]).decode("utf-8"):
            print("VERIFIED: main now carries the Dependabot skip.")
        else:
            print("VERIFY FAILED: main does not carry the skip.", file=sys.stderr)
            return 1

    print()
    print("Next: the branch still exists locally and is now a squash-merge orphan.")
    print("Clean it up with the ADR-0217 graft recipe, not `branch -D`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
