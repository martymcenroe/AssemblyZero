#!/usr/bin/env python3
"""Upgrade one repository's stale auto-reviewer.yml caller to the canonical one (#3641).

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT (ADR-0216). It decrypts
the classic PAT into this process's heap; an agent-spawned process would be
the agent's child and defeat that guarantee.

The general form of `upgrade_boostgauge_auto_reviewer.py` and
`upgrade_comp_environ_auto_reviewer.py`, which each did this for one
repository. An OLD-format caller (`name: auto-reviewer`, `secrets: inherit`,
no `permissions:` block, no `required_checks` input) hits `startup_failure`
on every PR against the reusable workflow, so Cerberus never approves and
every PR in the repository is blocked. `deploy_auto_reviewer_workflow.py`
cannot fix it: it skips a repository that already has the file.

Why direct-to-main and not a PR: the thing being fixed is the PR approver, so
a PR carrying the fix could never be approved. The Contents API PUT to the
default branch is the only way in; the commit message carries the target
repository's closing directive for `--issue`.

The caller content is `new_repo._CANONICAL_AUTO_REVIEWER_CALLER`, the one
canonical copy (#1193); it is imported, never re-typed here.

Protection: active rulesets targeting the branch get the Repository admin role
added to `bypass_actors`, and classic `enforce_admins` is switched off, for
the one PUT only; both are restored in a `finally`, rulesets first. This is not
`gh pr merge --admin`, not a force push, and no protection rule changes.

Usage (the user, in Git Bash, from AssemblyZero):
    poetry run python tools/upgrade_auto_reviewer_caller.py --repo gh-galaxy-quest --issue 11
    poetry run python tools/upgrade_auto_reviewer_caller.py --repo gh-galaxy-quest --issue 11 --apply

Required classic PAT scopes: repo (full) and workflow.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from new_repo import _CANONICAL_AUTO_REVIEWER_CALLER as CALLER_WORKFLOW  # noqa: E402

GITHUB_USER = "martymcenroe"
WORKFLOW_PATH = ".github/workflows/auto-reviewer.yml"
GH_API = "https://api.github.com"
HTTP_TIMEOUT_S = 30
REPO_ADMIN_ROLE_ID = 5  # GitHub repository role: admin
REVIEWER_SECRETS = ("REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY")
# Fields writable via the "Update a repository ruleset" PUT; server-managed ones must not appear.
RULESET_WRITABLE_FIELDS = ("name", "target", "enforcement", "conditions", "rules")


def commit_message(issue: int) -> str:
    return (
        f"ci: upgrade auto-reviewer.yml to the canonical caller (Closes #{issue})\n"
        "\n"
        "The OLD caller format (secrets: inherit, no permissions block, no\n"
        "required_checks input) causes startup_failure on every PR, so Cerberus\n"
        "never approves. Landed directly on the default branch through the\n"
        "Contents API: a PR carrying this fix could not be approved, because the\n"
        "broken approver is what this fixes.\n"
    )


class Repo:
    """One target repository and the calls this tool makes against it."""

    def __init__(self, name: str, branch: str, pat: str, http=requests) -> None:
        self.base = f"{GH_API}/repos/{GITHUB_USER}/{name}"
        self.name, self.branch, self.http = name, branch, http
        self.headers = {
            "Authorization": f"token {pat}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, path: str, **kw):
        return self.http.get(f"{self.base}{path}", headers=self.headers, timeout=HTTP_TIMEOUT_S, **kw)

    def get_file(self) -> tuple[str | None, str | None]:
        r = self._get(f"/contents/{WORKFLOW_PATH}", params={"ref": self.branch})
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json()
        decoded = base64.b64decode((data.get("content") or "").replace("\n", "")).decode("utf-8")
        return decoded, data.get("sha")

    def blocking_rulesets(self) -> list[dict]:
        r = self._get("/rulesets")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        out = []
        for summary in r.json():
            if summary.get("enforcement") != "active" or summary.get("target") != "branch":
                continue
            rd = self._get(f"/rulesets/{summary['id']}")
            rd.raise_for_status()
            detail = rd.json()
            include = ((detail.get("conditions") or {}).get("ref_name") or {}).get("include") or []
            if "~DEFAULT_BRANCH" in include or f"refs/heads/{self.branch}" in include:
                out.append(detail)
        return out

    def _put_ruleset(self, current: dict, actors: list[dict]) -> None:
        body = {f: current[f] for f in RULESET_WRITABLE_FIELDS if f in current}
        body["bypass_actors"] = actors
        r = self.http.put(f"{self.base}/rulesets/{current['id']}", headers=self.headers, json=body,
                          timeout=HTTP_TIMEOUT_S)  # fmt: skip
        r.raise_for_status()

    def add_admin_bypass(self, ruleset_id: int) -> list[dict]:
        """Add the admin role to bypass_actors; return the ORIGINAL list for the restore."""
        r = self._get(f"/rulesets/{ruleset_id}")
        r.raise_for_status()
        current = r.json()
        original = current.get("bypass_actors") or []
        if any(a.get("actor_id") == REPO_ADMIN_ROLE_ID and a.get("actor_type") == "RepositoryRole"
               for a in original):  # fmt: skip
            return original
        admin = {"actor_id": REPO_ADMIN_ROLE_ID, "actor_type": "RepositoryRole", "bypass_mode": "always"}
        self._put_ruleset(current, [*original, admin])
        return original

    def restore_bypass(self, ruleset_id: int, original: list[dict]) -> None:
        r = self._get(f"/rulesets/{ruleset_id}")
        r.raise_for_status()
        self._put_ruleset(r.json(), original)

    def enforce_admins_on(self) -> bool:
        r = self._get(f"/branches/{self.branch}/protection")
        if r.status_code == 404:
            return False
        r.raise_for_status()
        enforce = r.json().get("enforce_admins")
        return bool(enforce.get("enabled", False)) if isinstance(enforce, dict) else False

    def set_enforce_admins(self, on: bool) -> None:
        call = self.http.post if on else self.http.delete
        r = call(f"{self.base}/branches/{self.branch}/protection/enforce_admins", headers=self.headers,
                 timeout=HTTP_TIMEOUT_S)  # fmt: skip
        r.raise_for_status()

    def reviewer_secrets_missing(self) -> list[str]:
        r = self._get("/actions/secrets")
        if r.status_code >= 300:
            return [f"(could not list secrets: HTTP {r.status_code})"]
        present = {s["name"] for s in r.json().get("secrets", [])}
        return [n for n in REVIEWER_SECRETS if n not in present]

    def put_file(self, blob_sha: str, issue: int) -> None:
        content = CALLER_WORKFLOW.replace("\r\n", "\n").encode("utf-8")  # the API stores bytes verbatim
        payload = {
            "message": commit_message(issue),
            "content": base64.b64encode(content).decode("ascii"),
            "branch": self.branch,
            "sha": blob_sha,
        }
        r = self.http.put(f"{self.base}/contents/{WORKFLOW_PATH}", headers=self.headers, json=payload,
                          timeout=HTTP_TIMEOUT_S)  # fmt: skip
        if r.status_code >= 300:
            print(f"    PUT failed: {r.status_code} {r.text[:600]}")
        r.raise_for_status()


def upgrade(repo: Repo, issue: int, apply: bool) -> int:
    """The whole procedure against one repository. Returns the exit code."""
    current, blob_sha = repo.get_file()
    if current is None:
        print("  The file does not exist: wrong tool. deploy_auto_reviewer_workflow.py creates it.")
        return 1
    if current.replace("\r\n", "\n") == CALLER_WORKFLOW:
        print("  Already the canonical caller: nothing to do.")
        return 0
    print(f"  Existing file (blob {blob_sha[:7]}) differs. First line: {current.splitlines()[0]!r}")
    rulesets = repo.blocking_rulesets()
    classic = repo.enforce_admins_on()
    print(f"  Protection: rulesets={len(rulesets)} classic_enforce_admins={classic}")
    missing = repo.reviewer_secrets_missing()
    if missing:
        print(f"  Cerberus secrets MISSING: {', '.join(missing)}. The format fix alone will not make")
        print("  Cerberus approve; deploy them with tools/deploy_cerberus_secrets.py, then retest.")
    else:
        print("  Cerberus secrets: both present.")
    if not apply:
        print("  DRY RUN: nothing changed. Re-run with --apply.")
        return 0

    restorations: list[tuple[int, list[dict]]] = []
    classic_off = False
    try:
        if classic:
            repo.set_enforce_admins(False)
            classic_off = True
        for rs in rulesets:
            restorations.append((rs["id"], repo.add_admin_bypass(rs["id"])))
        repo.put_file(blob_sha, issue)
        print("  PUT succeeded.")
    finally:
        for rs_id, original in restorations:  # rulesets first, then classic
            try:
                repo.restore_bypass(rs_id, original)
            except Exception as exc:  # noqa: BLE001 -- report, and keep restoring the rest
                print(f"  WARNING: restoring ruleset {rs_id} failed: {exc}; bypass_actors={original!r}")
        if classic_off:
            try:
                repo.set_enforce_admins(True)
            except Exception as exc:  # noqa: BLE001
                print(f"  WARNING: restoring enforce_admins failed: {exc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="repository name under martymcenroe")
    ap.add_argument("--issue", required=True, type=int, help="the target repository's issue this closes")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--apply", action="store_true", help="write; without it the tool only reports")
    args = ap.parse_args(argv)
    print(f"Target: {GITHUB_USER}/{args.repo} branch={args.branch} issue=#{args.issue}")
    print(f"Mode:   {'APPLY' if args.apply else 'DRY RUN'}")
    from _pat_session import classic_pat_session

    with classic_pat_session() as pat:
        return upgrade(Repo(args.repo, args.branch, pat), args.issue, args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
