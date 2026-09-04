"""Replaying a recorded run through the current graph (#2724).

Every gate fix since 2026-08-01 was proven against a hand-made fixture of one
death and then verified by launching a run that costs real money and an hour of
attention. Twelve launches were allowed on boostgauge #421 and all twelve are
spent. The operator's ruling of 2026-09-02 is that nothing relaunches until the
recorded runs replay past the walls that killed them.

This module is the replay. `ScriptedProvider` (#2567) replaces the transport and
only the transport: the graph, the routers, the janitors, the gates, the pinning
enforcement, the file writes and the halt path all run for real, in seconds,
against a throwaway clone, with no network.

## What replay proves, and what it cannot

It proves that **the gate which killed a recorded run no longer kills that run's
recorded content under the current code**. It cannot prove the run would have
finished: once a code change alters a prompt, the recorded response is no longer
the response the model would give, and the honest answer is to stop and name the
divergence rather than invent a verdict. `ReplayResult.verdict` is never
``passed`` on a divergence, and `DIVERGED` is a first-class outcome, not a
failure of the runner.

## Reconstruction, and why the fidelity is stated rather than assumed

The pipeline does NOT persist raw model responses. It persists the artifacts it
derived from them, so every rule here is a reconstruction and each one is
declared in `Reconstruction` so the report can carry it:

* ``NNN-spec-draft.md`` is written by `generate_spec` AFTER preamble stripping,
  pinning adjudication and decision-table re-assertion. It is the round's
  outcome, not the drafter's words.
* ``NNN-readiness-verdict.md`` is markdown assembled from the parsed verdict,
  while the reviewer is called with `REVIEW_SPEC_SCHEMA` and Standard 0028
  leaves no regex fallback. Replaying the file verbatim would be parsed as an
  infrastructure failure, so `verdict_to_json` re-encodes it into the shape the
  parser expects. The three schema fields round-trip; anything the model said
  outside them was never recorded and cannot be replayed.
* A revision round calls the drafter with `EDIT_SCRIPT_SYSTEM_PROMPT` and
  expects SEARCH/REPLACE blocks, not a document. `synthesize_edit_script`
  derives blocks that carry the recorded draft N to the recorded draft N+1, so
  the real parse, the real application and the real pinning enforcement all run
  on the real change. Where a minimal unique anchor cannot be found the round
  degrades to a full-document answer, which is counted and reported rather than
  hidden.

``hallucination-check.json`` is deterministic telemetry, not an LLM call, and is
deliberately not scripted.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from assemblyzero.core.call_recording import (
    SOURCE_RECONSTRUCTION,
    SOURCE_RECORDING,
    summarize,
)
from assemblyzero.core.scripted_provider import ScriptedRule

# ---------------------------------------------------------------------------
# Closed vocabularies
# ---------------------------------------------------------------------------

#: A run-scoped lineage directory is named by `make_run_id()`, second-resolution
#: UTC. The NAME is authoritative and a copy cannot change it, which is why the
#: run-to-directory match keys on it rather than on a filesystem timestamp.
AUDIT_DIR_FMT = "%Y-%m-%dT%H-%M-%SZ"

KIND_LLD = "lld"
KIND_SPEC = "spec"
KINDS: tuple[str, ...] = (KIND_LLD, KIND_SPEC)

#: The stage labels the scripted rules carry. `ScriptedProvider` fails a call
#: that matches rules for two different stages, so these must stay disjoint.
CALLER_DRAFTER = "spec-drafter"
CALLER_EDITOR = "spec-editor"
#: A retry of the SAME round, which the recording cannot answer. It gets its own
#: stage so the round counter on `CALLER_EDITOR` keeps counting rounds rather
#: than attempts -- the two are only the same while nothing goes wrong.
CALLER_EDITOR_RETRY = "spec-editor-retry"
CALLER_REVIEWER = "spec-reviewer"

#: Where the replay ended relative to where the recording ended.
VERDICT_SAME_GATE = "same_gate"
VERDICT_OTHER_GATE = "other_gate"
VERDICT_LATER = "later"
VERDICT_EARLIER = "earlier"
VERDICT_DIVERGED = "diverged"
VERDICT_PASSED = "passed"
VERDICTS: tuple[str, ...] = (
    VERDICT_SAME_GATE, VERDICT_OTHER_GATE, VERDICT_LATER, VERDICT_EARLIER,
    VERDICT_DIVERGED, VERDICT_PASSED,
)

#: One line each, printed under the table so the words in it are defined where
#: they are read rather than in a doc nobody opens.
VERDICT_MEANING: dict[str, str] = {
    VERDICT_SAME_GATE: "died at the same gate, the same distance in",
    VERDICT_OTHER_GATE: "same distance in, but a different gate ended it",
    VERDICT_LATER: "got further than the recording did",
    VERDICT_EARLIER: "got less far than the recording did",
    VERDICT_DIVERGED: (
        "the recorded responses stopped fitting the code's prompts, so the "
        "replay could not continue and reports no verdict on the gate"
    ),
    VERDICT_PASSED: "ran to the end of the stage without a halt",
}

#: Roots a recorded lineage directory can be found under. `reset-artifacts` is
#: load-bearing: `speedrun_reset` moves a run's lineage there before clearing
#: it, so runs 10 and 11 of boostgauge #4 exist ONLY there.
LINEAGE_ROOTS: tuple[tuple[str, ...], ...] = (
    ("docs", "lineage", "active"),
    ("docs", "lineage", "done"),
    ("data", "speedrun", "reset-artifacts"),
)

_RE_AUDIT_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$")
_RE_NUMBERED = re.compile(r"^(\d{3})-(.+?)\.(md|json)$")
_RE_VERDICT = re.compile(r"^Verdict:\s*(\S+)\s*$", re.MULTILINE)
_RE_RATIONALE = re.compile(
    r"^Rationale:\s*(.*?)(?=\n##\s|\Z)", re.MULTILINE | re.DOTALL
)


# ---------------------------------------------------------------------------
# Recorded artifacts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditDir:
    """One run-scoped lineage directory found on disk."""

    kind: str
    stamp: datetime
    path: Path
    file_count: int


@dataclass(frozen=True)
class RecordedResponse:
    """One numbered artifact inside an audit directory."""

    number: int
    suffix: str
    path: Path
    text: str


@dataclass
class Reconstruction:
    """How faithful this replay's rules are, counted rather than asserted.

    Every field is a count of a place where the recording did not hold what the
    transport actually carried. The report prints this beside the verdict so a
    reader can tell a clean replay from one held together with reconstruction.
    """

    drafts: int = 0
    verdicts: int = 0
    edit_scripts: int = 0
    #: Revision rounds where no unique anchor could be built and the round
    #: degrades to answering with the whole document.
    edit_script_degraded: int = 0
    notes: list[str] = field(default_factory=list)


def parse_audit_stamp(name: str) -> datetime | None:
    """The UTC instant a run-scoped lineage directory name encodes.

    Two different answers, deliberately kept apart. A name that is not a stamp
    at all -- `4-implspec`, `issue-brief.md`, every ordinary directory in a
    lineage tree -- returns None, because walking past it is the normal case.
    A name that has the SHAPE of a stamp but is not a real instant raises,
    because `make_run_id()` cannot have written it and something that is not the
    pipeline has been naming run directories.

    The shape test is a regex over a closed, authored format, not a judgement
    about content (standard 0028a, §28a).
    """
    if not _RE_AUDIT_STAMP.match(name):
        return None
    return datetime.strptime(name, AUDIT_DIR_FMT).replace(tzinfo=timezone.utc)


def discover_audit_dirs(target_repo: Path, issue: int) -> list[AuditDir]:
    """Every run-scoped lineage directory for one issue, wherever it landed.

    Both stage kinds and all three roots, because a reset moves a directory out
    of `docs/lineage/` entirely and a replay that only looked where the pipeline
    writes would silently find nothing for exactly the runs worth replaying.
    """
    found: list[AuditDir] = []
    for parts in LINEAGE_ROOTS:
        root = target_repo.joinpath(*parts)
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_dir():
                continue
            stamp = parse_audit_stamp(path.name)
            if stamp is None:
                continue
            parent = path.parent.name
            if not parent.startswith(f"{issue}-"):
                continue
            if "lld" in parent:
                kind = KIND_LLD
            elif "implspec" in parent:
                kind = KIND_SPEC
            else:
                continue
            count = sum(1 for f in path.iterdir() if f.is_file())
            found.append(AuditDir(kind, stamp, path, count))
    return sorted(found, key=lambda d: (d.stamp, d.kind, -d.file_count))


def run_window(log_path: Path) -> tuple[datetime, datetime]:
    """When a run started and last wrote, in UTC.

    `st_ctime` is creation time on Windows, which is where every recorded run in
    the corpus was produced. The window is used only to associate a run with the
    lineage directories it created, and a directory's own name supplies the
    precision.
    """
    stat = log_path.stat()
    return (
        datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
        datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    )


def audit_dirs_for_run(
    dirs: list[AuditDir], start: datetime, end: datetime
) -> tuple[dict[str, AuditDir], list[str]]:
    """The lineage directories one run created, one per stage kind.

    Returns (chosen, notes). A reset can leave SEVERAL copies of one directory
    under different reset stamps -- boostgauge run 11's spec lineage exists
    twice, once with 26 files and once with 4 -- so a tie on the directory name
    is broken by file count and the choice is recorded in `notes` rather than
    made silently. Two DIFFERENT names for one kind inside one run's window is
    not a tie and is reported as ambiguity, not resolved by guessing.
    """
    notes: list[str] = []
    chosen: dict[str, AuditDir] = {}
    for kind in KINDS:
        candidates = [
            d for d in dirs if d.kind == kind and start <= d.stamp <= end
        ]
        if not candidates:
            continue
        stamps = {d.stamp for d in candidates}
        if len(stamps) > 1:
            notes.append(
                f"{kind}: {len(stamps)} different lineage directories fall in "
                f"this run's window "
                f"({', '.join(sorted(s.strftime(AUDIT_DIR_FMT) for s in stamps))}). "
                f"The run cannot be told apart from a neighbour; not replayed."
            )
            continue
        best = max(candidates, key=lambda d: d.file_count)
        if len(candidates) > 1:
            notes.append(
                f"{kind}: {len(candidates)} copies of "
                f"{best.stamp.strftime(AUDIT_DIR_FMT)} exist (a reset copied "
                f"the lineage); took the one with the most files "
                f"({best.file_count} vs "
                f"{', '.join(str(c.file_count) for c in candidates if c is not best)})."
            )
        chosen[kind] = best
    return chosen, notes


def responses_in(audit_dir: Path) -> list[RecordedResponse]:
    """Every numbered artifact in an audit directory, in call order."""
    out: list[RecordedResponse] = []
    for path in sorted(audit_dir.iterdir()):
        if not path.is_file():
            continue
        match = _RE_NUMBERED.match(path.name)
        if not match:
            continue
        out.append(
            RecordedResponse(
                number=int(match.group(1)),
                suffix=match.group(2),
                path=path,
                text=path.read_text(encoding="utf-8", errors="replace"),
            )
        )
    return sorted(out, key=lambda r: r.number)


# ---------------------------------------------------------------------------
# Re-encoding a persisted verdict into the shape the parser needs
# ---------------------------------------------------------------------------


def parse_verdict_file(text: str) -> dict:
    """Read back what `review_spec` wrote to ``NNN-readiness-verdict.md``.

    The writer's format is fixed at review_spec.py: a ``Verdict:`` line, a
    ``Rationale:`` block that runs to the next heading, and an optional
    ``## Feedback Items`` list. Reading it back is therefore a parse of a known
    format, not a guess at prose.
    """
    verdict_match = _RE_VERDICT.search(text)
    rationale_match = _RE_RATIONALE.search(text)
    items: list[str] = []
    in_items = False
    for line in text.splitlines():
        if line.startswith("## Feedback Items"):
            in_items = True
            continue
        if in_items:
            if line.startswith("## "):
                break
            if line.startswith("- "):
                items.append(line[2:].strip())
    return {
        "verdict": verdict_match.group(1) if verdict_match else "",
        "rationale": (
            rationale_match.group(1).strip() if rationale_match else ""
        ),
        "feedback_items": items,
    }


def verdict_to_json(text: str) -> str:
    """A persisted verdict, re-encoded for `REVIEW_SPEC_SCHEMA`.

    The reviewer is called with a schema and Standard 0028 removed the regex
    fallback, so handing the markdown back verbatim would be parsed as "no
    extractable verdict" -- an infrastructure failure the recording never had.
    """
    return json.dumps(parse_verdict_file(text), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Synthesising the edit script a revision round expects
# ---------------------------------------------------------------------------


def synthesize_edit_script(before: str, after: str) -> str:
    """SEARCH/REPLACE blocks carrying ``before`` to ``after``.

    A revision round asks the drafter for edit blocks, not a document, so a
    replay that answered with the recorded draft would exercise the fallback
    path instead of the pinning enforcement that actually adjudicates a
    revision. Deriving the blocks from the two recorded drafts runs the real
    parse, the real application and the real enforcement over the real change.

    Each SEARCH must occur exactly once in ``before`` (`apply_edit_blocks`
    rejects an ambiguous anchor), so a hunk's context is widened until it is
    unique. Returns "" when no unique anchor can be built -- the caller then
    degrades to a whole-document answer and counts it.
    """
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    blocks: list[tuple[str, str]] = []

    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # A hunk with nothing on one side is degenerate line-wise: an insertion
        # has no SEARCH text of its own, and a deletion would leave an empty
        # REPLACE, which substring-replaces the lines away but leaves the
        # newline that separated them -- a blank line where the deleted text
        # was. Borrowing a line of context on each side makes both halves whole
        # lines, so the edit is a line replacement in both directions.
        degenerate = i1 == i2 or j1 == j2
        anchor = _unique_anchor(
            before_lines, before, i1, i2, context=1 if degenerate else 0
        )
        if anchor is None:
            return ""
        lo, hi = anchor
        search = "\n".join(before_lines[lo:hi])
        replace = "\n".join(
            before_lines[lo:i1] + after_lines[j1:j2] + before_lines[i2:hi]
        )
        blocks.append((search, replace))

    if not blocks:
        return ""
    return "\n\n".join(
        f"<<<<<<< SEARCH\n{search}\n=======\n{replace}\n>>>>>>> REPLACE"
        for search, replace in blocks
    )


def _unique_anchor(
    lines: list[str],
    whole: str,
    i1: int,
    i2: int,
    *,
    context: int = 0,
    limit: int = 40,
) -> tuple[int, int] | None:
    """Widen ``lines[i1:i2]`` until it appears exactly once in ``whole``.

    ``context`` is the minimum number of surrounding lines to take before the
    first uniqueness test, which is what a degenerate hunk needs -- an insertion
    has no text of its own to anchor on, and a deletion needs a neighbour so its
    replacement is a whole line rather than nothing.
    """
    lo = max(0, i1 - context)
    hi = min(len(lines), i2 + context)
    for _ in range(limit):
        if hi > lo:
            candidate = "\n".join(lines[lo:hi])
            if candidate and whole.count(candidate) == 1:
                return lo, hi
        if lo == 0 and hi >= len(lines):
            return None
        lo = max(0, lo - 1)
        hi = min(len(lines), hi + 1)
    return None


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

#: Anchored on wording unique to each system prompt. `ScriptedProvider` refuses
#: a call that matches two stages, so an overlap here fails loudly at the first
#: call rather than misrouting the reviewer to the drafter.
PATTERN_DRAFTER = r"technical architect creating an Implementation Specification"
PATTERN_EDITOR = r"precision patch engine"
PATTERN_REVIEWER = r"Implementation Readiness Review"

#: The heading `build_edit_script_prompt` adds when re-prompting after a script
#: failed to apply (#2569). Its presence is what tells a fresh round apart from
#: a retry of one, and the two rule sets below are mutually exclusive on it, so
#: exactly one stage ever matches an editor call.
RETRY_MARK = r"YOUR PREVIOUS ATTEMPT FAILED TO APPLY"
PATTERN_FIRST_ATTEMPT = rf"\A(?!.*{RETRY_MARK})"

#: Why a retry is a finding rather than something to answer. The recording holds
#: one outcome per round because the original script applied; if the code is
#: asking again, the draft this replay built is not the draft the recording had,
#: and inventing a second answer would bury exactly the fact worth reporting.
RETRY_IS_DIVERGENCE = (
    "ScriptedProvider: the code asked for another edit-script attempt at this "
    "round. The recording holds one outcome per round, because in the recording "
    "the script applied. Being asked again means the draft this replay built is "
    "no longer the draft the recording had, so there is nothing faithful to "
    "answer with -- this is the divergence point (#2724)."
)


def build_spec_rules(
    spec_dir: Path,
) -> tuple[list[ScriptedRule], Reconstruction]:
    """Rules for one recorded spec stage, in call order.

    Round 1 is a full draft; every later round is an edit script derived from
    the pair of recorded drafts around it. The reviewer's rounds are the
    re-encoded verdicts.
    """
    recon = Reconstruction()
    responses = responses_in(spec_dir)
    drafts = [r for r in responses if r.suffix == "spec-draft"]
    verdicts = [r for r in responses if r.suffix == "readiness-verdict"]

    rules: list[ScriptedRule] = []

    if drafts:
        rules.append(
            ScriptedRule(
                CALLER_DRAFTER,
                system_pattern=PATTERN_DRAFTER,
                response=drafts[0].text,
                on_call=1,
            )
        )
        recon.drafts += 1

    # #2569 removed the full-regeneration fallback: a revision is edit blocks or
    # it is a halt. So the drafter's own prompt is used exactly once, for the
    # initial draft, and every later round is an edit script.
    for index, draft in enumerate(drafts[1:], start=1):
        previous = drafts[index - 1].text
        script = synthesize_edit_script(previous, draft.text)
        if script:
            rules.append(
                ScriptedRule(
                    CALLER_EDITOR,
                    system_pattern=PATTERN_EDITOR,
                    content_pattern=PATTERN_FIRST_ATTEMPT,
                    response=script,
                    on_call=index,
                )
            )
            recon.edit_scripts += 1
        else:
            # Declared, not swallowed: a whole document in answer to an
            # edit-script call is not what the recording's drafter sent, and the
            # round replays a different path because of it.
            rules.append(
                ScriptedRule(
                    CALLER_EDITOR,
                    system_pattern=PATTERN_EDITOR,
                    content_pattern=PATTERN_FIRST_ATTEMPT,
                    response=draft.text,
                    on_call=index,
                )
            )
            recon.edit_script_degraded += 1
            recon.notes.append(
                f"round {index + 1}: no unique SEARCH anchor between "
                f"{drafts[index - 1].path.name} and {draft.path.name}; "
                f"answered with the whole document, so this round does not "
                f"replay the edit path."
            )
        recon.drafts += 1

    if len(drafts) > 1:
        rules.append(
            ScriptedRule(
                CALLER_EDITOR_RETRY,
                system_pattern=PATTERN_EDITOR,
                content_pattern=RETRY_MARK,
                fail_with=RETRY_IS_DIVERGENCE,
            )
        )

    for index, verdict in enumerate(verdicts, start=1):
        rules.append(
            ScriptedRule(
                CALLER_REVIEWER,
                system_pattern=PATTERN_REVIEWER,
                response=verdict_to_json(verdict.text),
                on_call=index,
            )
        )
        recon.verdicts += 1

    recon.notes.append(
        f"{len(drafts)} recorded draft(s) and {len(verdicts)} recorded "
        f"verdict(s); drafts are post-pinning artifacts, verdicts are "
        f"re-encoded into REVIEW_SPEC_SCHEMA."
    )
    return rules, recon


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


@dataclass
class ReplayResult:
    """One recorded run, replayed. Every field is measured, none inferred."""

    tag: str
    stage: str
    #: What the recording did: the registry key that ended it, and how far in.
    recorded_cause: str
    recorded_progress: int
    #: What the replay did.
    replay_cause: str = ""
    replay_progress: int = 0
    #: Set when `ScriptedProvider` refused a call: the recorded responses no
    #: longer fit the prompts the code sends. Non-empty means DIVERGED.
    divergence: str = ""
    verdict: str = VERDICT_DIVERGED
    reconstruction: Reconstruction = field(default_factory=Reconstruction)
    notes: list[str] = field(default_factory=list)
    #: The stage labels the provider was actually asked for, in order. A roll
    #: that reaches the right end state by the wrong route is a defect an
    #: end-state assertion does not catch.
    path: list[str] = field(default_factory=list)
    #: Which transport answered: a recording of the actual calls (#2731), or
    #: rules reconstructed from the drafts and verdicts. The report prints it,
    #: because "the recording said so" and "a draft was reconstructed into a
    #: rule" are different evidence and a reader deciding whether to launch is
    #: entitled to know which they have.
    source: str = SOURCE_RECONSTRUCTION
    #: Calls the recording held, when one answered. 0 under reconstruction.
    recorded_calls: int = 0


def classify(
    *,
    recorded_cause: str,
    recorded_progress: int,
    replay_cause: str,
    replay_progress: int,
    divergence: str,
    finished: bool,
) -> str:
    """Where the replay ended, against where the recording ended.

    Divergence is tested FIRST and beats everything, including a clean finish.
    Once the recorded responses stop fitting the prompts the code sends, the run
    is no longer the recorded run, and a `passed` here would be the runner
    inventing the one verdict replay is least able to justify (#2724).
    """
    if divergence:
        return VERDICT_DIVERGED
    if finished and not replay_cause:
        return VERDICT_PASSED
    if replay_progress > recorded_progress:
        return VERDICT_LATER
    if replay_progress < recorded_progress:
        return VERDICT_EARLIER
    if replay_cause == recorded_cause:
        return VERDICT_SAME_GATE
    return VERDICT_OTHER_GATE


def render_table(results: list[ReplayResult]) -> str:
    """The replay table a pipeline PR carries in its body (#2724).

    The legend is printed with the table rather than kept in a doc, because the
    table travels into PR bodies read by people who will not open the doc.
    """
    lines = [
        "| run | stage | answered by | recorded ended at | replay ended at | verdict |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        recorded = f"`{r.recorded_cause}` at round {r.recorded_progress}"
        if r.divergence:
            reached = f"diverged at round {r.replay_progress}"
        elif r.verdict == VERDICT_PASSED:
            reached = "finished the stage"
        else:
            reached = f"`{r.replay_cause}` at round {r.replay_progress}"
        # #2731: which transport answered is part of the verdict's weight, not
        # a footnote. A recording is the calls the run actually made; a
        # reconstruction is rules derived from the artifacts, exact for about
        # five rounds. The table says which, on every row.
        source = (
            f"{r.source} ({r.recorded_calls} calls)"
            if r.source == SOURCE_RECORDING else r.source
        )
        lines.append(
            f"| {r.tag} | {r.stage} | {source} | {recorded} | {reached} | "
            f"**{r.verdict}** |"
        )
    shown = [name for name in VERDICTS if any(r.verdict == name for r in results)]
    legend = [f"- **{name}** — {VERDICT_MEANING[name]}" for name in shown]
    if any(r.source == SOURCE_RECONSTRUCTION for r in results):
        legend.append(
            f"- **{SOURCE_RECONSTRUCTION}** — the run recorded no model calls, "
            "so its responses were rebuilt from the drafts and verdicts it left "
            "behind. Exact for about five rounds (#2731)."
        )
    if any(r.source == SOURCE_RECORDING for r in results):
        legend.append(
            f"- **{SOURCE_RECORDING}** — answered from the run's own calls, "
            "prompt for prompt; a divergence names the call and the diff."
        )
    return "\n".join([*lines, "", *legend])


def recording_for(spec_dir: Path) -> tuple[bool, int, str]:
    """Whether this run recorded its calls, how many, and what to say about it.

    Returns (usable, calls, note). The note is carried into the result's notes
    so a reader can tell "this run predates the recorder" from "this run's
    recording is unreadable" -- two very different reasons for falling back.
    """
    summary = summarize(spec_dir)
    if summary.usable:
        note = f"answered from {summary.calls} recorded call(s)"
        if summary.unreadable:
            note += f"; {summary.unreadable} unreadable line(s) in the recording"
        return True, summary.calls, note
    if summary.unreadable:
        return False, 0, (
            f"the recording holds {summary.unreadable} unreadable line(s) and "
            f"no usable call; fell back to reconstruction"
        )
    return False, 0, (
        "this run recorded no model calls (it predates #2731); its responses "
        "were reconstructed from the drafts and verdicts it left behind"
    )
