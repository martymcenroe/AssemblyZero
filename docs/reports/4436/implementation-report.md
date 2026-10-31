# Implementation Report: the green phase judges the lines a run changed (#4436, #4266)

The green phase graded whole files, so a run that changed a large existing module could never pass, whatever the model wrote. This blocked the first real run on any target that is not small and new. N5 now judges the lines the run added or changed against its base commit, for each framework, and a new file counts whole. `--coverage-target` now wins on every load path.

## What was built

- `assemblyzero/workflows/testing/changed_lines.py` (new): the run's base commit, the lines it changed, and which of them are executable.
- `assemblyzero/workflows/testing/coverage_report.py`: readers for coverage.py's JSON report and Istanbul's `coverage-final.json`, into one shape. `CoverageReportError` moved here so `jest_runner` can import the reader without a cycle; `base_runner` still exports it.
- `verify_phases.py`: both green paths judge changed lines. `coverage_achieved` is that figure, and the whole-file figure is printed and logged and decides nothing.
- `augment_tests.py`: N4c reads the lines N5 named, and tests those and no others. It no longer parses a report, so N5 is the report's one reader.
- `jest_runner.py`: Vitest and Jest ask for the per-line report, are told which files it must cover, and have their own thresholds switched off.
- `load_lld.py`: `resolve_coverage_target` decides the target for all three load paths and says where it came from.
- `stages.py` and `tools/run_implement_from_lld.py`: both entry points pass the base.
- ADR 0207, the 0102 template and the drafter's prompt now say changed lines.

## Design decisions

**Base commit.** The merge-base of HEAD with `origin/<base>` and `<base>`, whichever is nearer to HEAD. The orchestrator cuts its worktree from origin and the standalone tool from the local branch, and a commit on either is not the run's. Being a merge-base, it gives the same answer on a fresh cut, on a resume carved from a graveyard attempt, and on a seed branch, and the base branch moving on changes nothing. It is recomputed at each N5, so nothing goes stale.

A run in place has no such branch: its checkpoints move the branch it is on, so a merge-base would always read as nothing changed. The launcher freezes HEAD as `base_commit` for that case. On `--resume` it freezes nothing, because `app.stream(initial_state, config)` merges the state and today's HEAD would replace the checkpoint's commit. The measured branch is kept apart from `base_branch`, which is also the PR base: on an issue branch it is `origin/main`, which is no PR base.

No base halts. It never reads as no changed lines.

**Executable lines.** A line is executable when the coverage tool says so, so comments, blank lines, docstrings and excluded lines are in no denominator. coverage.py counts type-only Python lines as statements, so `python_line_facts` takes them out: `if TYPE_CHECKING:` bodies, `@overload`, bare annotations, and Protocol stubs. A later line of a multi-line statement is judged as that statement. For Istanbul that holds only for a statement that contains no other, because an `if` spans its body and a comment in a block belongs to no statement.

