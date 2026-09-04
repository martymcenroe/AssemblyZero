#!/usr/bin/env python
"""Wait for a pull request to be mergeable, and stop when it cannot be (#2702).

The shell loop the merge sequence documents cannot end once its PR has merged,
because a merged PR reports `mergeable_state` as `unknown` and never as
`clean`. Two of them polled the API every thirty seconds for twelve hours after
their PRs landed.

    poetry run python tools/wait_for_pr.py --repo martymcenroe/AssemblyZero --pr 2691

Exit codes are the verdict, so this drops into a `&&` chain where the loop used
to sit:

    0  ready      -- merge it
    2  gone       -- already merged or closed; do not merge, do not wait
    3  stuck      -- a conflict or a rebase is needed
    4  timed out  -- the bound was reached with no verdict

Bounded by `--timeout`, so a poll that is wrong for a reason nobody predicted
still ends. That is the backstop, not the fix: the fix is that the terminal
states are checked at all.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assemblyzero.core.pr_poll import (  # noqa: E402
    POLL_FIELDS,
    VERDICT_GONE,
    VERDICT_READY,
    VERDICT_STUCK,
    VERDICT_WAIT,
    describe,
    poll_verdict,
)

EXIT_READY = 0
EXIT_GONE = 2
EXIT_STUCK = 3
EXIT_TIMEOUT = 4

_EXIT_FOR = {
    VERDICT_READY: EXIT_READY,
    VERDICT_GONE: EXIT_GONE,
    VERDICT_STUCK: EXIT_STUCK,
}


def fetch(repo: str, pr: int) -> dict:
    """The three fields the verdict reads, in one call. {} on any failure.

    An empty payload reads as `wait`, so a transient API failure costs one poll
    interval rather than a wrong verdict. The bound is what stops that being
    forever.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{pr}",
         "--jq", "{" + ",".join(f"{f}:.{f}" for f in POLL_FIELDS) + "}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout or "{}")
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def wait(
    repo: str, pr: int, *, timeout: float, interval: float,
    accept_unstable: bool = False, now=time.time, sleep=time.sleep,
    log=print,
) -> tuple[str, dict]:
    """Poll until a terminal verdict or the bound. Returns (verdict, payload)."""
    deadline = now() + timeout
    payload: dict = {}
    while True:
        payload = fetch(repo, pr)
        verdict = poll_verdict(payload, accept_unstable=accept_unstable)
        log(f"  {describe(verdict, payload)}")
        if verdict != VERDICT_WAIT:
            return verdict, payload
        if now() >= deadline:
            return VERDICT_WAIT, payload
        sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="owner/name")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument(
        "--accept-unstable", action="store_true",
        help=(
            "treat 'unstable' as ready. For a PR that removes the very check "
            "making it unstable, which can never reach 'clean'"
        ),
    )
    args = parser.parse_args(argv)

    print(f"Waiting for {args.repo}#{args.pr} (bound {args.timeout:.0f}s):")
    verdict, _ = wait(
        args.repo, args.pr, timeout=args.timeout, interval=args.interval,
        accept_unstable=args.accept_unstable,
    )
    if verdict == VERDICT_WAIT:
        print(
            f"  gave up after {args.timeout:.0f}s with no verdict. The PR is "
            f"neither ready nor finished; look at its checks."
        )
        return EXIT_TIMEOUT
    return _EXIT_FOR[verdict]


if __name__ == "__main__":
    raise SystemExit(main())
