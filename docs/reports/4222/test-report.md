# Test Report: #4222

`tests/unit/test_profile_bench.py::TestTheRunbook`:

- **T1** `test_it_says_what_fresh_deletes`: the runbook no longer says "never deleted", and it names the PR closing and the branch deletion on origin.
- **T2** `test_the_audition_copy_is_the_file_the_command_rolls`: the audition command's `--models` path ends in `new-model.toml`, and the prose copies to that same file.
- The existing `test_every_tool_it_names_answers_help` and `test_it_states_the_audition_cost` pass unchanged. The added `git ls-remote` line is not a `poetry run python tools/` line, so the tool list is still `compare_profiles.py` and `speedrun_roll.py`.

`tests/unit/test_profile_bench.py`: 21 passed. Every CI tier in the worktree:

- unit: 11230 passed, 66 skipped, 6 xfailed, in 9 min 32 s
- integration: 64 passed, 7 skipped
- e2e: 19 passed

`ruff check` on the changed test file reports 6 findings, on lines 18 to 126. `main`'s copy of the file reports the same 6, so none is in the added lines.
