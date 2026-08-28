# Implementation Report — The Golden-Disaster Corpus (#2572)

## Issue Reference
[#2572: a golden-disaster eval corpus -- preserved kill lineage becomes the gate for prompt and model changes](https://github.com/martymcenroe/AssemblyZero/issues/2572)

## Files Changed
- `assemblyzero/speedrun/golden_disasters.py` (new): the corpus — cases, runners, reporting.
- `tools/golden_disasters.py` (new): `--tier deterministic|live`, `--list`.
- `tests/fixtures/golden_disasters/**` (new): four committed artifacts across three cases.
- `tests/unit/test_golden_disasters.py` (new): 20 tests.
- `docs/audits/0906-golden-disaster-corpus.md` (new): the corpus doc with per-case provenance.

## The Central Design Decision, With Evidence

**The corpus owns its fixtures.** The scattered one-shot replays this gathers were written against live lineage paths, and `data/scratch-2026-08-27-2555/replay_331.py` opens `docs/lineage/active/331-implspec/2026-08-27T15-02-19Z/001-spec-draft.md` — **which no longer exists**, verified one day after that script was written.

Lineage dirs are swept, archived and reset by design (standard 0027). A corpus pointing into them decays silently and is found broken on the day it is needed. So artifacts are copied in and committed, with provenance recorded naming the lineage they came from. The provenance is a fact about history; the fixture is the thing that runs.

## The Cases

Three, all replaying **real** preserved artifacts through the **real** machinery:

- **`fence-deadlock`** (#2555): the real `check_api_symbols_exist` against the real preserved draft; the complaint text is produced, never asserted. Currently addresses lines 89–92 via `named_line_ranges`.
- **`eliding-rewrite`** (#2559): test definitions counted across the real preserved pair. 13 survive 17 `[UNCHANGED]` placeholders.
- **`hallucinated-symbol`** (#2337): the check must fire **and name** `exec_module` — a complaint that fires without naming its target cannot be acted on.

## Design Decisions

1. **A case asserts a class, never a byte string.** Asserting exact bytes makes every case fail on an unrelated reword, and a corpus that cries wolf is a corpus nobody runs — which is how the museum was lost the first time.

2. **A missing fixture ERRORS; it does not fail.** "The guard regressed" and "the corpus is broken" are different findings and must never render identically. `CaseResult.errored` carries the distinction into the report.

3. **The empty live tier exits 1, not 0.** A tier with no cases has measured nothing. Exiting 0 would let "the live tier is green" be said about a tier that never ran anything.

4. **`fixture_digest` makes a silent fixture edit visible.** The corpus's value depends on the fixture being what came out of the kill; an edit must show in a diff rather than hide in a passing run.

5. **The deterministic tier is a gate and exits non-zero on regression**, unlike the read-only reporters (`factory_report`, `heal_report`) whose empty state is a fact rather than a failure.

## Coverage, Stated Honestly

#2572 names four cases. **Three are in the corpus.** The fourth — the duplicate-registration conftest — is not in the preserved tree, and neither is the group of four byte-identical drafts (`md5 379d0859…`) the issue cites: no two `.md` files in lineage now match. Both were real on 2026-08-27 and unreachable on 2026-08-28.

Filed as #2599, which asks that the refs be searched and, explicitly, that neither be **reconstructed** — a hand-built lookalike would be fabricated evidence entering a corpus whose whole value is that every case traces to a real kill.

The live tier is registered and empty, tracked in #2598 along with the open question of whether the 2026-08-27 prompts are recoverable at all.
