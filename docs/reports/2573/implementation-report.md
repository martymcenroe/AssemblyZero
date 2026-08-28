# Implementation Report — Best-of-N Drafts (#2573)

## Issue Reference
[#2573: best-of-N drafts judged by the mechanical gates -- replace the serial revision loop where stagnation is the pathology](https://github.com/martymcenroe/AssemblyZero/issues/2573)

## Files Changed
- `assemblyzero/workflows/requirements/best_of_n.py` (new): scoring, selection, the scored table, the candidate clamp.
- `assemblyzero/workflows/requirements/nodes/generate_draft.py`: `_generate_best_of_n`, taken only on an initial lld draft when asked for.
- `assemblyzero/workflows/requirements/state.py`: `config_draft_candidates`, defaulting to 1.
- `tools/run_requirements_workflow.py`: `--draft-candidates`.
- `tests/unit/test_best_of_n.py` (new): 21 tests.

## The Cost Math, Verified First

The issue asked for the breakeven to be verified before building. Counted with `tools/factory_report.py` (#2575) over the boostgauge stores, 2026-08-01 onward:

| measure | counted |
|---|---|
| highest spec review round, #331 | **9** |
| highest spec review round, #1 | **7** |
| cap grants (all spec stage) | **5** |
| edit scripts applied / fell back | 165 / 14 |

A revision round costs one drafter call plus one validation. N=3 costs three drafter calls and three validations and **zero** revision rounds when any candidate clears. Against loops that actually reached seven and nine rounds, three is favourable. That is a counted comparison — the tool built for #2575 feeding the decision for #2573, which is the dependency the sequence was designed around.

## Design Decisions

1. **Initial drafts only, lld only, opt-in.** `--draft-candidates 1` is the serial path *exactly* — no scoring runs, no extra state, the node behaves as it did before. Revisions are deliberately excluded: they travel as edit scripts against a specific prior draft (#2569), so N independent revisions would be N different documents with no common parent.

2. **Scoring uses the real gates.** A candidate is scored by running the actual `validate_lld_mechanical` and `validate_test_plan_node` against a state carrying that candidate. A cheaper approximation would drift from the gate, and a winner chosen by a proxy the real gate then rejects is worse than no selection.

3. **Candidates are scored in isolation.** The probe state clears `validation_errors` before each gate run — leaking them would score candidate 3 for candidate 2's failures. A test asserts both halves: the probe is clean, and the caller's own state is not mutated.

4. **An empty draft is `unusable`, not perfect.** Registry class 1 — a zero needs a denominator. An empty draft trips no gate that reads content, so "zero failures" would otherwise make the drafter's failure the winner.

5. **A gate that crashes counts against the candidate.** Otherwise a candidate could win by breaking a validator.

6. **Ties go to the earlier candidate.** Not longest (rewards padding), not shortest (rewards elision — #2559's exact pathology). Arbitrary but stable, and stability is what makes a roll replayable.

7. **A clean candidate short-circuits.** The remaining calls cannot beat zero failures.

8. **`MAX_CANDIDATES = 5`.** Not a claim about what is useful — a bound on what a typo costs, since the flag is one keystroke from 3 and every candidate is a real drafter call.

9. **Every candidate is preserved to lineage.** The losers are the evidence for whether best-of-N is worth keeping; discarding them would make that unanswerable the same way the serial loop's discarded drafts did.

## Known Limitation: Generation Is Sequential

The issue asks for parallel. Three process globals sit in the loop's path — cumulative cost accounting, prompt-failure telemetry appends, and the provider's cross-instance circuit-breaker state — and none could be proven concurrency-safe here.

**The cost argument does not depend on parallelism**, and cost is the decisive number. Filed as #2604, which also notes that the short-circuit makes parallel a *worse* trade than it looks if clearing on the first candidate is common — something #2575's rollup can now measure. #2604 says measure before building.
