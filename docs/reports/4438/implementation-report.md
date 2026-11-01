# Implementation report: #4438, #4489

## The mock scaffolds every framework of the run (#4438 R1)

`assemblyzero/workflows/testing/nodes/scaffold_tests.py`: `_mock_scaffold_tests` wrote one pytest file whatever the run was. It now goes through `_scaffold_every_framework`, the path a real run takes, and only the pytest scaffolder is the mock's (`_mock_scaffold_python`). A run of one non-pytest framework now writes that framework's file and no Python.

## A rehearsal of a two-framework target (#4438 R2, R3)

`tools/rehearse_two_frameworks.py` builds a throwaway target with pytest at its root and Vitest in `web/`, and has two named steps. `docs/runbooks/0959-two-framework-rehearsal.md` says how to run and read them.

- `mock` runs the LLD and implementation workflows under `--mock`, offline, and passes only when both exit 0, both scaffolds were written, and the snapshots before and after are byte-identical. `tests/integration/test_two_framework_rehearsal.py` runs it in the integration tier, in child processes, with a throwaway home.
- `provision` cuts a worktree of the target, really runs `poetry install` and `npm ci` through `provision_worktree`, then runs both whole suites in what was installed. It passes only when both ran tests and passed, and then removes that worktree and its Poetry environment.

The fixture's `package-lock.json` is real, kept as `tests/fixtures/two_framework/web-package-lock.json.txt`. The `.txt` keeps dependency scanners off a project that does not exist. It was generated once in this worktree, because #1355 keeps JavaScript on Ubuntu to worktrees; the first version of the tool ran `npm install` from the primary checkout and the guard refused it, correctly.

## A mock's placeholders alert no one (#4489)

`assemblyzero/workflows/testing/nodes/validate_tests_mechanical.py`: a mock's scaffold is placeholders by design, so a wholly hollow suite on a mock run prints a `[MOCK]` line and alerts no one. A real run's still alerts. ADR 0236 is untouched: this is not a failure, and a mock run's real halts alert as before. Before this, every mock run that reached N2.5 emailed the operator.

## What the rehearsal found

It found #4490: `run_pytest` inherits the workflow's `VIRTUAL_ENV`, so a run's pytest tests in AssemblyZero's virtualenv, not the one provisioning built. That is not fixed here, because deciding coverage support in the target's environment changes what every Python target needs. `provision` therefore runs pytest in the target's environment itself, through `hook_environment`, so its pass means what it says. The gate's own `run_pytest` does not yet do this, and until #4490 lands, this rehearsal proves provisioning and the Vitest side of a run, not that a real run's pytest uses what was provisioned.

## Left behind

`data/scratch-2026-11-01-4438/mock1` (831 KB) and `provision1` (226 KB) in the primary checkout are the first two rehearsals' work directories: throwaway git trees and logs, in a gitignored folder. They stay because scratch goes file by file and a tree cannot be removed by rule, and they are listed on #4438. Later rehearsals ran under this worktree's `data/`, which its removal takes.
