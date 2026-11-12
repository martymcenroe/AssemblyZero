# Test report: #4723

Run in Ubuntu (WSL) in the worktree, with the worktree's own poetry environment. The branch also carries #4724; its report is `docs/reports/4724/test-report.md`, and the full-suite run below covers both.

## New tests

In `tests/unit/test_cerberus_after_auto_review.py`:

- `test_the_cerberus_health_audit_and_its_tests_are_gone` (T1, R2: the audit no longer exists): `tools/audit_cerberus_health.py` and `tests/tools/test_audit_cerberus_health.py` are absent.
- `test_nothing_live_names_the_retired_audit`: no `.py` or `.md` file under `tools/`, `tests/`, `assemblyzero/` or `docs/` names the audit, except the historical `docs/audits/` and `docs/reports/`.

T2 does not apply: the audit is retired, as the issue's AC2 allows. The retirement rests on #4724's finding that no per-repository key has a reader; the tests that hold that finding are in #4724's report.

Removed with the tool: `tests/tools/test_audit_cerberus_health.py`.

## Each new test fails when its change is reverted

The tool and runbook changes were stashed by name: `tools/new_repo.py`, `tools/audit_fleet_auto_merge_readiness.py`, `tools/test_governance_system.py`, and runbooks 0927 and 0939. The audit was written back from `HEAD` (a staged deletion cannot be stashed by path). Both tests above failed. The restored audit was checked identical to `HEAD` and removed, and the stash was applied. Every stashed path was checked identical to the stash, and the stash was dropped.

## Targeted

- `tools/audit_loud_failure.py --check` passes at 115 sites; the baseline held no entry for the audit.
- Ruff finds nothing in the new test file and adds no finding to any changed file.

## Full suite

`pytest -q` on this branch, off `origin/main` at 823f30ee: 15056 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 19 min 5 s. No failure comes from this branch. The 18 are the ones that fail the same way on unchanged `main`, each tracked:

- 16 in `tests/test_auto_reviewer_wait_loop.py` (see #4528);
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success` (see #4529, #3737);
- `tests/test_universal_claude_md.py::test_adr_references_resolve` (see #3730).

After the full run, two blocks of print text in `tools/new_repo.py` were reworded (the keep-the-key-active advice). The new test file and every `new_repo` test file were run again on the final tree: 244 passed.
