"""The factory records everything and aggregates nothing (#2575).

Every judgment call of the 2026-08-27 campaign — is the density heuristic
noise (#2539)? which checks deserve the fact-verifier badge (#2540)? does
the edit-script path fall back often enough to matter? — was decided by
whichever kill happened most recently, while the counts to decide them
properly already sat on disk. `prompt_telemetry` counts every validation
failure (#2074), the healing ledger records every janitor action (#2164),
`preserved-branches.jsonl` records every preservation (#2355), run logs
carry per-stage wall-clock against the watchdog's nominal, and since
2026-08-27 every halt leaves a machine-readable evidence bundle (#2574)
and, while it is live, a resume contract (#2570).

This module reads those stores and counts. **v1 adds no instrumentation**:
every number here comes from a file some other mechanism already writes,
which is what makes the report safe to run against a live campaign.

## Counts, never estimates

Every number is derived by counting records. Where a store cannot answer a
question, the report says so with its denominator rather than guessing —
standard 0025's cold-start rule, applied to aggregation: a zero that means
"nothing fired" and a zero that means "nothing was recorded" are different
facts and are printed differently.

## The zero-fire denominator is declared, not inferred

"Which gates never fire" needs the set of gates that COULD fire. Inferring
it from observed records is circular — a gate that never fires is exactly
the one absent from the data. So the recording sites are declared here in
`DECLARED_CHECKS`, and `tests/unit/test_factory_report.py` greps the
workflow sources and fails when a new `record_failure(s)` site appears
that this tuple does not name. The registry cannot silently drift behind
the code, because the test is the thing that keeps it honest.

## Run logs are read with errors="replace", always

Speedrun run logs carry stray bytes from model output. GNU grep's binary
detection silently suppresses matching lines in them (the 2026-08-27
near-miss: `[PINNING] refused:` lines existed and a multi-pattern grep
printed only the REGRESSION lines plus "Binary file matches", which is a
confident wrong answer rather than a failure). `errors="replace"` is the
Python-side equivalent of `grep -a` and is not optional here.

## Determinism

Identical input produces byte-identical output, so two reports can be
diffed across days to see what changed rather than re-read in full. Every
ordering has an explicit tie-break on a stable key.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assemblyzero.core.gate_registry import JUDGES_BUDGET
from assemblyzero.speedrun.convergence import (
    SOURCE_BANNER,
    SOURCE_RECORD,
    furthest_by_run,
    read_records,
    terminals_by_run,
)

_TS_FMT = "%Y-%m-%d %H:%M:%S"

#: Every (stage, check) pair a `record_failure`/`record_failures` call site
#: can write, as declared by the workflow sources. This is the DENOMINATOR
#: for zero-fire reporting: a declared pair with no records in the window
#: is a gate that did not fire, which is either perfect or dead, and the
#: report refuses to distinguish those for the reader.
#:
#: Kept honest by test_factory_report.py::TestDeclaredChecks, which greps
#: the workflow tree for recording sites and fails when one is missing.
DECLARED_CHECKS: tuple[tuple[str, str], ...] = (
    ("lld", "mechanical"),
    ("lld", "requirements-conflict"),
    ("lld", "test-plan"),
    ("spec", "reviewer-revise"),
)

#: Run-log markers this report counts, and what each one means. Counting is
#: line-oriented on purpose: these markers are emitted one per event by the
#: pipeline, so a line count IS an event count.
_RE_STAGE_WATCHDOG = re.compile(
    r"\[STAGE\]\s+(?P<stage>\S+)\s+running\s+(?P<elapsed>\d+)s"
    r"\s+\(nominal\s+~(?P<nominal>\d+)s\)"
)
_RE_PINNING_REFUSED = re.compile(r"\[PINNING\]\s+refused:")
_RE_PINNING_REGRESSION = re.compile(r"\[PINNING\]\s+REGRESSION CLASS:")
_RE_EDIT_APPLIED = re.compile(r"\[EDIT-SCRIPT\]\s+Applied\s+(?P<edits>\d+)\s+edit")
_RE_EDIT_FALLBACK = re.compile(
    r"\[EDIT-SCRIPT\]\s+Falling back to full revision:\s*(?P<reason>.*)"
)
_RE_CAP_GRANT = re.compile(r"\[CAP\]\s+(?P<detail>.*)")
_RE_REVIEW_ROUND = re.compile(
    r"\[REVIEW\]\s+(?P<what>\S+)\s+review\s+\S+\s+\[(?P<verdict>[^\]]+)\]:"
    r"\s+round\s+(?P<round>\d+)"
)
#: The run-log filename carries the issue and the run stamp by construction:
#: `run-issue<N>-<HHMMSS>.log`. Nothing else links a log to an issue, so the
#: name is the linkage and a log that does not match is reported as unlinked
#: rather than silently attributed.
_RE_RUN_NAME = re.compile(r"^run-issue(?P<issue>\d+)-(?P<stamp>\d+)\.log$")

# ---------------------------------------------------------------------------
# How a run ended (#2717) and how far it got (#2718)
# ---------------------------------------------------------------------------
#
# The report counted what fired INSIDE a run and never said how the run
# ended. Counted over boostgauge's 180 logs on 2026-09-02: 135 carry an
# `ORCHESTRATION FAILED at stage:` banner (lld 49, impl 45, spec 40, pr 1),
# 26 carry `[ORCHESTRATOR] All stages passed.`, and 19 carry neither -- the
# process was killed mid-call. The `Error:` line under a failure banner is a
# closed set of prefixes the pipeline's own code emits, so a run's cause of
# death is a table lookup, not a judgment.

#: The orchestrator's stage order, mirrored so this module stays free of
#: workflow imports. test_factory_report.py asserts it equals
#: `assemblyzero.workflows.orchestrator.state.STAGE_ORDER`.
_STAGE_ORDER: tuple[str, ...] = (
    "triage", "lld", "visual", "spec", "impl", "pr", "cleanup",
)

#: The implementation workflow's node markers in graph order. The run log
#: prints them as `[HH:MM:SS] [N5] ...`; the timestamp prefix is what
#: separates them from the spec workflow's untimestamped `[N2] Generating`.
#: Kept honest by test_factory_report.py, which greps the testing workflow
#: for every `[N..]` literal it prints.
_IMPL_NODE_ORDER: tuple[str, ...] = (
    "N0", "N1", "N1.5", "N2", "N2.5", "N3", "N4", "N4b", "N4c",
    "N5", "N6", "N7", "N8", "N9",
)

#: One row of the closing STAGE / VERDICT / TIME table the orchestrator
#: prints: `{stage:<9} {status:<9} {secs:>6.1f}s  {detail}`, or
#: `{stage:<9} -         -` for a stage never reached.
_RE_STAGE_ROW = re.compile(
    r"^(?P<stage>triage|lld|visual|spec|impl|pr|cleanup)\s+"
    r"(?P<verdict>passed|failed|blocked|skipped|-)\s+"
    r"(?P<secs>\d+\.\d+s|-)(?:\s+(?P<detail>.*))?$"
)
_RE_FAILED_BANNER = re.compile(
    r"^\s*ORCHESTRATION FAILED at stage:\s*(?P<stage>\S+)"
)
#: The first `  Error:` line AFTER the failure banner. Fifteen of the 135
#: banners carry an empty one; that is `unrecorded`, not `unclassified`.
_RE_BANNER_ERROR = re.compile(r"^\s{2}Error:\s?(?P<msg>.*)$")
_RE_ALL_PASSED = re.compile(r"\[ORCHESTRATOR\] All stages passed\.")
#: The exit classifier label the spec stage prints since #2383. Eight of
#: 180 logs carry one, so it is recorded when present and never required.
_RE_EXIT_LABEL = re.compile(r"^\s{2}exit:\s*(?P<label>\S+)")
_RE_IMPL_NODE = re.compile(
    r"^\[\d\d:\d\d:\d\d\]\s+\[(?P<node>N\d+(?:\.\d+)?[a-z]?)\]"
)

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_KILLED = "killed"

CAUSE_UNRECORDED = "unrecorded"
CAUSE_UNCLASSIFIED = "unclassified"
CAUSE_KILLED = "killed"


@dataclass(frozen=True)
class Cause:
    """One authored row of the cause-of-death table.

    `pattern` is anchored at the start of the banner's Error line. `example`
    is a real Error line from the boostgauge logs, and the test suite asserts
    every row matches its own example and no earlier row's. `source_literal`
    is a static fragment of the message that must appear in `emitted_by`, so
    a row cannot name code that does not say what the row claims.
    """

    key: str
    pattern: str
    emitted_by: str
    judges: str
    example: str
    source_literal: str


#: Authored from the 135 banners on disk, most frequent first within a stage.
#: A message matching no row is `unclassified` and the report prints it
#: verbatim, so this table grows deliberately rather than by guessing.
#: `judges` is what the gate reads: the drafter's output, the issue body,
#: a spending limit, or the environment. That column is the seed of the gate
#: registry (#2719) and of the routing policy (#2723).
CAUSE_TABLE: tuple[Cause, ...] = (
    Cause(
        "lld.mechanical_validation", r"MECHANICAL VALIDATION FAILED",
        "assemblyzero/workflows/requirements/nodes/validate_mechanical.py", "budget",
        "MECHANICAL VALIDATION FAILED:", "MECHANICAL VALIDATION FAILED:",
    ),
    Cause(
        "spec.requirements_conflict",
        r"Spec review BLOCKED: REQUIREMENTS CONFLICT",
        "assemblyzero/workflows/implementation_spec/nodes/review_spec.py", "issue_body",
        "Spec review BLOCKED: REQUIREMENTS CONFLICT: The LLD contains an "
        "unresolvable contradiction",
        "REQUIREMENTS CONFLICT:",
    ),
    Cause(
        "lld.requirements_conflict", r"REQUIREMENTS CONFLICT",
        "assemblyzero/workflows/requirements/nodes/analyze_requirements.py", "issue_body",
        "REQUIREMENTS CONFLICT: the issue's requirements are internally "
        "inconsistent",
        "REQUIREMENTS CONFLICT:",
    ),
    Cause(
        "lld.test_plan_validation", r"test plan validation failed",
        "assemblyzero/workflows/requirements/nodes/validate_test_plan.py", "budget",
        "test plan validation failed after 6 revision(s): Requirement REQ-1 "
        "has no test coverage",
        "test plan validation failed after",
    ),
    Cause(
        "spec.completeness_cap", r"Iteration cap: \d+ revision\(s\) ended with",
        "assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py",
        "budget",
        "Iteration cap: 3 revision(s) ended with 1 unresolved completeness "
        "check(s).",
        "Iteration cap:",
    ),
    Cause(
        # The verdict word varies: REVISE on the ordinary ceiling, BLOCKED
        # when the reviewer blocked on the round that hit it. Same emitter,
        # same spending limit, one row.
        "spec.review_cap", r"Iteration cap: \d+ review rounds ended \w+",
        "assemblyzero/core/halt_node.py", "budget",
        "Iteration cap: 3 review rounds ended REVISE, so the run stopped "
        "rather than spend another round on the same objection.",
        "Iteration cap:",
    ),
    Cause(
        "spec.edit_script_rejected", r"\[EDIT-SCRIPT\] spec revision rejected",
        "assemblyzero/workflows/implementation_spec/nodes/generate_spec.py", "budget",
        "[EDIT-SCRIPT] spec revision rejected after 3 attempt(s): block 1: "
        "SEARCH text not found",
        "spec revision rejected after",
    ),
    Cause(
        # Judges the LLD's test plan, an earlier stage's artifact this stage
        # cannot revise (#2675 moves the check upstream).
        "impl.scenario_ratio_guard", r"GUARD: Mechanical pre-checks failed",
        "assemblyzero/workflows/testing/nodes/review_test_plan.py",
        "upstream_artifact",
        "GUARD: Mechanical pre-checks failed \u2014 Only 1 scenario(s) for "
        "2 requirement(s)",
        "Mechanical pre-checks failed",
    ),
    Cause(
        "impl.stagnation.coverage", r"Coverage stagnant",
        "assemblyzero/workflows/testing/nodes/verify_phases.py", "model_output",
        "Coverage stagnant: 97.0% -> 97.0% (< 1% improvement). Halting to "
        "prevent token waste.",
        "Coverage stagnant:",
    ),
    Cause(
        "impl.stagnation.test_count", r"Test count stagnant",
        "assemblyzero/workflows/testing/nodes/verify_phases.py", "model_output",
        "Test count stagnant: 44/94 passed (unchanged from previous "
        "iteration). Halting to prevent token waste.",
        "Test count stagnant:",
    ),
    Cause(
        "impl.stagnation.test_identity", r"Test identity stagnant",
        "assemblyzero/workflows/testing/nodes/verify_phases.py", "model_output",
        "Test identity stagnant: same 47 test(s) failing across iterations. "
        "Halting to prevent token waste.",
        "Test identity stagnant:",
    ),
    Cause(
        "impl.stagnation.full_suite", r"Full suite regression stagnant",
        "assemblyzero/workflows/testing/nodes/verify_phases.py", "model_output",
        "Full suite regression stagnant: same 4 test(s) failing across "
        "iterations. Halting.",
        "Full suite regression stagnant:",
    ),
    Cause(
        "impl.file_generation_failed",
        r"Implementation stage error: FATAL: Failed to implement",
        "assemblyzero/workflows/testing/nodes/implementation/claude_client.py",
        "budget",
        "Implementation stage error: FATAL: Failed to implement "
        "src/boostgauge/skins/stingray.py",
        "FATAL: Failed to implement",
    ),
    Cause(
        "impl.branch_exists",
        r"Implementation stage error: branch '[^']+' already exists",
        "assemblyzero/workflows/orchestrator/stages.py", "infrastructure",
        "Implementation stage error: branch 'issue-384' already exists and "
        "carries 1 commit(s)",
        "already exists and carries",
    ),
    # #2761: three gates emit the DETERMINISTIC_FAILURE token, and until
    # 2026-09-04 one generic row swallowed all of them. Measured over
    # boostgauge's runs/, the four runs that died carrying it were:
    # run-issue384 and run-issue4 on the scaffolder's suite-invalid halt, and
    # run-issue331 and run-issue379 on the red phase -- so HALF of
    # `impl.deterministic_failure`'s recorded kills belonged to a different
    # row, which the registry's own note already said was a different gate.
    #
    # The tell was in the table itself: the generic row's `example` was the
    # scaffolder's message, so the row was documented, and its own test
    # pinned, against a gate it is not. Specific rows first -- `classify_cause`
    # takes the first match.
    Cause(
        "impl.scaffold_suite_invalid",
        r"DETERMINISTIC FAILURE: the generated test suite cannot be",
        "assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py",
        "upstream_artifact",
        "DETERMINISTIC FAILURE: the generated test suite cannot be validated "
        "and the scaffolder",
        "the generated test suite cannot be",
    ),
    # #2761 split the last of the three in two, because it also named two
    # things: the worktree already held the implementation (the pipeline's
    # fault) and a generated test cannot pass anywhere (the drafter's). Both
    # rows are specific -- there is deliberately no generic
    # `DETERMINISTIC FAILURE` catch-all left, so a fourth emitter of the token
    # lands in `unclassified` and gets printed verbatim rather than absorbed
    # by a neighbour, which is how the first three came to share one row.
    Cause(
        "impl.red.preexisting_implementation",
        r"DETERMINISTIC FAILURE: Red phase failed",
        "assemblyzero/workflows/testing/nodes/verify_phases.py",
        "infrastructure",
        "DETERMINISTIC FAILURE: Red phase failed: 3 tests passed "
        "unexpectedly, and neither a red-entry marker nor this run's own "
        "prior writes explain them",
        "tests passed unexpectedly, and neither a red-entry marker",
    ),
    Cause(
        "impl.deterministic_failure",
        r"DETERMINISTIC FAILURE: Test\(s\) failing for a reason",
        "assemblyzero/workflows/testing/nodes/verify_phases.py", "model_output",
        "DETERMINISTIC FAILURE: Test(s) failing for a reason no "
        "implementation can fix: test_dynamic_256_matches_baseline",
        "Test(s) failing for a reason no implementation can fix",
    ),
    Cause(
        "impl.red_phase_failed", r"Red phase failed",
        "assemblyzero/workflows/testing/nodes/verify_phases.py", "model_output",
        "Red phase failed: 23 tests passed unexpectedly. Tests should fail "
        "before implementation",
        "Red phase failed:",
    ),
    Cause(
        "impl.green_phase_stopped", r"Green phase stopped",
        "assemblyzero/workflows/testing/nodes/verify_phases.py", "infrastructure",
        "Green phase stopped: pytest test execution interrupted (exit code 2)",
        "Green phase stopped:",
    ),
    Cause(
        "infra.worktree", r"Git worktree error",
        "assemblyzero/workflows/orchestrator/stages.py", "infrastructure",
        "Git worktree error (exit 255): Preparing worktree (new branch "
        "'issue-7')",
        "Git worktree error",
    ),
    Cause(
        "infra.pr_creation", r"PR creation error",
        "assemblyzero/workflows/orchestrator/stages.py", "infrastructure",
        "PR creation error: To https://github.com/martymcenroe/boostgauge.git",
        "PR creation error:",
    ),
    Cause(
        "infra.lld_stage_exception", r"LLD stage error",
        "assemblyzero/workflows/orchestrator/stages.py", "infrastructure",
        "LLD stage error: 'charmap' codec can't encode character '\\u2265' "
        "in position 239",
        "LLD stage error:",
    ),
    Cause(
        # The 2026-08 logs carry the bare form; load_lld.py now prefixes it
        # with MISSING REQUIRED INPUT. Both are the same precondition.
        "infra.missing_spec",
        r"(?:MISSING REQUIRED INPUT: )?[Nn]o implementation spec found",
        "assemblyzero/workflows/testing/nodes/load_lld.py", "infrastructure",
        "No implementation spec found for issue #7. Run: poetry run python "
        "tools/run_implementation",
        "no implementation spec found",
    ),
)

_COMPILED_CAUSES: tuple[tuple[Cause, re.Pattern[str]], ...] = tuple(
    (cause, re.compile(cause.pattern)) for cause in CAUSE_TABLE
)


def classify_cause(error_head: str) -> str:
    """The cause key for a banner's first Error line, or a named absence.

    An empty line is `unrecorded`: the banner printed and carried nothing,
    which is a fact about the halt path, not about the run. A line no row
    matches is `unclassified`, never the nearest bucket.
    """
    head = (error_head or "").strip()
    if not head:
        return CAUSE_UNRECORDED
    for cause, pattern in _COMPILED_CAUSES:
        if pattern.match(head):
            return cause.key
    return CAUSE_UNCLASSIFIED


_NODE_RANKS: dict[str, int] = {n: i for i, n in enumerate(_IMPL_NODE_ORDER)}
_STAGE_RANKS: dict[str, int] = {s: i for i, s in enumerate(_STAGE_ORDER)}


def _node_rank(node: str) -> int:
    """-1 for "" and for a marker the order does not rank. An unranked
    marker is a test failure (the order must cover every marker printed),
    never a silent substitution here."""
    return _NODE_RANKS.get(node, -1)


def _stage_rank(stage: str) -> int:
    """-1 for "": the closing table and the watchdog only ever name the
    seven stages, so no other value reaches this."""
    return _STAGE_RANKS.get(stage, -1)


def _normalize_digits(text: str) -> str:
    """`Calling Claude... (645s)` and `(15s)` are one event for a tally."""
    return re.sub(r"\d+", "N", text)


def parse_since(spec: str, *, now: datetime | None = None) -> datetime | None:
    """`7d` / `24h` / `2026-08-27` / `2026-08-27 09:00:00` -> a lower bound.

    An empty spec means no lower bound (read everything), which is a real
    answer and not an error. An unparseable spec raises, because silently
    reading everything when the operator asked for a window would put a
    wrong denominator under every number in the report.
    """
    text = (spec or "").strip()
    if not text:
        return None
    now = now or datetime.now()
    relative = re.fullmatch(r"(?P<n>\d+)\s*(?P<unit>[dhw])", text.lower())
    if relative:
        count = int(relative.group("n"))
        unit = relative.group("unit")
        delta = {
            "h": timedelta(hours=count),
            "d": timedelta(days=count),
            "w": timedelta(weeks=count),
        }[unit]
        return now - delta
    for fmt in (_TS_FMT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            # fail-open: trying the next format is the point of the loop, not
            # a swallowed failure -- when every format misses, the function
            # RAISES two lines below rather than returning a default window.
            continue
    raise ValueError(
        f"unparseable --since {spec!r}: use 7d, 24h, 2w, YYYY-MM-DD, "
        f"or 'YYYY-MM-DD HH:MM:SS'"
    )


def _parse_ts(raw: str) -> datetime | None:
    for fmt in (_TS_FMT, "%Y-%m-%d"):
        try:
            return datetime.strptime(str(raw).strip(), fmt)
        except (ValueError, TypeError):
            # fail-open: try the next format. None is returned only when all
            # of them miss, and every caller treats None as "cannot place this
            # record in time" and KEEPS the record -- see _in_window, where
            # dropping it would silently shrink a printed denominator.
            continue
    return None


def _in_window(raw: str, since: datetime | None) -> bool:
    """A record with an unparseable timestamp is KEPT, and counted as such.

    Dropping it would silently shrink a denominator the report is about to
    print, which is the failure this module exists to prevent.
    """
    if since is None:
        return True
    parsed = _parse_ts(raw)
    if parsed is None:
        return True
    return parsed >= since


# ---------------------------------------------------------------------------
# Run logs
# ---------------------------------------------------------------------------


@dataclass
class RunLogFacts:
    """What one run log says, counted. Every field is an event count."""

    run_id: str
    issue: int | None
    path: str
    mtime: str
    pinning_refusals: int = 0
    pinning_regressions: int = 0
    edit_scripts_applied: int = 0
    edit_script_fallbacks: int = 0
    fallback_reasons: list[str] = field(default_factory=list)
    cap_grants: list[str] = field(default_factory=list)
    review_rounds: dict[str, int] = field(default_factory=dict)
    #: stage -> (max observed elapsed, nominal). The watchdog prints one
    #: line per minute per stage, so the LAST elapsed for a stage is the
    #: longest that stage was observed running in this run. It is a floor,
    #: not the true duration -- the stage ends between watchdog ticks --
    #: and the report says so rather than presenting it as a measurement.
    stage_elapsed: dict[str, tuple[int, int]] = field(default_factory=dict)
    unreadable: bool = False
    # -- how the run ended (#2717) and how far it got (#2718) --------------
    #: `passed` (the all-stages banner), `failed` (a failure banner), or
    #: `killed` (neither: the process died mid-call and the log just stops).
    outcome: str = OUTCOME_KILLED
    #: The stage the failure banner names; "" unless outcome is `failed`.
    failed_stage: str = ""
    #: The last stage with any verdict in the closing table, or for a killed
    #: run the last stage a watchdog line saw running.
    furthest_stage: str = ""
    #: For a run that reached impl, the highest node marker printed.
    furthest_node: str = ""
    #: The first line of the banner's Error, or a killed run's last line.
    error_head: str = ""
    #: A CAUSE_TABLE key, or unrecorded / unclassified / killed.
    cause: str = CAUSE_KILLED
    #: The exit classifier label when the log printed one (#2383).
    exit_label: str = ""
    #: stage -> verdict from the closing table, in table order.
    stage_verdicts: dict[str, str] = field(default_factory=dict)
    #: The run's window in UTC, from the log file's creation and last write.
    #: Used to join halt bundles to runs (#2725); None when the log could not
    #: be stat'd, in which case the run takes part in no join.
    started: datetime | None = None
    ended: datetime | None = None
    #: Where `outcome`, `furthest_stage` and `cause` came from (#2721):
    #: `record` if the graph wrote one, `banner` if they were parsed out of the
    #: log's prose. Printed, because the two are different evidence and a reader
    #: deciding whether to launch is entitled to know which they have.
    source: str = SOURCE_BANNER

    @property
    def furthest(self) -> str:
        """`impl:N5`, `spec`, `cleanup` -- one token for the reader."""
        if self.furthest_stage == "impl" and self.furthest_node:
            return f"impl:{self.furthest_node}"
        return self.furthest_stage or "(none)"

    @property
    def furthest_key(self) -> tuple[int, int, int]:
        """Sortable: a passed run beats any failed one at the same stage."""
        return (
            _stage_rank(self.furthest_stage),
            _node_rank(self.furthest_node) if self.furthest_stage == "impl" else -1,
            1 if self.outcome == OUTCOME_PASSED else 0,
        )


def scan_run_log(path: Path) -> RunLogFacts:
    """Count every marker in one run log. Never raises."""
    name = path.name
    match = _RE_RUN_NAME.match(name)
    issue = int(match.group("issue")) if match else None
    run_id = name[:-4] if name.endswith(".log") else name

    started: datetime | None = None
    ended: datetime | None = None
    try:
        stat = path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime(_TS_FMT)
        # #2725: the run's window, in UTC, for joining halt bundles to runs. A
        # bundle names no run tag, so the instant it was written is the only
        # join the data supports. `st_ctime` is creation time on Windows, which
        # is where every recorded run in the corpus was produced.
        started = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
        ended = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    except OSError:
        # fail-open: an unstattable log keeps an empty mtime, and scan_run_logs
        # INCLUDES a log it cannot date rather than filtering it out. Excluding
        # it would drop real events from a window silently; including it can
        # only ever widen the count, which is visible in the printed total.
        mtime = ""

    facts = RunLogFacts(
        run_id=run_id, issue=issue, path=str(path), mtime=mtime,
        started=started, ended=ended,
    )

    try:
        # errors="replace": see the module docstring. Model output leaves
        # stray bytes in these logs and a strict decode drops real events.
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        # fail-open: one unreadable log must not kill a report over the other
        # four hundred. The substitution is not silent -- `unreadable` is set
        # on the record, so the shortfall is carried in the data rather than
        # disguised as a run in which nothing happened.
        facts.unreadable = True
        return facts

    last_stage_running = ""
    last_nonblank = ""
    awaiting_error = False
    for line in text.splitlines():
        if _RE_PINNING_REFUSED.search(line):
            facts.pinning_refusals += 1
        if _RE_PINNING_REGRESSION.search(line):
            facts.pinning_regressions += 1
        applied = _RE_EDIT_APPLIED.search(line)
        if applied:
            facts.edit_scripts_applied += 1
        fallback = _RE_EDIT_FALLBACK.search(line)
        if fallback:
            facts.edit_script_fallbacks += 1
            reason = fallback.group("reason").strip()
            if reason:
                facts.fallback_reasons.append(reason[:120])
        cap = _RE_CAP_GRANT.search(line)
        if cap:
            facts.cap_grants.append(cap.group("detail").strip()[:160])
        review = _RE_REVIEW_ROUND.search(line)
        if review:
            what = review.group("what").lower()
            facts.review_rounds[what] = max(
                facts.review_rounds.get(what, 0), int(review.group("round"))
            )
        watchdog = _RE_STAGE_WATCHDOG.search(line)
        if watchdog:
            stage = watchdog.group("stage")
            elapsed = int(watchdog.group("elapsed"))
            nominal = int(watchdog.group("nominal"))
            prior = facts.stage_elapsed.get(stage, (0, nominal))
            facts.stage_elapsed[stage] = (max(prior[0], elapsed), nominal)
            last_stage_running = stage
        # -- terminal parse (#2717 / #2718) --------------------------------
        row = _RE_STAGE_ROW.match(line)
        if row:
            facts.stage_verdicts[row.group("stage")] = row.group("verdict")
        node = _RE_IMPL_NODE.match(line)
        if node and _node_rank(node.group("node")) > _node_rank(
            facts.furthest_node
        ):
            facts.furthest_node = node.group("node")
        banner = _RE_FAILED_BANNER.match(line)
        if banner:
            facts.outcome = OUTCOME_FAILED
            facts.failed_stage = banner.group("stage")
            awaiting_error = True
        elif awaiting_error:
            error = _RE_BANNER_ERROR.match(line)
            if error:
                facts.error_head = error.group("msg").strip()[:200]
                awaiting_error = False
        if _RE_ALL_PASSED.search(line):
            facts.outcome = OUTCOME_PASSED
        exit_label = _RE_EXIT_LABEL.match(line)
        if exit_label:
            facts.exit_label = exit_label.group("label")
        if line.strip():
            last_nonblank = line.strip()

    # The furthest stage is the last row of the closing table that carries a
    # verdict. A run that resumed at spec shows lld as `skipped`, which still
    # counts as reached: the pipeline stood on that artifact.
    reached = [s for s, v in facts.stage_verdicts.items() if v != "-"]
    if reached:
        facts.furthest_stage = max(reached, key=_stage_rank)
    elif last_stage_running:
        facts.furthest_stage = last_stage_running
    if facts.furthest_stage != "impl":
        facts.furthest_node = ""

    if facts.outcome == OUTCOME_FAILED:
        facts.cause = classify_cause(facts.error_head)
    elif facts.outcome == OUTCOME_PASSED:
        facts.cause = ""
        facts.error_head = ""
    else:
        # Killed: no banner at all. The last line is the only evidence of
        # where it died, and it is carried verbatim rather than guessed at.
        facts.cause = CAUSE_KILLED
        facts.error_head = last_nonblank[:120]

    return facts


def runs_dir(repo_root: Path | str) -> Path:
    return Path(repo_root) / "data" / "speedrun" / "runs"


def scan_run_logs(
    repo_root: Path | str, since: datetime | None = None
) -> list[RunLogFacts]:
    """Every `run-issue*.log` in the window, oldest first.

    The window is applied on the file's mtime: run logs carry no header
    timestamp, and the stamp in the name has no date component, so mtime is
    the only date the filesystem actually knows.
    """
    directory = runs_dir(repo_root)
    if not directory.is_dir():
        # fail-open: a repo with no runs directory has never been rolled, which
        # is a real answer and not an error. It is NOT reported as "zero runs":
        # build_report records the directory's absence, and render_report
        # prints `| NO |` for the store so an absent store never reads as an
        # empty one.
        return []
    facts: list[RunLogFacts] = []
    for path in sorted(directory.glob("run-issue*.log")):
        if path.name.endswith("-events.log") or path.name.endswith(
            "-heartbeat.log"
        ):
            continue
        scanned = scan_run_log(path)
        if since is not None and scanned.mtime and not _in_window(
            scanned.mtime, since
        ):
            continue
        facts.append(scanned)
    facts = apply_records(facts, repo_root)
    return sorted(facts, key=lambda f: (f.mtime, f.run_id))


def apply_records(
    facts: list[RunLogFacts], repo_root: Path | str
) -> list[RunLogFacts]:
    """Let the graph's own terminal record override the banner parse (#2721).

    The record wins wherever it exists, because it was written by the code that
    knew, at the moment it knew, rather than recovered from prose afterwards.
    Where it does not exist -- every run before this landed, and any run whose
    write failed -- the banner parse stands and the run says `banner`, so the
    two are never silently mixed into one number.

    `furthest_stage` is deliberately NOT overwritten from the terminal record's
    field alone: the entry records are the better source for it, since they are
    written as the run advances and survive a run that died before it could
    write anything terminal.
    """
    records, _ = read_records(repo_root)
    if not records:
        return facts
    terminals = terminals_by_run(records)
    furthest = furthest_by_run(records)
    for run in facts:
        entry = terminals.get(run.run_id)
        reached = furthest.get(run.run_id)
        if entry is None and reached is None:
            continue
        run.source = SOURCE_RECORD
        if reached:
            stage, node = reached
            if stage:
                run.furthest_stage = stage
            if node:
                run.furthest_node = node
        if entry is None:
            # Entries but no terminal: the run died before it could say how it
            # ended. That is exactly the killed run the banner parse cannot
            # describe, and the entries still say how far it got.
            continue
        outcome = str(entry.get("outcome") or "")
        if outcome in (OUTCOME_PASSED, OUTCOME_FAILED):
            run.outcome = outcome
        key = str(entry.get("gate_key") or "")
        if key and outcome == OUTCOME_FAILED:
            run.cause = key
            run.failed_stage = str(entry.get("furthest_stage") or run.failed_stage)
    return facts


def source_counts(facts: list[RunLogFacts]) -> dict[str, int]:
    """How many runs each source accounts for. Counted, never estimated."""
    counts = {SOURCE_RECORD: 0, SOURCE_BANNER: 0}
    for run in facts:
        counts[run.source] = counts.get(run.source, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Halt evidence bundles (#2574) and resume contracts (#2570)
# ---------------------------------------------------------------------------


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        # fail-open: deliberately toward EXCLUSION. This answers "is this
        # halt attributable to the repo being reported on". A path that cannot
        # be resolved or compared is not proof of containment, and the safe
        # direction is to omit a halt rather than credit this repo with
        # another repo's. Undercounting is visible in the total; misattribution
        # is not (see #2588).
        return False


#: Every place inside a target repo a halt bundle can come to rest. `docs/lineage`
#: is where the halt writes it; the other two are where it is MOVED to, by
#: `speedrun_reset` and by the run archiver. Counted on boostgauge 2026-09-03:
#: 39 bundles exist, and scanning `docs/lineage` alone finds 8 of them. A report
#: that says "7 bundles against 135 kills" while 31 sit in directories it never
#: opens is not measuring coverage, it is measuring its own search path (#2725).
HALT_BUNDLE_SUBDIRS: tuple[tuple[str, ...], ...] = (
    ("docs", "lineage"),
    ("data", "speedrun", "reset-artifacts"),
    ("data", "speedrun", "archives"),
)


def halt_bundle_roots(repo_root: Path | str) -> list[Path]:
    """The directories under one repo that can hold a halt bundle."""
    repo = Path(repo_root)
    return [repo.joinpath(*parts) for parts in HALT_BUNDLE_SUBDIRS]


def attribute_bundles(
    bundles: list[dict], runs: list[RunLogFacts]
) -> tuple[dict[str, int], int]:
    """Which run each bundle belongs to, by its `halted_at` instant.

    A bundle names no run tag -- #2574 predates the run record (#2721) -- so the
    join is built from the two things it does carry: the ISSUE it halted on, and
    the INSTANT it halted at. Issue first, because rolls of different issues run
    concurrently and their log windows overlap freely; within one issue's runs
    the windows are effectively sequential.

    Returns (bundles per run id, bundles that could not be placed). The second
    number is returned rather than dropped: a coverage figure whose denominator
    quietly excludes what it could not place is not a measurement. A bundle that
    lands in two windows of the SAME issue is left unplaced rather than assigned
    to the earlier one, because putting a real halt against the wrong run's name
    is worse than admitting the join is ambiguous.
    """
    by_issue: dict[int, list[tuple[datetime, datetime, str]]] = defaultdict(list)
    for run in runs:
        if run.started and run.ended and run.issue is not None:
            by_issue[run.issue].append((run.started, run.ended, run.run_id))
    per_run: dict[str, int] = defaultdict(int)
    unplaced = 0
    for bundle in bundles:
        when = _parse_halted_at(str(bundle.get("halted_at", "")))
        issue = bundle.get("issue")
        if when is None or not isinstance(issue, int):
            unplaced += 1
            continue
        hit = [
            tag for start, end, tag in by_issue.get(issue, ())
            if start <= when <= end
        ]
        if len(hit) == 1:
            per_run[hit[0]] += 1
        else:
            unplaced += 1
    return dict(per_run), unplaced


def _parse_halted_at(raw: str) -> datetime | None:
    if not raw:
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        # fail-open: a bundle with an unreadable stamp cannot be placed against
        # a run. It is COUNTED as unplaced by the caller and reported, never
        # silently folded into the coverage figure.
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def read_halt_bundles(
    search_roots: list[Path],
    since: datetime | None = None,
    *,
    scope_repo: Path | None = None,
) -> list[dict]:
    """Every readable `halt-evidence.json` under the given roots.

    Added by the 2026-08-28 update to #2575: since #2574 landed, a halt
    leaves machine-readable counters, event lists and artifact hashes, so
    halts can be counted from a structured store instead of parsed out of
    run-log prose.

    `scope_repo` is load-bearing when a root is SHARED. The halt path writes
    one copy of the bundle beside the state snapshot in
    ``~/.assemblyzero/workflow_state``, which is global across every repo
    the fleet has ever rolled, and one copy into the run's audit dir inside
    the target repo. Counting the shared directory unscoped attributes every
    other repo's halts to this one -- a wrong number presented confidently,
    which is the exact failure this report exists to end. A bundle found
    outside the target repo is therefore kept only when its own `audit_dir`
    points back inside it; a bundle with no `audit_dir` cannot be attributed
    to any repo and is dropped rather than guessed at.
    """
    bundles: list[dict] = []
    seen: set[str] = set()
    for root in search_roots:
        if not root or not Path(root).is_dir():
            continue
        for path in sorted(Path(root).rglob("halt-evidence.json")):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                # fail-open: one corrupt bundle drops that halt from the
                # count and never the report. The count is reported with
                # its own denominator so a reader can see the shortfall.
                continue
            if not isinstance(data, dict):
                continue
            if scope_repo is not None and not _under(path, Path(scope_repo)):
                audit_dir = str(data.get("audit_dir", "") or "")
                if not audit_dir or not _under(
                    Path(audit_dir), Path(scope_repo)
                ):
                    continue
            halted = str(data.get("halted_at", ""))
            if since is not None and halted:
                # Bundles stamp UTC ISO-8601; compare on the date portion
                # only, because the window bound is local and converting
                # would claim a precision the comparison does not have.
                parsed = _parse_ts(halted[:10])
                if parsed is not None and parsed.date() < since.date():
                    continue
            data["_path"] = str(path)
            bundles.append(data)
    return sorted(
        bundles, key=lambda b: (str(b.get("halted_at", "")), str(b.get("_path")))
    )


# ---------------------------------------------------------------------------
# The counted picture
# ---------------------------------------------------------------------------


def _top(counter: dict[str, int], limit: int = 3) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]


def build_report(
    repo_root: Path | str,
    *,
    since: datetime | None = None,
    extra_halt_roots: list[Path] | None = None,
) -> dict:
    """Read every store and return the counted picture. Read-only."""
    from assemblyzero.speedrun.healing import heals_path, read_heals
    from assemblyzero.speedrun.preserved import ledger_path, read_ledger
    from assemblyzero.speedrun.prompt_telemetry import (
        read_failures,
        telemetry_path,
    )

    repo = Path(repo_root)

    failures = [
        row
        for row in read_failures(repo)
        if _in_window(row.get("ts_local", ""), since)
    ]
    heals = [
        row for row in read_heals(repo) if _in_window(row.get("ts", ""), since)
    ]
    preserved = [
        rec for rec in read_ledger(repo) if _in_window(rec.at, since)
    ]
    runs = scan_run_logs(repo, since)

    halt_roots = list(extra_halt_roots or [])
    halt_roots.append(Path.home() / ".assemblyzero" / "workflow_state")
    halt_roots.extend(halt_bundle_roots(repo))
    # scope_repo: the state dir is shared across every repo the fleet rolls.
    # See read_halt_bundles -- counting it unscoped would attribute other
    # repos' halts to this one.
    bundles = read_halt_bundles(halt_roots, since, scope_repo=repo)

    # -- gates: which fire, which never do -------------------------------
    per_check: dict[str, int] = defaultdict(int)
    per_fingerprint: dict[str, int] = defaultdict(int)
    for row in failures:
        stage = str(row.get("stage") or "?")
        check = str(row.get("check") or "?")
        per_check[f"{stage}:{check}"] += 1
        per_fingerprint[str(row.get("fingerprint") or "unknown")] += 1

    declared = [f"{stage}:{check}" for stage, check in DECLARED_CHECKS]
    zero_fire = sorted(key for key in declared if per_check.get(key, 0) == 0)
    undeclared = sorted(key for key in per_check if key not in declared)

    # -- loops: revision rounds, cap grants, edit-script health -----------
    rounds_per_issue: dict[str, int] = defaultdict(int)
    cap_grants: list[tuple[str, str]] = []
    fallback_reasons: dict[str, int] = defaultdict(int)
    applied_total = 0
    fallback_total = 0
    for run in runs:
        applied_total += run.edit_scripts_applied
        fallback_total += run.edit_script_fallbacks
        for reason in run.fallback_reasons:
            fallback_reasons[reason] += 1
        for detail in run.cap_grants:
            cap_grants.append((run.run_id, detail))
        for what, highest in run.review_rounds.items():
            key = f"#{run.issue}:{what}" if run.issue else f"?:{what}"
            rounds_per_issue[key] = max(rounds_per_issue[key], highest)

    # -- pinning ---------------------------------------------------------
    pinning_refusals = sum(run.pinning_refusals for run in runs)
    pinning_regressions = sum(run.pinning_regressions for run in runs)

    # -- janitor and preservation ----------------------------------------
    heals_by_category: dict[str, int] = defaultdict(int)
    heals_by_outcome: dict[str, int] = defaultdict(int)
    heal_targets: dict[str, int] = defaultdict(int)
    for row in heals:
        heals_by_category[str(row.get("category") or "?")] += 1
        heals_by_outcome[str(row.get("outcome") or "?")] += 1
        heal_targets[
            f"{row.get('category', '?')}:{row.get('target', '?')}"
        ] += 1

    preserved_by_source: dict[str, int] = defaultdict(int)
    for rec in preserved:
        preserved_by_source[rec.source or "(unnamed)"] += 1

    # -- halts -----------------------------------------------------------
    halts_by_stage: dict[str, int] = defaultdict(int)
    for bundle in bundles:
        halts_by_stage[
            f"{bundle.get('workflow', '?')}:{bundle.get('stage', '?')}"
        ] += 1

    # -- cap coverage (#2725) --------------------------------------------
    # The question the launch gate actually needs answered: when a spending
    # limit ends a run, is the work preserved? "N bundles exist" cannot answer
    # it -- a bundle count against a kill count compares two different things,
    # since most kills are gates rather than caps. This joins the two.
    judges_by_cause = {cause.key: cause.judges for cause in CAUSE_TABLE}
    bundles_per_run, bundles_unplaced = attribute_bundles(bundles, runs)
    cap_runs = [
        run for run in runs
        if run.outcome == OUTCOME_FAILED
        and judges_by_cause.get(run.cause) == JUDGES_BUDGET
    ]
    cap_covered = [run for run in cap_runs if bundles_per_run.get(run.run_id)]
    cap_uncovered = sorted(
        (run.mtime, run.run_id, run.cause)
        for run in cap_runs if not bundles_per_run.get(run.run_id)
    )

    # -- outcomes and cause of death (#2717) -----------------------------
    outcomes: dict[str, int] = defaultdict(int)
    failed_by_stage: dict[str, int] = defaultdict(int)
    kills_by_cause: dict[str, int] = defaultdict(int)
    kills_by_stage_cause: dict[str, int] = defaultdict(int)
    unclassified: list[tuple[str, str]] = []
    killed_tails: dict[str, int] = defaultdict(int)
    for run in runs:
        outcomes[run.outcome] += 1
        if run.outcome == OUTCOME_FAILED:
            stage = run.failed_stage or "?"
            failed_by_stage[stage] += 1
            kills_by_cause[run.cause] += 1
            kills_by_stage_cause[f"{stage}:{run.cause}"] += 1
            if run.cause == CAUSE_UNCLASSIFIED:
                unclassified.append((run.run_id, run.error_head))
        elif run.outcome == OUTCOME_KILLED:
            killed_tails[
                _normalize_digits(run.error_head) or "(empty log)"
            ] += 1
    judges_by_key = {cause.key: cause.judges for cause in CAUSE_TABLE}
    kills_by_judges: dict[str, int] = defaultdict(int)
    for key, count in kills_by_cause.items():
        kills_by_judges[judges_by_key.get(key, key)] += count

    # -- convergence (#2718): how far the furthest run got, per day -------
    # Days are by run-log mtime: the only date the filesystem knows. The
    # best run of a day is the furthest one; ties go to the later stamp.
    by_day: dict[str, list[RunLogFacts]] = defaultdict(list)
    for run in runs:
        by_day[run.mtime[:10] if run.mtime else "(undated)"].append(run)
    convergence_rows: list[dict] = []
    previous_key: tuple[int, int, int] | None = None
    for day in sorted(by_day):
        day_runs = by_day[day]
        best = max(day_runs, key=lambda r: (r.furthest_key, r.run_id))
        if previous_key is None:
            trend = "first"
        elif best.furthest_key > previous_key:
            trend = "up"
        elif best.furthest_key == previous_key:
            trend = "same"
        else:
            trend = "down"
        convergence_rows.append(
            {
                "day": day,
                "launches": len(day_runs),
                "furthest": best.furthest,
                "run_id": best.run_id,
                "outcome": best.outcome,
                "cause": best.cause,
                "trend": trend,
            }
        )
        previous_key = best.furthest_key
    best_run = (
        max(runs, key=lambda r: (r.furthest_key, r.run_id)) if runs else None
    )

    return {
        "repo": str(repo),
        "since": since.strftime(_TS_FMT) if since else "",
        "generated_at": datetime.now().strftime(_TS_FMT),
        "stores": {
            "prompt_failures": {
                "path": str(telemetry_path(repo)),
                "exists": telemetry_path(repo).exists(),
                "in_window": len(failures),
            },
            "heals": {
                "path": str(heals_path(repo)),
                "exists": heals_path(repo).exists(),
                "in_window": len(heals),
            },
            "preserved": {
                "path": str(ledger_path(repo)),
                "exists": ledger_path(repo).is_file(),
                "in_window": len(preserved),
            },
            "run_logs": {
                "path": str(runs_dir(repo)),
                "exists": runs_dir(repo).is_dir(),
                "in_window": len(runs),
            },
            "halt_bundles": {
                "path": "; ".join(str(r) for r in halt_roots),
                "exists": any(Path(r).is_dir() for r in halt_roots),
                "in_window": len(bundles),
            },
        },
        "gates": {
            "per_check": dict(per_check),
            "declared": declared,
            "zero_fire": zero_fire,
            "undeclared": undeclared,
            "top_fingerprints": _top(per_fingerprint),
        },
        "loops": {
            "rounds_per_issue": dict(rounds_per_issue),
            "cap_grants": cap_grants,
            "edit_scripts_applied": applied_total,
            "edit_script_fallbacks": fallback_total,
            "fallback_reasons": _top(fallback_reasons, 5),
        },
        "pinning": {
            "refusals": pinning_refusals,
            "regressions": pinning_regressions,
        },
        "runs": runs,
        "heals": {
            "by_category": dict(heals_by_category),
            "by_outcome": dict(heals_by_outcome),
            "recurring_targets": [
                (target, count)
                for target, count in sorted(
                    heal_targets.items(), key=lambda kv: (-kv[1], kv[0])
                )
                if count >= 2
            ],
        },
        "preserved": {
            "by_source": dict(preserved_by_source),
            "total": len(preserved),
        },
        "halts": {
            "by_stage": dict(halts_by_stage),
            "total": len(bundles),
            "cap_runs": len(cap_runs),
            "cap_covered": len(cap_covered),
            "cap_uncovered": cap_uncovered,
            "unplaced": bundles_unplaced,
        },
        "outcomes": {
            "counts": dict(outcomes),
            "failed_by_stage": dict(failed_by_stage),
            "kills_by_cause": dict(kills_by_cause),
            "kills_by_stage_cause": dict(kills_by_stage_cause),
            "kills_by_judges": dict(kills_by_judges),
            "unclassified": unclassified,
            "killed_tails": dict(killed_tails),
            "sources": source_counts(runs),
        },
        "convergence": {
            "by_day": convergence_rows,
            "best": (
                {
                    "run_id": best_run.run_id,
                    "furthest": best_run.furthest,
                    "outcome": best_run.outcome,
                    "cause": best_run.cause,
                }
                if best_run
                else None
            ),
        },
    }


def _bar(label: str, count: int, width: int) -> str:
    return f"  {label.ljust(width)}  {count}"


def render_report(data: dict) -> str:
    """The counted picture as deterministic text."""
    lines: list[str] = []
    window = data["since"] or "(all time)"
    lines.append(f"# Factory report — {data['repo']}")
    lines.append("")
    lines.append(f"Window: since {window}. Generated {data['generated_at']}.")
    lines.append("")

    # Convergence first: it is the number the operator reads (#2718). A
    # session's report card is this table, not its count of closed issues.
    conv = data["convergence"]
    lines.append("## Convergence: how far the furthest run got, per day")
    lines.append("")
    if conv["by_day"]:
        lines.append(
            "Days are by run-log mtime. `furthest` is the last stage with a "
            "verdict; for impl, the highest node marker printed."
        )
        lines.append("")
        lines.append("| day | launches | furthest | trend | run | ended by |")
        lines.append("|---|---|---|---|---|---|")
        for row in conv["by_day"]:
            ended = (
                row["cause"] if row["outcome"] == OUTCOME_FAILED
                else row["outcome"]
            )
            lines.append(
                f"| {row['day']} | {row['launches']} | {row['furthest']} | "
                f"{row['trend']} | {row['run_id']} | {ended} |"
            )
        lines.append("")
        best = conv["best"]
        ended = (
            best["cause"] if best["outcome"] == OUTCOME_FAILED
            else best["outcome"]
        )
        lines.append(
            f"Furthest run in window: {best['run_id']} reached "
            f"{best['furthest']} ({ended})."
        )
    else:
        lines.append("No run logs in this window, so nothing to place.")
    lines.append("")

    outcomes = data["outcomes"]
    lines.append("## Outcomes")
    lines.append("")
    counts = outcomes["counts"]
    total_runs = sum(counts.values())
    if total_runs:
        failed_split = ", ".join(
            f"{stage} {n}"
            for stage, n in sorted(
                outcomes["failed_by_stage"].items(),
                key=lambda kv: (-kv[1], kv[0]),
            )
        )
        lines.append(
            f"{total_runs} run(s): passed {counts.get(OUTCOME_PASSED, 0)}, "
            f"failed {counts.get(OUTCOME_FAILED, 0)}"
            + (f" ({failed_split})" if failed_split else "")
            + f", killed {counts.get(OUTCOME_KILLED, 0)} (no terminal "
            f"banner: the process died mid-call)."
        )
    else:
        lines.append("No run logs in this window.")
    sources = outcomes.get("sources") or {}
    if total_runs:
        # #2721: which evidence this section rests on, said rather than assumed.
        # A record was written by the graph at the moment it knew; a banner was
        # recovered from prose afterwards and cannot describe a run that died
        # before printing one.
        lines.append("")
        lines.append(
            f"Source: {sources.get(SOURCE_RECORD, 0)} run(s) from the graph's "
            f"own terminal record, {sources.get(SOURCE_BANNER, 0)} parsed from "
            f"the closing banner."
        )
    lines.append("")

    lines.append(
        "## Cause of death (failed runs, by the Error line under the banner)"
    )
    lines.append("")
    if outcomes["kills_by_cause"]:
        width = max(len(k) for k in outcomes["kills_by_cause"])
        judges = {cause.key: cause.judges for cause in CAUSE_TABLE}
        for key, count in sorted(
            outcomes["kills_by_cause"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(f"  {count:>4}  {key.ljust(width)}  {judges.get(key, '-')}")
        lines.append("")
        lines.append(
            "By what the gate judges: "
            + ", ".join(
                f"{k} {v}"
                for k, v in sorted(
                    outcomes["kills_by_judges"].items(),
                    key=lambda kv: (-kv[1], kv[0]),
                )
            )
        )
    else:
        lines.append("No failed runs in this window.")
    if outcomes["unclassified"]:
        lines.append("")
        lines.append(
            "Unclassified Error lines -- add a CAUSE_TABLE row deliberately, "
            "never by guessing:"
        )
        for run_id, head in outcomes["unclassified"]:
            lines.append(f"  {run_id}: {head}")
    if outcomes["killed_tails"]:
        lines.append("")
        lines.append("Killed runs end on (digits normalized to N):")
        for tail, count in sorted(
            outcomes["killed_tails"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(f"  {count:>4}  {tail}")
    lines.append("")

    # Stores read, with their denominators. A store that does not exist is
    # a different fact from a store that exists and is empty, and the two
    # are never collapsed.
    lines.append("## Stores read")
    lines.append("")
    lines.append("| store | present | records in window |")
    lines.append("|---|---|---|")
    for name, info in sorted(data["stores"].items()):
        present = "yes" if info["exists"] else "NO"
        lines.append(f"| {name} | {present} | {info['in_window']} |")
    lines.append("")

    gates = data["gates"]
    lines.append("## Gates: which fire, which never do")
    lines.append("")
    if gates["per_check"]:
        width = max(len(k) for k in gates["per_check"])
        lines.append("Failures per stage:check:")
        for key, count in sorted(
            gates["per_check"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(_bar(key, count, width))
    else:
        lines.append(
            f"No validation failures recorded in this window "
            f"(of {len(gates['declared'])} declared recording sites)."
        )
    lines.append("")
    if gates["zero_fire"]:
        lines.append(
            f"Zero-fire gates ({len(gates['zero_fire'])} of "
            f"{len(gates['declared'])} declared) — each is either perfect "
            f"or dead, and this report does not distinguish those:"
        )
        for key in gates["zero_fire"]:
            lines.append(f"  {key}")
    else:
        lines.append("Zero-fire gates: none — every declared gate fired.")
    lines.append("")
    if gates["undeclared"]:
        lines.append(
            "Recorded but NOT declared in DECLARED_CHECKS — the registry is "
            "behind the code, which test_factory_report.py should have "
            "caught:"
        )
        for key in gates["undeclared"]:
            lines.append(f"  {key}")
        lines.append("")
    if gates["top_fingerprints"]:
        lines.append("Top fingerprints by volume:")
        for key, count in gates["top_fingerprints"]:
            lines.append(f"  {count:>4}  {key}")
        lines.append("")

    loops = data["loops"]
    lines.append("## Loops: revision rounds, caps, edit-script health")
    lines.append("")
    applied = loops["edit_scripts_applied"]
    fell_back = loops["edit_script_fallbacks"]
    total = applied + fell_back
    if total:
        pct = (fell_back * 100.0) / total
        lines.append(
            f"Edit scripts: {applied} applied, {fell_back} fell back to full "
            f"revision ({pct:.1f}% of {total} attempts)."
        )
    else:
        lines.append("Edit scripts: no attempts recorded in this window.")
    if loops["fallback_reasons"]:
        lines.append("")
        lines.append("Fallback reasons by volume:")
        for reason, count in loops["fallback_reasons"]:
            lines.append(f"  {count:>4}  {reason}")
    lines.append("")
    if loops["rounds_per_issue"]:
        lines.append("Highest review round reached, per issue and loop:")
        width = max(len(k) for k in loops["rounds_per_issue"])
        for key, highest in sorted(
            loops["rounds_per_issue"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(_bar(key, highest, width))
        lines.append("")
    if loops["cap_grants"]:
        lines.append(f"Cap grants ({len(loops['cap_grants'])}):")
        for run_id, detail in loops["cap_grants"]:
            lines.append(f"  {run_id}: {detail}")
        lines.append("")

    pinning = data["pinning"]
    lines.append("## Pinning enforcement")
    lines.append("")
    lines.append(
        f"{pinning['refusals']} refusal(s), {pinning['regressions']} "
        f"regression-class event(s) across "
        f"{data['stores']['run_logs']['in_window']} run log(s)."
    )
    lines.append("")

    heals = data["heals"]
    lines.append("## Janitor and preservation activity")
    lines.append("")
    if heals["by_category"]:
        lines.append("Heals by category:")
        width = max(len(k) for k in heals["by_category"])
        for key, count in sorted(
            heals["by_category"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(_bar(key, count, width))
        lines.append("")
        lines.append(
            "Outcomes: "
            + ", ".join(
                f"{k} {v}" for k, v in sorted(heals["by_outcome"].items())
            )
        )
        lines.append("")
    else:
        lines.append("No heals recorded in this window.")
        lines.append("")
    if heals["recurring_targets"]:
        lines.append(
            "Targets healed more than once (a spike here is the signal — "
            "three sweeps of one file in one day should be visible, not "
            "discovered by forensics):"
        )
        for target, count in heals["recurring_targets"]:
            lines.append(f"  {count:>4}  {target}")
        lines.append("")

    preserved = data["preserved"]
    lines.append(
        f"Preservations: {preserved['total']} in window"
        + (
            " ("
            + ", ".join(
                f"{k} {v}" for k, v in sorted(preserved["by_source"].items())
            )
            + ")."
            if preserved["by_source"]
            else "."
        )
    )
    lines.append("")

    halts = data["halts"]
    lines.append("## Halts (from #2574 evidence bundles)")
    lines.append("")
    if halts["by_stage"]:
        lines.append(f"{halts['total']} bundle(s):")
        for key, count in sorted(
            halts["by_stage"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            lines.append(f"  {count:>4}  {key}")
    else:
        lines.append(
            "No halt-evidence bundles found. #2574 landed 2026-08-28, so "
            "halts before it left no bundle; their count is not zero, it "
            "is unrecorded."
        )
    if halts.get("unplaced"):
        lines.append(
            f"  ({halts['unplaced']} bundle(s) could not be placed against a "
            f"run and are excluded from the coverage figure below.)"
        )
    lines.append("")

    # #2725: the question a launch decision needs answered. A bundle count on
    # its own cannot answer it -- most kills are gates, not caps -- so this
    # joins bundles to the runs a spending limit actually ended.
    lines.append("### When a cap ended a run, was the work preserved?")
    lines.append("")
    if halts["cap_runs"]:
        lines.append(
            f"{halts['cap_covered']} of {halts['cap_runs']} cap-ended run(s) "
            f"left a halt bundle."
        )
        if halts["cap_uncovered"]:
            lines.append("")
            lines.append("Cap-ended runs with no bundle, oldest first:")
            for when, run_id, cause in halts["cap_uncovered"]:
                lines.append(f"  {when or '(undated)':<20}  {run_id:<24}  {cause}")
    else:
        lines.append("No run in this window was ended by a cap.")
    lines.append("")

    # The shortlist the report COMPUTES, not the reader.
    lines.append("## Shortlist (computed)")
    lines.append("")
    shortlist: list[str] = []
    # A report where every store was empty still ranks the declared gates as
    # zero-fire, which is true but reads as a finding about the gates when it
    # is actually a finding about the window. Say which it is, first.
    if not any(info["in_window"] for info in data["stores"].values()):
        shortlist.append(
            "No store carried records in this window -- every zero below is "
            "an absence of data, not an absence of events."
        )
    if conv["best"]:
        shortlist.append(
            f"Furthest run in window: {conv['best']['run_id']} reached "
            f"{conv['best']['furthest']}"
        )
    for key, count in _top(outcomes["kills_by_cause"], 1):
        shortlist.append(f"Top cause of death: {key} ({count})")
    for key, count in _top(gates["per_check"]):
        shortlist.append(f"Top check by failure volume: {key} ({count})")
    if fell_back and total:
        shortlist.append(
            f"Edit-script fallback rate: {fell_back}/{total} "
            f"({(fell_back * 100.0) / total:.1f}%)"
        )
    for key in gates["zero_fire"]:
        shortlist.append(f"Zero-fire gate (perfect or dead): {key}")
    if heals["recurring_targets"]:
        target, count = heals["recurring_targets"][0]
        shortlist.append(f"Most-repeated heal target: {target} ({count})")
    if not shortlist:
        shortlist.append("Nothing ranked: no store carried records in window.")
    for item in shortlist:
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines) + "\n"
