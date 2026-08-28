# Implementation Report — An End-to-End Mock Roll (#2567)

## Issue Reference
[#2567: the factory has no test of the factory -- an end-to-end mock-drafter roll in CI](https://github.com/martymcenroe/AssemblyZero/issues/2567)

## Files Changed
- `assemblyzero/core/scripted_provider.py` (new): a drafter and reviewer made of fixtures, routed by what the caller asked.
- `assemblyzero/core/llm_provider.py`: `get_provider` learns the `scripted:` spec.
- `tests/unit/test_mock_roll.py` (new): 20 tests — the transport, and two defect classes replayed through the real machinery.

## What Is Mocked, Exhaustively

The LLM transport, and `gh issue view`. That is the whole list, and a test pins it: `test_gh_issue_view_is_the_only_non_llm_stub` asserts the stub intercepts the `gh` call and that a real `git` subprocess still runs underneath the same patch.

The graph, routing, janitor, enforcement, gates, loaders, file writes and halt path all run for real against a throwaway repo with a **real bare origin** under `tmp_path` — preservation is only preservation when the ref is pushed, so the janitor needs somewhere to push.

## Design Decisions

1. **A new provider rather than extending `MockProvider`.** `MockProvider` cycles a list and ignores the prompt, which is right for a unit test of one node and wrong for a roll: the drafter, reviewer and analyst are different callers, and a roll's shape is exactly which of them is asked what, in what order. Routing on the call is the feature.

2. **An unmatched call fails loudly.** A default response would let a roll go green while exercising a path the fixture set never covered. The error names the call number, the system and content heads, and every rule tried — so building the graph roll (#2596) is incremental: run it, read what went unmatched, add that fixture.

3. **Ambiguity is an error, not a precedence question.** *Found by my own test failing.* `system_pattern="draft"` also matches "You review the draft"; first-match-wins routed the reviewer's call to the drafter. That is silent misrouting — a green roll that exercised the wrong path — which is precisely the class this harness exists to catch. Two rules for different stages matching one call now fail with both stage names.

4. **`on_call` numbers the calls to a STAGE, not to a rule object.** *Also found by a test failing.* The first implementation counted per rule index, so each rule's counter lagged by however many earlier rules had declined, silently breaking every scripted sequence past the second. The counter belongs to the stage, because several same-stage rules are one sequence.

5. **Running past the script is a finding.** A loop that will not converge asks for more rounds than the fixtures script. The provider says "round N of stage X, script covers rounds [...]" rather than recycling round 1 — which would make a non-converging loop look like a converging one.

6. **One instance per roll.** `get_provider("scripted:...")` returns the active instance to every caller. Fresh instances would reset the counters that `on_call` and the recorded path depend on.

7. **`tests/unit/`, not `tests/e2e/`.** The marker taxonomy is about external dependencies, not scope: `e2e` means "requiring sandbox repo" and is deselected by `addopts`, and CI runs `tests/unit/` plus `tests/integration/ -m integration`. This suite needs no sandbox, no network and no LLM, exactly like `test_leavings_janitor.py`, which builds the same throwaway repo and lives in unit. Filing it as e2e would put it in the one directory CI never runs.

## The Acceptance: Two Defect Classes Re-Broken

**Class 3 — the demanded change is never refusable** (`TestDemandedChangeSurvivesEnforcement`). The 11:17 shape: a dashed `lines 5-8` citation unlocks the fence span it names; a bare `line 1` quoted out of a `SyntaxError` does **not** become a draft address; a demanded addition is recognised with no line to cite. A fourth test is the control — a complaint that is deliberately unaddressable — which proves the other three measure something.

**Class 5 — the input/litter distinction** (`TestSweepDoesNotClearTheRollingInput`). Run against the real janitor and a real repo: the rolling issue's LLD appears in neither sweep list; another issue's file at the same path is still leavings (a blanket exemption would fix the deletion and re-create #2144); and the re-broken shape — an unprotected launch — is executed for real, clearing the input and leaving it preserved on a pushed ref.

Both green on main, as the acceptance requires.

## Known Limitations

The compiled graphs are not yet driven end to end — filed as #2596 with the fixture, lineage and halt-path assertions it needs. #2567's stated acceptance is the two defect-class reproductions, which are delivered; the graph roll is the next increment and rides on this harness.
