#!/usr/bin/env python3
"""Backfill: normalize invalid PEP 440 requires-python across fleet repos (#1574).

`poetry init` writes `requires-python = "^3.x"` into the PEP 621 [project]
table. The caret is valid Poetry syntax but INVALID PEP 440, so ruff and every
strict PEP 621 consumer refuse to parse pyproject.toml (#1571). The scaffolder
root cause is fixed (#1573); this tool backfills repos that predate that fix.

Why it clones instead of using the Contents API: changing requires-python
invalidates poetry.lock's content-hash, so a pure pyproject edit would break
each target's CI with "pyproject.toml changed significantly since poetry.lock
was last generated" -- exactly what happened in AZ PR #1576. So the tool clones
each repo, edits pyproject.toml, regenerates the lock with `poetry lock`,
commits both, and lands a PR. This mirrors the flow proven by hand in #1576.

Auth: the `gh` CLI's fine-grained PAT throughout (clone, push, PR, merge).
pyproject.toml and poetry.lock are not workflow files, so no `workflow` scope
and no classic PAT are needed; Cerberus auto-approves each PR after pr-sentinel
passes (the PR body carries a No-Issue exemption per AZ #1574).

Dry-run by default. Mutating the fleet requires --apply. Operator-run.

Usage:
    poetry run python tools/fix_requires_python.py --fleet            # preview
    poetry run python tools/fix_requires_python.py --repo NAME        # preview one
    poetry run python tools/fix_requires_python.py --fleet --apply    # do it
"""
import argparse
import base64
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from new_repo import _normalize_requires_python  # noqa: E402

GH_API = "https://api.github.com"
GITHUB_USER = "martymcenroe"
HTTP_TIMEOUT_S = 30
POLL_INTERVAL_S = 10
MERGEABLE_TIMEOUT_S = 300
BRANCH = "fix-requires-python-pep440"
PR_TITLE = "fix(pyproject): valid PEP 440 requires-python"
NO_ISSUE = (
    "No-Issue: requires-python PEP 440 normalization, fleet backfill "
    "(AssemblyZero #1574)"
)

_RP_RE = re.compile(r'(?m)^\s*requires-python\s*=\s*"([^"]+)"')


