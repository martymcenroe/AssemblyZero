#!/usr/bin/env python3
"""Remove the unused Cerberus App secrets from every repository the operator owns.

Issue #4728. Since Auto Review's retirement nothing reads `REVIEWER_APP_ID` or
`REVIEWER_APP_PRIVATE_KEY`, in the Actions scope or the Dependabot scope: #4724 traced
every reader, and the pr-sentinel Worker signs as Cerberus with its own Worker secrets.
Each repository that still holds them keeps a copy of an App private key that nothing
uses, and anyone who can push a workflow there could read it. This program finds those
repositories and, with `--apply`, removes the two secrets from them.

Reading or deleting a repository's secrets needs a permission the agents' fine-grained
token lacks, so the program runs under the in-process classic PAT (ADR-0216,
`tools/_pat_session.py`). Standard 0017 is the pattern it follows.

## What one run does

  1. Prints what it is about to do, then opens `classic_pat_session()`: a box asks for
     the classic PAT's passphrase, and the program says when the decryption is done.
  2. Reads `/user` to check the token, then lists every repository the token's account
     owns (`/user/repos?affiliation=owner`), archived ones last.
  3. For each repository in that order, asks GitHub for each of the two secrets in each of
     the two scopes (`GET /repos/<owner>/<repo>/<scope>/secrets/<name>`: 200 holds it,
     404 does not) and prints what it holds. A repository holding neither is clean and
     is skipped.
  4. With `--apply`, deletes each secret it holds (`DELETE`, which must answer 204), then
     reads it back, which must answer 404. Without `--apply`, nothing is written.

It names, reads and deletes no other secret: every URL it builds refuses any name but
the two above, and any scope but the two above.

The first failure (a read answered with anything but 200 or 404, a refused deletion, a
read-back that still finds the secret, a failed decryption) stops the run with exit 1,
naming the step, the repository, the scope and the secret, and says how many
repositories were cleaned, were already clean and were not finished. A rerun lists
again, so the repositories already clean are skipped and it goes on where it stopped.

No repository name is written here: this repository is public and some of the
operator's are not. The names come from GitHub at run time and are printed only to the
terminal that runs this.

## Usage

OPERATIONAL RULE (ADR-0216): the operator runs this himself, in his own terminal
(Ubuntu bash, or Git Bash on Windows). An agent never runs it through its Bash tool: the
Python process would be the agent's child, and its heap holds the PAT while the session
is open. The gpg-agent passphrase cache must be off (`default-cache-ttl 0` and
`max-cache-ttl 0` in `~/.gnupg/gpg-agent.conf`).

    # from the AssemblyZero checkout; the dry run is the default and deletes nothing
    poetry run python tools/fleet_remove_cerberus_secrets.py
    poetry run python tools/fleet_remove_cerberus_secrets.py --apply

`--repo NAME` (repeatable) limits the run to those repositories, for a first try on one.
After `--apply`, the dry run's last line says whether any repository still holds either
secret.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gh_retry import request_with_retry
from _pat_session import classic_pat_session

GH_API = "https://api.github.com"
SECRETS = ("REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY")
SCOPES = ("actions", "dependabot")
PER_PAGE = 100
COMMAND = "poetry run python tools/fleet_remove_cerberus_secrets.py"

#: `request(method, url, pat, **kwargs)` -> a response with `status_code` and `json()`;
#: `_gh_retry.request_with_retry` in a real run, a fake GitHub in the tests.
Request = Callable[..., Any]
Session = Callable[..., AbstractContextManager[str]]


class Stop(Exception):
    """One step failed; the run stops here and exits 1."""

    def __init__(self, step: str, message: str):
        super().__init__(f"{step}: {message}")
        self.step, self.message = step, message


def say(text: str = "") -> None:
    """Print one line now, so the terminal is never silent while a call is in flight."""
    print(text, flush=True)


def _detail(resp: Any) -> str:
    """`HTTP <status>`, with GitHub's own message when the body carries one."""
    try:
        body = resp.json()
    except ValueError:
        body = None
    message = body.get("message") if isinstance(body, dict) else None
    return f"HTTP {resp.status_code}" + (f" ({message})" if message else "")


