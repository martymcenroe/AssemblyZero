# Test Report — Best-of-N Drafts (#2573)

## Issue Reference
[#2573: best-of-N drafts judged by the mechanical gates -- replace the serial revision loop where stagnation is the pathology](https://github.com/martymcenroe/AssemblyZero/issues/2573)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_best_of_n.py` (new) | **21 passed in 0.4s** |
| `tests/unit` (full) | see below |
| `ruff` on `best_of_n.py`, `test_best_of_n.py`, `state.py` | clean |
| `ruff` on `generate_draft.py`, `run_requirements_workflow.py` | 26 errors before, **26 after** — none introduced |

The lint delta was briefly +1 (an `E402` on the new import, in a file that already carries many). It is now zero.

## The Acceptance Fixture

The issue names it specifically: **a fixture where candidate two alone clears the gates asserts the winner selection**. `test_candidate_two_alone_clears_and_wins` builds three candidates, drives the real scoring path, and asserts:

- candidate 1 scores 2 failures, candidate 2 clears, candidate 3 scores 3;
- `select_winner` returns candidate **2**, and the winning draft is candidate 2's text;
- the rendered table marks exactly candidate 2 as `WINNER` and shows each other candidate's count.

Candidate two is the load-bearing choice: any arrangement where the winner is first or last would also pass under an order-based selector, so only a middle winner proves selection happens on **score**.

## What Else Is Pinned

**Scoring (6).** A clean candidate clears; failures are counted per gate; an empty draft is `unusable` rather than perfect (a zero needs a denominator); a gate that raises counts *against* the candidate, so nothing wins by breaking a validator; candidates are scored in isolation — asserted in both directions, that the probe carries no sibling's errors **and** that the caller's state is not mutated; and unrelated state (issue number, target repo) still reaches the gates, so isolation has not become amnesia.

**Selection (4).** Fewest failures wins; ties go to the earlier candidate; an unusable candidate never wins even against a flawed usable one; all-unusable returns `None`, which is a halt condition for the caller rather than something papered over with the least-bad empty draft.

**Opt-in discipline (3).** `create_initial_state` defaults `config_draft_candidates` to 1; the parameter reaches state when passed; the CLI declares `--draft-candidates` with `default=1`. The serial path stays the default, which is the issue's own instruction.

**Clamping (3).** 1, `None` and garbage all fall back to serial; 0 and negatives too; 30 clamps to 5 — a typo cannot cost thirty drafter calls on a live roll.

**Determinism (1, parameterised over 2/3/5 candidates).** Identical candidates produce an identical winner across repeat runs. A roll that picks differently on replay is not replayable, which would defeat the golden-disaster corpus (#2572) and the mock roll (#2567) both.

## What Is Not Covered

No test drives `_generate_best_of_n` end to end through the node, because doing so honestly needs a live-ish drafter and a real audit dir. The scoring and selection it delegates to are fully covered; the node function is assembly. #2596 (the graph roll on the `ScriptedProvider` harness) is where that gap closes, and it is the natural place — a scripted roll with `--draft-candidates 3` exercises exactly this path with no network.

## Regression Risk

The feature is off by default and the default path is unchanged: `use_best_of_n` requires `candidates > 1`, `workflow_type == "lld"`, and a non-revision. All three must hold before any new code executes. The full unit suite confirms the serial path is untouched.
