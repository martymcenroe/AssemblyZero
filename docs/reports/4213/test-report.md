# Test Report: #4213

- Issue test 1: `tests/integration/test_cascade_hook_integration.py::TestClaudeMdCascadeRule` passes against the new `CLAUDE.md` (the run's working directory was the worktree, so the test read the changed file).
- Issue test 2: `tests/unit/test_merge_instructions.py`, `tests/unit/test_archive_keeps_venv.py` and `tests/unit/test_archival_tool_passes_the_guard.py` pass; the lineage command and the `[skip ci]` rule are intact. With `tests/unit/test_lint_per_repo_claude_md.py` and the cascade file: 70 passed.
- Issue test 3: full unit tier on the branch (`pytest tests/unit/`): 11228 passed, 66 skipped, 7 deselected, 6 xfailed, in 10m32s.
- Issue test 4: the fleet's agy rules generator with `--check` on the worktree reports `ok` after `--apply`, and reported a changed source before it.
- Acceptance 2: `git diff` touches only the Cascade Prevention and Standing Orders sections of `CLAUDE.md` and the regenerated `.agents/rules/repo-claude-md.md`.
