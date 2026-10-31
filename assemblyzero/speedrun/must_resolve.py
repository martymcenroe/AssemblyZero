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
halting when it is called. A filing failure -- no network, no auth, no `gh`, a
ledger that cannot be written -- alerts the operator with its cause (ADR 0236)
and returns a failed result; it never converts a `REQUIREMENTS CONFLICT` halt
into a different result. A failure here means a conflict the launch gate may
not see, which is exactly what the operator has to be told.

**The launch gate never reads "could not check" as "nothing open".** When
GitHub cannot be asked, `open_must_resolve_issues` alerts and returns the
error, and the launcher refuses. The filed-questions ledger reads as empty only
when it does not exist; one it cannot read, or a corrupt line in it, alerts and
raises, because a skipped line can hide an open question.

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

from assemblyzero.core import alert
from assemblyzero.core.github_writes import inert_reason, suppress_if_inert

MUST_RESOLVE_LABEL = "must-resolve"
_WHERE = "assemblyzero/speedrun/must_resolve.py"
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
# Is this filing something an operator can actually rule on? (#2462)
# ---------------------------------------------------------------------------
#
# boostgauge #344 was filed with this conflict block, verbatim:
#
#     - A: alpha at distance 2 reads fully opaque; at 2.5 midway within +/-10; at 3 baseline
#     - B: additive bloom on the body
#     - Diverge when: ?
#
# The `?` is this module's own renderer default showing through: the model
# returned no `diverging_situation`, `build_body` substituted `?`, and the
# result was a launch-blocking question with nothing to rule ON.
#
# The must-resolve contract is "edit the source issue so only one reading
# survives", which presupposes the filing names where the two readings part.
# A filing that does not delegates the gate's own job -- articulating the
# conflict -- to the operator, at launch-blocking priority. By the fleet's
# no-false-alarms rule, a check that files what it cannot articulate trains the
# operator to skim its filings.
#
# Deliberately narrow: the DIVERGENCE only. `conflict_from_rationale` emits an
# empty `criterion_b` on purpose when the reviewer's prose cannot be split in
# two (#2192, "a slightly coarse issue is worth having; a missing one is the
# defect"), and rejecting that would re-open the blocked-roll-with-no-question
# defect this module exists to close.

#: One letter or digit anywhere is enough to be saying something. A condition
#: made only of punctuation -- `?`, `-`, `...` -- is not.
_HAS_MEANING = re.compile(r"[^\W_]", re.UNICODE)

#: Words that fill the slot without answering it. Punctuation-only strings are
#: not listed here -- the check above owns those, and a second list of `?`,
#: `??`, `???` would be dead the day it was written.
_PLACEHOLDER_WORDS = frozenset({
    "n/a", "na", "none", "null", "nil", "unknown", "unclear", "unspecified",
    "tbd", "todo",
})


def unanswerable_reason(conflict: dict) -> str | None:
    """Why this conflict cannot be ruled on, or None if it can be (#2462).

    Returns a phrase naming the defect, so a rejection is surfaced by name
    rather than dropped -- the pairing may sit near a real conflict even when
    the model could not articulate it, which is exactly what happened on #344.
    """
    stated = str(conflict.get("diverging_situation") or "").strip()
    if not stated:
        return "the model stated no situation where the two readings diverge"
    if not _HAS_MEANING.search(stated):
        return (
            "the divergence condition is punctuation only "
            f"({stated!r}), so there is nothing to rule on"
        )
    if stated.casefold() in _PLACEHOLDER_WORDS:
        return (
            f"the divergence condition is the placeholder {stated!r}, "
            "so there is nothing to rule on"
        )
    return None


# ---------------------------------------------------------------------------
# gh plumbing
# ---------------------------------------------------------------------------


@dataclass
class FilingResult:
    ok: bool
    action: str  # filed | commented | skipped | suppressed | rejected | failed
    issue_number: int | None = None
    fingerprint: str | None = None
    detail: str = ""


class MustResolveError(RuntimeError):
    """GitHub could not answer a question the filer needs answered."""


