# Factory report — C:\Users\mcwiz\Projects\boostgauge

Window: since (all time). Generated 2026-09-03 00:11:13.

## Convergence: how far the furthest run got, per day

Days are by run-log mtime. `furthest` is the last stage with a verdict; for impl, the highest node marker printed.

| day | launches | furthest | trend | run | ended by |
|---|---|---|---|---|---|
| 2026-07-31 | 30 | cleanup | first | run-issue7-131616 | passed |
| 2026-08-01 | 38 | cleanup | same | run-issue7-080837 | passed |
| 2026-08-09 | 9 | lld | down | run-issue7-233727 | lld.requirements_conflict |
| 2026-08-10 | 24 | cleanup | up | run-issue4-023810 | passed |
| 2026-08-11 | 6 | spec | down | run-issue1-014959 | unrecorded |
| 2026-08-12 | 2 | spec | same | run-issue7-082047 | unrecorded |
| 2026-08-13 | 6 | pr | up | run-issue7-231606 | infra.pr_creation |
| 2026-08-14 | 4 | cleanup | up | run-issue7-011504 | passed |
| 2026-08-15 | 5 | cleanup | same | run-issue41-014846 | passed |
| 2026-08-16 | 1 | spec | down | run-issue331-153544 | killed |
| 2026-08-25 | 6 | spec | same | run-issue331-233939 | spec.review_cap |
| 2026-08-26 | 5 | impl:N5 | up | run-issue331-235455 | impl.stagnation.coverage |
| 2026-08-27 | 4 | spec | down | run-issue331-170916 | spec.review_cap |
| 2026-08-28 | 4 | impl:N5 | up | run-issue331-201554 | impl.stagnation.coverage |
| 2026-08-29 | 5 | cleanup | up | run-issue331-101529 | passed |
| 2026-08-30 | 19 | cleanup | same | run-issue384-102849 | passed |
| 2026-09-01 | 7 | spec | down | run-issue41-184913 | spec.edit_script_rejected |
| 2026-09-02 | 5 | impl:N5 | up | run-issue4-172600 | impl.stagnation.coverage |

Furthest run in window: run-issue7-131616 reached cleanup (passed).

## Outcomes

180 run(s): passed 26, failed 135 (lld 49, impl 45, spec 40, pr 1), killed 19 (no terminal banner: the process died mid-call).

## Cause of death (failed runs, by the Error line under the banner)

    29  lld.requirements_conflict      issue_body
    15  lld.mechanical_validation      model_output
    15  unrecorded                     -
    12  spec.completeness_cap          budget
    11  impl.stagnation.coverage       model_output
    11  impl.stagnation.test_count     model_output
     7  spec.review_cap                budget
     6  impl.file_generation_failed    model_output
     5  impl.deterministic_failure     model_output
     5  spec.requirements_conflict     issue_body
     3  impl.stagnation.full_suite     model_output
     3  spec.edit_script_rejected      model_output
     2  impl.green_phase_stopped       infrastructure
     2  infra.worktree                 infrastructure
     2  lld.test_plan_validation       model_output
     1  impl.branch_exists             infrastructure
     1  impl.red_phase_failed          model_output
     1  impl.scenario_ratio_guard      model_output
     1  impl.stagnation.test_identity  model_output
     1  infra.lld_stage_exception      infrastructure
     1  infra.missing_spec             infrastructure
     1  infra.pr_creation              infrastructure

By what the gate judges: model_output 59, issue_body 34, budget 19, unrecorded 15, infrastructure 8

