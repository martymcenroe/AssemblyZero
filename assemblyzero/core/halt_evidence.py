"""Auto-forensics at halt: the evidence bundle, emitted, not excavated (#2574).

The same forensic dig was performed by hand eight times on 2026-08-27:
locate the lineage dir, count and hash the drafts (four byte-identical,
md5-confirmed, was the load-bearing fact of #2555), collect the [PINNING]
events, name the preserved refs, and assemble an issue body from it all.
Every input to that dig is in scope at the moment of the halt; the halt
path used to discard it.

The bundle is state-side evidence: the events the run recorded, the
lineage artifacts with their hashes and identical groups, the refs the
machinery preserved, and a DRAFT issue body — saved, never auto-filed, so
the operator's filing step starts at "verify and sharpen" instead of
"excavate". Log-line excerpts are deliberately NOT here: the halt node is
the process writing the log and cannot portably read its own transcript;
the wrapper-side death detection (#2510) owns that half, and this module's
formats are what it will share.

#3778 (ADR 0236): evidence the bundle cannot read is a failure of its own.
The HALT node builds the bundle after the halt has alerted and its state and
plan are saved, so the bundle is written, and every piece it could not read is
named in ``unread_evidence`` and in the markdown, never left out as if it were
not there. An unreadable lineage artifact, an unreadable preservation record
and a corrupt record in its tail each alert the operator with the cause. A
lineage directory the state names and that is not there is an ERROR line: the
HALT node's copy into that directory raises on it and alerts. An alert that
cannot be delivered raises out of the bundle, and so out of the HALT node.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assemblyzero.core import alert
from assemblyzero.core.recovery_plan import build_resume_command

logger = logging.getLogger(__name__)

#: How many trailing preserved-branch records travel in the bundle. The
#: record has no reliable run-id linkage (leavings refs carry run="" by
#: construction), so the tail is the honest cut, said in the bundle.
PRESERVED_TAIL = 8

#: Event caps keep the markdown a bundle, not a transcript. The JSON always
#: carries everything.
MD_EVENT_CAP = 20


@dataclass
class _Gathering:
    """Whose halt the bundle describes, and what it could not read (#3778).

    ``unread`` names every piece of evidence the bundle could not gather, each
    already alerted (or, for a missing lineage dir, an ERROR line), so the
    bundle says what it is missing instead of reading as complete.
    """

    workflow: str
    repo: str
    issue: int
    unread: list[str] = field(default_factory=list)

    def where(self, function: str) -> str:
        return f"assemblyzero.core.halt_evidence.{function} ({self.workflow} HALT)"


def _sha256(path: Path) -> str:
    """The file's content hash. A file that cannot be read raises (#3778)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_inventory(audit_dir: Path, gathering: _Gathering) -> dict[str, Any]:
    """Every top-level lineage file: name, size, hash — and the identical
    groups, because four byte-identical drafts was the fact a manual dig
    took an md5 loop to establish.

    A file that cannot be read alerts the operator with its cause (#3778). Its
    row stays, with no hash and the cause under ``unreadable``, and the groups
    are over the readable files only, which the markdown says. The bundle is
    still written: it is the halt's evidence, and raising would cost the
    operator every other artifact and event for one file.
    """
    files: list[dict[str, Any]] = []
    by_hash: dict[str, list[str]] = {}
    for path in sorted(audit_dir.iterdir()):
        if not path.is_file():
            continue
        try:
            digest = _sha256(path)
        except OSError as exc:
            cause = f"{type(exc).__name__}: {exc}"
            gathering.unread.append(f"lineage artifact {path}: {cause}")
            files.append({"name": path.name, "bytes": None, "sha256": None, "unreadable": cause})
            alert.alert_operator(
                what=f"cannot read the lineage artifact {path} for the halt's evidence bundle",
                where=gathering.where("_artifact_inventory"),
                cause=cause,
                consequence=(
                    "the bundle lists the file as unreadable and leaves it out of the "
                    "byte-identical groups; the halt's own alert, state and plan stand"
                ),
                repo=gathering.repo,
                issue=gathering.issue or None,
            )
        else:
            files.append({
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": digest[:12],
            })
            by_hash.setdefault(digest, []).append(path.name)
    identical = sorted(
        names for names in by_hash.values() if len(names) >= 2
    )
    return {"files": files, "identical_groups": identical}


def _parse_record(line: str) -> dict[str, Any]:
    """One preservation record. A line that is not a JSON object raises."""
    entry = json.loads(line)
    if not isinstance(entry, dict):
        raise TypeError(f"the line holds a JSON {type(entry).__name__}, not a record")
    return entry


def _preserved_tail(repo_root: Path, gathering: _Gathering) -> list[dict[str, Any]]:
    """The last ``PRESERVED_TAIL`` records of the repo's preservation log.

    No log is an answer: no branch was ever preserved in this repo, so the
    bundle has none to list. Only the tail is read, because only the tail is
    carried; a line before it shapes nothing in the bundle.

    A log that exists and cannot be read, and a record in the tail that is not
    a JSON object, each alert the operator with the cause (#3778). A corrupt
    record keeps its place in the tail as ``{"corrupt_line": n, "cause": ...}``
    so the tail is never short, and both are named in ``unread_evidence``.
    """
    record = repo_root / "data" / "speedrun" / "runs" / "preserved-branches.jsonl"
    if not record.is_file():
        return []
    try:
        text = record.read_text(encoding="utf-8")
    except OSError as exc:
        cause = f"{type(exc).__name__}: {exc}"
        gathering.unread.append(f"preservation record {record}: {cause}")
        alert.alert_operator(
            what=f"cannot read the preservation record {record} for the halt's evidence bundle",
            where=gathering.where("_preserved_tail"),
            cause=cause,
            consequence=(
                "the bundle names the record as unreadable and lists no preserved "
                "refs; the halt's own alert, state and plan stand"
            ),
            repo=gathering.repo,
            issue=gathering.issue or None,
        )
        return []
    numbered = [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    entries: list[dict[str, Any]] = []
    for number, line in numbered[-PRESERVED_TAIL:]:
        try:
            entries.append(_parse_record(line))
        except (ValueError, TypeError) as exc:  # JSONDecodeError is a ValueError
            cause = f"{type(exc).__name__}: {exc}"
            gathering.unread.append(f"preservation record {record} line {number}: {cause}")
            entries.append({"corrupt_line": number, "cause": cause})
            alert.alert_operator(
                what=(
                    f"line {number} of the preservation record {record} is not a "
                    f"record, in the halt's evidence bundle"
                ),
                where=gathering.where("_preserved_tail"),
                cause=cause,
                consequence=(
                    "the bundle's tail shows the line as a corrupt record; the "
                    "halt's own alert, state and plan stand"
                ),
                repo=gathering.repo,
                issue=gathering.issue or None,
            )
    return entries


def build_halt_evidence(
    state: dict, workflow: str, *, stage: str, error_message: str
) -> dict[str, Any]:
    """The state-side evidence a forensic reader needs, as one document.

    ``unread_evidence`` lists what could not be gathered (#3778); see
    ``_artifact_inventory`` and ``_preserved_tail``. A state that names no
    audit dir or no repo has nothing of that kind to read, which is quiet.
    An audit dir it names that is not a directory is an ERROR line and is
    listed; the HALT node's copy into that dir raises on it and alerts, so a
    second alert here would only repeat that one.
    """
    audit_dir_str = str(state.get("audit_dir", "") or "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    repo_root_str = str(
        state.get("repo_root", "") or state.get("target_repo", "") or ""
    )
    issue_number = int(state.get("issue_number", 0) or 0)
    gathering = _Gathering(workflow=workflow, repo=repo_root_str, issue=issue_number)

    events: dict[str, list[str]] = {
        "pinning_events": [str(e) for e in state.get("pinning_events") or []],
        "completeness_issues": [
            str(i) for i in state.get("completeness_issues") or []
        ],
        "validation_errors": [
            str(e) for e in state.get("validation_errors") or []
        ],
    }

    artifacts: dict[str, Any] = {"files": [], "identical_groups": []}
    if audit_dir is not None:
        if audit_dir.is_dir():
            artifacts = _artifact_inventory(audit_dir, gathering)
        else:
            message = (
                f"the state names audit_dir {audit_dir}, which is not a directory, "
                f"so the {workflow} halt's evidence bundle has no lineage artifacts"
            )
            gathering.unread.append(f"lineage dir {audit_dir}: not a directory")
            logger.error("[HALT EVIDENCE] %s", message)
            print(f"ERROR [HALT EVIDENCE] {message}", file=sys.stderr, flush=True)

    preserved: list[dict[str, Any]] = []
    if repo_root_str:
        preserved = _preserved_tail(Path(repo_root_str), gathering)

    return {
        "bundle_version": 2,
        "workflow": workflow,
        "issue": issue_number,
        "stage": stage,
        "halted_at": datetime.now(tz=timezone.utc).isoformat(),
        "error_message": error_message,
        # #2725: the three things a reader needs and had to reconstruct by hand.
        # When only a spending limit may end a run, a cap that fires and leaves
        # no way to pick the work back up has turned a limit into a loss.
        "gate_key": gate_key_for(error_message),
        "outstanding": outstanding_items(state),
        "resume_command": build_resume_command(workflow, issue_number, state),
        "counters": {
            "review_iteration": state.get("review_iteration", 0),
            "iteration_count": state.get("iteration_count", 0),
            "max_iterations": state.get("max_iterations", 0),
        },
        "events": events,
        "audit_dir": audit_dir_str,
        "artifacts": artifacts,
        "preserved_refs_tail": preserved,
        "unread_evidence": gathering.unread,
    }


def gate_key_for(error_message: str) -> str:
    """The registry key this halt belongs to, by the two readings in use.

    The `[gate:<key>]` tag a `halted()` site appends (#2719) is authoritative
    where it exists. Retagging the 160 legacy sites is #2723's job, so most
    halts still emit untagged prose and the cause classifier is the bridge --
    the same pair of readings the terminal record uses (#2721), deliberately,
    so a bundle and a record never disagree about which gate fired.
    """
    head = (error_message or "").strip().splitlines()
    if not head:
        return ""
    from assemblyzero.core.gate_registry import gate_key_of
    from assemblyzero.speedrun.factory_report import classify_cause

    return gate_key_of(error_message) or classify_cause(head[0])


def outstanding_items(state: dict[str, Any]) -> list[str]:
    """What the run was still being asked for when the cap fired.

    A review cap's whole content is the last verdict's items: run
    run-issue4-183941 stopped at the ninth round with three assertions still
    demanded, and nothing in the bundle said which three. `review_feedback`
    holds the last verdict, and `review_feedback_history` is consulted only if
    the last round left the field empty -- a cap can fire on a round whose
    feedback never landed on the state.

    Deliberately NOT merged with `completeness_issues`: those are the mechanical
    validator's findings and already have their own field. Two different judges
    with two different remedies do not belong in one list.
    """
    feedback = str(state.get("review_feedback", "") or "").strip()
    if not feedback:
        history = [
            str(entry).strip()
            for entry in (state.get("review_feedback_history") or [])
            if str(entry).strip()
        ]
        feedback = history[-1] if history else ""
    if not feedback:
        return []
    items = [
        line.strip().lstrip("-").strip()
        for line in feedback.splitlines()
        if line.strip().startswith("-")
    ]
    return items or [feedback]


def _md_events(title: str, lines: list[str]) -> list[str]:
    if not lines:
        return []
    out = [f"## {title}", ""]
    for line in lines[:MD_EVENT_CAP]:
        out.append(f"> {line}")
    if len(lines) > MD_EVENT_CAP:
        out.append(
            f"> (and {len(lines) - MD_EVENT_CAP} more; the JSON bundle "
            f"carries all of them)"
        )
    out.append("")
    return out


def render_halt_evidence_md(evidence: dict[str, Any]) -> str:
    """The bundle as a document, ending in the draft issue body."""
    lines: list[str] = [
        f"# Halt evidence — {evidence['workflow']} #{evidence['issue']}, "
        f"{evidence['stage']}",
        "",
        f"Halted at {evidence['halted_at']}. Assembled by the halt path "
        f"(#2574) from state-side evidence; the run log carries the full "
        f"transcript.",
        "",
        "## What halted",
        "",
        f"> {evidence['error_message']}",
        "",
        f"Counters: iteration {evidence['counters']['review_iteration']}"
        f"/{evidence['counters']['max_iterations']} (review), "
        f"{evidence['counters']['iteration_count']} (loop).",
        "",
    ]
    # #2725: gate, outstanding work, and the way back in -- above the artifact
    # inventory, because a reader arriving at a cap needs those three first.
    if evidence.get("gate_key"):
        lines += [f"Gate: `{evidence['gate_key']}`", ""]
    outstanding = evidence.get("outstanding") or []
    if outstanding:
        lines += [
            f"## Still outstanding when the run stopped ({len(outstanding)})",
            "",
        ]
        lines += [f"- {item}" for item in outstanding]
        lines.append("")
    if evidence.get("resume_command"):
        lines += ["## Resume", "", f"```\n{evidence['resume_command']}\n```", ""]
    # #3778: what the bundle could not read is said, never left out.
    unread = evidence["unread_evidence"]
    if unread:
        lines += [f"## Evidence that could not be read ({len(unread)})", ""]
        lines += [f"- {item}" for item in unread]
        lines.append("")
    events = evidence["events"]
    lines += _md_events("Pinning events", events["pinning_events"])
    lines += _md_events("Completeness issues", events["completeness_issues"])
    lines += _md_events("Validation errors", events["validation_errors"])

    artifacts = evidence["artifacts"]
    if artifacts["files"]:
        lines += ["## Lineage artifacts", ""]
        lines += ["| file | bytes | sha256 |", "|---|---|---|"]
        unreadable = 0
        for entry in artifacts["files"]:
            size = entry["bytes"] if entry["bytes"] is not None else "?"
            digest = entry["sha256"]
            if digest is None:
                unreadable += 1
                digest = f"unreadable ({entry['unreadable']})"
            lines.append(f"| {entry['name']} | {size} | {digest} |")
        lines.append("")
        if unreadable:
            lines += [
                (
                    f"Byte-identical groups are over the readable files only; "
                    f"{unreadable} file(s) could not be read."
                ),
                "",
            ]
        for group in artifacts["identical_groups"]:
            lines.append(
                f"**Byte-identical group:** {', '.join(group)} — "
                f"{len(group)} file(s), one content."
            )
        if artifacts["identical_groups"]:
            lines.append("")

    if evidence["preserved_refs_tail"]:
        lines += [
            "## Preserved refs (tail of the preservation record; no "
            "run-id linkage exists, so this is the recent slice)",
            "",
        ]
        for entry in evidence["preserved_refs_tail"]:
            if "corrupt_line" in entry:
                lines.append(
                    f"- line {entry['corrupt_line']}: corrupt record ({entry['cause']})"
                )
                continue
            lines.append(
                f"- {entry.get('at', '?')} `{entry.get('branch', '?')}` "
                f"({entry.get('source', '?')}: {entry.get('detail', '')})"
            )
        lines.append("")

    head = (evidence["error_message"] or "halt with no message").splitlines()[0]
    lines += [
        "## Draft issue body (verify and sharpen before filing — never "
        "auto-filed)",
        "",
        f"**Suggested title:** {head[:120]}",
        "",
        "```markdown",
        f"Observed on the {evidence['workflow']} workflow for issue "
        f"#{evidence['issue']}, stage {evidence['stage']}, "
        f"{evidence['halted_at']}.",
        "",
        "## What the halt said",
        "",
        f"> {evidence['error_message']}",
        "",
        "## Evidence",
        "",
        f"- Lineage: `{evidence['audit_dir'] or '(no audit dir)'}`",
        f"- {len(events['pinning_events'])} pinning event(s), "
        f"{len(events['completeness_issues'])} completeness issue(s) — "
        f"quoted in halt-evidence.md beside this draft",
        f"- {len(artifacts['identical_groups'])} byte-identical artifact "
        f"group(s)",
    ]
    if unread:
        lines.append(
            f"- {len(unread)} piece(s) of evidence could not be read — listed "
            f"in halt-evidence.md beside this draft"
        )
    lines += [
        "",
        "## Repro state",
        "",
        "Preserved, read-only: the lineage dir above and the refs listed "
        "in halt-evidence.md.",
        "```",
        "",
    ]
    return "\n".join(lines)


def write_halt_evidence(
    evidence: dict[str, Any], directory: Path
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "halt-evidence.json"
    md_path = directory / "halt-evidence.md"
    json_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    md_path.write_text(render_halt_evidence_md(evidence), encoding="utf-8")
    return json_path, md_path
