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

Pending; recorded in the next commit.
