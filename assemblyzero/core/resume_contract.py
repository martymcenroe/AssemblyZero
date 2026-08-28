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


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        # fail-open: None IS the signal -- an unreadable file hashes as
        # absent, which the verifier reports as a named mismatch rather
        # than crashing the halt or the resume check.
        return None


def contract_path(workflow: str, issue: int, directory: Path | None = None) -> Path:
    return (directory or STATE_DIR) / f"resume-contract-{workflow}-{issue}.json"


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

    return {
        "contract_version": 1,
        "workflow": workflow,
        "issue": int(state.get("issue_number", 0) or 0),
        "halted_at": datetime.now(tz=timezone.utc).isoformat(),
        "audit_dir": str(state.get("audit_dir", "") or ""),
        "inputs": inputs,
        "counters": counters,
        "state_snapshot": snapshot_entry,
    }


def save_resume_contract(
    contract: dict, directory: Path | None = None
) -> Path:
    target = contract_path(
        contract["workflow"], contract["issue"], directory
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return target


def load_resume_contract(
    workflow: str, issue: int, directory: Path | None = None
) -> dict | None:
    path = contract_path(workflow, issue, directory)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # fail-open: an unreadable or corrupt contract reads as no
        # contract, which is the pre-#2570 world -- the resume proceeds
        # unverified rather than being blocked by a broken manifest the
        # halt half-wrote. The contract protects the resume; it must
        # never be able to brick it.
        return None


def verify_resume_contract(contract: dict) -> list[str]:
    """Every way the world differs from the halt, named. Empty means intact.

    An input that did not exist at halt and exists now is not a mismatch —
    the world gaining an input breaks nothing a resume depends on.
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


def check_and_consume(
    workflow: str,
    issue: int,
    *,
    accept_changed: bool = False,
    directory: Path | None = None,
    log: Callable[[str], None] = print,
) -> bool:
    """Verify the halt's contract, consume it, and say so. False = refuse.

    No contract (a fresh run, or a halt that predates the mechanism) is a
    silent pass — the contract constrains resumes, never first runs. A
    verified or explicitly-accepted contract is deleted: it described the
    halt it came from, and the next halt writes its own.
    """
    contract = load_resume_contract(workflow, issue, directory)
    if contract is None:
        return True
    mismatches = verify_resume_contract(contract)
    path = contract_path(workflow, issue, directory)
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
    except OSError:
        # fail-open: a verified contract that could not be deleted only
        # costs a redundant re-verification on the next launch, and the
        # WARN names it; refusing the run over a leftover file would
        # invert the cost.
        log(f"  [WARN] verified contract could not be consumed: {path}")
    return True
