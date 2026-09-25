# Test Report — The unit suite stays out of the operator's home state (#3531)

## What was run

From the main checkout's venv, against this worktree
(`PYTHONPATH=<worktree>`, `--rootdir <worktree>`, `-p no:cacheprovider`).

The six test files that patch or read the guarded paths:

```
tests/unit/test_home_state_guard.py tests/unit/test_halt_node.py tests/unit/test_state_persistence.py
tests/unit/test_path_constants_absolute.py tests/unit/test_factory_report.py tests/unit/test_lld_mock_is_offline.py
88 passed, 1 warning in 12.53s
```

The full unit tier, to completion, with no other pytest session running:

```
tests/unit
2 failed, 10651 passed, 21 skipped, 7 deselected, 5 xfailed, 14 warnings in 682.44s (0:11:22)
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_it_refuses_only_the_two_runs_that_moved_their_tests
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_every_other_draft_passes
```

The two are #3468's pair (a unit test reading another repo's working tree),
red on `main` before this change. **The session guard printed nothing**: the
real `~/.assemblyzero/workflow_state/` and
`~/.claude/assemblyzero/workflow-audit.jsonl` were byte-identical at session
end, which is the acceptance criterion.

```
poetry run ruff check tests/conftest.py tests/home_state_guard.py tests/unit/test_home_state_guard.py tests/unit/test_path_constants_absolute.py
All checks passed!
```

## The guard caught a real write, once, and it was the right one

The first full-tier run of this change reported:

```
FAIL: the suite wrote into the operator's home state (#3531). Redirect the writer through tests/home_state_guard.redirect:
  changed: C:\Users\mcwiz\.claude\assemblyzero\workflow-audit.jsonl (size 24111886 -> 24114687)
```

The 2,801 bytes were traced by the audit log's own `target_repo` fields to
`test_load_lld_accepts_spec` and `test_a_full_mock_run_leaves_the_origin_unchanged`,
run at 12:05 AM from a **different worktree** (the #3548 test run, which did
not carry this fix) while the tier was in flight. A diagnostic run of the
tier with `-x` and no concurrent session, and the second full run above,
both printed nothing. The guard measured the file, not the process, and
reported a true change; the writer was the concurrent unfixed session.

## The new tests fail on the old conftest

`tests/conftest.py` and `tests/unit/test_path_constants_absolute.py` were
stashed by name and `tests/home_state_guard.py` moved aside:

```
tests/unit/test_home_state_guard.py tests/unit/test_path_constants_absolute.py
1 error in 0.25s
ERROR tests/unit/test_home_state_guard.py   (ModuleNotFoundError: tests.home_state_guard)
```

## What each new test shows

| Test | Shows |
|---|---|
| `test_the_four_bindings_point_under_tmp_path` | Requirement 1: `state_persistence.STATE_DIR`, `resume_contract.STATE_DIR`, `halt_node.STATE_DIR` and `testing_audit.WORKFLOW_AUDIT_FILE` all resolve under the test's `tmp_path`. |
| `test_a_halt_snapshot_lands_under_tmp_path_and_home_is_untouched` | `save_state_snapshot("testing", 4242, ...)` writes `testing-4242.json` under `tmp_path`, and the real paths' snapshot is unchanged across the write. |
| `test_a_resume_contract_lands_under_tmp_path` | `contract_path("testing", 4242)` is under `tmp_path`. |
| `test_the_halt_node_binding_is_the_same_directory` | The two `STATE_DIR` copies agree. |
| `test_an_audit_append_lands_under_tmp_path_and_home_is_untouched` | `log_workflow_execution` appends under `tmp_path`, and the real paths' snapshot is unchanged. |
| `test_a_test_that_patches_the_binding_itself_still_wins` | The existing per-test patches keep working. |
| `test_the_guarded_paths_are_the_two_the_issue_names` | The guard watches exactly the two paths. |
| `test_a_missing_root_contributes_nothing` / `test_the_snapshot_sees_added_removed_and_changed_files` / `test_an_unchanged_tree_reports_nothing` | The snapshot and diff on temporary trees. |
| `test_the_real_bindings_are_remembered_before_the_redirect` | `real_bindings()` holds the design values, for `test_path_constants_absolute.py`. |
| `test_the_hooks_are_wired_in_conftest` | `pytest_sessionstart` and `pytest_sessionfinish` exist. |
| `test_a_session_that_writes_into_home_fails_with_the_path_named` | Requirement 2, end to end: a subprocess pytest session with `HOME` and `USERPROFILE` under `tmp_path`, one test writing a halt snapshot by the raw path, exits 1 with `wrote into the operator's home state` and `testing-1.json` named. |

## Not verified

- The integration and e2e tiers were not run. The fixture and the hooks
  apply to them too, but nothing in this PR exercises them.
