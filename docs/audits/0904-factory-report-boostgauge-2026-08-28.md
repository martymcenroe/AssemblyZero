# Factory report — C:\Users\mcwiz\Projects\boostgauge

Window: since 2026-08-27 00:00:00. Generated 2026-08-28 00:32:12.

## Stores read

| store | present | records in window |
|---|---|---|
| halt_bundles | yes | 0 |
| heals | yes | 9 |
| preserved | yes | 6 |
| prompt_failures | yes | 5 |
| run_logs | yes | 4 |

## Gates: which fire, which never do

Failures per stage:check:
  lld:mechanical        3
  spec:reviewer-revise  2

Zero-fire gates (2 of 4 declared) — each is either perfect or dead, and this report does not distinguish those:
  lld:requirements-conflict
  lld:test-plan

Top fingerprints by volume:
     1  lld:mechanical:critical-source-decision-table-row-s3-s-qualifiers-were-lost-in-derivation-2-56-px-appear-s-nowhere-in-the-lld-carry-the-qualifying-clause-sampling-window-offset-threshold-into-the-derived-requirement-and-test-rows-verbatim-the-qualifier-is-the-ruling-not-commentary-2563
     1  lld:mechanical:critical-source-decision-table-row-s5-s-qualifiers-were-lost-in-derivation-0-665-r-0-065-r-appear-s-nowhere-in-the-lld-carry-the-qualifying-clause-sampling-window-offset-threshold-into-the-derived-requirement-and-test-rows-verbatim-the-qualifier-is-the-ruling-not-commentary-2563
     1  lld:mechanical:critical-source-decision-table-row-s6-s-qualifiers-were-lost-in-derivation-0-775-r-0-065-r-0-27-r-appear-s-nowhere-in-the-lld-carry-the-qualifying-clause-sampling-window-offset-threshold-into-the-derived-requirement-and-test-rows-verbatim-the-qualifier-is-the-ruling-not-commentary-2563

## Loops: revision rounds, caps, edit-script health

Edit scripts: 24 applied, 6 fell back to full revision (20.0% of 30 attempts).

Fallback reasons by volume:
     5  edits produced no change
     1  block 3: SEARCH text ambiguous (2 occurrences): 'def test_req_8_chrome_housing():\n    # Chrome housing gradients (REQ-8

Highest review round reached, per issue and loop:
  #331:spec  9

Cap grants (1):
  run-issue331-111729: 3 revision(s) spent, but criteria_have_tests has never been shown to the drafter. Granting one revision for it (#2304).

## Pinning enforcement

52 refusal(s), 45 regression-class event(s) across 4 run log(s).

## Janitor and preservation activity

Heals by category:
  janitor            3
  restore-reconcile  3
  base-replace       1
  reset              1
  reset-refused      1

Outcomes: healed 8, refused 1

Targets healed more than once (a spike here is the signal — three sweeps of one file in one day should be visible, not discovered by forensics):
     3  janitor:docs/lld/active/LLD-331.md
     3  restore-reconcile:docs/lld/active/LLD-331.md

Preservations: 6 in window (leavings 6).

## Halts (from #2574 evidence bundles)

No halt-evidence bundles found. #2574 landed 2026-08-28, so halts before it left no bundle; their count is not zero, it is unrecorded.

## Shortlist (computed)

- Top check by failure volume: lld:mechanical (3)
- Top check by failure volume: spec:reviewer-revise (2)
- Edit-script fallback rate: 6/30 (20.0%)
- Zero-fire gate (perfect or dead): lld:requirements-conflict
- Zero-fire gate (perfect or dead): lld:test-plan
- Most-repeated heal target: janitor:docs/lld/active/LLD-331.md (3)


---

## Reconciliation against the hand-derived record (#2575 acceptance)

The acceptance names three facts derived by hand during the 2026-08-27
campaign and requires this report's counts to reconcile with them.
**None of the three reconciles**, and each discrepancy is a finding about
the record or the stores rather than a defect in this tool. Every number
below was counted, not estimated; the counting script is preserved at
`data/scratch-2026-08-28-factory-sequence/reconcile.py`.

### 1. "six pinning refusals in run-issue331-111729" — right number, wrong run

| run log | `[PINNING] refused:` | `REGRESSION CLASS:` |
|---|---|---|
| run-issue331-092913 | **6** | 6 |
| run-issue331-111729 | **43** | 36 |
| run-issue331-170916 | 3 | 3 |
| the other 13 `#331` logs | 0 | 0 |

Six is a real count and it belongs to `run-issue331-092913` — the 09:29
lineage the campaign replayed #2555 against. `run-issue331-111729` is the
11:17 death, and it carries 43. The hand-derived note attached the right
number to the wrong run id. Filed as a record correction.

### 2. "four leavings sweeps" — the stores say six and three, and neither is four

Six leavings preservations are recorded on 2026-08-27, at 09:29, 10:08,
11:17, 12:04, 13:01 and 13:25, each `1 file(s)`. Separately the healing
ledger records **three** `janitor` heals of `docs/lld/active/LLD-331.md`.
Both are correct and they count different things: a sweep preserves
whatever it cleared, and only three of the six sweeps cleared the LLD.
Four matches neither, and is most likely a count taken mid-campaign,
before the 13:01 and 13:25 sweeps existed. Filed.

### 3. "three spec-stage cap halts" — unverifiable from any store

This report finds **zero** halt-evidence bundles for boostgauge in the
window and one `[CAP]` grant line. The claim cannot be checked, for two
separate reasons, both filed:

- **#2574 landed 2026-08-28**, so every halt of the 2026-08-27 campaign
  predates the bundle and left none. The report says this in place of
  printing zero, because the count is unrecorded rather than nil.
- **The state snapshot is one file per (workflow, issue), overwritten.**
  `implementation_spec-331.json` holds only the LAST halt — 11 pinning
  events, `review_iteration` 9 against `max_iterations` 3, error message
  `Iteration cap: 3 review rounds ended REVISE`. The two earlier spec-stage
  cap halts of that day are not recoverable from it at any effort.

### 4. Incidental finding: an unattributable halt bundle

`~/.assemblyzero/workflow_state/halt-evidence.json` carries
`issue: 999`, `stage: N2_generate` and `audit_dir: ""`. With no audit dir
it cannot be attributed to any repository, so this report's repo-scoping
drops it rather than crediting boostgauge with another repo's halt. A real
halt that writes an empty `audit_dir` therefore goes uncounted. Filed.

### What reconciles

Everything the stores are actually authoritative for. The 52 pinning
refusals reported across the window are exactly 6 + 43 + 3 from the three
`#331` logs whose mtime falls on 2026-08-27; the other twelve `#331` logs
were last written on 08-16, 08-25 and 08-26 and are correctly outside the
window. The 20.0% edit-script fallback rate is 6 of 30 counted attempts.
The three-sweep spike on `LLD-331.md` — the recurrence #2551 was filed for
— surfaces at the top of the recurring-targets table without a forensic
dig, which is the outcome this report was built for.
