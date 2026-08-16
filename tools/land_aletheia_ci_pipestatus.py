#!/usr/bin/env python3
"""Land the CI pytest exit-code fix in the Aletheia repository.

Aletheia issue #831.

The `test` job pipes pytest into `tee`, so the step exits with tee's status.
GitHub Actions runs `bash -e` but not `pipefail`, and nothing afterwards
inspects the real code — the follow-up logic only verifies that tests were
*collected*, never that they *passed*. The check therefore reported success
over a red suite.

This lands a two-line fix (`EXIT_CODE=${PIPESTATUS[0]}` and a trailing
`exit $EXIT_CODE`), matching the `integration-tests` step in the same file,
which already handles it correctly.

Why this script exists at all
-----------------------------
The change touches `.github/workflows/`, and the fine-grained agent PAT
deliberately lacks `workflow` scope (ADR-0216 §1), so a direct push is refused
by the remote. The change lands via the GitHub Contents API using the in-process
classic-PAT context manager.

OPERATOR RUNS THIS. NOT AN AGENT.
    Per `_pat_session` module contract: a script importing that module must be
    run by the operator in their own shell. Invoked from an agent's Bash tool,
    the Python process becomes the agent's child and its heap is theoretically
    readable while the PAT is in scope.

Usage
-----
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_aletheia_ci_pipestatus.py            # dry run
    poetry run python tools/land_aletheia_ci_pipestatus.py --apply    # land it

Dry run performs every read-only step (fetches the remote file, diffs it
against the local replacement) and stops before any write.

Required PAT scopes: `repo`, `workflow`.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import sys
import time
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GITHUB_USER = "martymcenroe"
REPO = "Aletheia"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30

WORKFLOW_PATH = ".github/workflows/ci.yml"
BRANCH = "831-ci-pytest-exit-code"
ISSUE = 831

# The corrected workflow, produced and validated alongside the diagnosis.
LOCAL_FILE = (
    Path("C:/Users/mcwiz/Projects/Aletheia/data/scratch-20260809-backlog/ci.yml.fixed")
)

PR_TITLE = (
    "fix(ci): propagate pytest's real exit code so a failing suite fails "
    f"the check (Closes #{ISSUE})"
)

PR_BODY = f"""Closes #{ISSUE}

## The defect

`.github/workflows/ci.yml` pipes pytest into `tee`, so the step exits with
**`tee`'s** status rather than pytest's. GitHub Actions runs `bash -e` but not
`pipefail`, and nothing afterwards inspects the real code — the follow-up logic
verifies only that tests were *collected*, never that they *passed*.

The `test` job therefore reported success whenever pytest collected at least one
test, including when tests failed.

## Proof

PR #805, CI run `31337211982`:

```
tests/compliance/test_index_consistency.py::TestIndexConsistency::test_audit_index_complete FAILED
```

`gh pr checks 805` for that same run reported `test  pass`. A failing test and a
passing check, from one run.

The pipe was introduced in `5789741` (2026-01-10), so this check has been able
to certify a red suite for roughly seven months. It is also why the fleet
dependabot tool and CI disagreed: the tool calls pytest directly, saw exit 1,
and was correct.

## The change

Capture and propagate the real status, matching the `integration-tests` step in
the same file which already does this:

```yaml
EXIT_CODE=${{PIPESTATUS[0]}}
...
exit $EXIT_CODE
```

The collection check is kept — it guards a genuinely different failure (a green
run that silently collected nothing).

## Blast radius

**Expect red.** This surfaces whatever the check has been hiding. That is the
intent and should not be suppressed. The known audit-index failure is already
repaired on main, so the tree may be clean, but that is unverified until this
runs.

Risk of not landing it: the `test` check keeps certifying suites it has not
verified.

## Rollback

`git revert` on the workflow file.

## Landing note

