# Config persistence

Reconstructed from boostgauge #292, ruled 2026-08-13. Both criteria are the
gate's verbatim A and B.

ADR 0228 clause 4 kills it. The criteria partition the config into threshold
keys and non-threshold keys, and nothing defines the partition. The config also
carries `telltale_windows`, which is not under `thresholds` and which governs
how threshold values are evaluated, so the term decides its behaviour and
cannot classify it. A table row reading "every key under `thresholds`" settles
the case and is what this fixture is missing.

## Requirements

- WHILE the app is running the app shall apply threshold edits without a restart.

## Variables

| Variable | Extension | Owner |
|---|---|---|
| `position` | the `x` and `y` keys under `position` | `E` (the exit-write criteria) |
| `telltale_windows` | the `short`, `medium` and `long` keys under `telltale_windows` | `R` (the live re-read criteria) |

## Acceptance Criteria

- [ ] R1. Threshold values edited directly in the config file take effect without restart, and reading them does not modify the file
- [ ] R2. A non-threshold key edited directly in the config file while the app runs leaves the running session unchanged
