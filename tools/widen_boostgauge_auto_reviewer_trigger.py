"""One-shot: make boostgauge's Auto Review run on speedrun branches.

Closes boostgauge#90.

The problem: .github/workflows/auto-reviewer.yml only triggers on pull
requests that target main. Every speedrun PR targets a speedrun-attempt-*
branch, so the automated review never runs during a recorded take.

The fix: widen the trigger to include speedrun-attempt-* and
hardening-run-* branches.

Why this script exists: the everyday fine-grained token is not allowed to
edit workflow files. This script uses the gpg-encrypted classic token via
_pat_session (ADR-0216) — decrypted only inside this process — and lands
the change the normal way: branch -> pull request -> automatic review ->
squash merge. No branch protection is touched, nothing is forced.

Run it yourself (the agent must not):

    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/widen_boostgauge_auto_reviewer_trigger.py            # dry run
    poetry run python tools/widen_boostgauge_auto_reviewer_trigger.py --apply    # do it
"""

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from _pat_session import classic_pat_session  # noqa: E402

GH_API = "https://api.github.com"
OWNER = "martymcenroe"
REPO = "boostgauge"
FILE_PATH = ".github/workflows/auto-reviewer.yml"
OLD_LINE = "    branches: [main]"
NEW_LINE = "    branches: [main, 'speedrun-attempt-*', 'hardening-run-*']"
WORK_BRANCH = "90-widen-auto-reviewer-trigger"
PR_TITLE = "ci: run Auto Review on speedrun branches too (Closes #90)"
PR_BODY = (
    "Closes #90\n\n"
    "Auto Review only fired on PRs targeting main. Speedrun PRs target "
    "speedrun-attempt-* branches, so the automated review never ran during "
    "a recorded take. This widens the trigger to those branches (plus "
    "hardening-run-* for off-camera hardening runs).\n\n"
    "Landed via the classic-token one-shot pattern (ADR-0216) because the "
    "everyday token cannot edit workflow files.\n\n"
    "\U0001F916 Generated with Claude Code"
)
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGE_TIMEOUT_S = 300


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Actually land the change (default: dry run, no writes)",
    )
    args = parser.parse_args()

    with classic_pat_session() as pat:
        # 1. Fetch the current workflow file from main.
        r = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
            params={"ref": "main"},
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        info = r.json()
        raw = base64.b64decode(info["content"])
        # Contents API stores bytes verbatim — normalize Windows line
        # endings so the diff is one line, not the whole file.
        text = raw.replace(b"\r\n", b"\n").decode("utf-8")

        if NEW_LINE in text:
            print("Already widened — nothing to do.")
            return 0
        if text.count(OLD_LINE) != 1:
            print(f"ERROR: expected exactly one '{OLD_LINE.strip()}' line; "
                  f"found {text.count(OLD_LINE)}. Refusing to guess.")
            return 1

        new_text = text.replace(OLD_LINE, NEW_LINE, 1)

        print(f"File:   {FILE_PATH} @ main (sha {info['sha'][:9]})")
        print(f"Change: {OLD_LINE.strip()}")
        print(f"     -> {NEW_LINE.strip()}")

        if not args.apply:
            print("\nDry run. Re-run with --apply to land it.")
            return 0

        # 2. Branch from main.
        r = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/git/refs/heads/main",
            headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        main_sha = r.json()["object"]["sha"]
        r = requests.post(
            f"{GH_API}/repos/{OWNER}/{REPO}/git/refs",
            headers=_headers(pat),
            json={"ref": f"refs/heads/{WORK_BRANCH}", "sha": main_sha},
            timeout=HTTP_TIMEOUT_S,
        )
        if r.status_code == 422 and "already exists" in r.text:
            print(f"Branch {WORK_BRANCH} already exists — reusing.")
        else:
            r.raise_for_status()

        # 3. Put the updated file on the branch.
        r = requests.put(
            f"{GH_API}/repos/{OWNER}/{REPO}/contents/{FILE_PATH}",
            headers=_headers(pat),
            json={
                "message": PR_TITLE,
                "content": base64.b64encode(new_text.encode("utf-8")).decode("ascii"),
                "sha": info["sha"],
                "branch": WORK_BRANCH,
            },
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        print(f"Committed to {WORK_BRANCH}.")

        # 4. Open the pull request.
        r = requests.post(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
            headers=_headers(pat),
            json={"title": PR_TITLE, "head": WORK_BRANCH,
                  "base": "main", "body": PR_BODY},
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        pr_number = r.json()["number"]
        print(f"PR #{pr_number} opened. Waiting for checks + automatic review...")

        # 5. Wait until mergeable, then squash-merge.
        deadline = time.time() + MERGE_TIMEOUT_S
        state = "unknown"
        while time.time() < deadline:
            r = requests.get(
                f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{pr_number}",
                headers=_headers(pat), timeout=HTTP_TIMEOUT_S,
            )
            r.raise_for_status()
            state = r.json().get("mergeable_state", "unknown")
            print(f"  state: {state}")
            if state in ("clean", "unstable"):
                break
            time.sleep(POLL_INTERVAL_S)
        else:
            print(f"Timed out waiting (last state: {state}). "
                  f"PR #{pr_number} is open — finish it manually.")
            return 1

        r = requests.put(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{pr_number}/merge",
            headers=_headers(pat),
            json={"merge_method": "squash"},
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        print(f"Merged: {r.json().get('sha', '')[:9]}  (PR #{pr_number}, closes #90)")
        print("Done. Next: re-point the speedrun start tag (see boostgauge #88).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
