# Test Report — The Golden-Disaster Corpus (#2572)

## Issue Reference
[#2572: a golden-disaster eval corpus -- preserved kill lineage becomes the gate for prompt and model changes](https://github.com/martymcenroe/AssemblyZero/issues/2572)

## Suites Run

| suite | result |
|---|---|
| `tools/golden_disasters.py --tier deterministic` (the acceptance command) | **3 survived, 0 regressed, 0 could not run** |
| `tests/unit/test_golden_disasters.py` (new) | **20 passed in 0.5s** |
| with `test_fail_open_audit.py` and `test_mock_roll.py` | 92 passed |
| `tests/unit` (full) | see below |
| `ruff` on all three new Python files | clean |

## The Harder Property: The Cases Can Actually Fail

A corpus that cannot fail passes forever and protects nothing. Three tests defeat the guards deliberately and assert the corpus notices:

1. **`named_line_ranges` and `named_tokens` monkeypatched to return nothing** — the fence case reports `REGRESSION (#2555)`. This is the #2555 repair removed; the case sees the deadlock return.
2. **A test definition removed from the eliding revision**, staged into a `tmp_path` corpus root — the case reports `REGRESSION (#2559)`. This is the exact shape the conservation gate exists to refuse.
3. **A missing fixture** — the case sets `errored=True` rather than `passed=False`, so a broken corpus never masquerades as a regressed guard.

Without these three, the other seventeen tests would be compatible with a corpus of tautologies.

## What Else Is Pinned

**Fixture integrity (2).** The digest changes when a fixture's bytes change, and is stable for identical content. The corpus's value rests on the fixture being the artifact that came out of the kill.

**Committed-fixture discipline (6, parameterised).** Every case declares artifacts, every declared artifact exists and is non-empty, and every case records provenance and a `guards` field naming an issue. This is the guard against the decay that broke `replay_331.py`.

**Registry completeness (3).** Every registered case has a runner (a case without one would silently never execute); no case declares an unknown tier (a typo would drop it from every tier and every report, invisibly); no artifact path is absolute (the exact failure that decayed the scratch replays).

**Reporting (2).** `[ok]` / `[REGRESSED]` / `[ERROR]` render distinctly with a correct three-way tally; an empty tier says so.

**CLI (3).** The deterministic tier exits 0 on main. The empty live tier exits **1** with "not a pass" — a tier that measured nothing is not green. `--list` prints provenance and digests.

## Real-Artifact Verification

These are not synthetic fixtures. The acceptance command runs the real `check_api_symbols_exist` against the real preserved draft from `run-issue331-111729`'s lineage and reports what it actually emitted:

```
[ok] fence-deadlock
    the fence complaint addresses draft lines 89-92 via named_line_ranges
[ok] eliding-rewrite
    conservation holds across the eliding pair: 13 test definition(s)
    survive 17 [UNCHANGED] placeholder(s)
[ok] hallucinated-symbol
    the hallucinated symbol is named at draft time
```

## Regression Risk

Additive. The corpus module is imported only by its tool and its tests; no production path touches it. Fixtures are committed data. The `docs/audits/` entry is documentation.
