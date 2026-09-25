# Implementation Report — The fail-open denominator check leaves the PR gate for --check --strict (#3523)

Backfilled 2026-09-25 after the merge, from PR #3529 (merge `0bb5fa69`) and its body (#3559). No report was written at the time; nothing was re-run for the backfill, and every claim below is the PR's own.

Parent: #3502.

## What was wrong

`tests/unit/test_fail_open_audit.py` asserted that the baseline's `measured_against` block (files scanned, sites examined, findings total) equals a live re-walk. Every PR that added a function changed `sites_examined`, so it failed CI until `tests/fixtures/fail_open_baseline.json` was regenerated. Two concurrent PRs then collided on the same three count lines, and on 2026-09-24 three of six PRs needed a second push for that reason alone.

## What changed

- The denominator assertion leaves the PR gate. `tools/audit_fail_open.py --check --strict` carries it: strict mode exits 1 when any `measured_against` count differs from the tree, and names each count as `baseline N, tree M`. A missing or unreadable block counts as drift in every count, not as a pass. `--strict` without `--check` is a usage error.
- The staleness of the enforced part is unchanged and still runs on every PR: `test_the_baseline_is_not_stale` fails when a baselined site no longer exists.
- `write_baseline` builds the block through the same `measured()` helper that strict mode compares against, so the two cannot count differently.

The gate registry's baseline had the same lock; that is #3527, landed separately.

## Files

`tests/unit/test_fail_open_audit.py`, `tools/audit_fail_open.py`.