def secret_url(owner: str, repo: str, scope: str, name: str) -> str:
    """The URL of one of the two Cerberus secrets; any other name or scope is refused."""
    if name not in SECRETS or scope not in SCOPES:
        raise ValueError(f"{scope}/{name} is not a Cerberus secret this program handles; "
                         f"it handles only {SECRETS} in {SCOPES}")
    return f"{GH_API}/repos/{owner}/{repo}/{scope}/secrets/{name}"


def whoami(request: Request, pat: str) -> str:
    """The login the token belongs to (standard 0017's pre-flight `/user` check)."""
    resp = request("GET", f"{GH_API}/user", pat)
    if resp.status_code != 200:
        raise Stop("token check", f"GET /user answered {_detail(resp)}")
    return resp.json()["login"]


def owned_repos(request: Request, pat: str) -> list[dict]:
    """Every repository the token's account owns: `{"name", "archived"}`, archived last."""
    repos: list[dict] = []
    page = 1
    while True:
        resp = request("GET", f"{GH_API}/user/repos", pat,
                       params={"affiliation": "owner", "per_page": PER_PAGE, "page": page})
        if resp.status_code != 200:
            raise Stop("list repositories",
                       f"GET /user/repos page {page} answered {_detail(resp)}")
        batch = resp.json()
        repos.extend({"name": r["name"], "archived": bool(r.get("archived"))} for r in batch)
        if len(batch) < PER_PAGE:
            break
        page += 1
    return sorted(repos, key=lambda r: (r["archived"], r["name"].lower()))


def holds(request: Request, pat: str, owner: str, repo: str, scope: str, name: str,
          step: str = "read") -> bool:
    """True when the repository holds the secret (200), False when it does not (404)."""
    resp = request("GET", secret_url(owner, repo, scope, name), pat)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    raise Stop(step, f"{repo} {scope}/{name}: GET answered {_detail(resp)}; nothing is "
                     "read as absent unless GitHub says 404")


def held(request: Request, pat: str, owner: str, repo: str) -> list[tuple[str, str]]:
    """The (scope, name) pairs the repository holds, scope by scope."""
    return [(scope, name) for scope in SCOPES for name in SECRETS
            if holds(request, pat, owner, repo, scope, name)]


def delete(request: Request, pat: str, owner: str, repo: str, scope: str, name: str,
           *, archived: bool = False) -> None:
    """Delete one Cerberus secret and read it back; raise Stop when either step fails."""
    url = secret_url(owner, repo, scope, name)
    resp = request("DELETE", url, pat)
    if resp.status_code != 204:
        hint = (" The repository is archived; if that is why GitHub refused, unarchive it "
                "in its Settings, rerun, and archive it again.") if archived else ""
        raise Stop("delete", f"{repo} {scope}/{name}: DELETE answered {_detail(resp)}."
                             + hint)
    say(f"      deleted   {scope}/{name}")
    if holds(request, pat, owner, repo, scope, name, step="read back"):
        raise Stop("read back", f"{repo} {scope}/{name}: still there after GitHub "
                                "answered 204 to its DELETE")
    say(f"      read back {scope}/{name}: gone")


def _select(repos: list[dict], only: list[str] | None) -> list[dict]:
    if not only:
        return repos
    names = {r["name"] for r in repos}
    missing = [o for o in only if o not in names]
    if missing:
        raise Stop("select", f"--repo names {missing}, which the token's account does not "
                             "own. Nothing was deleted.")
    return [r for r in repos if r["name"] in only]


def _pairs(found: list[tuple[str, str]]) -> str:
    return ", ".join(f"{scope}/{name}" for scope, name in found)


