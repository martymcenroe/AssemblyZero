"""The healing ledger: every self-heal leaves a record (#2164).

The factory heals itself in many places -- resets, redraws, base
replacements, the worktree sweep, the file janitor, storm backoffs,
restore reconciles -- and each heal used to be a transient line in an
events log. This module gives them a durable, structured record, the
self-heal counterpart of the prompt-failure telemetry (#2074).

One JSONL record per heal at ``data/speedrun/telemetry/heals.jsonl`` in
the TARGET repo. Partial outcomes are first-class: a half-completed heal
(today's WinError 5 lineage deletion) is exactly the record the report
exists to surface. Recording never raises -- a ledger problem must never
cost a roll -- and per standard 0027 the ledger is evidence, exempt from
every janitor.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

HEALS_FILENAME = "heals.jsonl"

CATEGORIES = (
    "reset", "redraw", "base-replace", "sweep", "janitor",
    "storm-backoff", "restore-reconcile",
)

OUTCOMES = ("healed", "partial", "failed")


# ---------------------------------------------------------------------------
# Per-roll artifact vs recurring defect (#2269)
# ---------------------------------------------------------------------------
#
# The recurrence report groups heals by category+target and proposes an issue
# when one group spans enough runs. That grouping reads a STABLE LABEL as a
# recurring OBJECT, and those are not the same thing.
#
# Measured on boostgauge, 2026-08-10/11:
#
#   "reset healed '#1' in 9 distinct runs"        -> nine DIFFERENT LLD PRs
#                                                    (#244, #251, #254, #257,
#                                                    #258, #259, #260, #261,
#                                                    #264), each opened by one
#                                                    roll and correctly closed
#                                                    by the next launch.
#   "restore-reconcile healed
#    'docs/lld/active/LLD-001.md' in 5 runs"      -> five DIFFERENT emissions of
#                                                    that path, one per roll,
#                                                    each correctly preserved
#                                                    and cleared.
#
# Both were root-caused and both were correct-by-design (#2242, #2243). The
# target string was stable because it is derived from the issue number; the
# underlying object never was. A campaign that rolls one issue repeatedly makes
# this the ORDINARY condition, so a stub here trains the reader to skim past
# the stubs that matter.
#
# The rule has two tiers, strongest first.
#
# 1. INSTANCE. When a heal records what it actually touched, that is the
#    answer and no heuristic is consulted: distinct instances across runs is a
#    per-roll artifact, a repeated instance is a genuine recurrence. This is
#    the "distinguish the instance, not the label" half, and it is why
#    `record_heal` takes an optional `instance`.
#
# 2. CATEGORY. Older records carry no instance, and back-filling one would be
#    fabrication. For those, the category says whether a fresh object is
#    implied: a `reset` targets whatever debris the PREVIOUS roll left, so it
#    is a new object every time by construction. A `janitor` or `sweep` may
#    keep finding the same stale thing, which IS a recurrence.
#
# Nothing is ever silently dropped -- the report names what it set aside and
# why, so a suppressed group stays auditable rather than invisible.

#: Categories whose every firing addresses an object the previous roll created.
#: Membership is a claim about the heal's SUBJECT, not about its importance.
PER_ROLL_CATEGORIES = frozenset({"reset", "restore-reconcile"})


def is_per_roll(category: str, instances: list[str] | None = None) -> bool:
    """Is this group a per-roll artifact rather than a recurring defect?

    `instances` is one entry PER RECORD in the group, in any order -- a list,
    not a set, because the whole question is whether any object was healed
    twice, and a set has already thrown that away.

    When every firing named a different object the group is per-roll, whatever
    category it came from: recorded fact beats the category heuristic. When two
    firings name the SAME object it is a real recurrence, which is how a
    genuinely stuck `reset` still gets surfaced despite its category.

    Records with no instance are ignored for tier 1 rather than treated as a
    shared blank, since "not recorded" is not evidence of sameness. If that
    leaves fewer than two known instances there is nothing to compare, and the
    category decides.
    """
    known = [i for i in (instances or []) if i]
    if len(known) >= 2:
        return len(set(known)) == len(known)
    return category in PER_ROLL_CATEGORIES


def heals_path(repo_root: Path | str) -> Path:
    return Path(repo_root) / "data" / "speedrun" / "telemetry" / HEALS_FILENAME


def record_heal(
    repo_root: Path | str,
    category: str,
    target: str,
    outcome: str,
    *,
    detail: str = "",
    run_tag: str = "",
    instance: str = "",
) -> bool:
    """Append one heal record. Returns False (never raises) on failure.

    `instance` names the OBJECT this heal touched, when the caller knows it --
    the PR number a reset closed, the commit a file was preserved at. `target`
    is the label ("#1", a per-issue artifact path) and is frequently stable
    across runs by construction; the instance is what actually differs, and
    recording it is what lets the recurrence report tell a per-roll artifact
    from a recurring defect (#2269).

    Optional on purpose. A caller that cannot name the instance honestly omits
    it and the report falls back to the category rule, which is weaker but not
    a guess dressed as data.
    """
    try:
        path = heals_path(repo_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_tag": run_tag,
            "category": category,
            "target": target,
            "outcome": outcome,
            "detail": detail,
        }
        if instance:
            # Only when known: an empty key on every record would read as one
            # shared instance and turn every group into a false recurrence.
            record["instance"] = instance
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return True
    except Exception:  # noqa: BLE001 - the ledger must never cost a roll
        return False


def read_heals(repo_root: Path | str) -> list[dict]:
    """Every readable record, in order. Corrupt lines are skipped, counted
    by the caller via the length difference if it cares."""
    path = heals_path(repo_root)
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records
