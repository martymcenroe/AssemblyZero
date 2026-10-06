# Test Report: the rmtree guard judges the commit, not the disk (#3709)

## Before the change

Full unit tier on Ubuntu, `main` at `5af5af30`, on a checkout carrying an excluded local script under `tools/`:

```
FAILED tests/unit/test_rmtree_sites_are_gated.py::TestEveryRmtreeNamesItsGate::test_no_site_is_missing_from_the_allowlist
FAILED tests/unit/test_rmtree_sites_are_gated.py::TestEveryRmtreeNamesItsGate::test_the_walk_sees_the_sites_it_should
2 failed, 10757 passed, 68 skipped, 7 deselected, 6 xfailed, 12 warnings in 735.17s (0:12:15)
```

## After the change

- `PYTHONPATH=<worktree> <python> -m pytest tests/unit/test_rmtree_sites_are_gated.py -q -p no:cacheprovider`: `12 passed`, including the new `test_the_walk_judges_the_commit_not_the_disk`.
- Full unit tier in the worktree: see the closing comment on #3709 for the line.

## What the new test proves

A file git does not track, however it is excluded, is never scanned, so the guard's verdict is a property of the commit alone.
