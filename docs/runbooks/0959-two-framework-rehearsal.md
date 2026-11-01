# 0959 - Rehearse a pytest-plus-Vitest target

**Issue:** #4438, under #3585. **Runs:** after a change to framework detection, scaffolding, provisioning or the full-suite gate.

`tools/rehearse_two_frameworks.py` builds a throwaway target with pytest at its root and Vitest in `web/`, and has two named steps. Each one takes a directory that does not exist yet. Use one under the worktree's gitignored `data/`, so the worktree's removal takes it.

## The mock step

In bash, from the worktree:

    poetry run python tools/rehearse_two_frameworks.py mock --work-dir data/rehearsal/mock

It runs the LLD and implementation workflows under `--mock`, through every phase, offline. It passes only when both exit 0, both frameworks got a scaffold, and the snapshots before and after are byte-identical. The integration tier runs the same step (`tests/integration/test_two_framework_rehearsal.py`).

## The provision step

It needs the network. In bash, from the worktree:

    poetry run python tools/rehearse_two_frameworks.py provision --work-dir data/rehearsal/provision

This is what `--mock` only plans. It cuts a worktree of the target, runs `poetry install` and `npm ci` there through the run's own `provision_worktree`, then runs both whole suites, each in the environment just installed. It passes only when both suites ran tests and passed, and then it removes that worktree and its Poetry environment. On a failure the worktree stays, and the step names it.

pytest runs through `run_pytest`, the gate's own call, under this process's virtualenv, which is the condition a real run is in. So a pass proves a real run's pytest uses what was provisioned (#4490). Three things have to hold: pytest lists no plugin, because the fixture installs none; coverage is refused, naming pytest-cov; and once the fixture's optional `coverage` group is installed, coverage is measured and the one plugin listed is pytest-cov. A plugin the fixture never installed means the suite ran in another environment.

Run it from a worktree, because JavaScript on Ubuntu runs only in worktrees installed with Linux npm.

## Reading a failure

- `mock` fails with a scaffold missing: read `impl.log` in the work directory, and look for the `Frameworks for scaffold, red and green` line.
- `mock` fails with the snapshots different: compare `snapshot-before.txt` and `snapshot-after.txt`. Something a run wrote stayed behind.
- `provision` fails on an install: the `ProvisioningError` names the command, the directory and its output.

## The lock

`tests/fixtures/two_framework/web-package-lock.json.txt` is the fixture's real lock. It is named `.txt` so dependency scanners leave alone a project that does not exist. To refresh it, put a copy of `PACKAGE_JSON` from the tool in a directory inside a worktree, run `npm install --package-lock-only` there, and copy the result over the fixture.
