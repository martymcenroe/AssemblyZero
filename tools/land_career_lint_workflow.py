#!/usr/bin/env python3
"""One-shot: land career/.github/workflows/lint.yml via the classic-PAT Contents API (career #1236).

The fine-grained PAT lacks `workflow` scope, so a normal `git push` of a
`.github/workflows/*` file is rejected. This lands it the ADR-0216 way: the
classic PAT is gpg-decrypted in-process, consumed by `requests` directly (never
via gh / env / argv), and used to create a branch + commit the file + open a PR,
then squash-merge after pr-sentinel + Cerberus pass.

Run from AssemblyZero (for the poetry env + `_pat_session`):

    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/land_career_lint_workflow.py            # live
    poetry run python tools/land_career_lint_workflow.py --dry-run  # print the plan

The encrypted classic PAT must exist at ~/.secrets/classic-pat.gpg (ADR-0216).
Idempotent: reuses the branch/PR if a prior run was interrupted. Delete this
one-shot after it succeeds.
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

OWNER = "martymcenroe"
REPO = "career"
GH_API = "https://api.github.com"
BRANCH = "ci/1236-lint-workflow"
FILE_PATH = ".github/workflows/lint.yml"
HTTP_TIMEOUT_S = 30

# LF-only (the Contents API stores bytes verbatim -- never ship CRLF, per ADR-0216).
LINT_YML = (
    "name: lint\n"
    "on:\n"
    "  pull_request:\n"
    "  push:\n"
    "    branches: [main]\n"
    "jobs:\n"
    "  lint:\n"
    "    runs-on: ubuntu-latest\n"
    "    defaults:\n"
    "      run:\n"
    "        working-directory: dashboard\n"
    "    steps:\n"
    "      - uses: actions/checkout@v4\n"
    "      - uses: actions/setup-node@v4\n"
    "        with:\n"
    "          node-version: 20\n"
    "          cache: npm\n"
    "          cache-dependency-path: dashboard/package-lock.json\n"
    "      - run: npm ci\n"
    "      - run: npm run lint\n"
    "      - run: npm run typecheck\n"
)

COMMIT_MSG = "ci: add lint + typecheck workflow (Closes #1236)"
PR_TITLE = "ci: add lint + typecheck workflow (Closes #1236)"
PR_BODY = (
    "Adds `.github/workflows/lint.yml` -- server-side `npm run lint` + "
    "`npm run typecheck` enforcement on pull requests and push-to-main. This is "
    "the enforcement layer on top of the local lint rule that landed in #1183, "
    "so a push that skips local lint is still caught pre-merge.\n\n"
    "Landed via the in-process classic-PAT Contents API pattern (ADR-0216) "
    "because the fine-grained PAT deliberately lacks `workflow` scope.\n\n"
    "Verified locally from `dashboard/`: `npm run lint` 0 errors (warnings only), "
    "`npm run typecheck` clean -- so the workflow is green on `main` from the start.\n\n"
    "Closes #1236"
)


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="Print the plan; make no writes.")
    args = ap.parse_args()

    if args.dry_run:
        print(f"DRY-RUN: branch {BRANCH} -> commit {FILE_PATH} -> PR (Closes #1236) -> squash-merge.")
        print("--- lint.yml ---")
        print(LINT_YML)
        return 0

    with classic_pat_session() as pat:
        h = _headers(pat)

        # 1. Base SHA of main.
        r = requests.get(f"{GH_API}/repos/{OWNER}/{REPO}/git/ref/heads/main", headers=h, timeout=HTTP_TIMEOUT_S)
        r.raise_for_status()
        base_sha = r.json()["object"]["sha"]
        print(f"main @ {base_sha[:8]}")

        # 2. Create the branch (idempotent: 422 == already exists).
        r = requests.post(
            f"{GH_API}/repos/{OWNER}/{REPO}/git/refs",
            headers=h,
            json={"ref": f"refs/heads/{BRANCH}", "sha": base_sha},
            timeout=HTTP_TIMEOUT_S,
        )
        if r.status_code == 422:
            print(f"branch {BRANCH} already exists -- reusing")
        else:
            r.raise_for_status()
            print(f"created branch {BRANCH}")

        # 3. Commit the file via the Contents API (PUT). Include the existing blob
        #    sha if the file is already present on the branch (resumed run).
        content_b64 = base64.b64encode(LINT_YML.encode("utf-8")).decode("ascii")
        existing = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
            headers=h, params={"ref": BRANCH}, timeout=HTTP_TIMEOUT_S,
        )
        put_body = {"message": COMMIT_MSG, "content": content_b64, "branch": BRANCH}
        if existing.status_code == 200:
            put_body["sha"] = existing.json()["sha"]
        r = requests.put(
            f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
            headers=h, json=put_body, timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        print(f"committed {FILE_PATH} to {BRANCH}")

        # 4. Open the PR (reuse an existing open one for the branch).
        prs = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
            headers=h, params={"head": f"{OWNER}:{BRANCH}", "state": "open"}, timeout=HTTP_TIMEOUT_S,
        )
        prs.raise_for_status()
        if prs.json():
            pr = prs.json()[0]
            print(f"reusing PR #{pr['number']}")
        else:
            r = requests.post(
                f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
                headers=h,
                json={"title": PR_TITLE, "head": BRANCH, "base": "main", "body": PR_BODY},
                timeout=HTTP_TIMEOUT_S,
            )
            r.raise_for_status()
            pr = r.json()
            print(f"opened PR #{pr['number']}")
        num = pr["number"]

        # 5. Wait for `clean` (required check pr-sentinel green + Cerberus approval).
        #    lint is NOT a required check, so a transient `unstable` while it runs
        #    is fine -- we only merge on `clean`. `dirty` is a conflict; stop.
        for i in range(48):
            r = requests.get(f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{num}", headers=h, timeout=HTTP_TIMEOUT_S)
            r.raise_for_status()
            state = r.json().get("mergeable_state")
            print(f"[{i}] mergeable_state={state}")
            if state == "clean":
                break
            if state == "dirty":
                print("PR is dirty (merge conflict) -- resolve manually.")
                return 1
            time.sleep(10)
        else:
            print(f"Timed out waiting for `clean` -- inspect PR #{num} and merge manually if it looks good.")
            return 1

        # 6. Squash-merge (no --admin; branch protection is satisfied by `clean`).
        r = requests.put(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{num}/merge",
            headers=h, json={"merge_method": "squash"}, timeout=HTTP_TIMEOUT_S,
        )
        if not r.ok:
            print(f"merge failed: {r.status_code} {r.text[:300]}")
            return 1
        print(f"MERGED PR #{num} -- lint.yml is live on main. You can delete tools/land_career_lint_workflow.py now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
