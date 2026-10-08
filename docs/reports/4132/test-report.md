# Test Report: new_repo.py from Ubuntu (#4132, #4135, #4136, #4137)

## New and changed tests

```
poetry run pytest tests/unit/test_new_repo_ubuntu_run.py tests/tools/test_pat_session.py \
  tests/unit/test_new_repo.py tests/unit/test_new_repo_safety.py \
  tests/unit/test_new_repo_post_create_hooks.py tests/unit/test_new_repo_guidance.py \
  tests/unit/test_scaffolder_lint_integration.py tests/unit/test_new_repo_pypi.py \
  tests/unit/test_new_repo_python_version.py -q          228 passed
```

- `test_new_repo_ubuntu_run.py` (new). Resolve path: the real config gives `<checkout parent>/foo`; it asks for `fmt='auto'`; a relative root and a cwd-joined Windows root are both refused with nothing created. The audit asks for `fmt='auto'`. `failed_steps`, including the exact 2026-10-07 run, which names five failed steps. An end-to-end local run with one failed check exits 1, prints no `[SUCCESS]`, and records one alert.
- `test_pat_session.py`. All four sessions raise `PinentryUnavailable` after one gpg call, given the 2026-10-07 stderr. It is a `RuntimeError`. A wrong passphrase still retries `MAX_GPG_ATTEMPTS` times.
- `test_new_repo.py`. The #2113 settings tests are rewritten: a new file is `{}`; a stale registration is removed while permissions, other events, other matchers and sibling hooks survive; a re-run touches nothing. `deploy_canonical_hooks` no longer exists. Eight local-run tests now really run `git init` (`run_with_real_git_init`). The data-dl check needs a real repository, and a failed local check now exits 1.

## Audits

```
tools/audit_loud_failure.py --check      after --write-baseline: 323 sites
tools/audit_fail_open.py --check --strict   PASS -- 312 files, 9642 sites
```

## Full local suite, and why its failures are not this change

```
poetry run pytest tests -q    23 failed, 11557 passed, 66 skipped, 90 deselected, 6 xfailed
```

20 of the 23 failed identically when run on unchanged `main` (`0e1ead5a`) in the main checkout:

- `test_auto_reviewer_wait_loop.py` (16);
- `test_dependabot_review.py::TestRunJsGate` (2);
- `test_universal_claude_md.py::test_adr_references_resolve` (an ADR-0003 reference);
- `test_orchestrator_graph.py::test_full_pipeline_success` (a recursion limit).

The other 3 pass when run alone in this worktree: the two `test_cascade_detector.py` latency tests (load-sensitive, #3731) and `test_checkpoint_carries_no_enums.py`. None of the 23 touches `new_repo.py` or `_pat_session.py`.

## Lint

Per-file ruff counts against `origin/main`: `tools/new_repo.py` 23 to 23, `tools/_pat_session.py` 5 to 5, `tests/unit/test_new_repo.py` 15 to 15, `tests/tools/test_pat_session.py` 5 to 5. The new test file has no findings.
