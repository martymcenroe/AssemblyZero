# 0906 — The golden-disaster corpus

**Issue:** #2572
**Runner:** `poetry run python tools/golden_disasters.py --tier deterministic`
**Corpus:** `assemblyzero/speedrun/golden_disasters.py`
**Fixtures:** `tests/fixtures/golden_disasters/`
**Tests:** `tests/unit/test_golden_disasters.py` (20)
**Registry classes:** 3 and 4 (`docs/standards/0029-defect-class-registry.md`)

A model or prompt change ships blind against exactly the failure modes the
fleet paid to discover. Each case below cost a run to find and a session to
fix. This replays them before the next change, not after the next kill.

## The corpus owns its fixtures, and that decision has evidence

The scattered one-shot replays this gathers were written against **live
lineage paths**. `data/scratch-2026-08-27-2555/replay_331.py` opens

```
docs/lineage/active/331-implspec/2026-08-27T15-02-19Z/001-spec-draft.md
```

which **no longer exists** — verified 2026-08-28, one day after that script
was written. Lineage directories are swept, archived and reset by design
(standard 0027), so a corpus that points into them decays silently and is
found broken on the day it is needed.

Every case's artifacts are therefore **copied into the repo and committed**,
with provenance recorded naming the lineage they came from. The provenance
is a fact about history; the fixture is the thing that runs. A test asserts
every declared artifact is present, and `fixture_digest` makes a silent edit
visible in a diff rather than invisible in a passing run.

## The cases

| slug | guards | provenance |
|---|---|---|
| `fence-deadlock` | #2555 — dashed line-range citations enter the pinning vocabulary | boostgauge `run-issue331-111729`, lineage `docs/lineage/active/331-implspec/2026-08-27T22-27-33Z/001-spec-draft.md` |
| `eliding-rewrite` | #2559 — conservation through transformation | boostgauge lineage `docs/lineage/done/331-implspec/2026-08-27T04-05-46Z/{004,006}-spec-draft.md` |
| `hallucinated-symbol` | #2337 — the gathered-symbol check names the hallucination | boostgauge lineage `docs/lineage/done/331-implspec/2026-08-27T04-05-46Z/004-spec-draft.md` |

### fence-deadlock

The kill: a completeness failure demanded a fence retag and addressed its
target as `lines 89-92`, a scheme the pinning vocabulary could not read.
Pinning reverted the mandated retag three rounds running and the loop burned
its cap producing byte-identical drafts.

The replay runs the **real** `check_api_symbols_exist` against the **real**
preserved draft and classifies the message it actually emits — the complaint
text is produced, never asserted. Current result: addresses draft lines
89–92 via `named_line_ranges`.

### eliding-rewrite

The kill: the drafter emitted a "revision" replacing whole regions with
`[UNCHANGED]` markers. Merged naively, the document loses every test
definition the placeholder stood in for.

The replay counts test definitions across the real preserved pair. Current
result: 13 test definitions survive 17 `[UNCHANGED]` placeholders.

### hallucinated-symbol

The kill: a draft called `spec.loader.exec_module(conftest)` against a
project whose gathered symbols contain no such method. Unfound, it reaches
implementation and fails three stages from its cause.

The replay asserts the check fires **and names the symbol** — a complaint
that fires without naming its target cannot be acted on, which is registry
class 3's whole subject.

## A corpus that cannot fail protects nothing

The harder property is not that the cases pass; it is that they would fail.
Three tests defeat the guards deliberately:

- `named_line_ranges` and `named_tokens` monkeypatched to return nothing —
  the fence case reports `REGRESSION (#2555)`.
- A test definition removed from the eliding revision — the case reports
  `REGRESSION (#2559)`.
- A missing fixture — the case **errors** rather than failing, because "the
  guard regressed" and "the corpus is broken" are different findings and
  must never render identically.

## Two tiers

**Deterministic** — free, no network, CI-safe, and the acceptance command.
Three cases, all green on main.

**Live** — operator-invoked, spends tokens, gates a model or prompt change
by replaying the preserved PROMPT and asserting the response class. It is
**registered and empty**: `--tier live` exits 1 saying "Nothing was measured,
so this is not a pass", rather than reporting a vacuous green. Tracked in
#2598, which also carries the open question of whether the 2026-08-27
prompts are recoverable at all — the run logs carry stage narration, not
full prompt text, and reconstructing one would be fabricating evidence.

## Coverage, stated honestly

#2572 names four preserved cases. Three are in the corpus. The fourth — the
**duplicate-registration conftest that killed collection** — was searched
for across the whole lineage tree and **is not there**; nor is the group of
four byte-identical drafts (`md5 379d0859a6750175a48f42934fe31c03`) that the
issue cites, which no two `.md` files in lineage now match. Both were real
and both are gone from the preserved tree, which is the strongest possible
argument for this corpus existing and is filed as its own finding.
