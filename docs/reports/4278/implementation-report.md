# Implementation report: #4278

## The defect

`tests/tools/` held 15 test files, 559 tests, with no tier marker. CI runs `tests/unit/` whole and runs `tests/` three more times with `-m integration`, `-m e2e` and `-m adversarial`, so no CI step collected them, and neither did a local tier. They ran only under a bare `pytest`. The investigation behind this, with the counts, is on #4756, and the two issues land in one pull request.

## The move

`git mv tests/tools tests/unit/tools`, the package's `__init__.py` with it. The unit tier now collects all 559 tests, locally and in CI. `.github/workflows/ci.yml` is unchanged: its unit step already runs `tests/unit/`.

`tests/unit/test_dependabot_review.py` and `tests/unit/tools/test_dependabot_review.py` share a basename. Both folders are packages, so pytest imports them as `tests.unit.test_dependabot_review` and `tests.unit.tools.test_dependabot_review` and the names do not collide.

## Parent-folder counts

Each file that finds the repository by counting parent folders now counts one more, so it reaches the folder it reached before:

| File | Line | Before | After | Reaches |
|---|---|---|---|---|
| `test_backfill_issue_audit.py` | 14, 37 | `.parent.parent.parent` | `.parent.parent.parent.parent` | `tools/`, `tools/fixtures/` |
| `test_claude_usage_scraper.py` | 23, 27 | `parents[2]` | `parents[3]` | the repository root, `tools/claude-usage-scraper.py` |
| `test_claude_usage_scraper.py` | 270, 271 | `parents[1] / "fixtures"` | `parents[2] / "fixtures"` | `tests/fixtures/scraper/` |
| `test_dependabot_review.py` | 20 | `.parent.parent.parent` | `.parent.parent.parent.parent` | `tools/` |
| `test_dependabot_worktree_guard.py` | 17 | same | same | `tools/` |
| `test_fleet_delete_pr_sentinel.py` | 16 | same | same | `tools/` |
| `test_fleet_remove_cerberus_secrets.py` | 21 | same | same | `tools/` |
| `test_governance_suite_no_caller.py` | 22 | `parents[2]` | `parents[3]` | `tools/` |
| `test_land_staged_workflow.py` | 19 | `.parent.parent.parent` | `.parent.parent.parent.parent` | `tools/` |
| `test_land_workflow_plan.py` | 22 | same | same | `tools/` |
| `test_mine_quality_patterns.py` | 33 | same | same | `tools/` |
| `test_modernize_dependencies.py` | 16 | same | same | `tools/` |
| `test_pat_session.py` | 20 | same | same | `tools/` |
| `test_require_status_check.py` | 20 | same | same | `tools/` |
| `test_sentinel_migrate.py` | 16 | same | same | `tools/` |
| `test_verify_encrypted_secret.py` | 15 | `parents[2]` | `parents[3]` | `tools/` |

A grep of the 15 files for `__file__` finds no other file-relative path. Their remaining path strings, such as `.claude/hooks/...` or `tests/test_a.py`, are relative to the working directory or are data, and a move does not change them.

## References that followed the move

- `pyproject.toml`: the per-file `E402` ignore names `tests/unit/tools/test_claude_usage_scraper.py`.
- `tests/unit/test_dependabot_network_guard.py`: `KNOWN_LOADERS` names the two files at `tests/unit/tools/`. The check walks all of `tests/`, so it still finds them.
- `tests/unit/test_cerberus_after_auto_review.py`: the retired `test_audit_cerberus_health.py` is asserted absent from `tests/unit/tools/`, the folder where it would now live.
- `docs/adrs/0216-in-process-classic-pat-decryption.md`: names `tests/unit/tools/test_pat_session.py`.
- Comments that described the old layout as present fact: `tests/unit/test_pat_session_terminal.py`, `tests/unit/test_scraper_import_safety.py` and `tests/unit/test_verify_encrypted_secret_no_disclosure.py`. Each now says why its tests were put in `tests/unit/` and where the sibling file lives now.

Left as written, because they record history: the sentence in `tests/unit/test_scraper_import_safety.py` and the comment at `tools/claude-usage-scraper.py:31` saying pytest died collecting `tests/tools/` on Linux (#3452), and the LLDs and specs under `docs/lld/` that planned files in `tests/tools/`.

## The guard

`tests/unit/test_every_test_file_runs_in_a_tier.py`, shared with #4756, fails when a test file outside `tests/unit/` carries no tier marker and is not on its named list. Run against a copy of HEAD's `tests/` tree, it names all 15 files of the old `tests/tools/`. The report on #4756 describes it.

## Tests

On Ubuntu, 2026-11-14, through `tools/test-gate.py`, so the unit tier's conftest applies:

- `tests/unit/tools/`: `559 passed`.

No moved test needed a change beyond its path. The unit conftest's autouse fixtures apply to these tests now, and none of them failed under them.

`ruff check` on each moved file, compared with its text at HEAD under the new name: the same findings, none added.
