#!/usr/bin/env python3
"""Pin Hermes CI workflow refs to commit SHAs via the classic-PAT Contents API.

martymcenroe/Hermes#669.

Hermes's merge gate is a reusable workflow pinned to `@main` in another repo,
and its CI actions are pinned to the mutable tag `@v4`. A change upstream --
accidental or hostile -- silently changes what gates Hermes PRs, with no
Hermes-side commit and nothing to review. This pins all three to commit SHAs.

WHY A SCRIPT INSTEAD OF `git push`:
The fine-grained PAT used for normal Hermes work cannot create or update files
under `.github/workflows/` (GitHub rejects it: "without `workflow` scope").
ADR-0216 (in-process classic-PAT decryption) is the sanctioned path: the classic
PAT is gpg-decrypted inside THIS Python process, used for REST calls, and never
written to env / argv / disk.

REQUIRED CLASSIC-PAT SCOPES: repo (full) + workflow.

OPERATIONAL RULE (ADR-0216):
    The OPERATOR runs this script in their own Git Bash. An agent must NEVER
    invoke it via its Bash tool -- the spawned Python process would be the
    agent's child and its heap (holding the decrypted PAT for a few seconds) is
    theoretically agent-readable.

    Also confirm ~/.gnupg/gpg-agent.conf has `default-cache-ttl 0` /
    `max-cache-ttl 0` (then `gpgconf --kill gpg-agent`) so a sibling process
    cannot silently decrypt the PAT while a passphrase is cached.

USAGE (run from the AssemblyZero repo so poetry resolves `requests`):
    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/hermes_pin_workflow_shas.py            # dry-run
    poetry run python tools/hermes_pin_workflow_shas.py --apply    # land it

Default is dry-run: it fetches both files, computes the edits, prints a diff
summary, and mutates nothing. The source contains no command from the universal
CLAUDE.md "Banned commands (ALWAYS)" table, so the canonical `--apply` gate
applies -- NOT `--execute`.

HOW IT AVOIDS WRITING THE WRONG THING:
It does NOT embed the new file contents. It fetches each workflow from main,
applies exact string replacements, and asserts every expected replacement
actually changed something -- aborting if a pattern is missing or if a file
already differs from what is expected. A pin landed against an unexpected file
is worse than no pin, because it looks reviewed.

Idempotent: if every ref on main is already a SHA, it reports that and exits 0.
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
REPO = "Hermes"
GH_API = "https://api.github.com"
BRANCH = "669-pin-workflow-shas"
PR_TITLE = "security: pin CI workflow refs to commit SHAs (Closes #669)"
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 900

# ---------------------------------------------------------------------------
# The pins.
#
# Resolved 2026-08-28. Each entry is (mutable_ref, pinned_ref).
#
# The trailing version comment is REQUIRED, not decoration: Dependabot (#794)
# reads `@<sha> # v4` and updates both halves on a bump. Without the comment the
# pin is unreadable to a human and unmaintained by the bot.
#
# AssemblyZero's SHA is its main HEAD at the time of resolution -- i.e. exactly
# what `@main` pointed at, so this pin changes nothing about current behavior.
# It only stops the ref moving without review.
# ---------------------------------------------------------------------------

ASSEMBLYZERO_SHA = "71750f3a5b0dd6d1621ddd39842fa84c74e818a5"
CHECKOUT_SHA = "11d5960a326750d5838078e36cf38b85af677262"
SETUP_NODE_SHA = "49933ea5288caeca8642d1e84afbd3f7d6820020"

AUTO_REVIEWER_PATH = ".github/workflows/auto-reviewer.yml"
CI_PATH = ".github/workflows/ci.yml"

# path -> list of (old, new, minimum_expected_occurrences)
REPLACEMENTS: dict[str, list[tuple[str, str, int]]] = {
    AUTO_REVIEWER_PATH: [
        (
            "uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main",
            f"uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@{ASSEMBLYZERO_SHA}  # main @ 2026-08-28",
            1,
        ),
    ],
    CI_PATH: [
        (
            "uses: actions/checkout@v4",
            f"uses: actions/checkout@{CHECKOUT_SHA} # v4",
            2,
        ),
        (
            "uses: actions/setup-node@v4",
            f"uses: actions/setup-node@{SETUP_NODE_SHA} # v4",
            2,
        ),
    ],
}

PR_BODY = f"""## Summary

Pins the Hermes merge gate and its CI actions to commit SHAs.

