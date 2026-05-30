# 0852 - Deferred-Scope Audit — New Repo Creation Subset

**Auditor:** Claude Opus 4.7 (1M context) via `tools/audit_deferred_scope.py`
**Date:** 2026-05-22
**Corpus:** all closed AssemblyZero issues (snapshot closed-issues-snapshot-2026-05-22.json)
**Method:** regex first-pass + LLM (`claude --print`) classification per candidate
**Issue:** [#930](https://github.com/martymcenroe/AssemblyZero/issues/930)

## Summary

| Category | Meaning | Count |
|---|---|---|
| **CAUGHT** | follow-up issue was filed and is closed | 10 |
| **ADDRESSED_OPEN** | follow-up filed, still open | 8 |
| **ORPHANED** | still relevant; no follow-up filed | 11 |
| **OBSOLETE** | no longer applies (tech/process changed) | 3 |
| **UNCLASSIFIED** | still-relevant judgment unclear | 1 |
| **ERROR** | LLM call failed; needs human review | 0 |

## ORPHANED — 11 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #924 | docs: fix obsolete content in new-repo runbook chain (0901, 0925, 0926, 0927) | Item 7 of runbook fixes deferred to #886 Phase 4 | — | yes | Deferred runbook item tied to #886 Phase 4; no cross-reference directly resolves it, so likely still pending |
| #931 | fix: new_repo_setup.py generates misdirecting CLAUDE.md — point to root, surface PR discipline | GEMINI.md template generation in new_repo_setup.py deferred to follow-up | — | yes | GEMINI.md template work for new_repo_setup.py not clearly addressed by listed cross-references; remains a plausible open enhancement. |
| #964 | refactor: migrate privileged paths in new_repo_setup.py to in-process PAT pattern | Migrate privileged paths in new_repo_setup.py from env-scoped GH_TOKEN to in-process PAT pattern after #959 lands | — | yes | No cross-referenced issue clearly tracks this specific migration; in-process PAT pattern (ADR-0216) is active standard, so migration remains relevant |
| #1000 | refactor: new_repo_setup.py — eliminate env-scoped GH_TOKEN for initial push by deploying workflows via Contents API | Migrate Cerberus secret-set (--cerberus-pem) from gh auth to in-process classic PAT session | — | yes | Cerberus secret deployment still routes through gh auth; no cross-referenced issue directly tracks this migration to _pat_session pattern. |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | Updating ADR-0216 to reflect lessons from _pat_session hardening — optional follow-up | — | yes | ADR-0216 doc refresh was marked optional and no cross-referenced issue directly tracks it; still potentially useful but low-priority. |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | Classic PAT rotation TODO deferred to a separate tracking issue | — | yes | PAT rotation concerns _pat_session.py/runbook 0930 classic PAT flow; no cross-reference clearly addresses rotation TODO |
| #1022 | robustness: port _request_with_retry into new_repo_setup.py privileged calls | Porting _request_with_retry helper to other AZ tools making GitHub API calls (deploy_cerberus_secrets, fleet_delete_pr_sentinel, merge_sentinel_permissions_prs). | — | yes | Deferred migration of retry helper to other privileged tools; no cross-referenced issue directly tracks this follow-up work. |
| #1036 | robustness: port _request_with_retry into deploy_cerberus_secrets.py (follow-up to #1022) | Shared-module extraction of retry logic across new_repo_setup.py, deploy_cerberus_secrets.py, and fleet_set_delete_branch_on_merge.py deferred until more callers migrate. | — | yes | Deferred shared-module extraction is conditional on more callers migrating; no cross-referenced issue directly tracks this extraction work. |
| #1059 | fix: new_repo_setup.py — default .unleashed.json to assemblyZero=true for AZ-managed repos | One-shot fleet script to flip existing repos' assemblyZero=false to true across ~/Projects/*/.unleashed.json | — | yes | Backfill script for existing repos never filed; no cross-reference directly addresses fleet-wide flip, so concern remains open. |
| #1059 | fix: new_repo_setup.py — default .unleashed.json to assemblyZero=true for AZ-managed repos | One-shot fleet script to flip existing .unleashed.json assemblyZero=false→true across all repos | — | yes | Conditional follow-up (if user wants it); no cross-referenced issue directly tracks the fleet-flip script, so it remains an unfiled deferral |
| #1061 | feat: new_repo_setup.py — create canonical issue labels (implementation, lld) | Backfilling labels into existing repos via fleet rollout; automated label application; promoting workflow CONFIG names to GitHub labels. | — | yes | Fleet backfill of canonical labels into existing repos hasn't been tracked in the listed cross-refs; deferred work remains outstanding. |

## ADDRESSED_OPEN — 8 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #886 | fix: reconcile pr-sentinel dual-implementation and branch protection context spaghetti | strict=true branch protection outliers deferred as separate follow-up, orthogonal to pr-sentinel dual-implementation reconciliation | #918 (open) | yes | strict=true context outliers in branch protection remain a separate concern; no evidence of resolution in cross-referenced issues |
| #924 | docs: fix obsolete content in new-repo runbook chain (0901, 0925, 0926, 0927) | Removing pr-sentinel.yml references from runbooks 0927 and 0901 deferred to #886 Phase 4 (Actions workflow retirement). | #876 (open) | yes | #886 Phase 4 retirement of pr-sentinel.yml Actions workflow not yet confirmed complete; runbook references likely still obsolete-pending. |
| #960 | chore: migrate AssemblyZero + Sextant to fleet-standard pr-sentinel / issue-reference branch protection (#886 Phase 2) | Migrating 5 existing classic-PAT tools to new in-process pattern; fleet-wide retirement of pr-sentinel.yml from ~48 other repos | #963 (open) | yes | Deferred classic-PAT migration and fleet pr-sentinel retirement remain outstanding per cross-referenced open follow-ups |
| #960 | chore: migrate AssemblyZero + Sextant to fleet-standard pr-sentinel / issue-reference branch protection (#886 Phase 2) | Deferred migrating 5 existing classic-PAT tools to in-process pattern, and fleet-wide retirement of redundant pr-sentinel.yml from ~48 repos under #886 Phase 3-4 | #962 (open) | yes | Classic-PAT migration and fleet pr-sentinel cleanup remain tracked as open follow-ups; no evidence the work has landed |
| #975 | feat: fleet_delete_pr_sentinel.py — bulk-delete legacy .github/workflows/pr-sentinel.yml across 44 repos (#886 Phase 3) | Deferred migrating 5 existing classic-PAT tools (#961-#965) to new pattern; kept this PR scoped to bulk deletion only | #961 (open) | yes | Classic-PAT tool migrations #961-#965 remain open as of 2026-05-22, so the deferred scope is still pending |
| #1000 | refactor: new_repo_setup.py — eliminate env-scoped GH_TOKEN for initial push by deploying workflows via Contents API | Deploy workflows via Contents API in new_repo_setup.py to eliminate env-scoped GH_TOKEN for initial push | #1016 (open) | yes | Concerns new_repo_setup.py classic PAT flow per ADR-0216; no closed cross-reference clearly resolves the Contents API workflow deployment. |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | YubiKey migration of gpg key, executing PAT rotation, and updating ADR-0216 deferred from runbook 0930 PR | #1016 (open) | yes | YubiKey migration tracked at #1016 still open; PAT/gpg hardening remains active concern per recent memory entries |
| #1018 | docs+security: ship runbook 0930 + _pat_session retry/timeout hardening | ADR-0216 update with _pat_session hardening lessons; classic PAT and gpg passphrase rotation TODO | #1017 (open) | yes | Both deferrals tracked in open follow-ups (#1051 closed, #1017 open); PAT rotation still pending |

## CAUGHT — 10 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #886 | fix: reconcile pr-sentinel dual-implementation and branch protection context spaghetti | Phase 2: canonicalize branch protection contexts across repos and add protection to 3 unprotected repos | #887 (closed) | no | Follow-up phase tracked in #887 (closed); branch protection canonicalization work completed via subsequent closed issues. |
| #931 | fix: new_repo_setup.py generates misdirecting CLAUDE.md — point to root, surface PR discipline | GEMINI.md template generation in new_repo_setup.py deferred to follow-up | #1050 (closed) | no | Explicitly retro-filed and tracked in #1050, which is now closed — deferral resolved. |
| #959 | feat: in-process classic PAT decryption — never expose secret via env or argv | Migrating 5+ existing classic-PAT tools to the _pat_session.py pattern; each gets its own follow-up issue filed alongside | #960 (closed) | yes | Migration of classic-PAT tools to _pat_session.py is ongoing work; #960 closed but related follow-ups remain open |
| #964 | refactor: migrate privileged paths in new_repo_setup.py to in-process PAT pattern | Phase B: eliminate env-scoped GH_TOKEN for initial push via Contents API in new_repo_setup.py | #1000 (closed) | no | Explicitly tracked in #1000 which is now closed, indicating the deferred Phase B work has been addressed. |
| #1000 | refactor: new_repo_setup.py — eliminate env-scoped GH_TOKEN for initial push by deploying workflows via Contents API | Phase B follow-up scope deferred from Phase A PR for new_repo_setup.py Contents API workflow deployment refactor | #1004 (closed) | no | Follow-up #1004 closed; related new_repo_setup work tracked separately and largely resolved per closed cross-refs. |
| #1036 | robustness: port _request_with_retry into deploy_cerberus_secrets.py (follow-up to #1022) | Shared-module extraction of _request_with_retry deferred from deploy_cerberus_secrets.py | #1052 (closed) | no | Follow-up #1052 already closed; extraction precondition met and tracked separately. |
| #1050 | feat: new_repo_setup.py — generate GEMINI.md template alongside CLAUDE.md (#931 follow-up) | GEMINI.md template generation deferred from #931 was implemented without a follow-up issue being filed at the time. | #931 (closed) | no | The deferred work (GEMINI.md template in new_repo_setup.py) was implemented in this very issue #1050, which is now closed. |
| #1051 | docs: ADR-0216 — append _pat_session hardening lessons (#1018 follow-up) | Issue itself was the follow-up to #1018 — appending post-shipping _pat_session hardening lessons to ADR-0216. | #1018 (closed) | no | This issue WAS the deferred follow-up from #1018 and is now closed; ADR update presumably landed. |
| #1124 | fleet: branch protection is inconsistent across martymcenroe — audit + remediation needed | Remediation script to fix weak/unprotected repos to canonical branch protection policy | #1126 (closed) | no | Follow-up remediation filed as #1126 and already closed; branch protection remediation work completed |
| #1124 | fleet: branch protection is inconsistent across martymcenroe — audit + remediation needed | Remediation of inconsistent branch protection across fleet deferred to a separate follow-up issue/script | #1126 (closed) | no | Remediation tracked separately and closed; branch protection fleet work appears resolved |

## OBSOLETE — 3 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #510 | feat: PR issue-reference enforcer — GitHub App on Cloudflare Workers | Manual GitHub App creation, PKCS#8 key conversion, CF Worker deployment, and branch protection setup deferred to manual steps | — | no | pr-sentinel GitHub App was created and deployed long ago; it's been actively running and referenced throughout current workflows |
| #960 | chore: migrate AssemblyZero + Sextant to fleet-standard pr-sentinel / issue-reference branch protection (#886 Phase 2) | Phase 2 of #886: migrate AssemblyZero and Sextant to fleet-standard pr-sentinel worker check | — | no | References #886 Phase 2 scope; this issue itself completed the Phase 2 migration for the two outlier repos |
| #1050 | feat: new_repo_setup.py — generate GEMINI.md template alongside CLAUDE.md (#931 follow-up) | GEMINI.md template generation in new_repo_setup.py, punted from #931 | — | no | This issue #1050 itself addressed the deferred follow-up from #931 and is now closed. |

## UNCLASSIFIED — 1 item(s)

| Issue | Title | Deferred summary | Follow-up | Still relevant? | Rationale |
|---|---|---|---|---|---|
| #924 | docs: fix obsolete content in new-repo runbook chain (0901, 0925, 0926, 0927) | Item 7 (pr-sentinel.yml as automatic artifact) deferred to #886 Phase 4; touching references before Phase 3 lands would conflict | — | ? | Deferred to #886 Phase 4, not in cross-references; cannot determine current status of that phase from given context |

## Audit Record

| Date | Auditor | Findings | Issues Created |
|------|---------|----------|----------------|
| 2026-05-22 | Claude Opus 4.7 | ADDRESSED_OPEN:8 CAUGHT:10 OBSOLETE:3 ORPHANED:11 UNCLASSIFIED:1 | (filed manually after review) |

## Notes

- ORPHANED items in this report are candidates for the user to file as new issues.
- OBSOLETE items should be acknowledged (e.g., a comment on the original issue noting the deferred work is moot).
- The closing-discipline rule in root `CLAUDE.md` was added 2026-04-21 (issue #998 / PR #999) to prevent future ORPHANED items.
