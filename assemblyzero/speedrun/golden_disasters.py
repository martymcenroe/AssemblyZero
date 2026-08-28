"""The disaster museum, replayable (#2572).

A model or prompt change ships blind against exactly the failure modes the
fleet paid to discover. The 2026-08-27 campaign preserved a complete
museum — the fence complaint that deadlocked, the eliding rewrite with
`[UNCHANGED]` placeholders, a hallucinated symbol that reached a draft —
and each cost a run to find and a session to fix. When the drafter model
bumps or a prompt is reworded, nothing replays these; the first evidence of
regression is another killed roll.

## The corpus owns its fixtures, and that is the whole design

The scattered replay scripts this gathers were written against LIVE lineage
paths. `data/scratch-2026-08-27-2555/replay_331.py` opens

    docs/lineage/active/331-implspec/2026-08-27T15-02-19Z/001-spec-draft.md

which **no longer exists** — measured 2026-08-28, one day after it was
written. Lineage dirs are swept, archived and reset by design (standard
0027); a corpus that points into them decays silently and is discovered
broken on the day it is needed. So every case's artifacts are COPIED into
`tests/fixtures/golden_disasters/` and committed, with provenance recorded
naming the lineage they came from. The provenance is a fact about history;
the fixture is the thing that runs.

## Two tiers

**Deterministic** (CI, free): the preserved BAD artifact replayed through
the REAL machinery. These are regression tests for the guards, and they
half-existed already, scattered across one-shot scripts in gitignored
scratch dirs. The corpus names and gathers the set.

**Live** (operator-invoked, spends tokens): the preserved PROMPT replayed
against the current model, asserting the RESPONSE CLASS rather than the
bytes. Run before adopting a model change, the way `FORBIDDEN_MODELS` gates
ids — this gates behaviour. The live tier is defined here and its runner
refuses to invent a verdict it did not measure.

## A case asserts a class, never a byte string

`expected` is a predicate over the machinery's real output. Asserting exact
bytes would make every case fail on an unrelated reword, and a corpus that
cries wolf is a corpus nobody runs — which is how the museum was lost the
first time.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

#: Where the committed fixtures live, relative to the repo root.
CORPUS_REL = Path("tests") / "fixtures" / "golden_disasters"

DETERMINISTIC = "deterministic"
LIVE = "live"


@dataclass(frozen=True)
class DisasterCase:
    """One preserved kill, and the assertion that the pipeline survives it."""

    slug: str
    #: What this case is, in one line, for the report.
    title: str
    #: The kill it came from: run, lineage dir, and the issue that fixed it.
    provenance: str
    #: The issue whose repair this case guards.
    guards: str
    tier: str = DETERMINISTIC
    #: Files under `CORPUS_REL/slug/` the case reads.
    artifacts: tuple[str, ...] = ()

    def path(self, repo_root: Path, artifact: str) -> Path:
        return Path(repo_root) / CORPUS_REL / self.slug / artifact

    def read(self, repo_root: Path, artifact: str) -> str:
        return self.path(repo_root, artifact).read_text(
            encoding="utf-8", errors="replace"
        )


@dataclass
class CaseResult:
    slug: str
    tier: str
    passed: bool
    detail: str
    #: Set only when the case could not RUN (a missing fixture). Distinct
    #: from a failure: "the guard regressed" and "the corpus is broken" are
    #: different findings and must never render identically.
    errored: bool = False


# ---------------------------------------------------------------------------
# The cases
# ---------------------------------------------------------------------------


def _case_fence_deadlock(repo_root: Path) -> tuple[bool, str]:
    """The 2026-08-27 fence complaint, replayed through the real producer.

    The kill: a completeness failure demanded a fence retag and addressed
    its target as `lines 89-92`, a scheme the pinning vocabulary could not
    read. Pinning reverted the mandated retag three rounds running and the
    loop burned its cap on byte-identical drafts (#2555).

    The guard: `named_line_ranges` reads dashed citations, so the complaint
    now addresses the span it names. This runs the REAL check against the
    REAL preserved draft -- the complaint text is produced, never asserted.
    """
    import importlib

    from assemblyzero.workflows.implementation_spec.message_addressability import (
        addresses_draft,
    )

    vc = importlib.import_module(
        "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
    )
    draft = CASES["fence-deadlock"].read(repo_root, "draft.md")

    check = vc.check_api_symbols_exist(draft, ["render"], "")
    if check["passed"]:
        return False, (
            "the preserved draft no longer trips check_api_symbols_exist -- "
            "the case cannot guard a repair it does not reach"
        )

    verdict = addresses_draft(check["details"], draft)
    if not verdict.addressed:
        return False, (
            f"REGRESSION (#2555): the fence complaint addresses no line of "
            f"the draft. {verdict.summary()}. This is the deadlock: the "
            f"drafter retags, pinning reverts, the loop produces "
            f"byte-identical drafts until the cap."
        )
    return True, (
        f"the fence complaint addresses draft lines "
        f"{verdict.matched_lines[0]}-{verdict.matched_lines[-1]} via "
        f"{', '.join(verdict.via)}"
    )


def _case_eliding_rewrite(repo_root: Path) -> tuple[bool, str]:
    """A revision that elides content behind `[UNCHANGED]` placeholders.

    The kill: the drafter emitted a "revision" that replaced whole regions
    with `[UNCHANGED]` markers. Merged naively, the document loses every
    test definition the placeholder stood in for (#2559).

    The guard: conservation through transformation. The merge never emits a
    document holding fewer test definitions than the previous draft held
    and no verdict named. This replays the real preserved pair.
    """
    import re

    case = CASES["eliding-rewrite"]
    previous = case.read(repo_root, "draft.md")
    revision = case.read(repo_root, "revision.md")

    test_def = re.compile(r"^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(")

    def _defs(text: str) -> set[str]:
        return {
            match.group(1)
            for line in text.splitlines()
            if (match := test_def.match(line))
        }

    before, after = _defs(previous), _defs(revision)
    if not before:
        return False, (
            "the preserved draft holds no test definitions -- the case "
            "cannot measure conservation of a quantity that is zero"
        )
    lost = before - after
    if lost:
        return False, (
            f"REGRESSION (#2559): the revision loses {len(lost)} test "
            f"definition(s) the previous draft held: {sorted(lost)[:5]}. "
            f"The conservation gate must emit the revision unenforced or "
            f"the previous draft entire, never the stitch."
        )
    placeholders = revision.count("[UNCHANGED]")
    return True, (
        f"conservation holds across the eliding pair: {len(before)} test "
        f"definition(s) survive {placeholders} [UNCHANGED] placeholder(s)"
    )


def _case_hallucinated_symbol(repo_root: Path) -> tuple[bool, str]:
    """A spec calling a method the target project does not have.

    The kill: a draft called `spec.loader.exec_module(conftest)` against a
    project whose gathered symbols contain no such method. Unfound, it
    reaches implementation and fails there, three stages from the cause.

    The guard: `check_api_symbols_exist` names the symbol and the call site
    at draft time. This replays the real preserved draft.
    """
    import importlib

    vc = importlib.import_module(
        "assemblyzero.workflows.implementation_spec.nodes."
        "validate_completeness"
    )
    draft = CASES["hallucinated-symbol"].read(repo_root, "draft.md")

    check = vc.check_api_symbols_exist(draft, ["render"], "")
    if check["passed"]:
        return False, (
            "REGRESSION: the hallucinated symbol in the preserved draft is "
            "no longer detected -- it would reach implementation"
        )
    if "exec_module" not in check["details"]:
        return False, (
            f"the check fires but does not name the hallucinated symbol; "
            f"a complaint that does not name it cannot be acted on. "
            f"details={check['details'][:160]!r}"
        )
    return True, "the hallucinated symbol is named at draft time"


#: Every case, by slug. Ordered dict semantics are Python 3.7+ default, and
#: the report iterates in definition order so it reads the same every run.
CASES: dict[str, DisasterCase] = {
    "fence-deadlock": DisasterCase(
        slug="fence-deadlock",
        title="the fence complaint that deadlocked the 11:17 run",
        provenance=(
            "boostgauge run-issue331-111729, lineage "
            "docs/lineage/active/331-implspec/2026-08-27T22-27-33Z/"
            "001-spec-draft.md, copied 2026-08-28"
        ),
        guards="#2555 (dashed line-range citations enter the vocabulary)",
        artifacts=("draft.md",),
    ),
    "eliding-rewrite": DisasterCase(
        slug="eliding-rewrite",
        title="the eliding rewrite with [UNCHANGED] placeholders",
        provenance=(
            "boostgauge lineage docs/lineage/done/331-implspec/"
            "2026-08-27T04-05-46Z/{004,006}-spec-draft.md, copied 2026-08-28"
        ),
        guards="#2559 (conservation through transformation)",
        artifacts=("draft.md", "revision.md"),
    ),
    "hallucinated-symbol": DisasterCase(
        slug="hallucinated-symbol",
        title="a spec calling exec_module, a method the project lacks",
        provenance=(
            "boostgauge lineage docs/lineage/done/331-implspec/"
            "2026-08-27T04-05-46Z/004-spec-draft.md, copied 2026-08-28"
        ),
        guards="#2337 (gathered-symbol check names the hallucination)",
        artifacts=("draft.md",),
    ),
}

_RUNNERS: dict[str, Callable[[Path], tuple[bool, str]]] = {
    "fence-deadlock": _case_fence_deadlock,
    "eliding-rewrite": _case_eliding_rewrite,
    "hallucinated-symbol": _case_hallucinated_symbol,
}


def run_case(case: DisasterCase, repo_root: Path) -> CaseResult:
    """Replay one case. A missing fixture ERRORS rather than failing."""
    for artifact in case.artifacts:
        if not case.path(repo_root, artifact).is_file():
            return CaseResult(
                case.slug, case.tier, False,
                f"fixture missing: {case.path(repo_root, artifact)}. The "
                f"corpus is broken, which is a different finding from a "
                f"guard regressing.",
                errored=True,
            )
    runner = _RUNNERS.get(case.slug)
    if runner is None:
        return CaseResult(
            case.slug, case.tier, False,
            f"no runner registered for {case.slug}", errored=True,
        )
    passed, detail = runner(Path(repo_root))
    return CaseResult(case.slug, case.tier, passed, detail)


def run_tier(tier: str, repo_root: Path) -> list[CaseResult]:
    return [
        run_case(case, repo_root)
        for case in CASES.values()
        if case.tier == tier
    ]


def fixture_digest(case: DisasterCase, repo_root: Path) -> str:
    """A stable hash of a case's artifacts, so a silent fixture edit shows.

    The corpus's value depends on the fixture being the artifact that came
    out of the kill. Recording the digest makes an edit visible in a diff
    rather than invisible in a passing test.
    """
    hasher = hashlib.sha256()
    for artifact in case.artifacts:
        hasher.update(case.path(repo_root, artifact).read_bytes())
    return hasher.hexdigest()[:16]


def render_report(results: list[CaseResult], tier: str) -> str:
    lines = [f"Golden disasters — {tier} tier", ""]
    if not results:
        lines.append(f"No cases registered in the {tier} tier.")
        return "\n".join(lines) + "\n"

    errored = [r for r in results if r.errored]
    failed = [r for r in results if not r.passed and not r.errored]
    passed = [r for r in results if r.passed]

    for result in results:
        if result.errored:
            mark = "ERROR"
        elif result.passed:
            mark = "ok"
        else:
            mark = "REGRESSED"
        lines.append(f"[{mark}] {result.slug}")
        lines.append(f"    {result.detail}")
    lines.append("")
    lines.append(
        f"{len(passed)} survived, {len(failed)} regressed, "
        f"{len(errored)} could not run, of {len(results)} case(s)."
    )
    return "\n".join(lines) + "\n"
