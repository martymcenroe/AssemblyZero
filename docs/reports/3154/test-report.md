# Test Report: delete the spent one-shots (#3154, #3170)

This change adds no behaviour, so it adds no test. What it has to prove is that nothing still depended on what went.

## Checks before deleting

- Every issue a script's opening docstring names was read from GitHub: all closed or merged, apart from one reference that no longer resolves, whose script has another target that is closed.
- `git grep` for each script's name outside the deleted files and the generated records (`docs/lineage/`, `docs/reports/`, `docs/audits/`, `docs/lld/done/`) found no import from surviving code. The hits were prose and the four test files deleted here.
- `tools/fix_gemini_ack.py` failed this check and stays: its target is not finished.
- After the deletion, a check of every tracked file name, outside the generated records, against the 70 private repository names found nothing under `tools/`. Its two matches are the ordinary words in `.unleashed.json` and a `maintenance` idea file.

## Tiers on this branch

| Tier | Result |
|---|---|
| unit | 13,164 passed, 0 failed, 66 skipped, 7 xfailed |
| `tests/unit/test_loud_failure_check.py` | passes at the new ceiling of 118 |
| `tests/unit/test_fail_open_audit.py` | passes |

The count is lower than the 13,210 on `main` because four test files were deleted with their scripts, and the tests a tool's removal retires went with it.

The integration and e2e tiers run in CI on the PR. Nothing here touches a graph, a node or a route.
