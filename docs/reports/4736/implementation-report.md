# Implementation report: #4736

## The defect

The nightly tests a dependabot PR at the PR's own head. A head cut before #4706 does not carry `tests/fake_root_guard.py`, so its suite runs unguarded under Windows Python, and every fake absolute root its tests hand the code becomes a real folder. `C:\tmp\repo` and `C:\tmp\test_project` came back on every night PR #4315 was tested. The guard on `main` cannot stop it, because the guard is not in the tree under test. #2259 is the defect class.

## The guard files are a closed set (R3)

`FAKE_ROOT_GUARD_PATHS = ("tests/fake_root_guard.py",)` at `tools/dependabot_review.py:339`. It is checked for every repo the nightly tests, not only AssemblyZero, and a repo whose `main` has no such file passes the check unchanged. Only AssemblyZero has such a guard today: 164 `conftest.py` files under the projects folder were checked. A guard added elsewhere joins the tuple by name.

## `fake_root_guard_gap` (new)

`fake_root_guard_gap(worktree, rev="HEAD", fetch=True)` at `:803` returns `(missing, error)`. It fetches `main` from origin, then compares `git ls-tree origin/main -- <path>` with `git ls-tree <rev> -- <path>` for each guard path. A path present on `origin/main` and absent at `rev` is missing. A failed fetch or listing is an error, and then nothing may be tested.

It reads `origin/main`, never the local `main`. The nightly cuts its audit worktree from the primary checkout's local `main`, which can lag origin, and a stale local `main` must not hide the guard.

## The gate (R1)

In `_process_pr_inside_worktree` (`:1884-1914`), for a PR that touches Python, the check runs before `poetry install`:

- A check error records the PR `errored`, and no pytest runs.
- A missing guard prints `SKIP GATE: this head lacks tests/fake_root_guard.py, which origin/main has`, and install, pytest and the baseline are not run. The PR defers through the existing path (`:2017-2046`): a review comment carrying the reason, then `request_dependabot_rebase(pr, repo, explanation=...)` when the branch is stale. The explanation replaces the "Test suite failed" text and says the head predates the guard. The multi-package `@dependabot recreate` is not posted for such a PR.

A PR that touches no Python file is unaffected.

`run_baseline_gate` (`:1821-1831`) checks the baseline commit too, with `fetch=False`, because the baseline also comes from the local `main`. A base that lacks the guard, or a check that fails, is not run and reads as "not exonerable".

## PR #4315

Its head, 3991fb8b, lacks the guard, and its base, c775323f, is behind `main`. The first nightly that runs this code records it `deferred` with a `SKIP GATE` line and asks dependabot to rebase it. It is tested once the rebase brings the guard in.

## Tests

Tests 1 and 2 of the issue are in `tests/unit/test_dependabot_fake_root_guard.py`. The test report records the run.

## Left open

- Test 3 and AC2, the listing of `C:\tmp` and the other fake roots before and after a run: a follow-up issue carries the check after the next nightly.
- The scheduled checkout does not update itself today, so this fix reaches the nightly only once that checkout is brought to a `main` that carries it. The follow-up confirms that from the run's provenance SHA.
