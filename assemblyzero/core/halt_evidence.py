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
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from assemblyzero.core.recovery_plan import build_resume_command

#: How many trailing preserved-branch records travel in the bundle. The
#: record has no reliable run-id linkage (leavings refs carry run="" by
#: construction), so the tail is the honest cut, said in the bundle.
PRESERVED_TAIL = 8

#: Event caps keep the markdown a bundle, not a transcript. The JSON always
#: carries everything.
MD_EVENT_CAP = 20


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        # fail-open: an unreadable artifact is reported as unreadable in
        # the bundle rather than crashing the halt that is trying to
        # describe it.
        return None


def _artifact_inventory(audit_dir: Path) -> dict[str, Any]:
    """Every top-level lineage file: name, size, hash — and the identical
    groups, because four byte-identical drafts was the fact a manual dig
    took an md5 loop to establish."""
    files: list[dict[str, Any]] = []
    by_hash: dict[str, list[str]] = {}
    for path in sorted(audit_dir.iterdir()):
        if not path.is_file():
            continue
        digest = _sha256(path)
        files.append({
            "name": path.name,
            "bytes": path.stat().st_size if digest is not None else None,
            "sha256": digest[:12] if digest else None,
        })
        if digest:
            by_hash.setdefault(digest, []).append(path.name)
    identical = sorted(
        names for names in by_hash.values() if len(names) >= 2
    )
    return {"files": files, "identical_groups": identical}


def _preserved_tail(repo_root: Path) -> list[dict[str, Any]]:
    record = repo_root / "data" / "speedrun" / "runs" / "preserved-branches.jsonl"
    if not record.is_file():
        return []
    entries: list[dict[str, Any]] = []
    try:
        for line in record.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                # fail-open: one corrupt record in the preservation log
                # drops that record from the bundle's tail, never the
                # bundle -- the evidence is a best-effort slice of a file
                # this process does not own.
                continue
    except OSError:
        # fail-open: the preservation record is evidence ABOUT the run,
        # not of it -- a bundle without it still carries the events and
        # artifacts, and says nothing false.
        return []
    return entries[-PRESERVED_TAIL:]


def build_halt_evidence(
    state: dict, workflow: str, *, stage: str, error_message: str
) -> dict[str, Any]:
    """The state-side evidence a forensic reader needs, as one document."""
    audit_dir_str = str(state.get("audit_dir", "") or "")
    audit_dir = Path(audit_dir_str) if audit_dir_str else None
    repo_root_str = str(
        state.get("repo_root", "") or state.get("target_repo", "") or ""
    )

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
    if audit_dir is not None and audit_dir.is_dir():
        artifacts = _artifact_inventory(audit_dir)

    preserved: list[dict[str, Any]] = []
    if repo_root_str:
        preserved = _preserved_tail(Path(repo_root_str))

    issue_number = int(state.get("issue_number", 0) or 0)
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
    events = evidence["events"]
    lines += _md_events("Pinning events", events["pinning_events"])
    lines += _md_events("Completeness issues", events["completeness_issues"])
    lines += _md_events("Validation errors", events["validation_errors"])

    artifacts = evidence["artifacts"]
    if artifacts["files"]:
        lines += ["## Lineage artifacts", ""]
        lines += ["| file | bytes | sha256 |", "|---|---|---|"]
        for entry in artifacts["files"]:
            size = entry["bytes"] if entry["bytes"] is not None else "?"
            lines.append(
                f"| {entry['name']} | {size} | {entry['sha256'] or 'unreadable'} |"
            )
        lines.append("")
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
