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

#3585 (ADR 0236): a question git cannot answer about the base raises
``BaseTreeError`` naming the ref, the path, the exit code and git's stderr. A
failed fetch, a base that is not on origin and a git error used to read as
"the file is not there", so the spec was planned against a tree that was not
the one the implementation is cut from. A path that a readable base does not
ship is still an answer: ``False`` from ``exists_on_base`` and ``""`` from
``read_from_base``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class BaseTreeError(RuntimeError):
    """git could not answer a question about the base tree (#3585).

    Deliberately not an ``OSError``: callers read an ``OSError`` as a file
    that is not there, and a git failure is not that.
    """


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git; every caller reads the exit code itself (#3585)."""
    return subprocess.run(
        ["git", *args], cwd=str(repo_root), check=False,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _failure(what: str, repo_root: Path, result: subprocess.CompletedProcess) -> BaseTreeError:
    """The error for one failed git call: what was asked, where, and git's answer."""
    stderr = (result.stderr or "").strip() or "(no stderr)"
    command = " ".join(str(part) for part in result.args)
    return BaseTreeError(
        f"{what}: `{command}` in {repo_root} exited {result.returncode}: {stderr}"
    )


def base_ref(repo_root: Path, base_branch: str) -> str:
    """The ref to read the base from, which is always origin's (#2021).

    A bare attempt-branch name resolves to the LOCAL branch, which nothing
    fast-forwards -- every PR the pipeline opens merges on origin. The same trap
    made the clean-check blind to the pipeline's own merges.

    Raises:
        BaseTreeError: the fetch fails, or ``origin/<base_branch>`` does not
            resolve after it (#3585). Both used to fall back to the local
            branch, or to a stale origin ref, without a word.
    """
    if not base_branch:
        return ""
    if base_branch.startswith("origin/"):
        return base_branch
    fetch = _git(repo_root, "fetch", "origin", "--quiet")
    if fetch.returncode != 0:
        raise _failure(
            f"cannot fetch origin to read the base branch {base_branch!r}",
            repo_root, fetch,
        )
    remote = f"origin/{base_branch}"
    verify = _git(repo_root, "rev-parse", "--verify", "--quiet", f"{remote}^{{commit}}")
    if verify.returncode != 0:
        raise BaseTreeError(
            f"the base branch {base_branch!r} is not on origin: {remote} does not "
            f"resolve to a commit in {repo_root} after a fetch (exit "
            f"{verify.returncode}). The implementation is cut from origin, and the "
            f"local branch is never fast-forwarded (#2021), so it is not read instead."
        )
    return remote


def exists_on_base(repo_root: Path, base_ref_name: str, file_path: str) -> bool:
    """Does the base already ship this path?

    ``git ls-tree`` answers both questions at once: it exits 0 and prints
    nothing for a path the base lacks, and fails for a ref or repo it cannot
    read. ``git cat-file -e`` exited non-zero for both, so a git error read as
    absence.

    Raises:
        BaseTreeError: git cannot read ``base_ref_name`` here (#3585).
    """
    if not base_ref_name:
        return False
    normalised = file_path.replace("\\", "/")
    result = _git(repo_root, "ls-tree", "--full-tree", base_ref_name, "--", normalised)
    if result.returncode != 0:
        raise _failure(
            f"cannot tell whether {base_ref_name} ships {normalised}", repo_root, result,
        )
    return bool(result.stdout.strip())


def read_from_base(repo_root: Path, base_ref_name: str, file_path: str) -> str:
    """Contents of this path on the base, or "" if the base does not ship it.

    Raises:
        BaseTreeError: git cannot read the base, or cannot show a path the
            base ships (#3585). Both used to read as "" and the file was
            skipped as if it were absent.
    """
    if not base_ref_name:
        return ""
    normalised = file_path.replace("\\", "/")
    result = _git(repo_root, "show", f"{base_ref_name}:{normalised}")
    if result.returncode == 0:
        return result.stdout
    if not exists_on_base(repo_root, base_ref_name, normalised):
        return ""
    raise _failure(
        f"cannot read {normalised} from {base_ref_name}, which ships it",
        repo_root, result,
    )


def reclassify_against_base(
    files_to_modify: list[dict], repo_root: Path, base_branch: str
) -> tuple[list[dict], list[str]]:
    """Turn every Add whose file the base already ships into a Modify.

    Returns the updated list and a note per reclassified path, so the change is
    stated in the run log rather than being a silent rewrite of the plan.

    Deliberately one-way. A Modify the base does not have is left alone: the
    existing guard in analyze_codebase reports it, and inventing an Add here
    would paper over an LLD that named the wrong file.

    Raises:
        BaseTreeError: the base cannot be resolved or read (#3585); a base
            that does not exist used to leave every Add an Add.
    """
    if not base_branch:
        return files_to_modify, []

    ref = base_ref(repo_root, base_branch)

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
