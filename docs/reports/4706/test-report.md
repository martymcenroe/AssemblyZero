# Test report: #4706

Run in Ubuntu (WSL) in the worktree's own poetry environment.

## The guard's own tests

`tests/unit/test_fake_root_guard.py` (new, 25 tests):

- what counts as a write: write modes of `open` and the flags of `os.open`, `mkdir`, `remove`, both ends of a rename, a copy's destination only; reads and listing events are not;
- which paths are leaks: inside a root and the root itself; not a path that only shares a prefix (`fakeroot` against `fake`); `/dev/null` itself is not, below it is; an allowed store inside a root is not; a relative path or a file descriptor is never judged;
- the roots on each platform: Ubuntu watches the named folders and leaves its `/tmp` and `/dev` alone; Windows watches all of `/tmp` and `/dev`;
- the suite runs armed: the suite's own hook watches this machine's roots and refuses a probe raised with `sys.audit`, which touches no file whether the hook is armed or not (marked `windows_paths`, so the Windows job runs it too);
- end to end: a child pytest whose guard watches a folder under `tmp_path` runs a test that writes there and swallows the refusal; the session exits 1, names the test and the path, the test itself passes, and the file never exists. A child that only reads the root exits 0.

They cannot pass before the change: the module did not exist.

## Fails before, passes after

On `main`, each changed test writes into its fake root: the discovery trace on #4706 lists 131 writes under `/tmp/repo` from the nine N5 test files, 2 under `/tmp/audit` and 4 under `/tmp/test_project`. With the guard armed and the tests unchanged, `test_exit_code_verify_phases.py` gives 7 failed, 17 passed: the refusal of `/tmp/repo/report.json` halts N5. With the change, the eight N5 files that gained the fixture, run with `test_cov_target_resolution.py`, gave 103 passed, and the guard reported nothing.

## Targeted

`test_collection_failure_is_named.py`, `test_scaffold_tests_multifw.py`, `test_issue_161.py` and `test_inventory_node.py` (this branch's earlier version of T060, since replaced by `main`'s): 53 passed, before the merge of `main`.

## Full suite

FULL_SUITE
