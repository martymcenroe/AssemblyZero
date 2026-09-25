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

FULL_TIER_RESULT
