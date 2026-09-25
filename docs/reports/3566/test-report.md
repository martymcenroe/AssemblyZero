# Test Report: the bench (#3566)

## New tests

`tests/unit/test_profile_bench.py`:

| Class | Owns | What it pins |
|---|---|---|
| `TestTheFlag` | T1 | the roll, `orchestrate.py`, the three standalone tools and `compare_profiles.py` show the flag in `--help`; the roll forwards `--models` onto the detached relaunch's argv; the START line names the profile (`claude`, the default `gemini`, `mock` under `--mock`); an unloadable profile stops the roll with 91 before any issue |
| `TestResumeSafety` | T2 | a resume recorded under `gemini` and launched under `claude` is refused naming both and `--fresh`; the same profile resumes; state from before profiles and no state are not refused; the orchestrator keeps a resumed snapshot |
| `TestTheComparison` | T3 | two rolls of the real spec graph, under `gemini` and `claude`, plus recorded calls, give one table with the ten columns and two rows, in the order asked; verdicts, revisions, calls per seat, failures by node (the graph halts without an LLD) and answer-key coverage (#4 is in the key) are counted; the default output lands under `data/speedrun/comparisons/` |
| `TestTheRunbook` | T4 | every tool the runbook names answers `--help`; it states the audition cost |

Run-log rows naming the profile (T2's last clause) are pinned by #3565's `TestTheProfileOnEveryRow`.

## Runs

Full unit tier, from the worktree with the main checkout's interpreter, no other pytest session running:

```
4 failed, 10779 passed, 21 skipped, 7 deselected, 5 xfailed, 13 warnings in 700.96s (0:11:40)
FAILED tests/unit/test_runbook_0952_flags.py::TestTheFlagTableMatchesTheLauncher::test_no_operator_facing_flag_is_undocumented
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_it_refuses_only_the_two_runs_that_moved_their_tests
FAILED tests/unit/test_section_ten_carries_tests.py::TestAgainstEveryRecordedDraft::test_every_other_draft_passes
FAILED tests/unit/test_solo_runbook.py::test_the_runbook_documents_every_launcher_flag
```

Two failures were the runbook's own guards doing their job: runbook 0952's flag table must name every launcher flag, and `--models` was new. The table now documents it, and both tests pass (`test_runbook_0952_flags.py test_solo_runbook.py test_profile_bench.py`: 48 passed). The other two are #3468's pair, red on `main`.

Found on the way and filed as #3575: `--help` on the LLD tool crashes on a cp1252 pipe, because its `--retry-policy` help carries a non-ASCII arrow. `TestTheFlag` runs its subprocesses with `PYTHONIOENCODING=utf-8` until that is fixed.