Killed runs end on (digits normalized to N):
     5  Calling Claude... (Ns)
     5  Drafter: gemini:N.N-pro
     2  Reviewer: gemini:N.N-pro
     1  During task with name 'run_stage' and id 'NbeN-eN-NaNc-NaN-NbNeNbeN'
     1  [EDIT-SCRIPT] attempt N/N: every edit touched locked content and was refused by pinning (N refusal(s)) -- re-prompting w
     1  [NNc] Requirements-ambiguity analysis (#N)...
     1  [ORCHESTRATOR] ERROR: Model 'claude-opus-N-N' is not a valid Gemini model. Expected format: gemini-*
     1  [STAGE] lld running Ns (nominal ~Ns) - SLOW, Nx nominal
     1  [STAGE] spec running Ns (nominal ~Ns)
     1  [spec] implementation spec committed to the LLD PR (issue #N)

## Stores read

| store | present | records in window |
|---|---|---|
| halt_bundles | yes | 8 |
| heals | yes | 84 |
| preserved | yes | 27 |
| prompt_failures | yes | 154 |
| run_logs | yes | 180 |

## Gates: which fire, which never do

Failures per stage:check:
  lld:requirements-conflict  77
  lld:mechanical             52
  spec:reviewer-revise       16
  lld:test-plan              9

Zero-fire gates: none — every declared gate fired.

Top fingerprints by volume:
    10  lld:mechanical:critical-section-11-missing-from-lld
     8  lld:mechanical:critical-section-12-missing-from-lld
     6  lld:mechanical:critical-section-2-1-missing-from-lld

## Loops: revision rounds, caps, edit-script health

Edit scripts: 293 applied, 16 fell back to full revision (5.2% of 309 attempts).

Fallback reasons by volume:
     5  edits produced no change
     3  All credentials failed via agy (Antigravity CLI):
     2  block 3: SEARCH text not found (model did not copy verbatim): 'SUPPORTED_SKINS = {\n    "stingray": render_stingray,\n}\
     1  block 1: SEARCH text not found (model did not copy verbatim): 'from __future__ annotations\n\nfrom typing import Any'
     1  block 2: SEARCH text not found (model did not copy verbatim): '**Change 2:** Add `_draw_telltales()` and `_draw_legend()

Highest review round reached, per issue and loop:
  #331:spec  9
  #4:spec    9
  #379:spec  8
  #1:spec    7
  #384:spec  7
  #41:spec   3

Cap grants (7):
  run-issue331-123221: 3 revision(s) spent, but criteria_have_tests has never been shown to the drafter. Granting one revision for it (#2304).
  run-issue331-123221: 3 revision(s) spent, but change_instructions_specific has never been shown to the drafter. Granting one revision for it (#2304).
  run-issue331-150920: 3 revision(s) spent, but change_instructions_specific has never been shown to the drafter. Granting one revision for it (#2304).
  run-issue331-200815: 3 revision(s) spent, but change_instructions_specific has never been shown to the drafter. Granting one revision for it (#2304).
  run-issue331-111729: 3 revision(s) spent, but criteria_have_tests has never been shown to the drafter. Granting one revision for it (#2304).
  run-issue379-010841: 3 revision(s) spent, but api_symbols_exist has never been shown to the drafter. Granting one revision for it (#2304).
  run-issue384-063258: 3 revision(s) spent, but criteria_have_tests has never been shown to the drafter. Granting one revision for it (#2304).

## Pinning enforcement

145 refusal(s), 118 regression-class event(s) across 180 run log(s).

## Janitor and preservation activity

Heals by category:
  restore-reconcile  35
  reset              24
  janitor            9
  reset-refused      7
  sweep              5
  base-replace       2
  base-settled       2

Outcomes: healed 76, partial 1, refused 7

Targets healed more than once (a spike here is the signal — three sweeps of one file in one day should be visible, not discovered by forensics):
    12  restore-reconcile:docs/lld/active/LLD-331.md
    11  reset:#1
    11  restore-reconcile:docs/lld/active/LLD-001.md
     6  restore-reconcile:docs/lld/active/LLD-007.md
     5  reset:#331
     4  janitor:docs/lld/active/LLD-001.md
     4  janitor:docs/lld/active/LLD-331.md
     4  reset-refused:#331
     4  reset:#384
     4  restore-reconcile:docs/lld/drafts/spec-0007-implementation-readiness.md
     3  reset:#7
     2  base-settled:hardening-run-19
     2  sweep:384

Preservations: 27 in window (leavings 25, sweep 2).

## Halts (from #2574 evidence bundles)

8 bundle(s):
     3  implementation_spec:N5_review_iter3
     2  requirements:requirements_unknown
     1  implementation_spec:N5_review_iter5
     1  implementation_spec:N5_review_iter7
     1  requirements:N1_draft_iter3

## Shortlist (computed)

- Furthest run in window: run-issue7-131616 reached cleanup
- Top cause of death: lld.requirements_conflict (29)
- Top check by failure volume: lld:requirements-conflict (77)
- Top check by failure volume: lld:mechanical (52)
- Top check by failure volume: spec:reviewer-revise (16)
- Edit-script fallback rate: 16/309 (5.2%)
- Most-repeated heal target: restore-reconcile:docs/lld/active/LLD-331.md (12)

