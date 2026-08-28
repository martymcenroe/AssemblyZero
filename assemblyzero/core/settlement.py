"""Stage finality: an artifact that passed its gate is settled until its
inputs change (#2609).

Approvals did not bind. An LLD that survived the conservation gate, mechanical
validation and adversarial review was torn up by the next fresh attempt as if
none of that had happened: boostgauge #331 took 20 launches in 12 days and had
its LLD drawn from scratch seven times, shedding the same settled #361 sampling
window twice, to two different redraws.

## The mechanism was already there, minus a reader

The diagnosis on #2609 found the record already exists. `lld-status.json`
(`requirements.audit`) is repo-keyed, issue-keyed, lives under `data/` outside
the branch lifecycle, and says `"status": "approved"`. Every call site in the
tree writes it; **nothing read it**. Meanwhile `_delete_landed_working_copies`
removes the LLD working copy exactly when its PR merges -- and stage entry
resolves settledness by the presence of that file -- so landing an artifact
durably is what caused it to be redrawn.

The visual gate is immune for one reason: its stamp is READ at stage entry
(`visual_gate/gate.py`, the resume shortcut). It is not a different idea. It is
the same idea with a reader.

So this module does not invent a store. It gives the existing record the input
hashes it lacked, and gives it its first reader.

## Content, never timestamps

`draft_is_stale` (#2206) already unsettles a resumed draft on input change, by
comparing the issue's `updatedAt` against the draft time. **GitHub bumps
`updatedAt` when a comment is posted**, so that probe fires on events which
changed nothing about the derivation -- measured across three issues with a
control and filed as #2615. The campaign's own standing method, *post the
sharpened diagnosis on the issue before fixing*, invalidates every persisted
draft for that issue under a timestamp check.

Settlement therefore fingerprints CONTENT. Timestamps are recorded as
provenance for a human reader and are never an authority.

## Line endings are normalised before hashing

The issue body arrives from `gh` with LF; the same text checked out on Windows
is CRLF (`core.autocrlf=true`). Hashing raw bytes would make every artifact
unsettle on a platform difference and settle nothing, so every input is
normalised to LF first. This is the sibling of the CRLF trap that makes a raw
`diff` of git content against a working-tree file report every line as changed.

## Which direction the failures go

A false UNSETTLE costs one redraw -- the status quo before this module. A false
SETTLE reuses an artifact derived from inputs that have since changed, which is
the expensive error and the one the guard stack exists to catch. So every
ambiguity resolves toward unsettled:

* an unreadable or corrupt record is no record;
* an input that cannot be read is a mismatch, not a match;
* an input set that gained or lost a member is a mismatch, even if every
  common member still hashes the same -- a new binding design doc changes what
  the artifact should say.

Settlement is durable and is never consumed, which is what separates it from
the resume contract (#2570): a contract describes one halt and is deleted by
the resume that verifies it, while a settlement describes a ruling and outlives
every run until an input moves.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

#: Bumped only when a reader must reject records written by an older writer.
SETTLEMENT_VERSION = 1

#: Stages that can settle. `impl` and `pr` are excluded deliberately: they are
#: never skipped (`should_skip_stage`), and an implementation's inputs include
#: the whole worktree, which this fingerprint does not model.
SETTLEABLE_STAGES = ("lld", "spec")

#: The docs whose content binds a derivation. Canonical here so the settlement
#: check and `speedrun_roll.draft_is_stale` cannot drift apart -- they answer
#: the same question and disagreeing would make one of them wrong (#2206).
BINDING_DOC_PATHS = ("docs/design", "docs/adrs", "CLAUDE.md")

#: The stage each settleable stage derives FROM. #2611's ruling in structural
#: form: each stage derives from its immediate upstream settled artifact and
#: never reaches around it to the source.
UPSTREAM_OF = {"lld": None, "spec": "lld"}


def _normalise(raw: bytes) -> bytes:
    """CRLF and lone CR to LF, so a hash means content and not a checkout."""
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(_normalise(text.encode("utf-8"))).hexdigest()


def sha256_path(path: Path | str) -> str | None:
    """The file's content hash, or None when it cannot be read.

    None is the signal, never an exception: an unreadable input has to reach
    the verifier as a named mismatch rather than crashing a stage that was
    only asking whether it could skip work.
    """
    try:
        return hashlib.sha256(_normalise(Path(path).read_bytes())).hexdigest()
    except OSError:
        # fail-open: only in shape -- None is reported by `verify` as a named
        # mismatch, which unsettles. The run continues by DRAFTING, which is
        # the safe direction and the pre-#2609 behaviour.
        return None


@dataclass(frozen=True)
class SettledInput:
    """One input an artifact was derived from, by content.

    `key` is the stable identity used to pair a recorded input with a current
    one -- `issue_body`, `upstream:lld`, `binding:docs/design/dial.md`. `path`
    is carried for the mismatch message only; the issue body has none.
    """

    key: str
    sha256: str | None
    path: str = ""

    def as_dict(self) -> dict:
        return {"key": self.key, "sha256": self.sha256, "path": self.path}

    @staticmethod
    def from_dict(raw: dict) -> "SettledInput":
        return SettledInput(
            key=str(raw.get("key", "?")),
            sha256=raw.get("sha256"),
            path=str(raw.get("path", "") or ""),
        )


def input_from_text(key: str, text: str) -> SettledInput:
    return SettledInput(key=key, sha256=sha256_text(text))


def input_from_file(key: str, path: Path | str) -> SettledInput:
    return SettledInput(key=key, sha256=sha256_path(path), path=str(path))


def binding_inputs(repo_root: Path, doc_paths: tuple[str, ...]) -> list[SettledInput]:
    """Every binding design doc under ``doc_paths``, hashed, in a stable order.

    Directories are walked; a plain file is taken as itself. Sorted by relative
    POSIX path so the recorded order does not depend on the filesystem's, which
    would make an unchanged input set look changed.
    """
    found: list[SettledInput] = []
    root = Path(repo_root)
    for entry in doc_paths:
        target = root / entry
        if target.is_file():
            found.append(target)
        elif target.is_dir():
            found.extend(p for p in target.rglob("*") if p.is_file())
    unique = sorted({p.resolve(): p for p in found}.values(),
                    key=lambda p: _rel_posix(p, root))
    return [
        input_from_file(f"binding:{_rel_posix(p, root)}", p) for p in unique
    ]


def _rel_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        # fail-open: a path outside the repo (a symlinked doc tree) keeps its
        # absolute form as its key. The key only has to be STABLE, not
        # relative -- an absolute key hashes and compares exactly as well, and
        # refusing here would fail a settlement check over a layout choice.
        return path.as_posix()


def stage_of_artifact_path(path: str, issue: int) -> str | None:
    """Which settleable stage a pipeline artifact path belongs to.

    Mirrors `speedrun_clean_check._artifact_needles`, which is what produces
    the paths this reads. Kept as an explicit mapping rather than a guess: a
    path that matches nothing returns None and is treated as unsettled, so an
    unrecognised artifact never wins a reprieve by accident.
    """
    lower = path.lower().replace("\\", "/")
    if f"spec-{issue:04d}" in lower or f"spec-{issue}" in lower:
        return "spec"
    if f"lld-{issue:03d}" in lower or f"lld-{issue}" in lower:
        return "lld"
    return None


def collect_inputs(
    repo_root: Path | str,
    *,
    issue_body: str | None,
    upstream_artifact: Path | str | None = None,
    doc_paths: tuple[str, ...] = BINDING_DOC_PATHS,
) -> list[SettledInput]:
    """The inputs a derivation at this stage depends on, hashed.

    Pure apart from filesystem reads -- the issue body arrives already fetched,
    so this stays testable without a network and without `gh`. A None body is
    recorded as an unreadable input rather than omitted: an input that could
    not be read must reach `verify` as a mismatch, and omitting it would let a
    failed fetch read as "nothing to check" and settle everything.
    """
    inputs = [SettledInput(key="issue_body", sha256=None)] if issue_body is None \
        else [input_from_text("issue_body", issue_body)]
    if upstream_artifact is not None:
        inputs.append(input_from_file("upstream:artifact", upstream_artifact))
    inputs.extend(binding_inputs(Path(repo_root), doc_paths))
    return inputs


def build_settlement(
    stage: str,
    artifact_path: Path | str,
    inputs: list[SettledInput],
    *,
    verdict: str = "",
) -> dict:
    """The durable record of one artifact having passed its gate."""
    return {
        "settlement_version": SETTLEMENT_VERSION,
        "stage": stage,
        "artifact_path": str(artifact_path),
        "artifact_sha256": sha256_path(artifact_path),
        "verdict": verdict,
        "settled_at": datetime.now(tz=timezone.utc).isoformat(),
        "inputs": [i.as_dict() for i in inputs],
    }


def verify(record: dict | None, current: list[SettledInput]) -> list[str]:
    """Every way the world differs from what was settled. Empty means settled.

    Reported in the reader's terms, not the hasher's: which input, by name,
    and what it hashed then versus now.
    """
    if not isinstance(record, dict) or not record:
        return ["no settlement record exists for this stage"]
    if record.get("settlement_version") != SETTLEMENT_VERSION:
        return [
            f"settlement record is version {record.get('settlement_version')!r}; "
            f"this reader understands {SETTLEMENT_VERSION}"
        ]

    recorded = {
        entry.get("key"): SettledInput.from_dict(entry)
        for entry in record.get("inputs", [])
        if isinstance(entry, dict)
    }
    now = {i.key: i for i in current}

    mismatches: list[str] = []
    for key in sorted(set(recorded) | set(now)):
        was, is_ = recorded.get(key), now.get(key)
        if was is None:
            mismatches.append(
                f"{key}: a new input the settled artifact was not derived from"
            )
        elif is_ is None:
            mismatches.append(
                f"{key}: an input the settled artifact was derived from is gone"
            )
        elif is_.sha256 is None:
            mismatches.append(
                f"{key}: recorded as {_short(was.sha256)} and cannot be read now"
            )
        elif was.sha256 != is_.sha256:
            mismatches.append(
                f"{key}: hashed {_short(was.sha256)} when the artifact settled "
                f"and hashes {_short(is_.sha256)} now"
            )
    return mismatches


def artifact_matches(record: dict | None, artifact_path: Path | str) -> bool:
    """True when the artifact on disk is the one that settled.

    A settled record naming content that has since been hand-edited describes
    an artifact that no longer exists. Reusing the edited file would present an
    operator's unreviewed edit as gate-passed.
    """
    if not isinstance(record, dict) or not record:
        return False
    recorded = record.get("artifact_sha256")
    if not recorded:
        return False
    return sha256_path(artifact_path) == recorded


def evidence_lines(record: dict, current: list[SettledInput]) -> list[str]:
    """The hash evidence a reused stage prints. Short, and per input."""
    lines = [
        f"settled {record.get('settled_at', '?')} "
        f"(verdict {record.get('verdict') or 'n/a'}), "
        f"artifact {_short(record.get('artifact_sha256'))}"
    ]
    by_key = {i.key: i for i in current}
    for entry in record.get("inputs", []):
        key = entry.get("key", "?")
        matched = by_key.get(key)
        lines.append(
            f"  {key}: {_short(entry.get('sha256'))} "
            f"== {_short(matched.sha256 if matched else None)}"
        )
    return lines


def _short(digest: str | None) -> str:
    return str(digest)[:12] if digest else "absent"
