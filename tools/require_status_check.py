#!/usr/bin/env python3
"""Add one context to a branch's required status checks (#3447).

Generalizes the `--require-check` phase of `land_polybolos_ci_workflow.py`,
which does this correctly but has owner, repo, branch and check name welded in
as module constants. A second repository needed the same operation; copying the
file again would have made three.

The target arrives entirely through argv. ADR-0216 is explicit about why: this
repository is public and some targets are not, so a hardcoded target name in a
tool, a docstring or a commit message is a membrane leak.

## Why this needs the classic PAT

The fleet's fine-grained PAT gets a 403 on branch protection in both directions,
reading as well as writing. So both calls here go through the admin-scope
classic PAT that this process gpg-decrypts in-heap per ADR-0216: the PAT lives
only as a local variable inside the `with classic_pat_session()` block, is
consumed by `requests` directly, and never reaches env, argv, disk or a log.

## Two traps this encodes

**Required checks are keyed by JOB, not by workflow.** A workflow named `Tests`
containing a job `pytest` registers a check called `pytest`. Requiring `Tests`
produces a check that never reports and a branch nothing can merge into. The
same keying trap appears from the other direction in `land_staged_workflow.py`,
where polling by check-run name silently reports a workflow as never registered.
This tool cannot tell which name you meant, so it prints the contexts already
present before writing: if the list holds job names and you are about to add
something that is not one, that is the moment to notice.

**Never require a check that has not been seen green.** It blocks every open PR
in the repository until somebody with admin scope removes it again. Land the
workflow, watch one run go green, then run this.

## What it refuses to do

Two states stop it rather than being improvised through, because each is a
decision about the repository and not a step in a task:

  - the branch has no protection at all
  - the branch is protected but required status checks are switched off

Turning either on changes what every pull request in that repo must satisfy.

## Usage

RUN THIS YOURSELF in your own Git Bash, never through an agent's Bash tool
(ADR-0216 section 6.1): a Python process an agent spawns is the agent's child,
and its heap is theoretically readable while the PAT is in scope.

    poetry run python tools/require_status_check.py --repo <R> --context <name>
    poetry run python tools/require_status_check.py --repo <R> --context <name> --apply

Dry-run by default per standard 0017; `--apply` is the mutation flag. The
addition is additive: contexts already required are left alone.

Rollback, with the same PAT:

    DELETE /repos/<owner>/<repo>/branches/<branch>/protection/required_status_checks/contexts
    body: {"contexts": ["<name>"]}
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

GH_API = "https://api.github.com"
DEFAULT_OWNER = "martymcenroe"
HTTP_TIMEOUT_S = 30


def _headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _protection_url(cfg: argparse.Namespace, suffix: str = "") -> str:
    return (
        f"{GH_API}/repos/{cfg.owner}/{cfg.repo}"
        f"/branches/{cfg.branch}/protection{suffix}"
    )


def read_protection(pat: str, cfg: argparse.Namespace) -> dict | None:
    """Return the branch's protection record, or None if it has none."""
    r = requests.get(_protection_url(cfg), headers=_headers(pat), timeout=HTTP_TIMEOUT_S)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return dict(r.json())


def add_context(pat: str, cfg: argparse.Namespace) -> list[str]:
    """POST one context onto the existing list and return the new list.

    The POST .../required_status_checks/contexts endpoint appends. A PUT to
    /protection would replace the entire protection payload, so every setting
    not restated in the body would be silently dropped -- enforce_admins,
    review requirements, force-push blocks. Appending cannot do that.
    """
    r = requests.post(
        _protection_url(cfg, "/required_status_checks/contexts"),
        headers=_headers(pat),
        json={"contexts": [cfg.context]},
        timeout=HTTP_TIMEOUT_S,
    )
    r.raise_for_status()
    return list(r.json())


def run(pat: str, cfg: argparse.Namespace) -> int:
    target = f"{cfg.owner}/{cfg.repo}@{cfg.branch}"
    protection = read_protection(pat, cfg)

    if protection is None:
        print(
            f"{target} has no branch protection at all.\n"
            "Creating it decides what every pull request in that repository "
            "must satisfy, which is a decision about the repo rather than a "
            "step in this task. Stopping."
        )
        return 1

    checks = protection.get("required_status_checks")
    if not isinstance(checks, dict):
        print(
            f"{target} is protected, but required status checks are switched "
            "off.\nTurning them on changes what every pull request must "
            "satisfy. Stopping."
        )
        return 1

    contexts = list(checks.get("contexts") or [])
    print(f"  required status checks now : {contexts or '(none)'}")
    print(f"  adding                     : {cfg.context}")

    if cfg.context in contexts:
        print(f"  `{cfg.context}` is already required -- nothing to do.")
        return 0

    if not cfg.apply:
        print("  DRY-RUN -- nothing written. Re-run with --apply.")
        return 0

    now = add_context(pat, cfg)
    print(f"  required status checks are now: {now}")
    print(f"  `mergeable_state: clean` on {cfg.branch} now includes {cfg.context}.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True, help="Target repository name.")
    ap.add_argument(
        "--context",
        required=True,
        help="Check name to require. This is the JOB name, not the workflow name.",
    )
    ap.add_argument("--owner", default=DEFAULT_OWNER)
    ap.add_argument("--branch", default="main")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually write. Without it this reads and prints only.",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    cfg = parse_args(argv)
    reason = f"require check `{cfg.context}` on {cfg.owner}/{cfg.repo}@{cfg.branch}"
    with classic_pat_session(reason=reason) as pat:
        return run(pat, cfg)


if __name__ == "__main__":
    sys.exit(main())
