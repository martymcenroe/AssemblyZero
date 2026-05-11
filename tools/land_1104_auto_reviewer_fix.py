#!/usr/bin/env python3
"""Land the #1104 auto-reviewer poll-loop fix via classic-PAT Contents API.

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.

The fix is a one-shot edit to `.github/workflows/auto-reviewer.yml` in
AssemblyZero. The fine-grained PAT cannot push workflow files (no
`workflow` scope, intentionally per ADR-0216 section 1). The canonical
pattern is to land such edits via the GitHub Contents API using an
in-process classic PAT (`tools/_pat_session.classic_pat_session()`).

What this script does:

  1. Read `.github/workflows/auto-reviewer.yml` from origin/main via
     Contents API.
  2. Apply the #1104 fix: replace the if/elif/else poll dispatch with a
     case statement that covers all 8 GitHub check-run conclusion values
     plus the empty/pending state.
  3. Validate the patch (idempotent: refuse to land if the file already
     contains the fixed case statement).
  4. Create a branch from main HEAD via API.
  5. PUT the patched file via Contents API (creates a commit on the
     branch).
  6. Open a PR with `Closes #1104` in title and body.
  7. Poll mergeable_state until clean (NOT just clean -- also accept
     unstable for self-referential cleanups per the
     fleet_delete_pr_sentinel pattern, since this PR's own check uses
     the SAME poll-loop being fixed).
  8. Squash-merge via API.

Issue: #1104 | Related: ADR-0216 (in-process classic PAT)
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
REPO = f"{GITHUB_USER}/AssemblyZero"
GH_API = "https://api.github.com"
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"
ISSUE_NUMBER = 1104
BRANCH = f"{ISSUE_NUMBER}-auto-reviewer-poll-conclusions"

HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 900

OLD_DISPATCH = """              if [ \"$STATUS\" = \"success\" ]; then
                echo \"  ✅ ${check_name}: passed\"
              elif [ \"$STATUS\" = \"failure\" ] || [ \"$STATUS\" = \"cancelled\" ]; then
                echo \"  ❌ ${check_name}: ${STATUS} — will NOT approve\"
                exit 1
              else
                echo \"  ⏳ ${check_name}: pending (attempt $((ATTEMPT+1))/${MAX_ATTEMPTS})\"
                ALL_PASSED=false
              fi"""

NEW_DISPATCH = """              # #1104: handle all 8 GitHub check-run conclusion values explicitly.
              # Empty/null STATUS (check hasn't reported yet) falls through to
              # the catch-all and is treated as pending.
              case \"$STATUS\" in
                success|neutral|skipped)
                  echo \"  ✅ ${check_name}: ${STATUS:-success}\"
                  ;;
                failure|cancelled|timed_out|action_required|stale)
                  echo \"  ❌ ${check_name}: ${STATUS} — will NOT approve\"
                  exit 1
                  ;;
                *)
                  echo \"  ⏳ ${check_name}: pending (attempt $((ATTEMPT+1))/${MAX_ATTEMPTS})\"
                  ALL_PASSED=false
                  ;;
              esac"""


def _headers(pat: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    h = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if extra:
        h.update(extra)
    return h


def _api(method: str, url: str, pat: str, **kw: Any) -> requests.Response:
    return requests.request(method, url, headers=_headers(pat), timeout=HTTP_TIMEOUT_S, **kw)


def read_workflow(pat: str) -> tuple[str, str]:
    """Fetch the current file content + sha from main. Returns (content_text, blob_sha)."""
    r = _api("GET", f"{GH_API}/repos/{REPO}/contents/{WORKFLOW_PATH}?ref=main", pat)
    if r.status_code >= 300:
        sys.exit(f"GET contents failed: {r.status_code} {r.text[:300]}")
    data = r.json()
    content = base64.b64decode(data["content"]).decode("utf-8")
    return content, data["sha"]


def apply_patch(content: str) -> str | None:
    """Apply the #1104 fix. Returns the patched text, or None if already patched."""
    if "case \"$STATUS\" in" in content and "action_required|stale)" in content:
        return None  # already patched
    if OLD_DISPATCH not in content:
        sys.exit(
            "ERROR: expected if/elif/else dispatch block not found. The "
            "workflow file may have drifted since this script was written. "
            "Re-derive the patch from the current file."
        )
    return content.replace(OLD_DISPATCH, NEW_DISPATCH)


