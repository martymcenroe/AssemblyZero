# Test report: #4703, #4704, #4705

Run in Ubuntu (WSL) in the worktree's own poetry environment.

## Fails before, passes after

- `tests/unit/test_inventory_node.py::TestGracefulFailure::test_nonexistent_repo_path` and `::test_repo_path_that_is_a_file_raises`: with `assemblyzero/nodes/inventory.py` held at `origin/main`, both fail (2 failed, 3 passed in the class); with the change, both pass.
- `tests/unit/test_drive_root_guard.py` (new, 11 tests): the closed list of four roots; a missing root contributes nothing; an unchanged tree reports nothing; a root that appears is reported with the file under it; an empty folder added under an existing root is reported; a removed file and an appended file are reported; a same-length rewrite is reported; a root that is a link is recorded and never walked; the roots sit at the drive root; the conftest hooks, driven with the guard pointed at a folder under `tmp_path`, fail the session naming a folder made between start and finish, and leave a session that wrote nothing there alone. They cannot pass before the change: the module did not exist.

## Targeted

`tests/unit/test_drive_root_guard.py`, `tests/unit/test_inventory_node.py`, `tests/unit/test_orchestrator_repo_targeting.py`, `tests/unit/test_home_state_guard.py` and `tests/unit/test_orchestrator_lineage.py`: 75 passed.

## On Windows

Not run here: Windows interop is off in this Ubuntu session. On the next Windows run, the scheduled dependabot review's included, the session guard fails if any test still writes into `C:\nonexistent`, `C:\fake`, `C:\path` or `C:\c`, naming the paths.

## Full suite

`poetry run pytest -q --tb=short` in Ubuntu on this branch: 14976 passed, 18 failed, 66 skipped, 93 deselected, 7 xfailed, in 27 min 10 s. Every failure is in a file this branch does not touch, and each is already failing on `main` and tracked:

- 16 in `tests/test_auto_reviewer_wait_loop.py`: the workflow step they read is gone from `auto-reviewer.yml` on `main` (#4528).
- `tests/integration/test_orchestrator_graph.py::TestOrchestrateFullPipeline::test_full_pipeline_success`: the graph recursion limit (#4529, #3737).
- `tests/test_universal_claude_md.py::test_adr_references_resolve`: another repository's ADR numbers read as this one's (#3730).

One test from each group was run on `main` (6b119a45) in the primary checkout: 3 failed, the same three.
