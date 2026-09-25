"""Compare model profiles over the rolls a target repo has recorded (#3566).

boostgauge is the bench (#3562): its rolls are idempotent (standard 0027), so
the same issues rolled under two profiles differ only in the models. This tool
reads what the rolls wrote and prints one table, one row per profile:

    python tools/compare_profiles.py --repo ../boostgauge [--profiles gemini,claude]

Sources, all under the target repo, all written by the pipeline itself:

- ``data/speedrun/telemetry/run-records.jsonl`` (the convergence record): the
  stages and nodes each run entered and how it ended. Every row names the
  profile it ran under (#3565).
- every ``calls.jsonl`` under ``docs/`` and ``data/`` (#2731): one row per model
  call, naming its profile, seat and resolved model (#3565), with the response
  the review verdicts are read from.

Columns:

| Column | How it is counted |
|---|---|
| runs | distinct run tags |
| issues rolled | distinct issue numbers in those run tags |
| issues landed | issues with a `run.terminal` whose outcome is `passed` |
| verdicts | review-seat calls whose JSON response says APPROVED / BLOCKED |
| revisions | per stage, the mean over runs of (drafter-seat calls - 1): `requirements.draft` for lld, `spec.draft` for spec, and `impl.test_plan.revise` calls for impl |
| calls per seat | calls.jsonl rows per seat |
| wall time per stage | mean seconds from a `stage.enter` to the next one (or the run's end) |
| failures by node | `run.terminal` rows with outcome `failed`, by furthest node |
| answer key | how many of the issues rolled appear in the answer-key audit (`docs/audits/0907-...` in this repository); that audit scores gates against the shipped code and defines no score for a roll, so only its coverage is reported |

The table is written as Markdown to ``<repo>/data/speedrun/comparisons/<timestamp>.md``.
Nothing here calls a model or changes the target repo beyond that one file.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

AZ_ROOT = Path(__file__).resolve().parents[1]
if str(AZ_ROOT) not in sys.path:
    sys.path.insert(0, str(AZ_ROOT))

ANSWER_KEY = AZ_ROOT / "docs" / "audits" / "0907-answer-key-audit-boostgauge-2026-09-03.md"
COMPARISONS = Path("data") / "speedrun" / "comparisons"
CALL_ROOTS = ("docs", "data")

#: The drafter seat whose calls count a stage's revisions.
REVISION_SEATS = {
    "lld": ("requirements.draft", 1),
    "spec": ("spec.draft", 1),
    "impl": ("impl.test_plan.revise", 0),
}

COLUMNS = (
    "profile", "runs", "issues rolled", "issues landed", "verdicts",
    "revisions", "calls per seat", "wall time per stage", "failures by node",
    "answer key",
)


@dataclass
class ProfileStats:
    runs: set[str] = field(default_factory=set)
    issues: set[int] = field(default_factory=set)
    landed: set[int] = field(default_factory=set)
    approved: int = 0
    blocked: int = 0
    other_verdicts: int = 0
    seat_calls: Counter = field(default_factory=Counter)
    drafter_calls: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    stage_seconds: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    failures: Counter = field(default_factory=Counter)


def issue_of(run_tag: str) -> int | None:
    """``run-issue4-021938`` -> 4. None for a tag that names no issue."""
    for part in (run_tag or "").split("-"):
        if part.startswith("issue") and part[5:].isdigit():
            return int(part[5:])
    return None


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            # fail-open: a truncated line (a roll killed mid-write) is skipped
            # rather than failing the table; the table is read, not enforced.
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _ts(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def _verdict(response: str) -> str:
    try:
        parsed = json.loads(response or "")
    except ValueError:
        return ""
    return str(parsed.get("verdict", "")).upper() if isinstance(parsed, dict) else ""


def answer_key_issues(path: Path = ANSWER_KEY) -> set[int]:
    """Issue numbers the answer-key audit's verdict table names."""
    issues: set[int] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return issues
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 2 and cells[1].startswith("#") and cells[1][1:].isdigit():
            issues.add(int(cells[1][1:]))
    return issues


