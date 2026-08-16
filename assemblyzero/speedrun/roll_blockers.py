"""Refuse to launch while a known roll-killer is open, in either repo (#2436).

On 2026-08-15 a boostgauge relaunch aborted at exit 91 because #2311 -- filed
two days earlier, acceptance criteria already written -- cleared the resume's
spec artifact before the resume gate read it. Nothing in the machine knew #2311
existed. The audit that eventually found it was a human reading 127 open
issues, which by the fleet's own rule 6 is an inspection: it proves the state of
one moment and nothing about the next launch.

That audit left behind the thing that makes the question answerable -- the
`roll-blocker` label, created the same day in BOTH repos. This module asks it.

## The operator's ruling, 2026-08-15 (recorded on #2436)

Refuse, with an explicit override:

- An open `roll-blocker` in **either** the target repo or AssemblyZero halts the
  launch before the first paid model call, naming every blocker by number and
  title.
- ``--ignore-blockers`` proceeds anyway, and the launch record states that the
  override was used and which blockers were overridden. An override that leaves
  no trace is the accident the ruling exists to stop.
- The list prints on **every** launch, pass or fail. The clean case says it
  checked and found none, because silence is not evidence -- the same complaint
  #2381 makes about box health printing only when it refuses.

## Design decisions

**Both repos, because a roll executes both.** The pipeline code is
AssemblyZero's and the product code is the target's, so a killer in either one
kills the roll. The two slugs are derived from the two checkouts' own remotes
rather than hardcoded: a hardcoded `martymcenroe/AssemblyZero` would query the
wrong board the first time this runs from a fork or a second clone.

**Slug derivation is imported, never re-derived.** `must_resolve.repo_slug`
already turns a checkout into `owner/name`. A second copy here would be a
second parser of one fact, and the two would drift.

**GitHub being unreachable is reported, never fatal.** The sibling gate settled
this: the availability of GitHub must not brick a local roll. An unreachable
board is printed by name and the launch proceeds -- which is honest, and is not
silence. It is also the conservative direction: this gate exists to stop a roll
that is known to be doomed, and "could not ask" is not knowledge.

**No model call.** Two `gh issue list` queries and two `git remote` reads. The
cost is the same whether it passes or refuses, which is what lets it print
every time.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from assemblyzero.speedrun.must_resolve import repo_slug

#: Created 2026-08-15 in both repos by the audit that #2436 was filed from.
#: Its meaning is narrow and load-bearing: this issue KILLS A ROLL. A feature
#: the next roll exists to build is not a blocker, and labelling one that way
#: refuses the launch that would have built it.
ROLL_BLOCKER_LABEL = "roll-blocker"

#: The flag that overrides a refusal, quoted in the messages so the operator
#: never has to go and look it up.
OVERRIDE_FLAG = "--ignore-blockers"


def _default_runner(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except OSError as exc:
        # `gh` not installed. Modelled as a failed call rather than an
        # exception so every caller path stays identical.
        return subprocess.CompletedProcess(args, 127, "", str(exc))


@dataclass(frozen=True)
class Blocker:
    """One open issue that is known to kill a roll."""

    repo: str
    number: int
    title: str

    def describe(self) -> str:
        return f"{self.repo}#{self.number}  {self.title}"


@dataclass(frozen=True)
class BlockerScan:
    """What the board said, and which boards could be reached at all."""

    blockers: tuple[Blocker, ...] = ()
    consulted: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def refuses(self) -> bool:
        """Whether this scan halts a launch that did not override it."""
        return bool(self.blockers)


def _list_blockers(
    slug: str, runner
) -> tuple[list[Blocker], str | None]:
    result = runner([
        "gh", "issue", "list", "--repo", slug,
        "--label", ROLL_BLOCKER_LABEL, "--state", "open",
        "--limit", "100", "--json", "number,title",
    ])
    if result.returncode != 0:
        return [], (result.stderr or "gh issue list failed").strip()
    try:
        rows = json.loads(result.stdout or "[]")
    except ValueError:
        return [], "could not read the issue list response"
    found = []
    for row in rows:
        number = row.get("number")
        if not number:
            continue
        found.append(Blocker(slug, int(number), row.get("title", "")))
    return found, None


def scan_roll_blockers(
    target_root: Path | str,
    az_root: Path | str,
    *,
    runner=_default_runner,
) -> BlockerScan:
    """Open `roll-blocker` issues across the target repo and AssemblyZero.

    Both checkouts are asked for their own remote, so the same tree rolling
    itself is consulted once rather than listed twice.
    """
    slugs: list[str] = []
    errors: list[str] = []
    for root in (target_root, az_root):
        slug = repo_slug(root, runner=runner)
        if not slug:
            errors.append(f"{root}: no GitHub remote, so its board was not checked")
        elif slug not in slugs:
            slugs.append(slug)

    blockers: list[Blocker] = []
    consulted: list[str] = []
    for slug in slugs:
        found, error = _list_blockers(slug, runner)
        if error:
            errors.append(f"{slug}: {error}")
            continue
        consulted.append(slug)
        blockers.extend(found)

    blockers.sort(key=lambda b: (b.repo, b.number))
    return BlockerScan(tuple(blockers), tuple(consulted), tuple(errors))


def _joined(slugs: tuple[str, ...]) -> str:
    if not slugs:
        return "no repository"
    if len(slugs) == 1:
        return slugs[0]
    return " and ".join([", ".join(slugs[:-1]), slugs[-1]])


def blocker_report_lines(scan: BlockerScan, *, overridden: bool = False) -> list[str]:
    """What prints on EVERY launch, pass or fail.

    The clean case is the whole point of printing unconditionally: a check that
    is silent when it passes cannot be distinguished from a check that never
    ran, which is the defect #2381 names for box health.
    """
    lines: list[str] = []
    count = len(scan.blockers)

    if not count:
        lines.append(
            f"ROLL BLOCKERS: checked {_joined(scan.consulted)} -- none open."
        )
    else:
        noun = "issue" if count == 1 else "issues"
        verb = "OVERRIDDEN" if overridden else "OPEN"
        lines.append(
            f"ROLL BLOCKERS {verb}: {count} open {noun} known to kill a roll "
            f"(checked {_joined(scan.consulted)}):"
        )
        for blocker in scan.blockers:
            lines.append(f"  {blocker.describe()}")

    for error in scan.errors:
        lines.append(f"  WARNING: could not check {error}")

    if count and overridden:
        lines.append(
            f"  Rolling anyway because {OVERRIDE_FLAG} was given. This is "
            "recorded in the launch record."
        )
    return lines


def blocker_refusal_message(scan: BlockerScan) -> str:
    """Plain English. No stage names, no internal identifiers, no jargon.

    The operator reads this at a terminal and must be able to act on it without
    opening any code or document.
    """
    count = len(scan.blockers)
    noun = "problem is" if count == 1 else "problems are"
    lines = [
        "",
        f"BLOCKED: {count} known {noun} open that will kill this roll.",
        "",
    ]
    for blocker in scan.blockers:
        lines.append(f"  {blocker.describe()}")
    lines += [
        "",
        "  Each of these was marked as something that stops a roll outright, so",
        "  launching now spends time and money on a run whose ending is already",
        "  known. Fix and close it, or -- if it does not apply to what you are",
        "  about to roll -- take the `roll-blocker` mark off it.",
        "",
        f"  To roll into it deliberately anyway, relaunch with {OVERRIDE_FLAG}.",
        "  The launch will say that you did, and name what you rolled past.",
    ]
    return "\n".join(lines)


def blocker_trace_line(scan: BlockerScan, *, overridden: bool) -> str:
    """The single line the launch record carries, for either outcome.

    The override half is the operator's ruling: an override that leaves no
    trace is the accident this gate exists to stop. The clean half is here for
    the same reason the report prints unconditionally -- so a reader of the
    record can tell "checked, found none" from "never asked".
    """
    if not scan.blockers:
        return f"ROLL-BLOCKERS checked {_joined(scan.consulted)}: none open"
    numbers = ", ".join(f"{b.repo}#{b.number}" for b in scan.blockers)
    if overridden:
        return (
            f"ROLL-BLOCKERS OVERRIDDEN ({OVERRIDE_FLAG}) -- rolled past "
            f"{len(scan.blockers)}: {numbers}"
        )
    return f"ROLL-BLOCKERS open, launch refused -- {numbers}"
