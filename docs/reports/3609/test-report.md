# Test Report: derive the Projects root, never spell it (#3609, #3727)

## Tests added

- `tests/unit/test_no_spelled_projects_root.py`, the guard (requirement 3; T1 and T2):
  - `test_no_tracked_file_spells_the_projects_root` checks every tracked file under `assemblyzero/`, `tools/`, `tests/` and `.claude/`. Python sources are tokenized, and string tokens are checked both as written and decoded, so escaped forms are caught; comment tokens are checked too. Other text formats are searched as fixed strings. The set of five spellings is closed.
  - T2: `test_python_guard_catches_each_spelling_in_strings_and_comments` (five cases), `test_python_guard_catches_the_escaped_form_by_decoding`, `test_python_guard_ignores_code_that_derives_the_root`, and `test_text_guard_catches_each_spelling` (five cases).
- `tests/unit/test_projects_root.py`:
  - `REPO_ROOT` is the checkout and `PROJECTS` is its parent;
  - six drive spellings give the same three;
  - a path on no drive gives one;
  - a longer top-level directory is not a drive.

## Tests changed

- `tests/unit/test_repo_drift_check.py`: the handoff texts are built from the checker's own derived root, so they hold on a CI runner as well as on either side of the operator's machine.
- `tests/unit/test_lint_per_repo_claude_md.py`: `test_marker_9_hardcoded_user_path` (renamed), plus a corrected comment on why the lean template passes.
- `tests/unit/test_office_owner_file_ignores.py`: the global gitignore is whatever `git config --global core.excludesFile` names. It now runs on Ubuntu, where it used to be skipped.
- `tests/unit/test_campaign_timing_dashboard.py`: boostgauge is `PROJECTS / "boostgauge"`. It also runs on Ubuntu now.
- Test data in nine files uses a `dev` user instead of the operator's.

## Runs, 2026-10-06

- New and changed tests: `test_no_spelled_projects_root.py` and `test_projects_root.py`, 24 passed. `test_office_owner_file_ignores.py` and `test_campaign_timing_dashboard.py`, 42 passed, none skipped. `test_repo_drift_check.py`, 29 passed. The other tests of the changed tools (`test_lint_per_repo_claude_md`, `test_issue_104`, `test_verdict_analyzer_scanner`, and the transcript-cleaner tests): 162 passed in total.
- `tests/test_universal_claude_md.py` now runs on Ubuntu: 5 passed, 1 failed (`test_adr_references_resolve`, filed as #3730; not in the unit tier).
- Full `tests/unit` tier after the rebase, with the machine quiet: 10862 passed, 66 skipped, 7 deselected, 6 xfailed in 12m 24s. Two fewer skips than `main`: the global-gitignore and dashboard tests now run on Ubuntu.
- `ruff check` on the changed Python files: 185 findings on this branch against 186 on `main`, with none new. The new files are clean.
- `tools/audit_fail_open.py --check --strict` after the rebase: `PASS -- 311 files, 9545 sites examined, no new fail-open, denominator matches.` The baseline was regenerated for the moved denominator only (one new module); its 440 frozen sites are unchanged. `tools/audit_halt_sites.py --check`: PASS.

## Rehearsal (requirement 4, T3), Ubuntu side

`--mock` LLD and implementation runs from this branch against a throwaway target with a bare origin, under a gitignored directory of the main checkout:
- LLD: exit 0, `Status: APPROVED`, `[mock] 1 file(s) written; no branch cut, no PR opened.`, `[run] left in place (0):`.
- Implementation: exit 0, `Status: SUCCESS`, the run's worktree removed, `[run] left in place (0):`.
- Snapshots before and after are identical: target status, worktrees, branches, the origin's refs, and the listings of `~/.assemblyzero`, `~/.assemblyzero/workflow_state` and `~/.claude/assemblyzero`.

The Git Bash half is the operator's. The command is in #3609.
