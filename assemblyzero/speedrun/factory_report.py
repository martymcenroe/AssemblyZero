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
from datetime import datetime, timedelta
from pathlib import Path

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


def scan_run_log(path: Path) -> RunLogFacts:
    """Count every marker in one run log. Never raises."""
    name = path.name
    match = _RE_RUN_NAME.match(name)
    issue = int(match.group("issue")) if match else None
    run_id = name[:-4] if name.endswith(".log") else name

    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime(_TS_FMT)
    except OSError:
        # fail-open: an unstattable log keeps an empty mtime, and scan_run_logs
        # INCLUDES a log it cannot date rather than filtering it out. Excluding
        # it would drop real events from a window silently; including it can
        # only ever widen the count, which is visible in the printed total.
        mtime = ""

    facts = RunLogFacts(run_id=run_id, issue=issue, path=str(path), mtime=mtime)

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
    return sorted(facts, key=lambda f: (f.mtime, f.run_id))


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
    halt_roots.append(repo / "docs" / "lineage")
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
