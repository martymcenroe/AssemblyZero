"""File a `must-resolve` issue when N0c finds a requirements conflict (#2072).

N0c detects that an issue's text is internally inconsistent and says so: "an
operator ruling on the issue text is required". Before this module, that finding
went to a run log and nowhere else. N0c is LLM-judged, so a lenient redraw can
pass the same text minutes later and the roll proceeds over an unresolved
ambiguity. Measured live: boostgauge #4, run `run-issue4-111608`
(2026-08-01 11:16 Central) flagged a sampling conflict; the redraw at 11:16:41
passed and rolled. The only reason the operator ever saw it is that an agent
happened to be reading the log.

## Design decisions

**The halt outcome is never changed by this module.** The roll was already
halting when it is called. A filing failure -- no network, no auth, no `gh` --
is loud in the run log and returns a failure result; it never raises, and it
never converts a `REQUIREMENTS CONFLICT` halt into a different result.

**Dedupe reads a marker, not prose.** The fingerprint is embedded in the issue
body as an HTML comment alongside the source issue number. Re-deriving a
normalization from body text a human has since edited would break the moment
someone rewords the issue -- which is exactly what an operator does when ruling
on it.

**The fingerprint is order-independent.** The analysis does not guarantee stable
A/B ordering between runs, so the same conflict arriving with its two criteria
swapped must hash the same or a redraw storm files twenty copies of one
ambiguity.

**The run identifier travels from the launcher through the child environment.**
Only the launcher knows the tag its events / heartbeat / stdout triplet is named
after, and that tag is what a human needs in order to go read the logs. The
workflow's own run id identifies a run within the lineage, which is a different
thing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MUST_RESOLVE_LABEL = "must-resolve"
RUN_TAG_ENV = "SPEEDRUN_RUN_TAG"
RUN_START_ENV = "SPEEDRUN_RUN_START"

_TS_FMT = "%Y-%m-%d %H:%M:%S"
_WHITESPACE = re.compile(r"\s+")

#: Machine-readable dedupe marker. Both halves matter: the same conflict text on
#: a different source issue is a different ambiguity, and a different conflict on
#: the same source issue is too.
_MARKER = "<!-- must-resolve source_issue={issue} fingerprint={fp} -->"
_MARKER_RE = re.compile(
    r"<!--\s*must-resolve\s+source_issue=(?P<issue>\d+)\s+fingerprint=(?P<fp>[0-9a-f]+)\s*-->"
)


# ---------------------------------------------------------------------------
# Fingerprinting
# ---------------------------------------------------------------------------


def normalize_criterion(text: str) -> str:
    """Collapse whitespace and case-fold. Punctuation is deliberately kept.

    `2s` and `5s` differ by one character and nothing else; stripping
    punctuation or digits would collapse genuinely different conflicts onto one
    fingerprint, which is a far worse failure than an occasional near-duplicate.
    """
    return _WHITESPACE.sub(" ", (text or "").strip()).casefold()


def conflict_fingerprint(criterion_a: str, criterion_b: str) -> str:
    """Short, order-independent hash of a conflict's two criteria."""
    parts = sorted([normalize_criterion(criterion_a), normalize_criterion(criterion_b)])
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# gh plumbing
# ---------------------------------------------------------------------------


@dataclass
class FilingResult:
    ok: bool
    action: str  # filed | commented | skipped | failed
    issue_number: int | None = None
    fingerprint: str | None = None
    detail: str = ""