def _default_runner(args: list[str]) -> subprocess.CompletedProcess:
    # #2826: the filer's own runner honours the same switch as run_command,
    # so even a caller that bypasses the explicit branch in file_must_resolve
    # cannot write under a replay.
    suppressed = suppress_if_inert(args)
    if suppressed is not None:
        return suppressed
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


@dataclass(frozen=True)
class Origin:
    """Which gate found the conflict (#2192).

    The body used to state "Found by N0c" unconditionally. That is false on a
    filing from the spec reviewer, and the operator reading the issue needs to
    know which gate ruled -- an LLD-stage conflict and a spec-stage one are
    found against different documents.
    """

    tag: str        # short label for log lines
    sentence: str   # the provenance sentence that opens the issue body


N0C_ORIGIN = Origin(
    "N0c",
    "Found by N0c (requirements-consistency gate, #1899) during a live roll. "
    "The gate's own verdict: an operator ruling on the issue text is required "
    "before any roll.",
)

SPEC_REVIEW_ORIGIN = Origin(
    "spec review",
    "Found by the implementation-spec reviewer (#1900 escalation) during a live "
    "roll, after the LLD had already passed. The reviewer's verdict: two source "
    "requirements specify different outcomes for the same situation, so no spec "
    "can satisfy both and an operator ruling is required before any roll.",
)


#: The reviewer is told to quote the two conflicting sentences verbatim, so
#: quoted spans are the signal. Straight and curly pairs both appear in model
#: output, and a run that files nothing because of a typographic quote would
#: reproduce the very defect this exists to close.
_QUOTED = re.compile(r'"([^"]{8,})"|“([^”]{8,})”')
_DIVERGE = re.compile(r"[^.!?]*\bdiverge\w*\b[^.!?]*[.!?]", re.IGNORECASE)


