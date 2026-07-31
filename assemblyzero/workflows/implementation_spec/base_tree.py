"""Reading the integration branch a phase will actually be built on (#2033).

The spec is drafted against the CHECKOUT, which since #2012 sits permanently on
the default branch. The implementation happens in a worktree cut from the
attempt branch. Mid-arc those are different trees: `main` has none of the arc,
while the attempt branch carries every phase landed so far.

So a phase that extends an earlier one was planned as if that earlier one did
not exist. boostgauge #2 listed `telltale.py`, `gauge.py` and `stingray.py` as
files to Add -- all three were already on the base, landed by #41 and #1 -- and
the resulting spec described modules to create rather than modules to extend.

Everything here reads git rather than the working tree, because the working
tree is the wrong tree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo_root),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def base_ref(repo_root: Path, base_branch: str) -> str:
    """The ref to read the base from, preferring origin (#2021).

    A bare attempt-branch name resolves to the LOCAL branch, which nothing
    fast-forwards -- every PR the pipeline opens merges on origin. The same trap
    made the clean-check blind to the pipeline's own merges.
    """
    if not base_branch:
        return ""
    if base_branch.startswith("origin/"):
        return base_branch
    _git(repo_root, "fetch", "origin", "--quiet")
    remote = f"origin/{base_branch}"
    if _git(repo_root, "rev-parse", "--verify", "--quiet", f"{remote}^{{commit}}").returncode == 0:
        return remote
    return base_branch


def exists_on_base(repo_root: Path, base_ref_name: str, file_path: str) -> bool:
    """Does the base already ship this path?"""
    if not base_ref_name:
        return False
    normalised = file_path.replace("\\", "/")
    result = _git(repo_root, "cat-file", "-e", f"{base_ref_name}:{normalised}")
    return result.returncode == 0


def read_from_base(repo_root: Path, base_ref_name: str, file_path: str) -> str:
    """Contents of this path on the base, or "" if it is not there."""
    if not base_ref_name:
        return ""
    normalised = file_path.replace("\\", "/")
    result = _git(repo_root, "show", f"{base_ref_name}:{normalised}")
    return result.stdout if result.returncode == 0 else ""


def reclassify_against_base(
    files_to_modify: list[dict], repo_root: Path, base_branch: str
) -> tuple[list[dict], list[str]]:
    """Turn every Add whose file the base already ships into a Modify.

    Returns the updated list and a note per reclassified path, so the change is
    stated in the run log rather than being a silent rewrite of the plan.

    Deliberately one-way. A Modify the base does not have is left alone: the
    existing guard in analyze_codebase reports it, and inventing an Add here
    would paper over an LLD that named the wrong file.
    """
    if not base_branch:
        return files_to_modify, []

    ref = base_ref(repo_root, base_branch)
    if not ref:
        return files_to_modify, []

    updated: list[dict] = []
    notes: list[str] = []
    for spec in files_to_modify:
        path = spec.get("path", "")
        if spec.get("change_type") == "Add" and exists_on_base(repo_root, ref, path):
            changed = dict(spec)
            changed["change_type"] = "Modify"
            updated.append(changed)
            notes.append(
                f"{path}: planned as Add, but {ref} already ships it — "
                f"specifying a Modify so the earlier phase is extended"
            )
        else:
            updated.append(spec)
    return updated, notes
