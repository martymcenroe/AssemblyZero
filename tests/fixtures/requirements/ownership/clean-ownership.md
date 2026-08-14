# Config persistence

The negative case. Every clause of ADR 0228 holds, so the ownership check must
report nothing. A checker whose passing result has never been made to fail is
not a check, and this fixture is the other half of the four kill tests.

It is boostgauge #294's material written under the discipline: the same two
domains, the same keys, and no conflict, because the reload criteria cite the
exit-write criteria rather than stating what the file holds.

## Requirements

- WHEN the app exits the app shall write the keys the user hand-changed.
- WHILE the app is running the app shall apply edits to `thresholds` without a restart.

## Variables

| Variable | Extension | Owner |
|---|---|---|
| `theme` | the `theme` key | `E` (the exit-write criteria) |
| `size` | the `width` and `height` keys under `size` | `E` (the exit-write criteria) |
| `thresholds` | every key under `thresholds` | `R` (the live re-read criteria) |

Boundary term: a **hand-changed** key is one the user altered through the app's own controls during the session, such as dragging or resizing the window. A direct edit to the config file is not a hand change.

## Acceptance Criteria

- [ ] R1. An edit to `thresholds` during the session takes effect without a restart
- [ ] R2. An edit to any key other than `thresholds` during the session leaves the running session unchanged; what the file holds afterwards is governed by the exit-write criteria
- [ ] E1. With a direct file edit during the session, the edited key holds the edited value after quit, unless the user also hand-changed that same key, in which case the hand-changed value wins
- [ ] E2. `theme` and `size` hold their hand-changed values after quit, except where the session made no hand change, in which case they hold what the file already held
