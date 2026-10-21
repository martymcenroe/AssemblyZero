# Test Report: new_repo.py from WSL (#4179, #4180)

## New and changed tests

| Test | Covers |
|---|---|
| `tests/unit/test_new_repo_safety.py::TestGpgFindsTheTerminal` (2) | A real process on a pseudo-terminal calls `detach_stdin()` and opens `classic_pat_session`, with a stand-in `gpg` first on `PATH`. The stand-in sees `GPG_TTY` equal to the terminal's name, and its own stdin is not a terminal. With no terminal, `GPG_TTY` stays empty. #4179 test 1. |
| `tests/unit/test_pat_session_terminal.py::TestNoPromptAdvice` (2) | A real run with no terminal, through a stand-in `gpg` that fails as gpg does, is told it has no terminal, and the message does not mention Git Bash. With `GPG_TTY` set, the message names the terminal and `pinentry-program`. #4179 test 2. |
| `tests/unit/test_pat_session_terminal.py::TestGpgOutputStaysOffTheTerminal` (4) | Each of the four decrypt sessions captures gpg's output. #4179 requirement 4. |
| `tests/tools/test_pat_session.py::TestNoPromptStopsAtOnce` | The refusal must no longer mention Git Bash; the assertion is inverted. |
| `tests/unit/test_assemblyzero_config_derived.py` (3) | Off Windows, `C:\Users\dev\Projects\x` comes back unchanged with no warning; `C:\Users\..\..\Windows` comes back `C:\Users\Windows` with the traversal warning; the Windows format is the Windows spelling. #4180 tests 1 and 2. |
| `tests/unit/test_new_repo.py::test_a_wsl_project_root_writes_windows_paths_in_windows_form` | The real config, given a `/mnt/c` root, yields `PROJECT_ROOT_WINDOWS` and `inherit_from` in `C:\` form. #4180 test 3. |

The sanitizer tests were first added to `tests/unit/test_assemblyzero_config.py`, where they were skipped: that whole file is gated to Windows (#1601). They were moved to `test_assemblyzero_config_derived.py`, which runs on Linux.

## Proof the tests see the defects

With only the three tool files reverted to `origin/main` (a named-path stash), the 15 new or changed tests ran: 10 failed, 5 passed. The 5 that pass pin behavior that was already right: four check that gpg's output is captured, and one that nothing is recorded without a terminal.

## Full local suite

```
poetry run python tools/test-gate.py tests/unit/ tests/tools/ -q
3 failed, 11642 passed, 66 skipped, 7 deselected, 6 xfailed
```

None of the 3 is in a file this change touches:

- `tests/unit/test_cascade_detector.py::TestDetectionLatency::test_typical_input_latency` passes when run alone (load-sensitive).
- `tests/tools/test_dependabot_review.py::TestRunJsGate`, two `node_modules` tests, fail on every run. Tracked in #3631; recorded there on 2026-10-21 that they fail on Ubuntu too.

## Lint

Per-file ruff counts against `origin/main`, unchanged: `tools/new_repo.py` 23, `tools/_pat_session.py` 5, `tools/assemblyzero_config.py` 3, `tests/unit/test_new_repo.py` 15, `tests/unit/test_new_repo_safety.py` 11, `tests/tools/test_pat_session.py` 5, `tests/unit/test_assemblyzero_config_derived.py` 2. The new `tests/unit/test_pat_session_terminal.py` has none.

## Not run by an agent

#4179 test 3, the operator's end-to-end run from WSL, is carried by #4182.
