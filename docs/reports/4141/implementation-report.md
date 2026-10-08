# Implementation Report: runbook 0927 after PR #4138 (#4141)

## What landed

| File | Change |
|---|---|
| `docs/runbooks/0927-new-repo-human-checklist.md` | v6.9. Step 1 says to run `new_repo.py` in Git Bash on Windows 11, and why Ubuntu cannot prompt (#1806, #4135). The "handles automatically" list says `.claude/settings.json` is `{}`, with no hook installed (#4137). The summary paragraph describes `[SUCCESS]`, exit 0, and `[FAILED]`, alert, exit 1 (#4136). Three passphrase lines are corrected for `default-cache-ttl 0`. Two stale "revoke the Cerberus key when done" phrases are removed, per #1295. A history row is added. |

Runbook 0901 was already brought up to date in PR #4138.
