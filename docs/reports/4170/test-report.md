# Test Report — Issue #4170

| # | Check | Result |
|---|---|---|
| T1 | ADR 0240 carries Status Accepted and its seven sections: Decision, What failed and why, The cause, How to diagnose it next time, Tests that hold it, Consequences, Provenance | **passes**, by grep: Status Accepted, 7 of 7 headings |
| T2 | The diff of ADR 0239 changes only its Status line | **passes**: `git diff --numstat` shows 1 line added and 1 removed, the Status line |
| T3 | No private name appears (case-insensitive fixed-string search for thetrail, chiron, camino, secret-agent, kanon, unleashed, dispatch, thrivetech, and the private product's languages) in ADR 0240, ADR 0239, the implementation report, the PR body or the commit message | **passes**: 0 matches in each of the five |