**Measured scope.** A module target no test imports is left out of coverage's report; a directory target reports it at zero. So each changed file's directory is added, a file no test reaches reads as a real zero with nameable lines, and only a file the project omits is absent, which halts (#2637). A run that changed no source measures the repository root, because a module target nobody imports collects no data and writes no report, and "nothing to judge" must come from a report that exists.

**R3.** `--cov-fail-under` was only half of it. `--cov-fail-under=0` also overrides a `fail_under` in the target's config. Vitest's `coverage.thresholds` and Jest's `coverageThreshold` would each end a run non-zero, and N5 halts on a non-zero exit with no failure, so both are switched off.

## Found by measuring a real run

Three defects surfaced only from running the gate or reading the real target, and each would have cost a paid run. Each now has a test.

1. **The run's own snapshots.** The audit directory sits in the worktree at `docs/lineage/active/{issue}-testing/`, and a checkpoint commits it. It holds `.py` copies of the run's source. To git those are new files, so from the second iteration every run was judged on them at zero: measured, 80.0% fell to 1.3%. The workflow's records, hidden directories and generated trees are not code under test.
2. **An untracked report blocks the landing.** The merge driver refuses a worktree with any untracked file, and a target need not ignore `.assemblyzero/`. The report leaves once read.
3. **`web/coverage/` is not ignored on the target that measured this defect**, so a checkpoint's `git add -A` would commit the reports into the run's PR. #4246 left that exposure for the summary on the assumption that projects ignore it; the per-line report is far larger. Both leave once read, and a run whose reports nobody reads has them removed in `run_tests`, because Jest writes them even when tests fail.

Other choices made along the way:

- `measured_branch` is separate from `base_branch`, or `origin/main` would have reached the merge driver as a PR base.
- A file that does not parse under the harness's Python halts. An earlier draft fell back to the report's lines, which is the partial result ADR 0236 forbids.
- The handler in `_verify_green_pytest_single` returns where it stands. An earlier draft fell through to a later halt, which the fail-open audit rightly refused. The two gate rows it touches swapped index.

## What was removed

The chain in `_verify_green_pytest_single` that guessed a scope from `files_to_modify` and test names is gone, with the halts that guarded it. The scope above always answers, so it was unreachable. Ledger 0908 rows 2387 and 2393 say so in place.

## Limits

- **No real Vitest run was made.** The shell guard refuses `node_modules/.bin/vitest`, because the npm shim contains an `echo`. The flags were read from the installed Vitest 3.2.7 and 4.1.7 CLI definitions, the report shape from the 4.1.7 v8 provider and a real Jest `coverage-final.json`, and the array-flag rule from Jest 29.7's `args.js`. A flag that does not work halts loudly as `COVERAGE MEASUREMENT FAILED`; it cannot pass silently.
- **A project's `omit` halts.** A changed file the target's coverage config omits is absent from the report, and that is indistinguishable from a broken measurement, so it halts rather than pass unjudged. Of the fleet's `pyproject.toml` files only one has an `omit`.
- **Sibling files.** A directory target reports every file in the directory, so an unparseable `.py` beside a changed file fails the report and halts, loudly, with coverage's reason.
- **Non-editable installs.** A directory target measures the source tree, so a target installed non-editable into site-packages would read zero. Worktrees are provisioned editable (#2637).
- **Istanbul continuation.** A changed continuation line of an `if` header is not judged, because an `if` holds its body. Its own first line and body are.

## Loud-failure compliance (standard 0034)

Every failure below is written at ERROR on stderr by `_halt_coverage_unreadable` (`verify_phases.py:3766`) or `_step_failed`, and routes to HALT, which alerts. None continues.

| Site | Failure | Logged with | Stops |
|---|---|---|---|
| `changed_lines.py:110,133,139,156,162,254,278,286` | git cannot run or fails; no base; a frozen commit is not an ancestor; a new file cannot be read | the repository, the ref, the exit code, git's stderr | `ChangedLinesError`, caught at N5 |
| `changed_lines.py:187,199,237,242` | a diff that cannot be read | the header or hunk | same |
| `changed_lines.py:430,443,479` | a source that does not parse here or cannot be read; a changed file absent from the report | the file, the cause, and what the report names | `CoverageReportError`, caught at N5 |
| `coverage_report.py:129,137,176,185,213,221,233` | a report missing, unreadable or malformed | the path and the cause | same |
| `jest_runner.py:191` | a report that cannot be removed | the path and the cause | same |
| `verify_phases.py:1602` | an earlier report cannot be cleared | the path and the cause | halts before the suite runs |
| `verify_phases.py:1617` | a read report cannot be removed | the path and the cause | `PhaseStepError`, then HALT |
| `verify_phases.py:2987,4026,4414` | what the run changed cannot be established, before the run | the framework and the cause | HALT, before the suite runs |
| `verify_phases.py:3072,4397,4450` | the report cannot be read, after the run | the framework, the cause, coverage's own reason | HALT |
| `augment_tests.py:679` | a Python gap with no Python test file | the uncovered lines | HALT, through `_halt_augment_cannot_run` |
| `run_implement_from_lld.py:115` | no base can be determined at launch | the repository and git's stderr | `RunFailed`, exit 1, alert; nothing has run |

Adds no site to the loud-failure baseline, and `BASELINE_CEILING` is unchanged.

## Related open issues

- #3090: no contradiction. `resolve_coverage_target` removes the issue-only path's `or 80`, which #3090 lists. The mock's 90 stays, and the flag now wins over it.
- #4312: no contradiction. `parse_pytest_output` is untouched, and `test_320` keeps its xfail. The whole-file figure it yields now decides nothing.
- #4246: extended, not reversed. A shortfall still routes to N4c for every framework, and N4c still halts on a gap it cannot fill, now naming the lines.

## N7's reports name their figure

`coverage_achieved` is the changed-line figure, or, when nothing was judged, the whole-file figure, which decided nothing. Beside a target of 95 an unlabelled 54% reads as a failure that passed, so `finalize` now sets `coverage_scope`, and the console, the test report and the summary all say `changed lines` or `whole files, not judged`.

## Follow-up

No real Vitest ran. #4445 carries the check, with the exact command.
