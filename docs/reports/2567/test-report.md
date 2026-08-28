# Test Report — An End-to-End Mock Roll (#2567)

## Issue Reference
[#2567: the factory has no test of the factory -- an end-to-end mock-drafter roll in CI](https://github.com/martymcenroe/AssemblyZero/issues/2567)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_mock_roll.py` (new) | **20 passed in 2.3s** |
| with `tests/unit/test_fail_open_audit.py` | 72 passed — no new fail-open sites |
| `tests/unit` (full) | see below |
| `ruff` on `scripted_provider.py`, `test_mock_roll.py` | clean |
| `ruff` on `llm_provider.py` | 16 errors before my change, 16 after — none introduced |

Wall clock is **2.3 seconds**, against the issue's two-minute budget. No network, no LLM.

## Two Bugs Found By The Tests, In The Code Under Test

Both were in `ScriptedProvider` itself and both were caught by assertions failing, not by reading:

1. **Overlapping patterns misrouted silently.** `system_pattern="draft"` matches "You review the draft", so first-match-wins sent the reviewer's call to the drafter's fixture. A roll would have gone green having exercised the wrong path — the exact failure mode the harness exists to detect. Now an error naming both stages.
2. **`on_call` counters lagged per rule.** Counting per rule index meant a rule's counter only advanced when earlier rules declined, so any scripted sequence past round two silently fell through to `UNMATCHED`. The counter now belongs to the stage.

Both fixes have their own regression tests (`test_overlapping_stage_patterns_fail_rather_than_guess`, `test_running_past_the_script_says_so`).

## What Is Actually Pinned

**The transport (9 tests).** Routing on the system prompt; an unmatched call failing loudly rather than defaulting; ambiguity refused; `on_call` sequencing; a rule that fails the call (the halt-path primitive); one instance per roll from `get_provider`; `scripted:` refusing with no active provider; a missing fixture raising at the fixture rather than three stages later.

**Defect class 3 — the demanded change is never refusable (4 tests).** The dashed citation unlocks its span. The quoted `SyntaxError` position does not become an address — the exact string from the 2026-08-27 deadlock. A demanded addition is recognised with no line to cite. **And a control**: a deliberately unaddressable complaint, asserted to stay unaddressable, so the three positive tests are measuring something rather than passing on a vocabulary that matches everything.

**Defect class 5 — the input/litter distinction (4 tests).** Against the real janitor and a real repo with a real bare origin: the rolling issue's LLD is in neither sweep list; another issue's file at the same path is still leavings; the predicate is issue-scoped; and the re-broken shape runs for real — an unprotected launch preserves and clears the input, with the content verified on a pushed ref (`unpushed is unpreserved`).

The second of those is as load-bearing as the first: a blanket exemption would satisfy the "input survives" test and re-create #2144.

**The roll harness (3 tests).** The recorded path (`stages_called`), a halt-path failure carrying its message with `answered is False`, and the stub-surface test that pins `gh issue view` as the only non-LLM stub by asserting a real `git` call still succeeds under the same patch.

## Real-Repo Verification

`TestSweepDoesNotClearTheRollingInput::test_an_unprotected_launch_would_clear_it` is not a fixture simulation. It creates a git repo with a bare origin, drops an untracked LLD, runs the real `classify_dirt` and `preserve_and_clear`, asserts the file is gone from disk, then reads the content back out of the graveyard branch and confirms that branch exists on origin.

## Regression Risk

`scripted_provider.py` is new and imported by nothing in production paths. The change to `llm_provider.py` adds one `elif` branch reachable only via a `scripted:` spec, which no production config uses; the error message for an unknown provider gained `scripted` to its supported list. The full-suite run confirms nothing else moved.