Before this, `.github/workflows/auto-reviewer.yml` invoked a reusable workflow
from another repository at `@main`, and `ci.yml` used `actions/checkout@v4` and
`actions/setup-node@v4`. All three are mutable refs. A change upstream, whether
accidental or hostile, silently changes what gates every Hermes PR, with no
Hermes-side commit and nothing to review.

## The pins

| Ref | Pinned to |
|---|---|
| `martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml` | `{ASSEMBLYZERO_SHA}` (main HEAD at 2026-08-28) |
| `actions/checkout` | `{CHECKOUT_SHA}` (v4) |
| `actions/setup-node` | `{SETUP_NODE_SHA}` (v4) |

The AssemblyZero SHA is exactly what `@main` resolved to when this was
prepared, so **current behavior is unchanged**. The pin only stops the ref
moving without review.

## The trailing version comments matter

Each pin keeps a `# v4` comment. Dependabot reads `@<sha> # v4` and updates both
the SHA and the comment on a bump, so the pin stays readable and maintained.
Without the comment a pinned SHA is opaque to a human and invisible to the bot.

## The cost of pinning, and what covers it

A SHA pin stops receiving upstream fixes and ages silently: a two-year-stale pin
looks exactly like a fresh one. Dependabot for the `github-actions` ecosystem
landed in #794 precisely to cover this, and it landed first so there is no
window in which pins exist with nothing maintaining them.

## How this landed

Via the classic-PAT Contents API (ADR-0216), because fine-grained PATs cannot
push files under `.github/workflows/`. Script:
`tools/hermes_pin_workflow_shas.py` in AssemblyZero.

The script does not embed file contents. It fetches each workflow from `main`,
applies exact string replacements, and asserts every expected replacement
changed something, aborting otherwise. A pin landed against an unexpected file
would be worse than no pin, because it would look reviewed.

