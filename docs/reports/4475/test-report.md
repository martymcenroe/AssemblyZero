# Test report: #4475, #4476, #4479

## Changed tests

- `tests/unit/test_resume_commands_resolve.py::TestEveryToolTakesItsCommand` (new): `test_t2_the_tools_own_parser_accepts_the_line` hands each tool in `RESUME_COMMANDS` its line through its real parser (#4475 T2); `test_t1_a_requirements_issue_run_names_its_type` (#4475 T1); `test_no_other_tool_is_given_a_type`.
- `tests/unit/test_run_requirements_workflow_loud_failure.py::TestHelpersRaise::test_4476_resume_says_it_runs_the_brief_again_from_the_start` (new, #4476 T1).
- `TestHelpersRaise::test_4476_resume_never_opens_a_checkpoint_database` (new, #4476 T2): a junk database no longer stops the run.
- `test_118_an_unreadable_checkpoint_database_stops_the_resume` and `test_118_a_database_with_no_checkpoint_is_a_plain_no` are removed, because `checkpoint_exists` is. The existing `nothing to resume` test still holds #4476 T3.
- `tests/unit/test_halt_files_by_repository.py::TestBriefRunsHaveKeysOfTheirOwn::test_a_brief_runs_evidence_names_the_brief_not_issue_zero` (new, #4479 T1), through a real HALT node.
- `TestBriefRunsHaveKeysOfTheirOwn::test_an_issue_runs_evidence_keeps_its_heading` (new, #4479 T2).

## Runs, 2026-11-01

- The new tests against the old source, set aside with a named stash and restored after: 5 failed, 116 passed. The five are #4475's `test_t2[requirements]` and `test_t1`, #4476's two, and #4479's T1.
- Full `tests/unit` suite through `tools/test-gate.py`, on the fix: 13458 passed, 66 skipped, 7 deselected, 7 xfailed in 16m 17s.
- `ruff check` on the six changed Python files: 28 findings on this branch and 28 on `main`.

HALT routing does not change, so the unit tier is the tier the order asks for.
