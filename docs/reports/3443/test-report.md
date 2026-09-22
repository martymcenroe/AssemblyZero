# Test Report — Dependabot Config Tests Follow the File (#3443)

The change is to a test file, so the evidence is the tests themselves, run three
ways: failing before, passing after, and failing again when deliberately broken.

## 1. Reproduced the CI failure locally, before changing anything

```
poetry run pytest tests/unit/test_dependabot_config.py -q
3 failed, 4 passed
```

The same three names CI reported, for the same reason —
`FileNotFoundError: ...\.github\dependabot.yml`. The local repro matching CI is
what makes the rest of this report meaningful; a fix verified only in CI is a fix
verified once.

## 2. Green after the change

```
poetry run pytest tests/unit/test_dependabot_config.py -q
7 passed
```

All seven, including the four that already passed. No test was skipped, deleted,
xfailed or weakened to reach this — the count went 4 passing to 7 passing, and
the file still contains seven tests.

## 3. The tests still check the config, rather than passing vacuously

This is the assertion that matters, because a test made green by making it stop
looking is worse than the red it replaced.

`test_exactly_the_three_specified_ecosystems` passes by parsing the `.disabled`
file and matching all three entries against `EXPECTED` — npm at `/sentinel`
weekly, pip at `/` weekly, github-actions at `/` monthly — and asserting no
extras. It reached the content, while Dependabot is switched off. That is the
whole point of following the file instead of skipping.

## 4. The new ambiguity guard actually fires

Verified by deliberately breaking it rather than by reading it. A second config
was written to `.github/dependabot.yml` so both files existed at once:

```
4 failed, 3 passed
FAILED ...::test_config_exists_and_is_valid_yaml
FAILED ...::test_exactly_the_three_specified_ecosystems
FAILED ...::test_the_config_is_not_a_workflow_file
FAILED ...::test_the_sentinel_entry_targets_the_lockfile_that_had_the_alerts
```

Every test that resolves the config failed, with the intended message. The guard
is load-bearing, not decorative.

## What Is Not Verified Here

The full unit suite was not re-run locally for this change. The edited file is
standalone — it defines no shared fixture, exports no helper, and nothing imports
it — so its blast radius is itself. CI runs the whole suite on this PR and that is
the check that governs; the claim "CI is green" rests on that run, not on this
report.

The disable decision itself is untested and deliberately so. These tests assert
what the config says, never whether Dependabot ought to be on.
