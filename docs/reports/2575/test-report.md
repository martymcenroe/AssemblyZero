# Test Report — A Factory Telemetry Rollup (#2575)

## Issue Reference
[#2575: a factory telemetry rollup -- counts decide what the next kill currently decides](https://github.com/martymcenroe/AssemblyZero/issues/2575)

## Suites Run

| suite | result |
|---|---|
| `tests/unit/test_factory_report.py` | **31 passed** |
| `tests/unit/test_fail_open_audit.py` (the #2475 gate) | **passed** after six rulings |
| `tests/unit/test_healing_ledger.py`, `test_prompt_telemetry.py` (adjacent stores) | **passed** |
| `tests/unit` (full) | **8830 passed**, 21 skipped, 5 xfailed |
| `ruff check` on all three new files | clean |

The full-suite run that first exposed the fail-open gate was re-run after the rulings landed: a suite verdict binds only to the tree it read, and the tree changed.

## What Is Actually Pinned

**The registry cannot drift (2 tests).** `test_every_recording_site_is_declared` greps `assemblyzero/workflows/` for `record_failure(s)` call sites and fails when one is not in `DECLARED_CHECKS`. `test_no_declared_check_is_a_phantom` fails in the opposite direction — a declared pair with no recording site would report as permanently zero-fire, which reads as a perfect gate that does not exist. Both directions matter because the registry is the denominator for the zero-fire claim.

**Stray bytes do not suppress events (1 test).** `test_stray_bytes_do_not_suppress_events` writes a log containing `\x97` and `\xff\xfe` and asserts all three pinning events still count. This is the 2026-08-27 near-miss pinned: grep's binary fallback dropped real lines while printing others, which is a confident wrong answer rather than a visible failure.

**Repo scoping (2 tests).** `test_a_shared_root_is_scoped_to_the_target_repo` builds a shared state directory holding three bundles — one whose `audit_dir` points into the target, one pointing at another repo, one with no `audit_dir` — and asserts only the first is counted. `test_a_bundle_inside_the_repo_needs_no_audit_dir` asserts a bundle found inside the repo needs no containment proof. Together these are the guard against crediting one repo with another's halts.

**The window refuses to widen silently (1 test).** `test_unparseable_raises_rather_than_silently_widening` asserts `parse_since("last tuesday")` raises rather than returning `None`, because `None` means "all time" and would put a wrong denominator under the whole report.

**Absence is not zero (2 tests).** An empty repo renders `| NO |` for each store and leads the shortlist with "an absence of data, not an absence of events".

**Determinism (1 test).** Identical input renders byte-identically, so two reports can be diffed rather than re-read.

**Counting (7 tests).** Per-marker counts in one log, per-store counts in a seeded repo, the edit-script fallback split, pinning summed across runs, recurring heal targets surfacing while a single heal does not, preservations by source, and window exclusion.

## Real-Data Verification

Beyond fixtures, the tool was run against the live boostgauge stores for the campaign window and its output reconciled by hand against the three facts in the acceptance. Full working in `docs/audits/0904-factory-report-boostgauge-2026-08-28.md`; the counting script is preserved at `data/scratch-2026-08-28-factory-sequence/reconcile.py`.

Result: **none of the three hand-derived facts reconciles**, and each is a finding about the record or the stores rather than a defect in the tool — filed as #2585, #2586, #2587, with #2588 falling out incidentally. What does reconcile is everything the stores are authoritative for: the 52 reported pinning refusals are exactly 6 + 43 + 3 from the three `#331` logs dated 2026-08-27, and the 20.0% edit-script fallback rate is 6 of 30 counted attempts.

## Regression Risk

The module is additive and read-only; nothing existing imports it. The only shared surface touched is the fail-open baseline, which the gate itself verifies.
