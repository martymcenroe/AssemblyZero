# Config persistence

Reconstructed from boostgauge #290, ruled 2026-08-13. The gate's criterion A is
kept verbatim; the variable table around it is what ADR 0228 would require.

ADR 0228 clause 3 kills it. "Touches only hand-changed keys" is a blanket whose
held-fixed condition (that no direct file edit hit the same key) is nowhere in
the claim. The trailing "while the app ran" conditions the direct file edit,
not the "only", which is why the sentence read as complete to five reviewers.

## Requirements

- The app shall write the config file on exit.

## Variables

| Variable | Extension | Owner |
|---|---|---|
| `position` | the `x` and `y` keys under `position` | `E` (the exit-write criteria) |
| `size` | the `width` and `height` keys under `size` | `E` (the exit-write criteria) |

## Acceptance Criteria

- [ ] E1. The exit write touches only hand-changed keys: a direct file edit made while the app ran survives an exit that also writes a new `position` or `size`
- [ ] E2. With a direct file edit during the session, the edited key holds the edited value after quit, unless the user also hand-changed that same key, in which case the hand-made value wins
