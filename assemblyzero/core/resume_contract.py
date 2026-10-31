"""The resume contract: a halt names what its resume needs (#2570).

The 2026-08-27 campaign patched one invariant hole by hole: a resume finds
what the halted attempt had. The LLD swept as leavings (#2551), the
zero-requirements fallback that would have certified against nothing
(#2552), the stale counters that put a resumed round over its own ceiling
(#2514) — each was the same defect wearing a different artifact. The halt
knew exactly what it had; the resume had to rediscover it from a world
that had meanwhile changed.

So the halt writes a manifest: every input the resume will need, with
content hashes, plus the counters and the state snapshot the resume seeds
from. The resume verifies the manifest FIRST and refuses by name on any
mismatch, before a single token is spent. A deliberate override is an
explicit flag, logged, never a silent proceed.

Lifecycle: verification CONSUMES the contract. A verified resume deletes
it and proceeds; if that run halts again, the halt writes a fresh one. A
contract therefore always describes the most recent halt, and a completed
run leaves none behind.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from assemblyzero.core.halt_paths import (
    halt_directory,
    repository_key,
    run_key,
    state_is_mock,
    state_repo_root,
)
from assemblyzero.core.state_persistence import STATE_DIR

#: State keys that name input artifacts a resume re-reads. Key-generic on
#: purpose: in the testing workflow `lld_path` holds the SPEC and
#: `original_lld_path` the LLD (#2024); in the implementation_spec workflow
#: `lld_path` holds the LLD. The contract records whatever the halted state
#: actually pointed at, labeled by its state key.
_INPUT_KEYS = ("lld_path", "original_lld_path", "spec_path")

#: Counters the resume seeds from. Recorded so the contract is the durable
#: record of where the cap regime stood at halt (#2514's class).
_COUNTER_KEYS = ("review_iteration", "iteration_count", "max_iterations")

#: List-valued state whose LENGTH matters to a resume's regime.
_COUNTED_LIST_KEYS = (
    "checks_shown_to_drafter", "grace_revisions_used", "pinning_events",
)


class ResumeContractUnreadable(RuntimeError):
    """The halt's contract exists but cannot be read or parsed (#3788)."""

    def __init__(self, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.path = path


def _sha256_file(path: Path) -> str | None:
    """The file's sha256, or None when it does not exist.

    #3788: only absence is None. A file that exists but cannot be read
    raises with its cause; it used to hash as absent, so the verifier
    reported "now missing" for a permissions problem.
    """
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract_directory(repo_root: Path | str, mock: bool) -> Path:
    """Where a run's halt files live: its repository's own directory (#4292)."""
    return halt_directory(repo_root, mock, STATE_DIR)


def contract_path(workflow: str, issue: int | str, directory: Path) -> Path:
    """The contract's file in ``directory``. ``issue`` is the run key: the
    issue number, or a brief run's key (``halt_paths.run_key``)."""
    return Path(directory) / f"resume-contract-{workflow}-{issue}.json"


def _unscoped_contract_path(workflow: str, issue: int | str) -> Path:
    """Where a contract written before #4292 is: one directory for every
    repository, named by workflow and issue alone."""
    return contract_path(workflow, issue, STATE_DIR)


def build_resume_contract(
    state: dict, workflow: str, state_snapshot: Path | None = None
) -> dict[str, Any]:
    """The manifest of what this halt's resume will need. Pure except reads."""
    inputs: list[dict[str, Any]] = []
    for key in _INPUT_KEYS:
        raw = state.get(key)
        if not raw:
            continue
        path = Path(str(raw))
        digest = _sha256_file(path)
        inputs.append({
            "key": key,
            "path": str(path),
            "exists": digest is not None,
            "sha256": digest,
        })

    counters: dict[str, Any] = {
        key: state.get(key, 0) for key in _COUNTER_KEYS
    }
    for key in _COUNTED_LIST_KEYS:
        counters[f"{key}_count"] = len(state.get(key) or [])

    snapshot_entry = None
    if state_snapshot is not None:
        snapshot_entry = {
            "path": str(state_snapshot),
            "sha256": _sha256_file(Path(state_snapshot)),
        }

    # #4292: the contract names the repository it was written for, whether it
    # was a mock's, and the key its files carry. A state that names no
    # repository raises ``UnkeyableRun``: a contract nobody can attribute is
    # the defect this field ends.
    return {
        "contract_version": 2,
        "workflow": workflow,
        "issue": int(state.get("issue_number", 0) or 0),
        "run_key": run_key(state),
        "repository": repository_key(state_repo_root(state)),
        "mock": state_is_mock(state),
        "halted_at": datetime.now(tz=timezone.utc).isoformat(),
        "audit_dir": str(state.get("audit_dir", "") or ""),
        "inputs": inputs,
        "counters": counters,
        "state_snapshot": snapshot_entry,
    }


def save_resume_contract(contract: dict, directory: Path) -> Path:
    target = contract_path(
        contract["workflow"], contract["run_key"], directory
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return target


def load_resume_contract(
    workflow: str, issue: int | str, directory: Path
) -> dict | None:
    path = contract_path(workflow, issue, directory)
    if not path.exists():
        return None
    # #3788: an unreadable or corrupt contract raises. It used to read as no
    # contract, so the resume went ahead unverified against a world nobody
    # checked, which is the one thing the contract exists to prevent.
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResumeContractUnreadable(
            f"the resume contract {path} exists but cannot be read: "
            f"{type(exc).__name__}: {exc}",
            path,
        ) from exc


def verify_resume_contract(contract: dict) -> list[str]:
    """Every way the world differs from the halt, named. Empty means intact.

    An input that did not exist at halt and exists now is not a mismatch —
    the world gaining an input breaks nothing a resume depends on.

    #3788: an input or snapshot that exists but cannot be read raises
    ``OSError`` with its cause, and ``check_and_consume`` refuses the resume
    with an alert. It used to hash as absent, reported as "now missing".
    """
    mismatches: list[str] = []
    for entry in contract.get("inputs", []):
        key, path = entry.get("key", "?"), Path(entry.get("path", ""))
        recorded = entry.get("sha256")
        if not entry.get("exists"):
            continue
        current = _sha256_file(path)
        if current is None:
            mismatches.append(
                f"{key}: the file at {path} existed at halt "
                f"(sha256 {str(recorded)[:12]}) and is now missing"
            )
        elif current != recorded:
            mismatches.append(
                f"{key}: the file at {path} hashed {str(recorded)[:12]} at "
                f"halt and hashes {current[:12]} now"
            )
    snapshot = contract.get("state_snapshot")
    if snapshot and snapshot.get("sha256"):
        current = _sha256_file(Path(snapshot["path"]))
        if current is None:
            mismatches.append(
                f"state_snapshot: the snapshot at {snapshot['path']} the "
                f"resume seeds from is missing"
            )
        elif current != snapshot["sha256"]:
            mismatches.append(
                f"state_snapshot: the snapshot at {snapshot['path']} hashed "
                f"{snapshot['sha256'][:12]} at halt and hashes "
                f"{current[:12]} now -- the counters a resume seeds from "
                f"are not the ones the halt wrote"
            )
    return mismatches


#: What `_ownership` answers.
THIS_REPOSITORY = "this"
OTHER_REPOSITORY = "other"
UNKNOWN_REPOSITORY = "unknown"


def _ownership(
    contract: dict, repository: str, repo_root: Path | str
) -> tuple[str, str]:
    """Whose halt a contract describes: ``(answer, detail)`` (#4292).

    A contract written since #4292 names its repository. One written before
    it does not, and is attributed from its ``audit_dir``, which lies inside
    the repository's ``docs/lineage``: the directory above that is the
    repository, or a worktree of it, and `repository_key` maps either to the
    primary checkout. A contract that cannot be attributed is UNKNOWN, never
    guessed at: no audit_dir, one outside any ``docs/lineage``, or a root that
    is gone and is not this run's own path. A root git cannot read raises
    from ``repository_key``; ``check_and_consume`` refuses on it.
    """
    named = contract.get("repository")
    if named:
        if named == repository:
            return THIS_REPOSITORY, repository
        return OTHER_REPOSITORY, str(named)

    audit_dir = str(contract.get("audit_dir") or "")
    if not audit_dir:
        return UNKNOWN_REPOSITORY, "it names no repository and its audit_dir is empty"
    parts = Path(audit_dir).parts
    root = None
    for index in range(len(parts) - 1):
        if parts[index] == "docs" and parts[index + 1] == "lineage":
            root = Path(*parts[:index]) if index else None
            break
    if root is None:
        return UNKNOWN_REPOSITORY, (
            f"it names no repository and its audit_dir {audit_dir} is not "
            "inside a docs/lineage directory"
        )
    if root.is_dir():
        owner = repository_key(root)
        return (THIS_REPOSITORY if owner == repository else OTHER_REPOSITORY), owner
    ours = {repository, Path(repo_root).resolve().as_posix()}
    if root.resolve().as_posix() in ours:
        return THIS_REPOSITORY, repository
    return UNKNOWN_REPOSITORY, (
        f"it names no repository, and {root}, where its audit_dir points, is "
        "gone, so it cannot be told from a removed worktree of another repository"
    )


def check_and_consume(
    workflow: str,
    issue: int | str,
    *,
    repo_root: Path | str,
    mock: bool = False,
    accept_changed: bool = False,
    directory: Path | None = None,
    log: Callable[[str], None] = print,
) -> bool:
    """Verify the halt's contract, consume it, and say so. False = refuse.

    No contract (a fresh run, or a halt that predates the mechanism) is a
    silent pass — the contract constrains resumes, never first runs. A
    verified or explicitly-accepted contract is deleted: it described the
    halt it came from, and the next halt writes its own.

    #4292: a contract belongs to a repository. ``repo_root`` (a worktree or
    its primary checkout) says which, and the contract is looked for in that
    repository's own directory, a mock run's in its ``mock`` subdirectory, so
    another repository's issue of the same number and a mock's halt are never
    read here. ``directory`` overrides the location, not the ownership check.

    A contract written before #4292 sits in the shared directory with no
    repository field. It is attributed from its ``audit_dir`` (`_ownership`):
    this repository's is verified and consumed as before; another's is
    left where it is and does not hold this run; one that cannot be
    attributed refuses the run, by name, rather than be guessed at. Nothing
    is rewritten or moved.
    """
    from assemblyzero.core import alert

    where = f"assemblyzero.core.resume_contract.check_and_consume ({workflow})"
    alert_issue = issue if isinstance(issue, int) and issue else None
    repository = repository_key(repo_root)
    own_directory = (
        Path(directory) if directory is not None
        else contract_directory(repo_root, mock)
    )
    path = contract_path(workflow, issue, own_directory)
    unscoped = False
    try:
        contract = load_resume_contract(workflow, issue, own_directory)
        if contract is None and directory is None:
            legacy = _unscoped_contract_path(workflow, issue)
            contract = load_resume_contract(workflow, issue, STATE_DIR)
            if contract is not None:
                path, unscoped = legacy, True
    except ResumeContractUnreadable as exc:
        # #3788: refused, by name, with an alert; it used to resume unverified.
        alert.alert_operator(
            what="the resume contract cannot be read, so the resume cannot be verified",
            where=where,
            cause=str(exc),
            consequence=(
                "the resume is refused before any token is spent; inspect the "
                f"contract at {exc.path or path}, or move it aside to run "
                "without verification"
            ),
            repo=repository,
            issue=alert_issue,
        )
        return False
    if contract is None:
        return True

    from assemblyzero.workflows.requirements.git_operations import GitOperationError

    try:
        owner, detail = _ownership(contract, repository, repo_root)
    except (OSError, GitOperationError) as exc:
        # #4292: git cannot place the repository the contract's audit_dir
        # points at, so the contract cannot be attributed. Refused by name.
        log(f"RESUME CONTRACT: refusing, {path} cannot be attributed: {exc} (#4292)")
        alert.alert_operator(
            what="the resume was refused: its contract cannot be attributed to a repository",
            where=where,
            cause=f"{path}: {type(exc).__name__}: {exc}",
            consequence=(
                "the resume did not start and the contract was not consumed; "
                f"move {path} aside if it is not a halt of this run"
            ),
            repo=repository,
            issue=alert_issue,
        )
        return False
    if owner == OTHER_REPOSITORY and unscoped:
        log(
            f"resume contract: {path} was written for {detail}, not for "
            f"{repository}; it is left where it is and does not hold this run"
        )
        return True
    refusal = ""
    if owner == OTHER_REPOSITORY:
        refusal = (
            f"the contract at {path} was written for {detail}, and this run is "
            f"for {repository}"
        )
    elif owner == UNKNOWN_REPOSITORY:
        refusal = f"the contract at {path} cannot be attributed to a repository: {detail}"
    elif "repository" in contract and bool(contract.get("mock", False)) != mock:
        refusal = (
            f"the contract at {path} was written by a "
            f"{'mock' if contract.get('mock') else 'real'} run, and this is a "
            f"{'mock' if mock else 'real'} run"
        )
    if refusal:
        log(f"RESUME CONTRACT: refusing, {refusal} (#4292)")
        alert.alert_operator(
            what="the resume was refused: its contract is not this run's",
            where=where,
            cause=refusal,
            consequence=(
                "the resume did not start and the contract was not consumed; "
                f"move {path} aside if it is not a halt of this run"
            ),
            repo=repository,
            issue=alert_issue,
        )
        return False
    try:
        mismatches = verify_resume_contract(contract)
    except OSError as exc:
        # #3788: an input that exists but cannot be read is refused by name,
        # with its cause; it used to be reported as missing.
        alert.alert_operator(
            what="an input the resume needs cannot be read, so it cannot be verified",
            where=f"assemblyzero.core.resume_contract.check_and_consume ({workflow})",
            cause=f"{type(exc).__name__}: {exc}",
            consequence="the resume is refused before any token is spent",
            issue=alert_issue,
        )
        return False
    if mismatches and not accept_changed:
        log(
            "RESUME CONTRACT: the world changed since the halt -- refusing "
            "before any token is spent (#2570)"
        )
        for mismatch in mismatches:
            log(f"  {mismatch}")
        log(
            "  Rerun with --accept-changed-inputs to proceed against the "
            "changed world; the acceptance is printed and logged, never "
            "silent."
        )
        # #3788: the refusal reaches the operator, not only the console.
        alert.alert_operator(
            what="the resume was refused: the world changed since the halt",
            where=f"assemblyzero.core.resume_contract.check_and_consume ({workflow})",
            cause="; ".join(mismatches),
            consequence=(
                "the resume did not start; rerun with --accept-changed-inputs "
                "to proceed against the changed world"
            ),
            issue=alert_issue,
        )
        return False
    if mismatches:
        log(
            f"RESUME CONTRACT: {len(mismatches)} changed input(s) ACCEPTED "
            f"by --accept-changed-inputs (#2570):"
        )
        for mismatch in mismatches:
            log(f"  {mismatch}")
    else:
        log(
            f"resume contract verified: {len(contract.get('inputs', []))} "
            f"input(s), snapshot intact (#2570)"
        )
    try:
        path.unlink()
    except OSError as exc:
        # #3788: the resume does not depend on the deletion, so it goes
        # ahead; but a contract left behind is checked again by the next
        # launch for this issue, against a halt that is over. The operator
        # is told, where it used to be a WARN on stdout.
        alert.alert_operator(
            what=f"the verified resume contract {path} could not be deleted",
            where=f"assemblyzero.core.resume_contract.check_and_consume ({workflow})",
            cause=f"{type(exc).__name__}: {exc}",
            consequence=(
                "the resume proceeds; the leftover contract will be checked "
                "again by the next launch for this issue until it is removed"
            ),
            issue=alert_issue,
        )
    return True
