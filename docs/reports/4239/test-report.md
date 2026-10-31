# Test Report: a run must be able to start (#4239, #4241, #4158)

Each new test file was run against `main`'s unchanged source in the primary checkout (copied in, run, removed; the checkout was clean afterwards), and then against this branch.

## #4241: `tests/unit/test_worktree_relative_paths.py` (8)

- T2, the guard: `test_t2_every_worktree_add_passes_relative_paths` reads every `.py` file in `assemblyzero/` and `tools/` with `ast` and requires `--relative-paths` in every list or tuple literal holding `"worktree"` then `"add"`. `test_t2_the_guard_catches_a_call_without_the_flag` runs it on a fixture. `test_t2_the_sites_are_the_known_ones` pins the nine sites by file, so a site that disappears is noticed too.
- T1, five tests against a real throwaway repository: the implementation worktree, its existing-branch retry, the mock detached worktree, the LLD worktree and its retry. Each checks that the worktree's `.git` file and the admin `gitdir` file are relative.
- The operator's `~/.gitconfig` sets `worktree.useRelativePaths = true`, so on his machine every worktree was already relative and T1 passed on `main`. The fixture now points `GIT_CONFIG_GLOBAL` at an empty file and sets `GIT_CONFIG_NOSYSTEM`, which is how CI and his Windows side behave.
- Against `main`: 6 failed, 2 passed (the fixture check and the site count, which hold on both). The guard named all nine sites. On this branch: 8 passed.

## #4239: `tests/unit/test_impl_transport_preflight.py` (6)

- T1: the real transport check with agy hidden from the process (HOME at an empty directory, PATH at the system directories, the WSL lookup returning nothing). `main()` exits non-zero, the graph is never compiled, the resume contract is never consumed, `git worktree list` and `git branch -a` are unchanged, no worktree directory exists, and one alert names "agy CLI was not found".
- T2: with a working transport the check runs once, on `gemini-3.8-flash-high`, and the run lands through the stand-in driver.
- Dry and mock runs are not probed; a profile with no Gemini seat is not probed; one Gemini seat is enough to need the probe.
- Against `main`: 6 failed. On this branch: 6 passed.

## #4158: `tests/unit/test_impl_issue_branch_refuses.py` (7)

- T1: `main()` started on `42-implementation` exits non-zero before the graph is compiled and before the transport probe, lands nothing, and records one alert naming the branch and the integration branch.
- T2: a stand-in run that completes, started on its own branch, never exits 0 without landing. Its stand-in writes no work, because on `main` that path has no worktree to write into and a crash there would hide the defect.
- Dry, mock, scaffold-only and `--no-worktree` runs are not refused, and neither is the integration branch.
- Against `main`: 6 failed, 1 passed at first, because T2's stand-in crashed on `main`; with the stand-in writing nothing, T2 failed on `main` too (exit 0, nothing landed). On this branch: 7 passed.

## Neighbouring suites

Every test file under `tests/unit` and `tests/tools` that names one of the changed modules (123 files): 2020 passed, 20 skipped, 2 failed. The two failures, `tests/tools/test_dependabot_review.py::TestRunJsGate::test_node_modules_removed_after_gate` and `::test_node_modules_removed_even_on_failure`, fail identically on `main` in the primary checkout, and belong to the local test-tier defects.

## After merging `main` (the `core/` batch, PR #4252 and PR #4260)

- The merge was clean. This branch's two `tools/run_implement_from_lld.py` test files then made five tests in `main`'s new `tests/unit/test_preflight_loud_failure.py` fail when run after them: the shared fixture in `tests/unit/conftest.py` set the transport stand-in with `patch()`, these tests set the check again with `monkeypatch`, and the two undo steps ran in the wrong order, so the stand-in stayed for the rest of the process. The fixture now uses `monkeypatch` too. `tests/unit/test_preflight_stand_in_does_not_leak.py` (2) pins it: 1 failed on the old fixture, 2 pass now. The same combination, five files, went from 5 failed to 42 passed.
- Full unit tier, `poetry run pytest tests/unit -q -p no:cacheprovider`, 2026-10-30, 7:39 to 7:48 PM Central: `11566 passed, 66 skipped, 7 deselected, 6 xfailed, 13 warnings in 542.22s`. No failures; the session guards printed no `FAIL:` line; the tree was clean afterwards.
- `tools/audit_fail_open.py --check --strict`: PASS, 313 files, 9770 sites, no new fail-open. `tools/audit_loud_failure.py --check`: PASS, 263 sites, all in the baseline.
