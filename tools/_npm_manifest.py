#!/usr/bin/env python3
"""npm manifest inspection shared by the scaffolder and the fleet tooling.

#2182. A repo can receive npm dependabot PRs it is structurally incapable of
passing review on, and then every one of those PRs defers forever.

The review gate (#1839) refuses to merge an npm PR whose directory has no
runnable `test` script -- correctly, since merging an unverified dependency
bump is the thing that gate exists to prevent. Nothing on the enabling side
checks for one, so the two halves disagree: PRs arrive for a directory whose
PRs can never be merged.

WHY THIS SCANS THE REPO RATHER THAN dependabot.yml
--------------------------------------------------
The obvious design is to check each `directory:` in `.github/dependabot.yml`
when that file is written. That would not have caught the case that prompted
this module.

AssemblyZero's dependabot.yml declares npm for `/sentinel` only. There has
never been a `/dashboard` entry. `/dashboard` nevertheless received npm PRs
(#2111, "in the npm_and_yarn group across 1 directory") because **GitHub's
security updates fire on any lockfile in the repo, independent of
version-update configuration**. That repo's own dependabot.yml header records
the same asymmetry from the other direction: before it existed the repo "had
only GitHub's default security updates, and those do not cover everything".

So the set of directories that can receive npm PRs is not the set configured
in dependabot.yml -- it is every directory holding a package.json with a
lockfile. That is what these helpers enumerate.
"""

from __future__ import annotations

import json
from pathlib import Path

# A lockfile is what makes a directory reachable by security updates; a
# package.json alone (no lock) is not a dependency tree GitHub will bump.
NPM_LOCKFILES = ("package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
                 "pnpm-lock.yaml")

# Never descend into these. node_modules in particular contains thousands of
# vendored package.json files, none of them ours.
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".wrangler",
              ".venv", "__pycache__"}


def npm_test_script(pkg_dir: Path) -> str | None:
    """The package.json "test" script in `pkg_dir`, or None when unrunnable.

    Mirrors the semantics of the review gate's own check, deliberately and
    including its subtlety: `npm init`'s placeholder
    (`echo "Error: no test specified" && exit 1`) counts as NO script.
    Running it can only exit 1 with a message that would then be misreported
    as a test failure, when the real condition is "this package declares no
    tests".

    Any unreadable or malformed manifest returns None -- a directory we cannot
    evaluate is reported as lacking a script, which is the conservative
    direction: it prompts a human look rather than silently passing.
    """
    pkg = pkg_dir / "package.json"
    if not pkg.exists():
        return None
    try:
        with pkg.open("rb") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    script = (data.get("scripts") or {}).get("test")
    if not isinstance(script, str) or not script.strip():
        return None
    if "no test specified" in script:
        return None
    return script


def find_npm_manifests(root: Path) -> list[Path]:
    """Every directory under `root` holding a package.json AND a lockfile.

    These are exactly the directories GitHub can open npm PRs against,
    whether or not dependabot.yml mentions them. Returned sorted for
    deterministic output.
    """
    found: list[Path] = []
    for pkg in root.rglob("package.json"):
        if any(part in _SKIP_DIRS for part in pkg.relative_to(root).parts):
            continue
        d = pkg.parent
        if any((d / lf).exists() for lf in NPM_LOCKFILES):
            found.append(d)
    return sorted(found)


def dirs_missing_test_script(root: Path) -> list[str]:
    """Repo-relative directories that can receive npm PRs but cannot pass review.

    `"/"` denotes the repo root, matching dependabot.yml's `directory:` form
    so the output can be read against that file directly.
    """
    missing: list[str] = []
    for d in find_npm_manifests(root):
        if npm_test_script(d) is None:
            rel = d.relative_to(root).as_posix()
            missing.append("/" if rel == "." else f"/{rel}")
    return missing
