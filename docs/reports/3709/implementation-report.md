# Implementation Report: the rmtree guard judges the commit, not the disk (#3709)

## What was wrong

`tests/unit/test_rmtree_sites_are_gated.py` collected the files it scans with `(ROOT / sub).rglob("*.py")`, so the #3518 guard saw every Python file on disk under `assemblyzero/` and `tools/`, tracked or not. On a checkout carrying an ignored, untracked script with its own `shutil.rmtree`, the full unit tier failed two of the guard's tests while CI on the same SHA was green.

## Changes made

1. `_tracked_python_files(root)` enumerates the scanned tree with `git ls-files -z -- assemblyzero/*.py tools/*.py` from `ROOT`. The `sites` fixture walks that list.
2. `test_the_walk_judges_the_commit_not_the_disk`: in a temporary git repository with one tracked `tools/tracked.py` and one excluded `tools/local.py` that calls `shutil.rmtree`, the walker returns only the tracked file.
3. The literal count in `test_the_walk_sees_the_sites_it_should` stays: a new allowlist entry still has to be counted by hand, which is the friction that test exists to apply.

## Not done here

Requirement 3 of the issue (the same change for every other guard that walks source with `rglob` or `os.walk`) is counted and filed as its own issue; the count is on #3709.