def conflict_from_rationale(rationale: str, marker: str = "REQUIREMENTS CONFLICT:") -> dict:
    """A conflict dict from the spec reviewer's free-text rationale (#2192).

    N0c hands over a structured conflict; the spec reviewer writes prose behind
    a marker. Parsing is best-effort ON PURPOSE: when the two sentences cannot
    be separated, the whole finding becomes criterion A rather than the filing
    being skipped. A slightly coarse issue is worth having; a missing one is the
    defect -- it left a blocked roll with no question to resolve, an empty
    launch gate, and a re-roll straight back into the same wall.

    The result is deterministic for the same text, so the fingerprint is stable
    and a repeat detection comments on the existing issue instead of duplicating.
    """
    text = (rationale or "").strip()
    head, sep, tail = text.partition(marker)
    body = (tail if sep else text).strip()

    quotes = [a or b for a, b in _QUOTED.findall(body)]
    if len(quotes) >= 2:
        diverge = _DIVERGE.search(body)
        return {
            "criterion_a": quotes[0].strip(),
            "criterion_b": quotes[1].strip(),
            "diverging_situation": (
                diverge.group(0).strip() if diverge
                else "see the reviewer's finding above"
            ),
        }

    return {
        "criterion_a": body or text,
        "criterion_b": "",
        "diverging_situation": (
            "the reviewer did not quote two separable sentences; its full "
            "finding is recorded above"
        ),
    }


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
    origin: Origin = N0C_ORIGIN,
) -> str:
    return "\n".join([
        origin.sentence,
        "",
        f"**Run:** {run_id} | **Start:** {run_start} | **Conflict reported:** {conflict_ts}",
        "",
        f"**Source issue:** #{source_issue}",
        "",
        "**Conflict (verbatim):**",
        # `(not stated)` rather than `?`: the bare question mark is what made
        # #344 unreadable as a question at all. An empty divergence can no
        # longer reach here (unanswerable_reason rejects it before filing), and
        # an empty criterion says so in words (#2462).
        f"- A: {conflict.get('criterion_a') or '(not stated)'}",
        f"- B: {conflict.get('criterion_b') or '(not stated)'}",
        f"- Diverge when: {conflict.get('diverging_situation') or '(not stated)'}",
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
    """An open must-resolve issue for the same source issue AND fingerprint.

    None means GitHub answered and holds no such issue. A query that fails, or
    an answer that is not a list of issues, raises `MustResolveError`: reading
    it as "none found" would file a duplicate of a question already open.
    """
    result = runner([
        "gh", "issue", "list", "--repo", slug,
        "--label", MUST_RESOLVE_LABEL, "--state", "open",
        "--limit", "100", "--json", "number,body",
    ])
    if result.returncode != 0:
        raise MustResolveError(
            f"gh issue list --repo {slug} exited {result.returncode}: "
            f"{(result.stderr or '').strip()}"
        )
    try:
        rows = json.loads(result.stdout or "[]")
    except ValueError as exc:
        raise MustResolveError(
            f"gh issue list --repo {slug} answered with something that is not "
            f"JSON ({exc}): {(result.stdout or '')[:200]!r}"
        ) from exc
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise MustResolveError(
            f"gh issue list --repo {slug} answered with something that is not "
            f"a list of issues: {(result.stdout or '')[:200]!r}"
        )
    for row in rows:
        for match in _MARKER_RE.finditer(row.get("body") or ""):
            if (
                int(match.group("issue")) == source_issue
                and match.group("fp") == fingerprint
            ):
                return int(row.get("number"))
    return None


def _ensure_label(slug: str, runner) -> subprocess.CompletedProcess:
    """Create the label, returning gh's answer for the caller to report.

    A failure here is not reported on its own: when the retried issue create
    then succeeds, the issue carries the label, which proves it exists (the
    usual case is a label that already existed). When the retry fails, the
    caller names this answer's exit code and stderr beside the create's.
    """
    return runner([
        "gh", "label", "create", MUST_RESOLVE_LABEL, "--repo", slug,
        "--description", "Blocks rolls until an operator rules on the issue text",
        "--color", "B60205",
    ])


def _filing_failed(
    *,
    what: str,
    cause: str,
    consequence: str,
    repo_root: Path | str,
    source_issue: int,
    origin: Origin,
    log,
    fingerprint: str | None = None,
    issue_number: int | None = None,
    action: str = "failed",
) -> FilingResult:
    """Alert the operator about one filing failure and return the failed result.

    The roll is already halting, so nothing more can stop; the alert is what
    tells the operator that a conflict may have no question on GitHub, or
    none in the ledger the launch gate reads.
    """
    log(f"  [{origin.tag}] ERROR: {what}: {cause}")
    alert.alert_operator(
        what=what,
        where=f"{_WHERE} file_must_resolve ({origin.tag} gate)",
        cause=cause,
        consequence=consequence,
        repo=str(repo_root),
        issue=source_issue,
    )
    return FilingResult(False, action, issue_number, fingerprint, detail=cause)


_NOT_FILED = (
    "no must-resolve question exists for this conflict, so the launch gate "
    "will not refuse a re-roll on it; the run still halts. Rule on the source "
    "issue's text before rolling it again"
)

_NOT_RECORDED = (
    "the filed-questions ledger does not hold this question, so the run "
    "summary and the next launch's gate see it only if GitHub lists it; "
    "the run still halts"
)


def file_must_resolve(
    repo_root: Path | str,
    source_issue: int,
    conflict: dict,
    *,
    run_id: str | None = None,
    run_start: str | None = None,
    conflict_ts: str | None = None,
    origin: Origin = N0C_ORIGIN,
    runner=_default_runner,
    log=print,
) -> FilingResult:
    """File (or comment on) the must-resolve issue for one conflict.

    The roll is already halting, and the halt outcome is unchanged. Every
    filing failure -- a GitHub call that fails or answers nonsense, an issue
    created with no number, a ledger line that cannot be written, a conflict
    with nothing to rule on -- alerts the operator and returns a failed (or
    rejected) result. Only an alert that cannot be delivered, or an exception
    out of the runner itself, leaves this function.

    `origin` says which gate found it (#2192). The fingerprint deliberately does
    NOT include it: the same contradiction found at the LLD stage and again at
    the spec stage is one question for the operator, so the second detection
    comments on the first issue instead of opening a duplicate.
    """
    if not source_issue:
        # Brief and idea entry paths carry file input, not an issue number.
        # There is nothing to file against.
        return FilingResult(True, "skipped", detail="entry path has no issue number")

    def failed(what, cause, consequence=_NOT_FILED, **kw) -> FilingResult:
        return _filing_failed(
            what=what, cause=cause, consequence=consequence, repo_root=repo_root,
            source_issue=source_issue, origin=origin, log=log, **kw,
        )

    # #2462: never file a question nothing can answer. Enforced HERE, at the
    # filing boundary, so both gates that file -- N0c and the spec reviewer --
    # get the invariant from one predicate rather than each carrying a copy.
    unanswerable = unanswerable_reason(conflict)
    if unanswerable:
        log(
            f"  [{origin.tag}] NOT FILED: {unanswerable}. The pairing is "
            "reported here rather than raised as a question, because a "
            "must-resolve with nothing to rule on blocks every later launch "
            "and cannot be closed by ruling:"
        )
        log(f"      A: {conflict.get('criterion_a', '') or '(not stated)'}")
        log(f"      B: {conflict.get('criterion_b', '') or '(not stated)'}")
        return failed(
            f"file a must-resolve question for a conflict on #{source_issue}",
            unanswerable,
            consequence=(
                "the conflict is not filed, so no question blocks a re-roll; "
                "the pairing printed in the run log is all there is to rule on"
            ),
            action="rejected",
        )

    env_run_id, env_run_start = run_context()
    run_id = run_id or env_run_id
    run_start = run_start or env_run_start
    conflict_ts = conflict_ts or datetime.now().strftime(_TS_FMT)

    fingerprint = conflict_fingerprint(
        conflict.get("criterion_a", ""), conflict.get("criterion_b", "")
    )

    # #2826: a replay never writes to GitHub. On 2026-09-04 a replay of a
    # halted run reached this point and filed boostgauge #434 -- a copy of a
    # question already ruled and closed -- and the next launch was refused by
    # it. The suppressed filing is recorded in the ledger without a number so
    # the replay report can still say "this run would have asked here", and
    # the launcher's reader, which keys on the number, never counts it.
    inert = inert_reason()
    if inert:
        log(
            f"  [{origin.tag}] NOT FILED ({inert}): GitHub writes are inert. "
            f"A live roll would have raised must-resolve fingerprint {fingerprint} "
            f"against #{source_issue}."
        )
        try:
            record_filed(
                repo_root, number=None, title=build_title(source_issue, conflict),
                fingerprint=fingerprint, run_id=run_id, ts=conflict_ts,
                suppressed=inert,
            )
        except (OSError, ValueError) as exc:
            return failed(
                f"record the suppressed must-resolve question for #{source_issue}",
                f"{type(exc).__name__}: {exc}",
                consequence=(
                    "the replay report cannot say this run would have asked a "
                    "question here; nothing was filed, and the run still halts"
                ),
                fingerprint=fingerprint,
            )
        return FilingResult(True, "suppressed", None, fingerprint, detail=inert)

    slug = repo_slug(repo_root, runner=runner)
    if not slug:
        return failed(
            f"file a must-resolve question for a conflict on #{source_issue}",
            f"no GitHub origin remote for {repo_root}",
            fingerprint=fingerprint,
        )

    try:
        existing = _find_existing(slug, source_issue, fingerprint, runner)
    except MustResolveError as exc:
        return failed(
            f"check {slug} for an open must-resolve question on #{source_issue} "
            "before filing one",
            str(exc),
            consequence=(
                "nothing is filed, because filing without the check could open "
                "a duplicate of a question already open; " + _NOT_FILED
            ),
            fingerprint=fingerprint,
        )

    if existing is not None:
        comment = runner([
            "gh", "issue", "comment", str(existing), "--repo", slug,
            "--body",
            f"Detected again — run `{run_id}` at {conflict_ts}. "
            f"Still unresolved; the source issue text has not been ruled on.",
        ])
        if comment.returncode != 0:
            return failed(
                f"comment the recurrence on must-resolve #{existing} in {slug}",
                f"gh issue comment exited {comment.returncode}: "
                f"{(comment.stderr or '').strip()}",
                consequence=(
                    f"#{existing} does not show this recurrence and it is not "
                    "recorded in the ledger; the question is still open on "
                    "GitHub and the run still halts"
                ),
                fingerprint=fingerprint, issue_number=existing,
            )
        log(f"  [{origin.tag}] recurrence recorded on existing must-resolve #{existing}")
        # #2179: a recurrence is still an OPEN question blocking this run, so
        # it belongs in the summary and the gate exactly like a fresh filing.
        try:
            record_filed(
                repo_root, number=existing, title=build_title(source_issue, conflict),
                fingerprint=fingerprint, run_id=run_id, ts=conflict_ts,
            )
        except (OSError, ValueError) as exc:
            return failed(
                f"record must-resolve #{existing} in the filed-questions ledger",
                f"{type(exc).__name__}: {exc}",
                consequence=_NOT_RECORDED,
                fingerprint=fingerprint, issue_number=existing,
            )
        return FilingResult(True, "commented", existing, fingerprint)

    title = build_title(source_issue, conflict)
    body = build_body(
        source_issue, conflict, run_id=run_id, run_start=run_start,
        conflict_ts=conflict_ts, fingerprint=fingerprint, origin=origin,
    )
    create_args = [
        "gh", "issue", "create", "--repo", slug,
        "--title", title, "--body", body, "--label", MUST_RESOLVE_LABEL,
    ]

    created = runner(create_args)
    label = None
    if created.returncode != 0:
        # Most likely the target repo has never had the label. Create it and
        # retry exactly once -- a second failure is a real problem, not a
        # missing label, and looping would delay a halt that already happened.
        label = _ensure_label(slug, runner)
        created = runner(create_args)

    if created.returncode != 0:
        cause = (
            f"gh issue create exited {created.returncode}: "
            f"{(created.stderr or '').strip()}"
        )
        if label is not None and label.returncode != 0:
            cause += (
                f"; before the retry, gh label create exited {label.returncode}: "
                f"{(label.stderr or '').strip()}"
            )
        return failed(
            f"file a must-resolve question for a conflict on #{source_issue} in {slug}",
            cause,
            fingerprint=fingerprint,
        )

    url = (created.stdout or "").strip()
    number = _issue_number_from_url(url)
    if number is None:
        return failed(
            f"read the number of the must-resolve question just filed for "
            f"#{source_issue} in {slug}",
            f"gh issue create succeeded but its output names no issue number: {url!r}",
            consequence=(
                "the question may exist on GitHub but is not in the "
                "filed-questions ledger, so the run summary and the launch "
                "gate see it only if GitHub lists it; check "
                f"`gh issue list --repo {slug} --label {MUST_RESOLVE_LABEL}`"
            ),
            fingerprint=fingerprint,
        )
    log(f"  [{origin.tag}] filed must-resolve issue #{number} in {slug}")
    # #2179: record it HERE, where the number is known. The launcher used to
    # re-derive the list from a live query seconds later, which returns short
    # while GitHub is still indexing -- and that short answer fed both the
    # operator summary and the launch gate.
    try:
        record_filed(
            repo_root, number=number, title=title,
            fingerprint=fingerprint, run_id=run_id, ts=conflict_ts,
        )
    except (OSError, ValueError) as exc:
        return failed(
            f"record must-resolve #{number} in the filed-questions ledger",
            f"{type(exc).__name__}: {exc}",
            consequence=_NOT_RECORDED,
            fingerprint=fingerprint, issue_number=number,
        )
    return FilingResult(True, "filed", number, fingerprint)


def open_must_resolve_issues(
    repo_root: Path | str, *, runner=_default_runner
) -> tuple[list[dict], str | None]:
    """Open must-resolve issues in the target repo (#2073).

    Returns `(issues, error)`. `error` is non-None when GitHub could not be
    consulted, and the operator has already been alerted with its cause. It is
    a failed check, never an empty one (ADR 0236): the launcher refuses to
    launch on it, and the run summary says the list could not be read.
    """
    slug = repo_slug(repo_root, runner=runner)
    if not slug:
        return _gate_failed(repo_root, f"no GitHub origin remote for {repo_root}")

    result = runner([
        "gh", "issue", "list", "--repo", slug,
        "--label", MUST_RESOLVE_LABEL, "--state", "open",
        "--limit", "100", "--json", "number,title",
    ])
    if result.returncode != 0:
        return _gate_failed(
            repo_root,
            f"gh issue list --repo {slug} exited {result.returncode}: "
            f"{(result.stderr or '').strip() or 'no stderr'}",
        )
    try:
        rows = json.loads(result.stdout or "[]")
    except ValueError as exc:
        return _gate_failed(
            repo_root,
            f"gh issue list --repo {slug} answered with something that is not "
            f"JSON ({exc}): {(result.stdout or '')[:200]!r}",
        )
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return _gate_failed(
            repo_root,
            f"gh issue list --repo {slug} answered with something that is not "
            f"a list of issues: {(result.stdout or '')[:200]!r}",
        )
    return [
        {"number": r.get("number"), "title": r.get("title", "")} for r in rows
    ], None


def _gate_failed(repo_root: Path | str, cause: str) -> tuple[list[dict], str]:
    """Alert that the open-question check cannot run, and return its error."""
    alert.alert_operator(
        what="list the open must-resolve questions in the target repository",
        where=f"{_WHERE} open_must_resolve_issues",
        cause=cause,
        consequence=(
            "the open-question check cannot run: a launch refuses, and a run "
            "summary lists only the questions this machine recorded"
        ),
        repo=str(repo_root),
    )
    return [], cause


# ---------------------------------------------------------------------------
# The filed-questions ledger (#2179)
# ---------------------------------------------------------------------------
#
# The numbers exist in-process at filing time and were thrown away: this module
# returns each one on its FilingResult, the N0c node discarded the return value,
# and the launcher then re-derived the list from a live
# `gh issue list --label must-resolve --state open` seconds later. That query
# returns short when GitHub has not finished indexing a just-filed issue, and
# the one short answer fed BOTH the operator summary and the launch gate file.
#
# Six occurrences across 2026-08-09/10/11. The worst listed one question of
# three (run-issue7-083155 filed #273, #274, #275 within four seconds and
# printed "Next step: resolve #273."), so the operator would have ruled on a
# third of the block and been refused on the rest. The same short answer is
# what wrote an empty `blocking` list into prereqs.json -- the write half of
# #2196's launch brick.
#
# The ledger is a local record of what THIS machine filed, written at the
# moment the number is known. It does not replace the live query: it is unioned
# with it, so a question filed by an earlier run still surfaces and a question
# GitHub has not indexed yet surfaces too.

FILED_LEDGER_REL = Path("data") / "speedrun" / "filed-questions.jsonl"


def filed_ledger_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / FILED_LEDGER_REL


def record_filed(
    repo_root: Path | str,
    *,
    number: int | None,
    title: str,
    fingerprint: str | None = None,
    run_id: str = "",
    ts: str | None = None,
    suppressed: str = "",
) -> bool:
    """Append one filed question to the local ledger. True once it is on disk.

    Append-only JSONL so two rolls writing at once cannot lose each other's
    line. A line that cannot be written raises `OSError` naming the ledger;
    the one caller, `file_must_resolve`, alerts the operator with the issue
    number and returns a failed result. A call with neither a number nor a
    suppression reason has nothing to record and raises `ValueError`.

    ``suppressed`` (#2826) records a filing that was NOT made because GitHub
    writes were inert -- a replay reaching a question. Such a line carries no
    number, and ``read_filed`` keys on the number, so the launcher never
    counts it while the record that the replay got there survives.
    """
    if not number and not suppressed:
        raise ValueError(
            "record_filed needs an issue number or a suppression reason; "
            f"got number={number!r} for {title!r}"
        )
    row: dict = {
        "number": int(number) if number else None,
        "title": title or "",
        "fingerprint": fingerprint or "",
        "run_id": run_id or "",
        "ts": ts or datetime.now().strftime(_TS_FMT),
    }
    if suppressed:
        row["suppressed"] = suppressed
    path = filed_ledger_path(repo_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except (OSError, ValueError) as exc:
        raise OSError(
            f"cannot append to the filed-questions ledger {path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    return True


def _ledger_unreadable(path: Path, cause: str) -> None:
    alert.alert_operator(
        what="read the filed-questions ledger",
        where=f"{_WHERE} read_filed",
        cause=cause,
        consequence=(
            "the questions this machine filed cannot be listed, so the run "
            "summary and the launch gate built from the ledger stop here"
        ),
        repo=str(path.parents[2]),
    )


def _corrupt_line(path: Path, lineno: int, why: str) -> ValueError:
    """Alert about one ledger line that is not a record; the error to raise."""
    cause = f"{path}:{lineno} {why}"
    _ledger_unreadable(path, cause)
    return ValueError(f"the filed-questions ledger line {cause}")


def read_filed(repo_root: Path | str, *, since: str = "") -> list[dict]:
    """Ledger entries, newest last, optionally only those at or after `since`.

    `since` is a `_TS_FMT` stamp, which is lexicographically sortable, so the
    comparison needs no parsing. Bounding by the launcher's own start is what
    keeps a question closed last week out of tonight's summary.

    An absent ledger is the legitimate answer "this machine filed nothing"
    and returns ``[]``. A line with no number is a suppressed filing (#2826)
    and is left out by contract. A ledger that exists but cannot be read, or
    a line that is not a JSON object with a whole-number ``number``, alerts
    the operator and raises: skipping it could hide an open question.
    """
    path = filed_ledger_path(repo_root)
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _ledger_unreadable(path, f"{type(exc).__name__}: {exc} ({path})")
        raise

    entries: list[dict] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise _corrupt_line(path, lineno, f"is not JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise _corrupt_line(path, lineno, "is not a JSON object")
        number = row.get("number")
        if not number:
            continue
        if isinstance(number, bool) or not isinstance(number, int):
            raise _corrupt_line(path, lineno, f"has a number that is not a whole number: {number!r}")
        if since and str(row.get("ts", "")) < since:
            continue
        entries.append({
            "number": number,
            "title": row.get("title", ""),
        })
    return entries


def merge_questions(live: list[dict], recorded: list[dict]) -> list[dict]:
    """Union by issue number, preferring the live title, ordered by number.

    The live query is authoritative on titles -- an operator may have renamed
    the issue since it was filed -- and the ledger is authoritative on
    existence, because it recorded the number at the moment it was created.
    """
    merged: dict[int, dict] = {}
    for item in list(recorded) + list(live):
        number = item.get("number")
        if not number:
            continue
        merged[int(number)] = {
            "number": int(number),
            "title": item.get("title") or merged.get(int(number), {}).get("title", ""),
        }
    return [merged[n] for n in sorted(merged)]


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
    origin: Origin = N0C_ORIGIN,
    runner=_default_runner,
    log=print,
) -> list[FilingResult]:
    """One issue per distinct conflict.

    Every conflict is attempted: each filing is its own GitHub write, and one
    that fails must not leave the others unasked. A filing that raises is an
    alert and a failed result for that conflict; the halt is unchanged.
    """
    results = []
    for index, conflict in enumerate(conflicts or [], start=1):
        try:
            results.append(
                file_must_resolve(
                    repo_root, source_issue, conflict,
                    origin=origin, runner=runner, log=log
                )
            )
        except Exception as exc:  # noqa: BLE001 - each conflict is filed on its own
            cause = f"{type(exc).__name__}: {exc}"
            log(f"  [{origin.tag}] ERROR: must-resolve filing for conflict {index} raised: {cause}")
            alert.alert_operator(
                what=(
                    f"file the must-resolve question for conflict {index} of "
                    f"{len(conflicts)} on #{source_issue}"
                ),
                where=f"{_WHERE} file_all_conflicts ({origin.tag} gate)",
                cause=cause,
                consequence=(
                    f"conflict {index} is not filed, so no question blocks a "
                    "re-roll on it; the other conflicts are still filed and "
                    "the run still halts"
                ),
                repo=str(repo_root),
                issue=source_issue,
            )
            results.append(FilingResult(False, "failed", detail=cause))
    return results
