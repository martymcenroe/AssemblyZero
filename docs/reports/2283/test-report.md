# Test Report — CI Runs Every Test Tier Before Merge (#2283)

The change is a CI workflow, so the evidence is that each command the workflow
will run was run first, locally, exactly as written.

## Each Tier, Through `test-gate.py`

Not through raw `pytest` — through the wrapper the workflow actually invokes,
with the same markers and the same environment variables.

| command | result | time |
|---|---|---|
| `test-gate.py tests/ -m integration` (`ASSEMBLYZERO_MOCK_MODE=1`) | 64 passed, 6 skipped, 11065 deselected | 11.0s |
| `test-gate.py tests/ -m e2e` (`ASSEMBLYZERO_MOCK_MODE=1`) | 19 passed, 11116 deselected | 8.7s |
| `test-gate.py tests/ -m adversarial` | 1 skipped, 11134 deselected | 5.1s |

## The Adversarial Step's Exit Status Was Probed, Not Assumed

An all-skipped tier is the one case where a step can look fine in its output and
still fail the job. The command was run with its exit status gating a following
command, which executed — so `test-gate.py` exits 0 on `1 skipped`.

This matters because the step is deliberately not `continue-on-error`. If the
wrapper exited non-zero on a skip, every CI run would go red the moment this
landed.

## The Selector Choice Was Verified, Not Reasoned About

The workflow selects `tests/` plus a marker rather than `tests/e2e/`. The e2e
marker collects **19** tests; `tests/e2e/` as a directory holds 17. The two
missing ones are in `tests/unit/test_issue_257.py`. Using the directory would
have run 17 of 19 and reported success — a passing gate over a silently reduced
set, which is the failure mode this issue is about.

## Applies Cleanly to Current Main

The change was written against `378de81a` and sat unlanded for some time. It
applies to `586d3962` with no conflict, and the resulting workflow was read in
full rather than diffed alone.

## The Landing Script's Staleness Guard

`tests/unit/test_land_2283_guard.py` — 7 passed.

The script cannot be run to test it: it decrypts the classic PAT, and an agent
must never parent that process. So the guard is verified as a unit instead.

Two of the seven carry the weight:

- **`test_the_actual_regression_this_guard_exists_for`** reproduces the real
  case — main carrying `concurrency:` and `setup-python@v7` against the embed
  that carried neither — and asserts both are reported. It fails if the guard
  stops catching the thing it was written for.
- **`test_the_shipped_embed_is_current_against_the_branch_workflow`** asserts
  the embed equals the `ci.yml` in this same change. A guard that catches future
  drift while shipping stale content itself would be theatre; this is what stops
  that.

The rest pin the edges: identical content drops nothing, declared
`INTENDED_REMOVALS` do not trip it, blank lines are ignored, and reordering
alone is not treated as dropping (it compares line sets, not a diff).

## What Is Not Verified

**The workflow has not run on GitHub.** Every command was verified locally on
Windows; CI runs Ubuntu with a cold `.venv` and no credentials. Local success
predicts the runner but does not prove it. The first run on the PR is the real
check, and the integration tier's 6 skips are expected to remain skips there
(they need a GitHub token or Gemini access).

**No test asserts the workflow's shape.** Nothing fails if a future edit
re-adds an `if:` that defers a tier, or swaps a marker selector for a directory
one. Given that this issue exists because a tier silently stopped running, a
guard against that regression is worth its own issue rather than being assumed
covered here.