def collect(repo: Path) -> dict[str, ProfileStats]:
    """Every profile's numbers, from the repo's own records."""
    from assemblyzero.speedrun.convergence import records_path

    stats: dict[str, ProfileStats] = defaultdict(ProfileStats)

    by_run: dict[str, list[dict]] = defaultdict(list)
    for row in _read_jsonl(records_path(repo)):
        by_run[str(row.get("run_tag", ""))].append(row)

    for run_tag, rows in by_run.items():
        profile = next((str(r["profile"]) for r in rows if r.get("profile")), "(unrecorded)")
        s = stats[profile]
        s.runs.add(run_tag or "(untagged)")
        issue = issue_of(run_tag)
        if issue is not None:
            s.issues.add(issue)
        rows = sorted(rows, key=lambda r: str(r.get("ts", "")))
        enters = [r for r in rows if r.get("event") == "stage.enter"]
        end = _ts(str(rows[-1].get("ts", "")))
        for i, row in enumerate(enters):
            start = _ts(str(row.get("ts", "")))
            stop = _ts(str(enters[i + 1].get("ts", ""))) if i + 1 < len(enters) else end
            if start and stop:
                s.stage_seconds[str(row.get("stage", ""))].append((stop - start).total_seconds())
        for row in rows:
            if row.get("event") != "run.terminal":
                continue
            if row.get("outcome") == "passed" and issue is not None:
                s.landed.add(issue)
            elif row.get("outcome") == "failed":
                s.failures[str(row.get("furthest_node") or row.get("furthest_stage") or "?")] += 1

    for top in CALL_ROOTS:
        base = repo / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("calls.jsonl")):
            for row in _read_jsonl(path):
                profile = str(row.get("profile") or "(unrecorded)")
                s = stats[profile]
                seat = str(row.get("seat") or "(no seat)")
                s.seat_calls[seat] += 1
                run_tag = str(row.get("run_tag", "")) or str(path.parent)
                s.drafter_calls[seat][run_tag] += 1
                if seat.endswith(".review"):
                    verdict = _verdict(str(row.get("response", "")))
                    if verdict == "APPROVED":
                        s.approved += 1
                    elif verdict == "BLOCKED":
                        s.blocked += 1
                    else:
                        s.other_verdicts += 1
    return dict(stats)


def _revisions(s: ProfileStats) -> str:
    parts = []
    for stage, (seat, first_is_draft) in REVISION_SEATS.items():
        per_run = list(s.drafter_calls.get(seat, {}).values())
        if not per_run:
            parts.append(f"{stage} -")
            continue
        mean = sum(max(n - first_is_draft, 0) for n in per_run) / len(per_run)
        parts.append(f"{stage} {mean:.1f}")
    return " / ".join(parts)


def _counter(counter: Counter) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(counter.items())) or "-"


def row_for(profile: str, s: ProfileStats, key: set[int]) -> list[str]:
    stage_times = {
        stage: sum(values) / len(values) for stage, values in s.stage_seconds.items() if values
    }
    verdicts = f"APPROVED {s.approved} / BLOCKED {s.blocked}"
    if s.other_verdicts:
        verdicts += f" / unparsed {s.other_verdicts}"
    covered = len(s.issues & key)
    return [
        profile,
        str(len(s.runs)),
        str(len(s.issues)),
        str(len(s.landed)),
        verdicts,
        _revisions(s),
        _counter(s.seat_calls),
        ", ".join(f"{k} {v:.0f}s" for k, v in sorted(stage_times.items())) or "-",
        _counter(s.failures),
        f"{covered} of {len(s.issues)} issues in the key",
    ]


def render(stats: dict[str, ProfileStats], profiles: list[str] | None, key: set[int]) -> str:
    names = profiles or sorted(stats)
    lines = [
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    for name in names:
        cells = row_for(name, stats.get(name, ProfileStats()), key)
        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare model profiles over a target repo's recorded rolls (#3566)."
    )
    parser.add_argument("--repo", required=True, help="Target repo root (the bench, e.g. boostgauge)")
    parser.add_argument(
        "--profiles", default="",
        help="Comma-separated profile names, in row order. Default: every profile recorded",
    )
    parser.add_argument(
        "--out", default="",
        help=f"Where to write the Markdown. Default: <repo>/{COMPARISONS.as_posix()}/<timestamp>.md",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()] or None
    stats = collect(repo)
    table = render(stats, profiles, answer_key_issues())

    header = (
        f"# Profile comparison: {repo.name}\n\n"
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} by "
        "`tools/compare_profiles.py` from the repo's convergence records and "
        "`calls.jsonl` files.\n\n"
    )
    out = Path(args.out) if args.out else repo / COMPARISONS / (
        datetime.now().strftime("%Y-%m-%dT%H-%M-%S") + ".md"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header + table, encoding="utf-8")
    print(table, end="")
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
