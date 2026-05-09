# 0852 - Deferred-Scope Audit — New Repo Creation Subset

**Auditor:** Claude Opus 4.7 (1M context) via `tools/audit_deferred_scope.py`
**Date:** 2026-05-07
**Corpus:** all closed AssemblyZero issues (snapshot closed-issues-snapshot-2026-05-07.json)
**Method:** regex first-pass + LLM (`claude --print`) classification per candidate
**Issue:** [#930](https://github.com/martymcenroe/AssemblyZero/issues/930)

## Summary

| Category | Meaning | Count |
|---|---|---|
| **CAUGHT** | follow-up issue was filed and is closed | 11 |
| **ADDRESSED_OPEN** | follow-up filed, still open | 7 |
| **ORPHANED** | still relevant; no follow-up filed | 5 |
| **OBSOLETE** | no longer applies (tech/process changed) | 0 |
| **UNCLASSIFIED** | still-relevant judgment unclear | 0 |
| **ERROR** | LLM call failed; needs human review | 0 |

## ORPHANED — 5 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #931 | fix: new_repo_setup.py generates misdirecting CLAUDE.md — point to root, surface PR discipline | GEMINI.md template generation in new_repo_setup.py deferred as potential follow-up | — | yes | GEMINI.md template work for new_repo_setup.py was suggested as follow-up but no cross-referenced issue (#933/#935/#936) appears to address it. |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | Updating ADR-0216 to reflect lessons learned during _pat_session hardening | — | yes | Soft deferral ('could be a follow-up if desired'); ADR-0216 update not filed as separate issue, docstring captures MUSTs but ADR may still drift |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | Classic PAT and gpg passphrase rotation TODO tracked in a separate issue, not this docs+code hardening PR. | — | yes | Rotation of classic PAT/gpg passphrase remains an operational requirement; no cross-reference confirms it was filed or completed. |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | Rotation TODO for classic PAT and gpg passphrase tracked in a separate issue | — | yes | Rotation of classic PAT/gpg passphrase remains a live operational concern; no cross-reference identifies the tracking issue |
| #1036 | robustness: port _request_with_retry into deploy_cerberus_secrets.py (follow-up to #1022) | Shared-module extraction of retry logic across new_repo_setup.py, deploy_cerberus_secrets.py, and fleet_set_delete_branch_on_merge.py deferred until more callers migrate. | — | yes | Conditional deferral pending additional caller migrations; extraction not yet justified but remains a valid future refactor. |

## ADDRESSED_OPEN — 7 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #886 | fix: reconcile pr-sentinel dual-implementation and branch protection context spaghetti | strict=true branch protection outliers deferred to a separate follow-up issue, orthogonal to pr-sentinel dual-implementation reconciliation | #905 | yes | strict=true branch protection context handling concerns fleet-wide protection setup; no clear evidence it was filed or resolved |
| #924 | docs: fix obsolete content in new-repo runbook chain (0901, 0925, 0926, 0927) | Row 7 deferred updating runbooks 0927/0901 that list pr-sentinel.yml as automatic artifact until #886 Phase 4 retires the Actions workflow. | #886 (open) | yes | Depends on #886 Phase 4 completing; until pr-sentinel.yml Actions workflow is retired, runbooks 0927/0901 remain inaccurate for new repos. |
| #924 | docs: fix obsolete content in new-repo runbook chain (0901, 0925, 0926, 0927) | Item 7 (pr-sentinel.yml as automatic artifact) deferred to #886 Phase 4 to avoid conflicting state with Phase 3 | #886 | ? | Deferral tied to #886 Phase 4 sequencing; relevance depends on whether that phase has landed |
| #924 | docs: fix obsolete content in new-repo runbook chain (0901, 0925, 0926, 0927) | pr-sentinel.yml Actions artifact references in 0927/0901 to be removed after #886 Phase 4 retires Actions workflow | 886 (open) | ? | Deferred to #886 Phase 4; status of Actions workflow retirement unknown without checking #886 |
| #924 | docs: fix obsolete content in new-repo runbook chain (0901, 0925, 0926, 0927) | Item 7 of runbook fixes deferred to #886 Phase 4 | #886 | ? | Deferred to #886 Phase 4; status of that follow-up not provided in cross-references |
| #964 | refactor: migrate privileged paths in new_repo_setup.py to in-process PAT pattern | Phase B: eliminate env-scoped GH_TOKEN for initial push via Contents API in new_repo_setup.py | #1000 (open) | yes | Phase B work tracked in #1000 concerns new_repo_setup.py initial push path; not yet superseded. |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | YubiKey migration of gpg key and executing the PAT rotation itself deferred from this hardening PR | #1016 (open) | yes | Post-ADR-0216 hardening of classic PAT flow remains pending; YubiKey migration tracked at #1016 and rotation operational TODO still applicable |

## CAUGHT — 11 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #510 | feat: PR issue-reference enforcer — GitHub App on Cloudflare Workers | Manual GitHub App creation steps: create pr-sentinel App, convert private key to PKCS#8, deploy CF Worker secrets | #512 (closed) | no | pr-sentinel GitHub App was created and deployed; Cerberus/sentinel infrastructure is operational fleet-wide per current CLAUDE.md |
| #886 | fix: reconcile pr-sentinel dual-implementation and branch protection context spaghetti | Phase 2: canonicalize branch protection context to pr-sentinel/issue-reference; add protection to 3 unprotected repos | #924 (closed) | ? | Branch protection canonicalization is new-repo-related; cross-ref #924 likely tracks follow-up but current status needs verification |
| #959 | feat: in-process classic PAT decryption — never expose secret via env or argv | Migrating 5+ existing classic-PAT tools to the _pat_session.py in-process pattern; each gets its own follow-up issue filed alongside. | #960 (closed) | yes | Migration of classic-PAT tools to _pat_session.py is ongoing; concerns the PAT abstraction used by new_repo_setup and Cerberus deploy flows. |
| #960 | chore: migrate AssemblyZero + Sextant to fleet-standard pr-sentinel / issue-reference branch protection (#886 Phase 2) | Migrating 5 existing classic-PAT tools to new in-process pattern, and fleet-wide retirement of pr-sentinel.yml from ~48 other repos | #972 (closed) | yes | Classic-PAT migration and pr-sentinel fleet retirement remain ongoing concerns tied to PAT session pattern and branch protection standardization |
| #960 | chore: migrate AssemblyZero + Sextant to fleet-standard pr-sentinel / issue-reference branch protection (#886 Phase 2) | Migrate 5 existing classic-PAT tools to new in-process pattern; retire redundant pr-sentinel.yml from ~48 fleet repos (Phase 3-4). | #972 (closed) | yes | Classic-PAT migration and fleet pr-sentinel.yml retirement are ongoing concerns tied to PAT pattern and branch protection setup. |
| #960 | chore: migrate AssemblyZero + Sextant to fleet-standard pr-sentinel / issue-reference branch protection (#886 Phase 2) | Per-repo follow-up PRs to delete redundant .github/workflows/pr-sentinel.yml after migration to fleet-standard branch protection | #971 (closed) | no | Fleet pr-sentinel.yml deletion was tracked and executed via follow-up issues (#968/#971/#972/#975); migration completed. |
| #964 | refactor: migrate privileged paths in new_repo_setup.py to in-process PAT pattern | Migrate privileged paths in new_repo_setup.py from env-scoped GH_TOKEN to in-process classic PAT pattern | #1004 (closed) | no | Recent commit 4c0731f ported _request_with_retry into new_repo_setup.py privileged calls (Closes #1022), indicating migration work has progressed/landed |
| #1000 | refactor: new_repo_setup.py — eliminate env-scoped GH_TOKEN for initial push by deploying workflows via Contents API | Phase B follow-up to Phase A refactor of new_repo_setup.py eliminating env-scoped GH_TOKEN via Contents API workflow deployment | #1004 (closed) | ? | Phase A closed with follow-up filed per Closing Discipline; cross-referenced issues (#1004, #1022, #1033) appear to have continued the new_repo_setup hardening work |
| #1000 | refactor: new_repo_setup.py — eliminate env-scoped GH_TOKEN for initial push by deploying workflows via Contents API | Refactor new_repo_setup.py to deploy workflows via Contents API, eliminating env-scoped GH_TOKEN for initial push (Phase B of #964). | #1004 (closed) | yes | Concerns tools/new_repo_setup.py PAT exposure; #1004 likely addresses Phase B follow-up but verify current state of env-scoped token usage. |
| #1000 | refactor: new_repo_setup.py — eliminate env-scoped GH_TOKEN for initial push by deploying workflows via Contents API | Migrate Cerberus secret-set (--cerberus-pem) from gh auth to in-process classic PAT session | #1027 (closed) | ? | Cerberus PEM deploy still routes through gh auth; #1027 likely addresses related Cerberus/PAT migration but verification needed |
| #1022 | robustness: port _request_with_retry into new_repo_setup.py privileged calls | Porting _request_with_retry helper into other AZ tools (deploy_cerberus_secrets.py, fleet_delete_pr_sentinel.py, merge_sentinel_permissions_prs.py). | #1036 (closed) | yes | Other AZ tools still make unretried GitHub API calls; #1036 addressed deploy_cerberus_secrets but fleet/merge tools remain. |

## Audit Record

| Date | Auditor | Findings | Issues Created |
|------|---------|----------|----------------|
| 2026-05-07 | Claude Opus 4.7 | ADDRESSED_OPEN:7 CAUGHT:11 ORPHANED:5 | (filed manually after review) |

## Notes

- ORPHANED items in this report are candidates for the user to file as new issues.
- OBSOLETE items should be acknowledged (e.g., a comment on the original issue noting the deferred work is moot).
- The closing-discipline rule in root `CLAUDE.md` was added 2026-04-21 (issue #998 / PR #999) to prevent future ORPHANED items.