def main_head_sha(pat: str) -> str:
    r = _api("GET", f"{GH_API}/repos/{REPO}/git/refs/heads/main", pat)
    if r.status_code >= 300:
        sys.exit(f"GET main ref failed: {r.status_code}")
    return r.json()["object"]["sha"]


def create_branch(pat: str, main_sha: str) -> None:
    # Idempotent: 422 if branch already exists -- swallow and proceed.
    r = _api(
        "POST", f"{GH_API}/repos/{REPO}/git/refs", pat,
        json={"ref": f"refs/heads/{BRANCH}", "sha": main_sha},
    )
    if r.status_code == 422:
        print(f"  branch {BRANCH} already exists, reusing")
        return
    if r.status_code >= 300:
        sys.exit(f"POST branch failed: {r.status_code} {r.text[:300]}")


def get_blob_sha_on_branch(pat: str) -> str | None:
    r = _api("GET", f"{GH_API}/repos/{REPO}/contents/{WORKFLOW_PATH}?ref={BRANCH}", pat)
    if r.status_code >= 300:
        return None
    return r.json()["sha"]


def put_file(pat: str, new_content: str, blob_sha: str) -> None:
    # GitHub Contents API stores bytes verbatim. CRLF-normalize so we don't
    # flip the whole file's line endings (memory: 2026-04-30 incident).
    new_bytes = new_content.replace("\r\n", "\n").encode("utf-8")
    payload = {
        "message": f"fix: auto-reviewer poll handles all 8 conclusion values (Closes #{ISSUE_NUMBER})",
        "content": base64.b64encode(new_bytes).decode("ascii"),
        "branch": BRANCH,
        "sha": blob_sha,
    }
    r = _api("PUT", f"{GH_API}/repos/{REPO}/contents/{WORKFLOW_PATH}", pat, json=payload)
    if r.status_code >= 300:
        sys.exit(f"PUT contents failed: {r.status_code} {r.text[:300]}")


def open_pr(pat: str) -> int:
    body = (
        f"Closes #{ISSUE_NUMBER}\n\n"
        "Replaces the if/elif/else dispatch in `.github/workflows/auto-reviewer.yml` "
        "with a `case` statement that handles all 8 GitHub check-run conclusion values:\n\n"
        "- `success`, `neutral`, `skipped` -> pass\n"
        "- `failure`, `cancelled`, `timed_out`, `action_required`, `stale` -> fail (exit 1)\n"
        "- empty/null -> pending (poll loop continues)\n\n"
        "Before this change, the four conclusions `timed_out`, `action_required`, `stale`, and `neutral` "
        "fell through to the else branch and were treated as pending until the 30-attempt timeout, "
        "burning ~10 minutes per stuck PR. After this change they fail fast.\n\n"
        "Fleet-wide impact is automatic because consumer repos call this workflow as "
        "`uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main` -- the next "
        "PR they open picks up the new behavior.\n"
    )
    r = _api(
        "POST", f"{GH_API}/repos/{REPO}/pulls", pat,
        json={
            "title": f"fix: auto-reviewer poll handles all 8 conclusion values (Closes #{ISSUE_NUMBER})",
            "head": BRANCH,
            "base": "main",
            "body": body,
        },
    )
    if r.status_code >= 300:
        # Maybe PR already exists -- find it
        existing = _api(
            "GET", f"{GH_API}/repos/{REPO}/pulls?head={GITHUB_USER}:{BRANCH}&state=open", pat,
        )
        if existing.status_code == 200 and existing.json():
            pr_n = existing.json()[0]["number"]
            print(f"  PR #{pr_n} already exists, reusing")
            return pr_n
        sys.exit(f"POST PR failed: {r.status_code} {r.text[:300]}")
    return r.json()["number"]