Landed via the GitHub Contents API using the in-process classic-PAT pattern
(AssemblyZero ADR-0216) — the agent PAT deliberately lacks `workflow` scope, so
this path is a human checkpoint by design.
"""


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_file(path: str, pat: str, ref: str = "main") -> dict[str, Any]:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{path}",
        params={"ref": ref},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()


def get_branch_head(branch: str, pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/{branch}",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def branch_exists(branch: str, pat: str) -> bool:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs/heads/{branch}",
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    return r.status_code == 200


def create_branch(branch: str, source_sha: str, pat: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/git/refs",
        headers=_gh_headers(pat),
        json={"ref": f"refs/heads/{branch}", "sha": source_sha},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def put_file(
    path: str, content: bytes, file_sha: str, message: str, branch: str, pat: str
) -> None:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/contents/{path}",
        headers=_gh_headers(pat),
        json={
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
            "sha": file_sha,
            "branch": branch,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def find_open_pr(branch: str, pat: str) -> int | None:
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
        params={"head": f"{GITHUB_USER}:{branch}", "state": "open"},
        headers=_gh_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    prs = r.json()
    return prs[0]["number"] if prs else None


def create_pr(head: str, base: str, title: str, body: str, pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls",
        headers=_gh_headers(pat),
        json={"title": title, "head": head, "base": base, "body": body},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["number"]


def wait_for_mergeable(pr_number: int, pat: str, timeout_s: int = 900) -> str:
    """Poll until the PR is mergeable.

    Accepts `unstable` as well as `clean`. This change makes a previously
    always-green check capable of failing, so the very PR that introduces it can
    legitimately sit at `unstable` — strict-clean polling would wait forever on
    the check it is fixing. `gh pr merge --squash` succeeds in both states.

    `dirty` means a merge conflict and is returned immediately.
    """
    deadline = time.time() + timeout_s
    state = "unknown"
    while time.time() < deadline:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{pr_number}",
            headers=_gh_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        state = r.json().get("mergeable_state") or "unknown"
        print(f"  mergeable_state: {state}")
        if state in ("clean", "unstable", "dirty"):
            return state
        time.sleep(15)
    return state


def merge_pr(pr_number: int, pat: str) -> str:
    r = requests.put(
        f"{GH_API}/repos/{GITHUB_USER}/{REPO}/pulls/{pr_number}/merge",
        headers=_gh_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["sha"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the write. Without it, the run is read-only.",
    )
    args = parser.parse_args()

    if not LOCAL_FILE.exists():
        print(f"ERROR: replacement file not found: {LOCAL_FILE}")
        return 1

    # CRLF normalize. The working tree is Windows-checked-out, and the Contents
    # API stores bytes verbatim — without this the whole file's line endings
    # flip on origin and the diff becomes unreadable.
    content = LOCAL_FILE.read_bytes().replace(b"\r\n", b"\n")

    reason = f"land the CI workflow exit-code fix in {GITHUB_USER}/{REPO}"

    with classic_pat_session(reason=reason) as pat:
        remote = get_file(WORKFLOW_PATH, pat)
        remote_bytes = base64.b64decode(remote["content"])

        if remote_bytes == content:
            print("Remote already matches the replacement. Nothing to do.")
            return 0

        print(f"=== diff: origin/main {WORKFLOW_PATH} -> replacement ===")
        diff = difflib.unified_diff(
            remote_bytes.decode("utf-8").splitlines(),
            content.decode("utf-8").splitlines(),
            fromfile="origin/main",
            tofile="replacement",
            lineterm="",
        )
        for line in diff:
            print(line)

        if not args.apply:
            print("\nDRY RUN — no write performed. Re-run with --apply to land.")
            return 0

        if branch_exists(BRANCH, pat):
            print(f"Branch {BRANCH} already exists; reusing it.")
        else:
            head = get_branch_head("main", pat)
            create_branch(BRANCH, head, pat)
            print(f"Created branch {BRANCH} from main@{head[:7]}")

        # Re-read the file's sha ON THE BRANCH; on a reused branch it differs
        # from main's and a stale sha is rejected.
        branch_file = get_file(WORKFLOW_PATH, pat, ref=BRANCH)
        put_file(
            WORKFLOW_PATH,
            content,
            branch_file["sha"],
            f"fix(ci): propagate pytest's real exit code (Closes #{ISSUE})",
            BRANCH,
            pat,
        )
        print("Committed the workflow change to the branch.")

        pr_number = find_open_pr(BRANCH, pat)
        if pr_number:
            print(f"Reusing existing PR #{pr_number}")
        else:
            pr_number = create_pr(BRANCH, "main", PR_TITLE, PR_BODY, pat)
            print(f"Opened PR #{pr_number}")

        print("Waiting for the PR to become mergeable...")
        state = wait_for_mergeable(pr_number, pat)

        if state == "dirty":
            print("PR has a merge conflict. Resolve it, then re-run.")
            return 1
        if state not in ("clean", "unstable"):
            print(f"PR did not become mergeable (state={state}). Not merging.")
            return 1

        sha = merge_pr(pr_number, pat)
        print(f"Merged PR #{pr_number} as {sha[:7]}")

    print(
        "\nDone. Next CI run will report pytest's real status.\n"
        "Expect red if anything was failing behind the old check — that is the point."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
