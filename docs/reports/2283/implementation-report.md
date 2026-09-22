# Implementation Report — CI Runs Every Test Tier Before Merge (#2283)

## The Gap

`pyproject`'s `addopts` deselects the integration, e2e and adversarial markers, so
each tier needs a step naming its own marker. CI had one such step, for unit.
Integration ran only on push to `main`:

```yaml
      - name: Run integration tests
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

e2e and adversarial had no step at all. The consequence, counted rather than
estimated:

| tier | tests | when it gated a PR |
|---|---|---|
| unit | 10,459 | every push and PR |
| integration | 64 passing, 6 skipped | after merge to main |
| e2e | 19 passing | never |
| adversarial | 1 (skips without credentials) | never |

83 passing tests ran too late to prevent anything, and 19 of those never ran in
CI at all. That is how the e2e tier silently stopped reaching the loop it exists
to exercise (#2280): nothing ran it.

Integration running post-merge is worse than it sounds. It detects a break at the
exact point where reverting is most expensive.

## The Change

Three steps added, one `if:` removed. Every tier now runs before merge.

The selectors are `tests/` plus a marker, never a directory alone. That is
load-bearing: two e2e-marked tests live in `tests/unit/test_issue_257.py`, so
`tests/e2e/` would quietly run 17 of 19 and report success.

## Cost, Measured

| tier | via `tools/test-gate.py` |
|---|---|
| integration | 64 passed, 6 skipped — 11.0s |
| e2e | 19 passed — 8.7s |
| adversarial | 1 skipped — 5.1s |

About 25 seconds, against a unit tier that takes 5m45s in CI. There was never a
minutes argument for excluding these, and this lands during an active
Actions-cost squeeze precisely because the numbers say it is not part of that
problem.

## The Adversarial Step Is Deliberately Not `continue-on-error`

It needs live Gemini access. Without a credential its autouse fixture skips
before constructing a client, so the step exits 0 with `1 skipped` — verified,
not assumed: the command was run and its exit status checked.

`continue-on-error` was considered and rejected. A skip is already the quiet
outcome; swallowing a genuine failure on top of it would rebuild exactly the
blind spot this issue exists to close. When the credential in #2285 is settled,
this step starts asserting instead of skipping with no workflow change.

## Why This Landed via the Contents API

`.github/workflows/ci.yml` cannot be pushed with the fine-grained PAT, which has
no `workflow` scope — load-bearing per ADR-0216 §1, not an oversight to widen.
The sanctioned path is the in-process classic-PAT Contents API, run by the
operator rather than by an agent.

## The Landing Script Had Gone Stale, and Would Have Reverted Two Things

`tools/land_2283_ci_tiers.py` already existed, written 2026-08-13. It embeds the
workflow as a string literal and PUTs it through the Contents API, which replaces
the file wholesale.

In the five weeks it sat unlanded, main's `ci.yml` gained two things the embed
did not have:

| on main | in the embed |
|---|---|
| a `concurrency:` block with `cancel-in-progress: true` | absent |
| `actions/setup-python@v7` | `@v5` |

Running the script as written would have reverted both. The concurrency block is
an active Actions-cost measure, added during the same squeeze that disabled
Dependabot — so the revert would have quietly undone cost control while claiming
to land a test-coverage improvement. Nothing in the script's flow would have
reported it, because a wholesale PUT has no diff to inspect.

Two things changed here. The embed was refreshed to match current main plus the
tier steps, verified byte-for-byte against the branch's `ci.yml`. And
`would_drop()` now compares main's line set against the embed's before any write,
aborting on anything present upstream that the embed lacks and
`INTENDED_REMOVALS` does not declare.

The second is the part that matters. Refreshing the embed fixes today; the guard
is what makes the next five-week gap loud instead of silent.