def wait_for_mergeable(pat: str, pr_n: int) -> None:
    """Wait for mergeable_state to be 'clean' or 'unstable' (self-referential check)."""
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    while time.time() < deadline:
        r = _api("GET", f"{GH_API}/repos/{REPO}/pulls/{pr_n}", pat)
        if r.status_code >= 300:
            time.sleep(POLL_INTERVAL_S)
            continue
        state = r.json().get("mergeable_state")
        print(f"  PR #{pr_n}: mergeable_state={state}")
        if state in ("clean", "unstable"):
            return
        time.sleep(POLL_INTERVAL_S)
    sys.exit(f"Timed out waiting for PR #{pr_n} to be mergeable")


def squash_merge(pat: str, pr_n: int) -> None:
    r = _api("PUT", f"{GH_API}/repos/{REPO}/pulls/{pr_n}/merge", pat,
             json={"merge_method": "squash"})
    if r.status_code >= 300:
        sys.exit(f"PUT merge failed: {r.status_code} {r.text[:300]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Land #1104 auto-reviewer fix.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the patched YAML to stdout, take no action.")
    args = parser.parse_args()

    if args.dry_run:
        # Use a no-PAT path for dry-run -- just compute the patch from a local
        # copy if available. Otherwise instruct the user.
        local = Path(__file__).resolve().parents[1] / WORKFLOW_PATH
        if not local.is_file():
            print("Dry-run requires the workflow file in the current worktree. "
                  "Run from inside an AssemblyZero checkout.", file=sys.stderr)
            return 1
        content = local.read_text(encoding="utf-8", errors="replace")
        new_content = apply_patch(content)
        if new_content is None:
            print("Already patched. No change needed.")
            return 0
        # Write to a tempfile rather than stdout -- the patched YAML contains
        # emoji (✅, ❌, ⏳) from the existing file that Windows' CP1252 stdout
        # default can't encode (#837). Tempfile is more useful anyway: the
        # user can diff or open it in an editor.
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".yml",
            prefix="auto-reviewer-patched-", delete=False,
        )
        tmp.write(new_content)
        tmp.close()
        print(f"Patched YAML written to: {tmp.name}")
        print(f"Diff against current: diff -u '{local}' '{tmp.name}'")
        return 0

    with classic_pat_session() as pat:
        print("1. Reading current workflow file from main...")
        content, _main_blob_sha = read_workflow(pat)

        print("2. Applying patch...")
        new_content = apply_patch(content)
        if new_content is None:
            print("   Already patched. Nothing to do.")
            return 0

        print(f"3. Creating branch {BRANCH}...")
        main_sha = main_head_sha(pat)
        create_branch(pat, main_sha)

        print(f"4. PUTting patched file via Contents API on {BRANCH}...")
        branch_blob_sha = get_blob_sha_on_branch(pat)
        if branch_blob_sha is None:
            sys.exit("Failed to read blob sha on new branch -- aborting")
        put_file(pat, new_content, branch_blob_sha)

        print("5. Opening PR...")
        pr_n = open_pr(pat)
        print(f"   PR #{pr_n} -- https://github.com/{REPO}/pull/{pr_n}")

        print("6. Waiting for mergeable_state...")
        wait_for_mergeable(pat, pr_n)

        print("7. Squash-merging...")
        squash_merge(pat, pr_n)

    print(f"\nDone. #{ISSUE_NUMBER} fix landed via PR #{pr_n}.")
    print("Consumer repos pick up the new poll-loop behavior on their next PR run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