def _default_runner(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except OSError as exc:
        # `gh` not installed. Modelled as a failed call rather than an
        # exception so every caller path stays identical.
        return subprocess.CompletedProcess(args, 127, "", str(exc))


def repo_slug(repo_root: Path | str, runner=_default_runner) -> str | None:
    """`owner/name` from the target repo's origin remote."""
    result = runner(["git", "-C", str(repo_root), "remote", "get-url", "origin"])
    if result.returncode != 0:
        return None
    url = (result.stdout or "").strip()
    for prefix in ("https://github.com/", "git@github.com:"):
        if url.startswith(prefix):
            path = url[len(prefix) :]
            break
    else:
        return None
    return path[:-4] if path.endswith(".git") else path


def run_context(env: dict[str, str] | None = None) -> tuple[str, str]:
    """(run identifier, run start) as handed down by the launcher.

    Absence is expected -- a workflow invoked directly, outside a roll, has no
    launcher and therefore no log triplet to point at. It is reported as
    "unknown" rather than guessed, because a wrong log name sends a human to
    read the wrong file.
    """
    env = env if env is not None else os.environ
    return (
        env.get(RUN_TAG_ENV, "").strip() or "unknown",
        env.get(RUN_START_ENV, "").strip() or "unknown",
    )


# ---------------------------------------------------------------------------
# Body / title construction
# ---------------------------------------------------------------------------


def _first_line_summary(conflict: dict, limit: int = 60) -> str:
    text = normalize_criterion(conflict.get("criterion_a", "")) or "requirements conflict"
    text = text.splitlines()[0] if text else "requirements conflict"
    return text[:limit].rstrip()


def build_title(source_issue: int, conflict: dict) -> str:
    return (
        f"must-resolve: #{source_issue} requirements conflict "
        f"— {_first_line_summary(conflict)}"
    )


def build_body(
    source_issue: int,
    conflict: dict,
    *,
    run_id: str,
    run_start: str,
    conflict_ts: str,
    fingerprint: str,
) -> str:
    return "\n".join([
        "Found by N0c (requirements-consistency gate, #1899) during a live roll. "
        "The gate's own verdict: an operator ruling on the issue text is required "
        "before any roll.",
        "",
        f"**Run:** {run_id} | **Start:** {run_start} | **Conflict reported:** {conflict_ts}",
        "",
        f"**Source issue:** #{source_issue}",
        "",
        "**Conflict (verbatim):**",
        f"- A: {conflict.get('criterion_a', '?')}",
        f"- B: {conflict.get('criterion_b', '?')}",
        f"- Diverge when: {conflict.get('diverging_situation', '?')}",
        "",
        "**Ruling needed:** edit the source issue's text so only one reading "
        "survives, then close this issue. The roll will refuse to launch while "
        "it is open.",
        "",
        _MARKER.format(issue=source_issue, fp=fingerprint),
    ])


# ---------------------------------------------------------------------------
# Filing
# ---------------------------------------------------------------------------


def _find_existing(
    slug: str, source_issue: int, fingerprint: str, runner
) -> int | None:
    """An open must-resolve issue for the same source issue AND fingerprint."""
    result = runner([
        "gh", "issue", "list", "--repo", slug,
        "--label", MUST_RESOLVE_LABEL, "--state", "open",
        "--limit", "100", "--json", "number,body",
    ])
    if result.returncode != 0:
        return None
    try:
        rows = json.loads(result.stdout or "[]")
    except ValueError:
        return None
    for row in rows:
        for match in _MARKER_RE.finditer(row.get("body") or ""):
            if (
                int(match.group("issue")) == source_issue
                and match.group("fp") == fingerprint
            ):
                return int(row.get("number"))
    return None


def _ensure_label(slug: str, runner) -> None:
    runner([
        "gh", "label", "create", MUST_RESOLVE_LABEL, "--repo", slug,
        "--description", "Blocks rolls until an operator rules on the issue text",
        "--color", "B60205",
    ])


def file_must_resolve(
    repo_root: Path | str,
    source_issue: int,
    conflict: dict,
    *,
    run_id: str | None = None,
    run_start: str | None = None,
    conflict_ts: str | None = None,
    runner=_default_runner,
    log=print,
) -> FilingResult:
    """File (or comment on) the must-resolve issue for one conflict.

    Never raises. The roll is already halting; a filing problem is reported and
    the halt outcome is unchanged.
    """
    if not source_issue:
        # Brief and idea entry paths carry file input, not an issue number.
        # There is nothing to file against.
        return FilingResult(True, "skipped", detail="entry path has no issue number")

    env_run_id, env_run_start = run_context()
    run_id = run_id or env_run_id
    run_start = run_start or env_run_start
    conflict_ts = conflict_ts or datetime.now().strftime(_TS_FMT)

    fingerprint = conflict_fingerprint(
        conflict.get("criterion_a", ""), conflict.get("criterion_b", "")
    )

    slug = repo_slug(repo_root, runner=runner)
    if not slug:
        log(f"  [N0c] could not file must-resolve: no GitHub remote for {repo_root}")
        return FilingResult(
            False, "failed", fingerprint=fingerprint, detail="no origin remote"
        )

    existing = _find_existing(slug, source_issue, fingerprint, runner)
    if existing is not None:
        comment = runner([
            "gh", "issue", "comment", str(existing), "--repo", slug,
            "--body",
            f"Detected again — run `{run_id}` at {conflict_ts}. "
            f"Still unresolved; the source issue text has not been ruled on.",
        ])
        if comment.returncode != 0:
            log(f"  [N0c] could not comment on #{existing}: {comment.stderr.strip()}")
            return FilingResult(
                False, "failed", issue_number=existing, fingerprint=fingerprint,
                detail=comment.stderr.strip(),
            )
        log(f"  [N0c] recurrence recorded on existing must-resolve #{existing}")
        return FilingResult(True, "commented", existing, fingerprint)

    title = build_title(source_issue, conflict)
    body = build_body(
        source_issue, conflict, run_id=run_id, run_start=run_start,
        conflict_ts=conflict_ts, fingerprint=fingerprint,
    )
    create_args = [
        "gh", "issue", "create", "--repo", slug,
        "--title", title, "--body", body, "--label", MUST_RESOLVE_LABEL,
    ]

    created = runner(create_args)
    if created.returncode != 0:
        # Most likely the target repo has never had the label. Create it and
        # retry exactly once -- a second failure is a real problem, not a
        # missing label, and looping would delay a halt that already happened.
        _ensure_label(slug, runner)
        created = runner(create_args)

    if created.returncode != 0:
        log(f"  [N0c] could not file must-resolve issue: {created.stderr.strip()}")
        return FilingResult(
            False, "failed", fingerprint=fingerprint, detail=created.stderr.strip()
        )

    number = _issue_number_from_url((created.stdout or "").strip())
    log(f"  [N0c] filed must-resolve issue #{number or '?'} in {slug}")
    return FilingResult(True, "filed", number, fingerprint)


def open_must_resolve_issues(
    repo_root: Path | str, *, runner=_default_runner
) -> tuple[list[dict], str | None]:
    """Open must-resolve issues in the target repo (#2073).

    Returns `(issues, error)`. `error` is non-None when GitHub could not be
    consulted at all -- the caller warns and proceeds in that case. The
    availability of GitHub must not brick local rolls; the auto-filer is the
    enforcement backstop.
    """
    slug = repo_slug(repo_root, runner=runner)
    if not slug:
        return [], f"no GitHub remote for {repo_root}"

    result = runner([
        "gh", "issue", "list", "--repo", slug,
        "--label", MUST_RESOLVE_LABEL, "--state", "open",
        "--limit", "100", "--json", "number,title",
    ])
    if result.returncode != 0:
        return [], (result.stderr or "gh issue list failed").strip()
    try:
        rows = json.loads(result.stdout or "[]")
    except ValueError:
        return [], "could not read the issue list response"
    return [
        {"number": r.get("number"), "title": r.get("title", "")} for r in rows
    ], None


def refusal_message(issues: list[dict]) -> str:
    """Plain English. No stage names, no internal identifiers, no jargon.

    The operator reads this at a terminal, possibly having just been woken by
    it, and must be able to act on it without opening any code or document.
    """
    count = len(issues)
    noun = "question" if count == 1 else "questions"
    lines = [
        f"BLOCKED: this repository has {count} unanswered {noun} about what its "
        f"issue text actually asks for.",
        "",
    ]
    for issue in issues:
        lines.append(f"  #{issue['number']}  {issue['title']}")
    lines += [
        "",
        "  Each was raised because an issue's own wording supports two different",
        "  readings, and building the wrong one wastes the whole run. Decide which",
        "  reading is right, edit that issue so only one reading survives, and close",
        "  the question above. Rolling before then means the outcome is decided by",
        "  which reading the machine happened to pick.",
    ]
    return "\n".join(lines)


def _issue_number_from_url(url: str) -> int | None:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return int(tail) if tail.isdigit() else None


def file_all_conflicts(
    repo_root: Path | str,
    source_issue: int,
    conflicts: list[dict],
    *,
    runner=_default_runner,
    log=print,
) -> list[FilingResult]:
    """One issue per distinct conflict. Never raises."""
    results = []
    for conflict in conflicts or []:
        try:
            results.append(
                file_must_resolve(
                    repo_root, source_issue, conflict, runner=runner, log=log
                )
            )
        except Exception as exc:  # noqa: BLE001 - filing must never kill a halt
            log(f"  [N0c] must-resolve filing raised, continuing: {exc}")
            results.append(FilingResult(False, "failed", detail=str(exc)))
    return results
