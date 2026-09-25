# Implementation Report — The gate-registry denominator leaves the PR gate (#3527)

Parent: #3502. Sibling of #3523, which made the same change to the fail-open
baseline.

## What was wrong

`tests/unit/test_routing_policy.py::TestTheRatchet::test_the_denominator_matches_what_it_was_measured_against`
re-walked `assemblyzero/workflows/` on every PR and asserted that
`tests/fixtures/gate_registry_baseline.json`'s `measured_against` block
(`files_scanned`, `halt_sites`, `gates`) equalled the live counts. Any PR that
added a walked file, with or without a halt site in it, failed CI until the
baseline was regenerated, and two PRs that each added a file collided on the
`files_scanned` line.

The block is context for a reader. The counts that protect anything are
`halt_rows_per_stage` and `model_output_halt_rows`, and those were never the
problem.

## What changed

`tools/audit_halt_sites.py`:

- `measured(sites, coverage)` builds the denominator. `write_baseline` writes
  it through that helper, so the block written and the block compared cannot
  count differently.
- `denominator_drift(sites, coverage, path)` returns each count whose baseline
  value differs from the tree, as `{name: (baseline, live)}`. A missing or
  unreadable `measured_against` block is drift in every count, not a pass.
- `--strict`, with `--check`, exits 1 on drift and names each count as
  `baseline N, tree M`, then says to regenerate with `--write-baseline`.
  `--strict` without `--check` is a usage error. Plain `--check` does not look
  at the block. In `main`, the baseline path is passed at call time rather
  than bound as a default, so a test can point the module at another file.

`tests/unit/test_routing_policy.py`:

- `test_the_denominator_matches_what_it_was_measured_against` is replaced by
  `test_the_baseline_states_a_denominator`, which asserts only that the block
  is written with its three keys.
- New class `TestTheDenominatorLeftThePRGate`, six tests, described in the
  test report.

`tests/fixtures/gate_registry_baseline.json` is not touched. On the tree as it
stands, `--check --strict` passes: 178 files, 142 halt sites, 93 gates, and the
baseline says the same.

## What did not change

- `test_the_baseline_matches_the_registry` and
  `test_the_ratchet_records_what_is_left` run on every PR exactly as before.
- `test_gate_registry.py`'s two-way site check and its `model_output_halt_rows`
  exact match are unchanged.