Closes #669
"""


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_file(path: str, ref: str, pat: str) -> tuple[str, str]:
    """Return (decoded_text, blob_sha) for a file at a ref."""
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{path}",
        params={"ref": ref},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    payload = r.json()
    text = base64.b64decode(payload["content"]).decode("utf-8")
    return text, payload["sha"]


def apply_replacements(path: str, text: str) -> tuple[str, list[str]]:
    """Apply this path's replacements. Returns (new_text, notes).

    Raises RuntimeError if an expected pattern is missing, which means the file
    on main is not what this script was written against.
    """
    notes: list[str] = []
    out = text
    for old, new, expected in REPLACEMENTS[path]:
        if new in out:
            notes.append(f"    already pinned: {old.split('@')[0].split()[-1]}")
            continue
        found = out.count(old)
        if found < expected:
            raise RuntimeError(
                f"{path}: expected at least {expected} occurrence(s) of\n"
                f"    {old!r}\n"
                f"  but found {found}. The file on main is not what this script "
                f"was written against. Refusing to write a pin against an "
                f"unexpected file."
            )
        out = out.replace(old, new)
        notes.append(f"    pinned {found}x: {old}")
    return out, notes


def main_head_sha(pat: str) -> str:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/refs/heads/main",
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def create_branch(sha: str, pat: str) -> None:
    r = requests.post(
        f"{GH_API}/repos/{OWNER}/{REPO}/git/refs",
        headers=_headers(pat),
        json={"ref": f"refs/heads/{BRANCH}", "sha": sha},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 422:
        print(f"  branch {BRANCH} already exists, reusing")
        return
    r.raise_for_status()


def put_file(path: str, text: str, blob_sha: str, message: str, pat: str) -> None:
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/contents/{path}",
        headers=_headers(pat),
        json={
            "message": message,
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "branch": BRANCH,
            "sha": blob_sha,
        },
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()


def find_open_pr(pat: str) -> int | None:
    r = requests.get(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
        params={"state": "open", "per_page": 100},
        headers=_headers(pat),
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    for pr in r.json():
        if pr.get("title", "") == PR_TITLE or pr.get("head", {}).get("ref") == BRANCH:
            return pr["number"]
    return None


def create_pr(pat: str) -> int:
    r = requests.post(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls",
        headers=_headers(pat),
        json={"title": PR_TITLE, "head": BRANCH, "base": "main", "body": PR_BODY},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()["number"]


def wait_for_mergeable(pr_number: int, pat: str) -> str:
    """Poll until mergeable. Accepts 'clean' OR 'unstable'.

    'unstable' matters here for the same reason it did in
    hermes_add_ci_workflow.py: this PR edits the very workflows that run on it,
    so non-required jobs may be pending while the state settles.

    'blocked' is a WAIT state, not terminal -- right after the PR opens it
    usually means Cerberus-AZ has not posted its approving review yet. Keep
    polling THROUGH 'blocked'. Only 'dirty' (a real conflict) fails immediately,
    because waiting cannot resolve a conflict.
    """
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    last = "unknown"
    while time.time() < deadline:
        r = requests.get(
            f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{pr_number}",
            headers=_headers(pat),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        last = r.json().get("mergeable_state") or "unknown"
        if last in ("clean", "unstable", "dirty"):
            return last
        print(f"  mergeable_state={last}, waiting {POLL_INTERVAL_S}s for Cerberus approval...")
        time.sleep(POLL_INTERVAL_S)
    return last


def merge_pr(pr_number: int, pat: str) -> str:
    r = requests.put(
        f"{GH_API}/repos/{OWNER}/{REPO}/pulls/{pr_number}/merge",
        headers=_headers(pat),
        json={"merge_method": "squash"},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json().get("sha", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the mutation. Default is dry-run (plan only).",
    )
    args = parser.parse_args()

    with classic_pat_session() as pat:
        # 1. Fetch both files from main and compute the edits BEFORE any write.
        planned: dict[str, tuple[str, str]] = {}   # path -> (new_text, blob_sha)
        all_notes: list[str] = []
        for path in REPLACEMENTS:
            text, blob_sha = get_file(path, "main", pat)
            try:
                new_text, notes = apply_replacements(path, text)
            except RuntimeError as exc:
                print(f"ABORT: {exc}", file=sys.stderr)
                return 2
            all_notes.append(f"  {path}")
            all_notes.extend(notes)
            if new_text != text:
                planned[path] = (new_text, blob_sha)

        if not planned:
            print("Every ref on main is already pinned to a SHA -- nothing to do.")
            return 0

        print("Planned changes:")
        for line in all_notes:
            print(line)

        existing = find_open_pr(pat)
        if existing is not None:
            if not args.apply:
                print(f"\nOpen PR #{existing} already carries this change. "
                      f"Re-run with --apply to wait for it and merge it.")
                return 0
            print(f"\nResuming: open PR #{existing} already exists -- waiting for mergeable...")
            state = wait_for_mergeable(existing, pat)
            if state not in ("clean", "unstable"):
                print(f"  PR #{existing} not mergeable (state={state}). Retained for review.")
                return 1
            print(f"  PR #{existing} squash-merged at {merge_pr(existing, pat)[:8]}  OK")
            return 0

        if not args.apply:
            print("\nDRY-RUN (no changes). Would:")
            print(f"  1. branch {BRANCH} from main HEAD")
            for path in planned:
                print(f"  2. PUT {path} via Contents API")
            print(f"  3. open PR '{PR_TITLE}'")
            print("  4. wait for mergeable (clean/unstable), then squash-merge")
            print("\nRe-run with --apply to land it.")
            return 0

        print(f"\nLanding SHA pins on {OWNER}/{REPO}...")
        create_branch(main_head_sha(pat), pat)
        for path, (new_text, blob_sha) in planned.items():
            put_file(
                path, new_text, blob_sha,
                f"security: pin {Path(path).name} refs to commit SHAs (Closes #669)",
                pat,
            )
            print(f"  wrote {path}")

        pr_number = create_pr(pat)
        print(f"  opened PR #{pr_number}")

        state = wait_for_mergeable(pr_number, pat)
        if state not in ("clean", "unstable"):
            print(f"  PR #{pr_number} not mergeable (state={state}). Retained for review.")
            return 1

        print(f"  PR #{pr_number} squash-merged at {merge_pr(pr_number, pat)[:8]}  OK")

        # 2. Verify the pins actually landed on main, by re-reading from main.
        #    "Verify every substitution by re-reading from disk" -- the write
        #    succeeding is not the change landing.
        print("\nVerifying on main...")
        ok = True
        for path in REPLACEMENTS:
            text, _ = get_file(path, "main", pat)
            for _old, new, _n in REPLACEMENTS[path]:
                if new not in text:
                    print(f"  MISSING on main: {path} -> {new}", file=sys.stderr)
                    ok = False
        if not ok:
            print("Pins did NOT all land. Investigate before closing #669.", file=sys.stderr)
            return 1
        print("  all pins present on main  OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
