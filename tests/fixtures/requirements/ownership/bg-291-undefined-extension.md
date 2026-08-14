# Config persistence

Reconstructed from boostgauge #291, ruled 2026-08-13. Criterion A came from the
Reads section and criterion B was acceptance criterion 5.

ADR 0228 clauses 1 and 2 kill it. The original A said the app "re-reads it
during the session", and no reader could tell whether "it" was the whole file
or the thresholds section. Here the table declares `thresholds` under the live
re-read criteria. E1 is an exit-write criterion stating that variable's fate
anyway, which is clause 2. R2 names `telltale_windows.short`, which no row
declares, so its extension and its owner are undefined, which is clause 1.

## Requirements

- WHILE the app is running the app shall re-read the config file.

## Variables

| Variable | Extension | Owner |
|---|---|---|
| `thresholds` | every key under `thresholds` | `R` (the live re-read criteria) |
| `theme` | the `theme` key | `E` (the exit-write criteria) |

## Acceptance Criteria

- [ ] R1. The app re-reads `thresholds` during the session, so an edit takes effect without a restart
- [ ] R2. An edit to `telltale_windows.short` during the session takes effect without a restart
- [ ] E1. `thresholds` values edited directly in the config file take effect without restart, and reading them does not modify the file
