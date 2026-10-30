# Test Report: the scaffold's branch is main on WSL (#4185)

## New test

`tests/unit/test_new_repo.py::test_the_scaffold_branch_is_main_with_no_git_configuration` runs `main()` with `--no-github`, takes the one `git init` command it issues, and runs that command for real in a fresh directory with `GIT_CONFIG_GLOBAL` pointing at an empty file and `GIT_CONFIG_NOSYSTEM=1`, where git's own default branch is `master`. `git symbolic-ref --short HEAD` must print `main`.

With `tools/new_repo.py` reverted to `origin/main` (a named-path stash), it fails: `AssertionError: assert 'master' == 'main'`. With the change, it passes.

## Full local suite

```
poetry run python tools/test-gate.py tests/unit/ -q
11173 passed, 66 skipped, 7 deselected, 6 xfailed
```

## Lint

Ruff counts unchanged against `origin/main`: `tools/new_repo.py` 23, `tests/unit/test_new_repo.py` 15.

## Not run by an agent

The end-to-end run from WSL is the operator's (#4182), since an agent never runs a script that decrypts the classic PAT.
