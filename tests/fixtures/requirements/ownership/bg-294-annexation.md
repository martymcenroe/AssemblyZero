# Config persistence

Reconstructed from boostgauge #294, ruled 2026-08-13. Both criteria are the
gate's verbatim A and B.

ADR 0228 clause 2 kills it. R2 is a live re-read criterion, and its second
half promises what the file holds at the next launch. That outcome belongs to
the exit-write criteria, which own `theme` and `size`, and they say the
hand-made value wins. The annexation is the defect; the contradiction is only
its symptom.

## Requirements

- WHEN the app exits the app shall write the config file.

## Variables

| Variable | Extension | Owner |
|---|---|---|
| `theme` | the `theme` key | `E` (the exit-write criteria) |
| `size` | the `width` and `height` keys under `size` | `E` (the exit-write criteria) |
| `thresholds` | every key under `thresholds` | `R` (the live re-read criteria) |

## Acceptance Criteria

- [ ] R1. An edit to `thresholds` during the session takes effect without a restart
- [ ] R2. A non-`thresholds` key such as `theme` or `size`, edited directly in the config file while the app runs, leaves the running session unchanged; the edited value takes effect at the next launch
- [ ] E1. With a direct file edit during the session, the edited key holds the edited value after quit, unless the user also hand-changed that same key, in which case the hand-made value wins