class _Tally:
    """What the run has done so far, for the summary and for the stop report."""

    def __init__(self) -> None:
        self.total: int | None = None
        self.cleaned: list[str] = []
        self.clean: list[str] = []
        self.holding: list[str] = []

    def stopped(self, apply: bool) -> Iterator[str]:
        if self.total is None:
            yield "  The repositories were never listed, so nothing was deleted."
            return
        if apply:
            left = self.total - len(self.cleaned) - len(self.clean)
            yield (f"  cleaned {len(self.cleaned)}, already clean {len(self.clean)}, not "
                   f"finished {left} of {self.total} (the one it stopped at among them).")
            yield "  Fix the cause and rerun the same command; clean repositories are skipped."
        else:
            seen = len(self.clean) + len(self.holding)
            yield (f"  listed {seen} of {self.total} before the stop: {len(self.holding)} "
                   f"holding, {len(self.clean)} clean. Nothing was deleted.")


def _reason(apply: bool) -> str:
    verb = "delete" if apply else "list"
    return f"{verb} the unused Cerberus App secrets in every repository you own"


def run(apply: bool, only: list[str] | None = None, *,
        session: Session | None = None, request: Request | None = None) -> int:
    """List, and with `apply` delete, the Cerberus secrets; return the exit code."""
    session = session or classic_pat_session
    request = request or request_with_retry
    tally = _Tally()
    step = "decrypt"

    say(f"Remove the unused Cerberus App secrets ({', '.join(SECRETS)}) from the "
        f"{' and '.join(SCOPES)} scopes of every repository you own.")
    say("  mode : " + ("APPLY -- each secret found is deleted, then read back"
                       if apply else "DRY RUN -- lists only, deletes nothing (--apply deletes)"))
    if only:
        say(f"  only : {', '.join(only)}")
    say("Step 1: decrypting the classic PAT. A box will ask for its passphrase.")
    try:
        with session(reason=_reason(apply)) as pat:
            say("  decrypted; the PAT stays inside this process.")
            step = "token check"
            say("Step 2: checking the token (GET /user) ...")
            owner = whoami(request, pat)
            say(f"  the token belongs to {owner}")
            step = "list repositories"
            say("Step 3: listing the repositories it owns ...")
            repos = _select(owned_repos(request, pat), only)
            tally.total = len(repos)
            archived = sum(r["archived"] for r in repos)
            say(f"  {len(repos)} repositories ({archived} archived, listed last)")
            step = "read"
            say("Step 4: reading each repository's Cerberus secrets"
                + (", deleting each one found ..." if apply else " ..."))
            for i, r in enumerate(repos, 1):
                name = r["name"]
                step = f"read {name}"
                label = f"  [{i}/{len(repos)}] {name}" + (" (archived)" if r["archived"] else "")
                found = held(request, pat, owner, name)
                if not found:
                    say(f"{label}: clean")
                    tally.clean.append(name)
                    continue
                say(f"{label}: holds {_pairs(found)}")
                tally.holding.append(name)
                if not apply:
                    continue
                step = f"delete in {name}"
                for scope, secret in found:
                    delete(request, pat, owner, name, scope, secret, archived=r["archived"])
                tally.cleaned.append(name)
                say(f"    {name}: cleaned")
    except (Stop, requests.RequestException, FileNotFoundError, RuntimeError) as exc:
        print(f"\nSTOPPED at {step}: {exc}", file=sys.stderr, flush=True)
        for line in tally.stopped(apply):
            print(line, file=sys.stderr, flush=True)
        return 1
    except BaseException as exc:
        print(f"\nSTOPPED at {step}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        for line in tally.stopped(apply):
            print(line, file=sys.stderr, flush=True)
        raise

    say()
    if apply:
        say(f"Done: cleaned {len(tally.cleaned)}, already clean {len(tally.clean)}, of "
            f"{tally.total}.")
        say(f"To confirm, run the dry run: {COMMAND}")
        return 0
    if tally.holding:
        say(f"Done (dry run): {len(tally.holding)} of {tally.total} repositories hold a "
            f"Cerberus secret: {', '.join(tally.holding)}.")
        say(f"To delete them: {COMMAND} --apply")
    else:
        say(f"Done (dry run): no repository of the {tally.total} holds either secret.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="Delete each secret found and read it back. Without it: a dry run "
                         "that lists and deletes nothing.")
    ap.add_argument("--repo", action="append", default=None, metavar="NAME",
                    help="Limit the run to this repository (repeatable).")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.apply, args.repo)


if __name__ == "__main__":
    sys.exit(main())
