# Implementation report: #4706

Unit tests handed fake absolute paths under `/tmp` to code that writes. On Windows `/tmp/repo` is `C:\tmp\repo`, a folder at the root of the drive; on Ubuntu it is the system's temporary directory. Found on the C: drive on 2026-11-11: `C:\tmp\repo\.az-best-iteration\best-iteration`, last written at 5:39 AM Central, inside that morning's scheduled dependabot review run of the suite. This complements the drive-root guard of PR #4707 (see #4707), which watches `/nonexistent`, `/fake`, `/path` and `/c` and no `/tmp` path.

## How the leaks were found

A discovery-only audit hook (not shipped) recorded every write a full Ubuntu run made outside the checkout, pytest's `tmp_path` store and `~/.cache`, on 2026-11-11 from 12:35 to 1:02 PM Central: 1443 distinct (test, event, path) rows. Each row under a fake root was then read against its test and its writer. The grouped trace is posted on #4706.

## The tests

| Test | Fake path | Writer | Change |
|---|---|---|---|
| `test_exit_code_verify_phases.py`, `test_count_plateau_three_strikes.py`, `test_failure_feedback.py`, `test_freeze_tests_symmetry_break.py`, `test_green_cap_grace.py`, `test_verify_green_stagnation.py`, `test_verify_green_stagnation_both_branches.py`, `test_verify_green_tests_improved.py` | `repo_root="/tmp/repo"` | `verify_phases.py`: the best-iteration snapshot under `repo_root/.az-best-iteration`, and the removal of `repo_root/report.json` (131 writes in the trace) | an autouse fixture points the module's state repo at `tmp_path / "repo"`; the implementation file keeps its place under it |
| `test_collection_failure_is_named.py::TestItReachesTheHalt::test_the_error_message_carries_the_detail` | `repo_root="/tmp/repo"` | the same `report.json` removal | the state's repo is `tmp_path / "repo"` |
| `test_issue_161.py::test_020` | `/tmp/audit` | the test's own `mkdir` and `rmdir` | `tmp_path / "audit"` |
| `test_scaffold_tests_multifw.py`, four tests | `/tmp/test_project` | `determine_test_file_path` makes the test file's folder | `tmp_path / "test_project"` |

No assertion changed. The inventory test (`/path/that/does/not/exist`) is left to PR #4707's change, which this branch takes from `main`.

Read and left alone: a fake `/tmp` path that is only a value (argument parsing, a state dict the test inspects), only read, or handed to code that checks the folder exists before writing, which no test can now create.

## The guard

`tests/fake_root_guard.py` installs a `sys.addaudithook` hook from `pytest_sessionstart`. It judges every write-mode `open`, `os.open` with write flags, `mkdir`, `remove`, `rmdir`, `rename`, `shutil` copy, move and `rmtree`, and `sqlite3.connect`. A write whose path lies inside a watched root is refused with `PermissionError` and recorded with the running test's node id, kept by `pytest_runtest_logstart` and `pytest_runtest_logfinish`. `pytest_sessionfinish` fails the session with every test and path named, so a refusal the code under test swallows still fails the run.

Watched on both platforms: `/tmp/repo`, `/tmp/audit`, `/tmp/test_project`, `/nonexistent`, `/fake`, `/path`, and below `/dev/null` (on Ubuntu `/dev/null` itself is the null device). On Windows, all of `C:\tmp` and `C:\dev` as well, since nothing of the system's lives there; the system temporary directory stays allowed. On Ubuntu `/tmp` is where `tmp_path` and `tempfile` write, so only the named folders are watched there, and a new fake `/tmp` name is caught by the Windows run.

Why a hook beside the snapshot guard rather than more snapshot roots:

- It sees the attempt, so a write Ubuntu refuses fails the Ubuntu run too.
- It names the test that wrote.
- It watches this process only, so another checkout's suite writing `/tmp/repo` at the same time (one did while this was written) is never taken for this run's leak.
- The refused write never reaches the drive.

The snapshot guard keeps what the hook cannot see: a child process that is not a pytest one, and a folder created outside Python. A child pytest that loads this suite's `conftest.py` arms its own hook.

## Found on the way, filed separately

- see #4708: tests write into the operator's home (the telemetry buffer and the hourglass history).
- see #4709: four orchestrator tests leave their triage brief in the system's temporary directory.

## Lint

`ruff check .` finds 2626 on this branch before the merge and 2626 on `main` at 6b119a45; every changed file's findings match its `main` version, and the two new files are clean.
