# Test report: #1655, #4443

## Changed tests

- `tests/unit/test_resume_commands_resolve.py::TestABriefRunResumesByItsBrief` (new): the printed command is exact; the tool's real `parse_args` reads it as a resume of that brief; `run_resume_workflow` runs from it and hands the brief on, inside the repository and outside it; a path with a space stays one argument; an issue number wins over a brief; a run with neither says so, for every workflow; and only the requirements tool is ever given a brief.
- `tests/unit/test_halt_files_by_repository.py::TestBriefRunsHaveKeysOfTheirOwn::test_the_halted_plan_resumes_the_brief_not_issue_zero` (new, #4443 T1): a real HALT node run. The saved plan names the brief and no `--issue`, and the printed block shows `Brief:` and no `#0`.
- `TestBriefRunsHaveKeysOfTheirOwn::test_a_halted_issue_run_still_resumes_its_issue` (new, #4443 T2): the same through a halted issue run.
- `tests/unit/test_docs_name_no_deleted_gemini_tool.py` (new, #1655): reads the index, the inventory, every runbook, every skill doc and the two wiki pages for the deleted tool's name, and asserts the tool and its three docs are gone. Its first run failed on one inventory row, which is how that row was found.

## Runs, 2026-11-01

- The three resume and halt test files: 72 passed.
- `tests/unit/test_docs_name_no_deleted_gemini_tool.py`: first run 1 failed, 92 passed, on the inventory row; passing in the full run after that row was removed.
- Full `tests/unit` suite through `tools/test-gate.py`: 13448 passed, 66 skipped, 7 deselected, 7 xfailed in 16m 02s.
- Runbook 0957's new command, run from the probe directory with `gemini-3.8-flash-high`: `status SUCCESS`. The model answered that it had no shell or file tools, and no `probe.txt` was written.
- `ruff check` on the four changed Python files already on `main`: 18 findings on this branch and 18 on `main`. The new test file has none.