def _gh_token() -> str:
    """Return the gh CLI's token (fine-grained PAT) for REST polling.

    Never placed in argv: read via `gh auth token` and used only in request
    headers within this process.
    """
    out = subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """Run a command, raising with captured stderr on failure."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"command failed ({r.returncode}): {' '.join(cmd)}\n{r.stderr.strip()}"
        )
    return r


def get_requires_python(repo: str, token: str) -> str | None:
    """Return [project].requires-python from a repo's root pyproject.toml, or
    None if the repo has no root pyproject.toml."""
    r = requests.get(
        f"{GH_API}/repos/{GITHUB_USER}/{repo}/contents/pyproject.toml",
        params={"ref": "main"},
        headers=_headers(token),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    text = base64.b64decode(r.json()["content"]).decode("utf-8")
    m = _RP_RE.search(text)
    return m.group(1) if m else None


def is_invalid_caret(spec: str | None) -> bool:
    """True if the requires-python spec uses Poetry caret/tilde (invalid PEP 440)."""
    return spec is not None and spec.lstrip().startswith(("^", "~"))


def normalized_spec(spec: str) -> str:
    """The valid-PEP-440 replacement for a caret spec, via the scaffolder's
    own normalizer (single source of truth)."""
    fixed = _normalize_requires_python(f'requires-python = "{spec}"')
    m = _RP_RE.search(fixed)
    return m.group(1) if m else spec


def discover_targets(token: str) -> list[tuple[str, str]]:
    """All user-owned non-fork non-archived repos whose requires-python is an
    invalid caret form. Returns sorted [(repo, current_spec), ...]."""
    names: list[str] = []
    page = 1
    while True:
        r = requests.get(
            f"{GH_API}/user/repos",
            params={"per_page": 100, "page": page, "affiliation": "owner"},
            headers=_headers(token),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for repo in batch:
            if not repo.get("fork") and not repo.get("archived"):
                names.append(repo["name"])
        page += 1

    targets: list[tuple[str, str]] = []
    for name in sorted(set(names)):
        spec = get_requires_python(name, token)
        if is_invalid_caret(spec):
            targets.append((name, spec))
    return targets


def _wait_mergeable(repo: str, pr_number: str, token: str) -> str:
    """Poll mergeable_state until clean/unstable (mergeable) or dirty, or timeout."""
    deadline = time.time() + MERGEABLE_TIMEOUT_S
    last = "unknown"
    while time.time() < deadline:
        r = requests.get(
            f"{GH_API}/repos/{GITHUB_USER}/{repo}/pulls/{pr_number}",
            headers=_headers(token),
            timeout=HTTP_TIMEOUT_S,
        )
        r.raise_for_status()
        last = r.json().get("mergeable_state") or "unknown"
        if last in ("clean", "unstable", "dirty"):
            return last
        time.sleep(POLL_INTERVAL_S)
    return last


def fix_repo(repo: str, current_spec: str, token: str, apply: bool) -> str:
    """Normalize one repo. Returns a human-readable status line."""
    new_spec = normalized_spec(current_spec)
    if not apply:
        return f"{repo}: WOULD fix requires-python {current_spec!r} -> {new_spec!r}"

    full = f"{GITHUB_USER}/{repo}"
    with tempfile.TemporaryDirectory() as td:
        _run(["gh", "repo", "clone", full, td, "--", "--depth", "1"])
        pp = Path(td) / "pyproject.toml"
        text = pp.read_text(encoding="utf-8")
        fixed = _normalize_requires_python(text)
        if fixed == text:
            return f"{repo}: already valid after normalize (skipped)"
        pp.write_text(fixed, encoding="utf-8")

        _run(["git", "-C", td, "checkout", "-b", BRANCH])
        staged = ["pyproject.toml"]
        if (Path(td) / "poetry.lock").exists():
            # Regenerate the lock hash so the target's CI `poetry install`
            # does not reject a now-stale lock (the #1576 failure mode).
            _run(["poetry", "lock"], cwd=td)
            staged.append("poetry.lock")
        _run(["git", "-C", td, "add", *staged])
        _run([
            "git", "-C", td, "commit", "-m",
            f"{PR_TITLE}\n\nNormalize {current_spec} -> {new_spec}.\n\n{NO_ISSUE}",
        ])
        _run(["git", "-C", td, "push", "-u", "origin", BRANCH])

        pr_body = (
            f"Normalize `requires-python` `{current_spec}` -> `{new_spec}` to "
            f"valid PEP 440 so ruff and other PEP 621 consumers can parse "
            f"pyproject.toml. poetry.lock regenerated for the new hash.\n\n{NO_ISSUE}"
        )
        pr_url = _run([
            "gh", "pr", "create", "--repo", full, "--head", BRANCH,
            "--base", "main", "--title", PR_TITLE, "--body", pr_body,
        ]).stdout.strip()

    pr_number = pr_url.rstrip("/").rsplit("/", 1)[-1]
    state = _wait_mergeable(repo, pr_number, token)
    if state not in ("clean", "unstable"):
        return f"{repo}: PR {pr_url} stuck at {state!r}; left open for review"
    _run(["gh", "pr", "merge", pr_number, "--repo", full, "--squash"])
    return f"{repo}: fixed via {pr_url} ({current_spec} -> {new_spec})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo", help="single repo NAME (without owner)")
    g.add_argument("--fleet", action="store_true", help="all user-owned repos")
    ap.add_argument(
        "--apply", action="store_true",
        help="actually clone/edit/PR/merge (default: dry-run preview)",
    )
    args = ap.parse_args()

    token = _gh_token()

    if args.repo:
        spec = get_requires_python(args.repo, token)
        if not is_invalid_caret(spec):
            print(f"{args.repo}: requires-python is {spec!r} -- nothing to do.")
            return 0
        targets = [(args.repo, spec)]
    else:
        print("Scanning fleet for invalid PEP 440 requires-python...")
        targets = discover_targets(token)

    if not targets:
        print("No repos need fixing.")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n[{mode}] {len(targets)} repo(s) with invalid requires-python:\n")
    failures = 0
    for repo, spec in targets:
        try:
            print("  " + fix_repo(repo, spec, token, args.apply))
        except Exception as e:  # noqa: BLE001 -- isolate per-repo failures
            failures += 1
            print(f"  {repo}: ERROR -- {e}")

    if not args.apply:
        print(f"\nDry-run only. Re-run with --apply to land {len(targets)} PR(s).")
    print(f"\nDone. {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
