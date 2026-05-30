# Diagnosing the three repositories that block the dependabot drain

## What this document is for

The dependabot auto-merge tool, `tools/dependabot_review.py` in this repository, processes Python dependency-update pull requests across the fleet of repositories. As of 2026-05-30, it cleanly merges most of those pull requests, but ten of them remain stuck across three repositories. The two earlier tool-side bugs that the drain surfaced have already been fixed and merged (pull request #1412 corrected the `--with dev` flag handling, and pull request #1416 stopped the tool from leaking AssemblyZero's own virtual environment into the audit subprocesses). What remains is not a tool problem. Each of the three repositories has its own local test-setup problem that prevents the auto-merge tool from running the dependency-upgrade gate cleanly.

This document gives you, or any agent you delegate to, a careful and paranoid procedure for investigating each repository before changing anything. It begins with a list of safety rules that apply to every step, then walks through patent-general, Talos, and dispatch one at a time. For each repository it describes the symptom, the most likely shape of the underlying problem, the read-only checks that confirm the cause, and the possible fixes ranked by safety.

The procedure is meant to fail loudly when something looks wrong. If you reach an unexpected condition, the right action is almost always to stop, write down what you found, and come back to the operator. It is not to push past the surprise.

## Safety rules that apply to every section below

The full safety contract lives in `Projects/CLAUDE.md`. The rules below are the ones that come up most often in the investigation and fixes that follow. They apply to you and to any agent you delegate to. They are not optional and they are not subject to per-case exceptions; the presence of a rule on this list answers the question of whether the rule applies.

1. Never use `git reset --hard`, `git restore` on a tracked file that has been modified, `git branch -D`, `git clean -fd`, `git push --force`, `git push --force-with-lease`, `git worktree remove --force`, `git rebase --theirs`, `gh pr merge --admin`, `gh pr merge --auto`, or any command with `--no-verify` or `--no-gpg-sign`. If you find yourself reaching for one of these because the plain version refuses, treat that refusal as a signal to investigate, not as an obstacle to override. The plain command refusing is the safety check working correctly.

2. Never use `rm` to remove a tracked file or a file that you have not first inspected individually. Never use `rm` to clear an "untracked working tree files would be overwritten" error from a `git pull`. The right move in that case is to rename the offending file to `<name>.bak` so the content is preserved outside git's view, then run the pull. The wrong move is to delete the file.

3. Never run `git gc --prune`, `git filter-branch`, the BFG repo-cleaner, or any other operation whose purpose is to make the object database smaller or tidier. The history is the record of truth. Cleanups are uniformly worse than the situation they try to address.

4. Before changing any file, run `git status` and inspect each modified or untracked file individually. Do not assume that a directory's contents are all "the same kind of dirt" because the directory's name suggests so. The 2026-05-27 and 2026-05-30 incidents in `docs/lessons-learned.md` both followed this pattern; do not repeat them.

5. Never manually merge a dependabot pull request, with `gh pr merge` or any other means. The only sanctioned path is the auto-merge tool. Manual merges skip the test gate and the author gate, and they take attribution off the contribution graph.

6. If at any point in the investigation you find a modified file, an untracked file, a branch, a stash, or a worktree that you did not create and cannot account for, stop. That state may be operator work in progress. Do not change it. Bring the finding back to the operator and ask before doing anything.

7. If a command produces output you did not expect — different from what this document describes, different from a previous run, or contradictory across runs — stop and read carefully before acting. Do not run another command on the assumption that the previous one's surprise was a transient glitch. Surprise is the signal that the model in your head does not match reality. Update the model first.

## Repository 1: patent-general

### Symptom

When the dependabot tool processes pull request #171 in `martymcenroe/patent-general`, which proposes bumping `gitpython` from version 3.1.49 to 3.1.50, the `poetry install` step fails. The error tail from the most recent drain shows that poetry cannot find installation candidates for `torch` (version 2.7.1) or `torchvision` (version 0.22.1), because the wheels available on the package index do not support the current Python interpreter on this machine, which is Python 3.14. After the install fails, the tool marks the pull request as deferred and moves on.

### Shape of the problem

The dependency being bumped does not live in the root of the repository. The pull request title contains the phrase "in /tools/ip-timestamps", which means the version change applies to a `pyproject.toml` at `tools/ip-timestamps/pyproject.toml`. The repository is a small monorepo: two separate Python projects share one git history, each with its own dependency declarations.

The dependabot tool, in its current form, only knows how to install the root project. It runs `poetry install` against the worktree root, regardless of which subdirectory's `pyproject.toml` the bump actually affects. For this repository, the root install fails for reasons unrelated to the dependency upgrade being audited: the root depends on `torch` and `torchvision`, and Python 3.14 wheels for those packages are not yet published.

The dependency change itself, which is in `tools/ip-timestamps`, is never tested. Whether the version bump is safe is not the question this failure is answering.

### Read-only investigation steps

Run each of these from `C:\Users\mcwiz\Projects\patent-general`. Every one of them is read-only. Inspect the result of each before going to the next.

1. Confirm that the working tree is clean before you start.

   ```
   git -C /c/Users/mcwiz/Projects/patent-general status
   ```

   If `git status` shows any modified file, any untracked file, or any in-progress merge or rebase, stop. The investigation must begin from a known clean state. Resolve or surface the existing state before proceeding.

2. List every `pyproject.toml` in the repository, excluding the `.git` directory.

   ```
   git -C /c/Users/mcwiz/Projects/patent-general ls-files '*pyproject.toml'
   ```

   For this repository, the expected output is two paths: one at the root and one at `tools/ip-timestamps/pyproject.toml`. If you see more, examine each one before continuing.

3. Read the project name and Python version requirement from each `pyproject.toml`.

   ```
   git -C /c/Users/mcwiz/Projects/patent-general grep -n '^name\s*=\|^python\s*=' -- '*pyproject.toml'
   ```

   Confirm that the root project is named something like `patent-general` and that the subdirectory project is its own separate project.

4. Confirm the root depends on `torch` and `torchvision`.

   ```
   git -C /c/Users/mcwiz/Projects/patent-general grep -n 'torch\|torchvision' -- pyproject.toml
   ```

5. Confirm the subdirectory's pull request does not need `torch`.

   ```
   git -C /c/Users/mcwiz/Projects/patent-general grep -n 'gitpython\|torch' -- tools/ip-timestamps/pyproject.toml
   ```

   You should see `gitpython` declared and `torch` absent. If `torch` appears in the subdirectory, the picture is different and you must re-read.

6. Confirm that `torch` has no Python 3.14 wheel for the pinned version. From the root of the repository, in a shell where the python interpreter is on the path:

   ```
   poetry run python -c "import sys; print(sys.version_info)"
   ```

   And:

   ```
   pip index versions torch
   pip download torch==<pinned-version> --python-version 314 --only-binary=:all: --no-deps --dest C:\Users\mcwiz\AppData\Local\Temp\torch-test 2>&1
   ```

   Substitute the pinned version of `torch` from the root `pyproject.toml`. If `pip download` reports "could not find a version that satisfies the requirement", that confirms there is no Python 3.14 wheel available for that pinned version.

### Possible fixes, ranked by safety

The four candidate fixes below are in order from safest to most invasive. Do not skip past one because the next sounds easier; the order matters.

**(a) Remove `torch` and `torchvision` from the root `pyproject.toml` if the root project itself does not import them.** This is the safest fix, but only if it is true that the root does not actually use `torch`. To confirm, search the root project's Python source files for any `import torch` or `from torch` statement:

```
git -C /c/Users/mcwiz/Projects/patent-general grep -nE '^(import torch|from torch)' -- '*.py' ':!tools/'
```

If that returns nothing, `torch` is declared but not used at the root level, and removing it from the root `pyproject.toml` is correct and harmless. After the removal, the dependabot tool's root install will succeed for any future dependency bump that touches a subdirectory.

**(b) Pin the root project to a Python version with available wheels.** Edit the root `pyproject.toml` so that `python = "^3.13,<3.14"` (or whatever version torch does have wheels for). This means the root project will not install on Python 3.14. The dependabot tool will still try to install with whatever Python is configured for poetry. If poetry is set to Python 3.14, this fix changes nothing. Use only if you also reconfigure poetry to use Python 3.13.

**(c) Wait for torch to publish Python 3.14 wheels.** This requires no work and is the right answer if (a) is not safe and (b) is not desirable. The pull request will remain deferred until the wheels appear.

**(d) Teach the dependabot tool to handle subdirectory pull requests.** This is a substantial change to `tools/dependabot_review.py` in AssemblyZero. It would parse the pull request title for the `in /<subdir>` marker, change into that subdirectory, install and run tests against the subdirectory's `pyproject.toml` instead of the root's, and clean up that subdirectory's environment afterward. It does not belong in this repository; it belongs as a separate AssemblyZero issue. File it separately if you decide it is worth pursuing.

Option (a) is almost always the right answer for this specific case. Option (d) is the right answer for the general problem of monorepo dependency bumps, but is out of scope for the immediate goal of unblocking the drain.

### How to verify the fix worked

After applying any of (a) through (c), from `C:\Users\mcwiz\Projects\AssemblyZero`:

```
poetry run python tools/dependabot_review.py --repo martymcenroe/patent-general
```

The expected output, if the fix took effect, is a `merged` count of one for that repository. If the count is still `deferred` but the error message changed, that is also progress; the new error tells you what to investigate next.

## Repository 2: Talos

### Symptom

When the dependabot tool processes pull requests #169 through #172 in `martymcenroe/Talos` (which propose bumping `idna`, `urllib3`, `python-multipart`, and `pillow`), `poetry install` completes successfully, but `poetry run pytest` fails with exit code 4. The error tail, after the most recent fix, shows the call stack passing through Talos's own virtual environment (`talos-_d_lpmXE-py3.14`, not AssemblyZero's). The final exception is `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file`. The exception is raised during test collection, before any individual test has begun to run.

### Shape of the problem

Talos's shared test fixtures, in `src/conftest.py`, configure SQLAlchemy with the connection string `sqlite:///:memory:`. An in-memory SQLite database cannot raise "unable to open database file"; the in-memory case is a special path in SQLite that does not touch the file system. The error must therefore be coming from a different code path. Something in Talos, or something that Talos imports, calls `create_engine` with a file-backed connection string at module top level. When pytest imports that module during collection, the engine constructor opens a connection to the database file. If the file does not exist on disk in the audit worktree, SQLAlchemy raises the operational error and pytest fails to collect.

There are three candidate places the offending engine call could live:

1. A module that `conftest.py` itself imports. If `from database import Base` is at the top of `conftest.py`, and `database.py` contains `engine = create_engine("sqlite:///app.db")` at its module level, that call runs at import time during test collection.

2. A test file in some subdirectory whose own imports have a top-level engine call.

3. A pytest plugin installed via `poetry add` or `pip install`, that opens a database at its own import time. This case is rare; most plugins are well-behaved about not doing IO at import.

The shape of the problem is "find the offending top-level `create_engine` call, then make the call lazy or test-aware so it does not run during pytest collection."

### Read-only investigation steps

Run each of these from `C:\Users\mcwiz\Projects\Talos`. Every one is read-only.

1. Confirm a clean working tree before you start.

   ```
   git -C /c/Users/mcwiz/Projects/Talos status
   ```

   If there is any modified or untracked file, stop and surface it.

2. Show every test file pytest would collect, without actually running them.

   ```
   cd /c/Users/mcwiz/Projects/Talos
   poetry run pytest --collect-only -q 2>&1 | head -100
   ```

   The output will include the failing import. Note the exact file path in the error, and the import line that raises.

3. Search every Python file in Talos for `create_engine`, the SQLAlchemy entry point that opens the database.

   ```
   git -C /c/Users/mcwiz/Projects/Talos grep -n 'create_engine' -- '*.py'
   ```

   For each hit, read a few lines of context. Note the connection string that is passed to `create_engine`. The candidates are calls whose string is `sqlite:///<file-path>` (any path that is not `:memory:`).

4. For each candidate, determine whether the `create_engine` call is at module top level (runs at import) or inside a function body (runs only when the function is called). The top-level calls are the candidates that matter; in-function calls are not the cause.

5. For each top-level candidate, check whether the database file it points at exists on disk in a fresh Talos worktree.

   ```
   ls -l /c/Users/mcwiz/Projects/Talos/<the-database-path>
   ```

   If the file is missing, that is your culprit.

6. If no top-level `create_engine` call exists with a file-based connection string in Talos's own source, the call is happening inside an installed package. List the packages and look for any that are known to open SQLite databases at import time.

   ```
   cd /c/Users/mcwiz/Projects/Talos
   poetry show
   ```

   Read the names. Most packages do not open databases at import time; the ones that do are usually obvious (something like `sqlite-utils-something`).

### Possible fixes, ranked by safety

**(a) Make the offending `create_engine(...)` call lazy.** Instead of executing the call at module top level, wrap it in a function and call it where the engine is actually needed. For example, if the module currently contains:

```
from sqlalchemy import create_engine
engine = create_engine("sqlite:///app.db")
```

Change it to:

```
from sqlalchemy import create_engine
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine("sqlite:///app.db")
    return _engine
```

And update every site that uses `engine` to call `get_engine()` instead. This is the safest fix; it preserves the engine's identity (one engine per process) without running the constructor at import time.

**(b) Add a test fixture that creates the database file before any test runs.** This applies if the file really needs to exist as a file, not as memory. Add to `conftest.py`:

```
import pathlib

@pytest.fixture(autouse=True, scope="session")
def ensure_db_file():
    pathlib.Path("app.db").touch()
    yield
```

This creates an empty file, which is enough to satisfy SQLite's "open the file" step. Use only if you understand whether an empty database file is a safe state for the rest of the test suite.

**(c) Detect the test environment and choose the engine accordingly.** Replace the file-backed engine with `:memory:` when running under pytest. The detection uses an environment variable that pytest sets:

```
import os
from sqlalchemy import create_engine

if os.getenv("PYTEST_CURRENT_TEST"):
    engine = create_engine("sqlite:///:memory:")
else:
    engine = create_engine("sqlite:///app.db")
```

This works at module top level. It is a small change but it relies on a convention (the environment variable) that is documented but easy to overlook later.

**(d) Tell pytest not to collect the file with the offending import.** This is a workaround. It does not fix the bug. Use only as a temporary stopgap, and only when you understand which test coverage you are giving up.

Option (a) is the right fix in almost every case. Option (b) is reasonable when (a) is impossible because some other production code path depends on the file existing. Options (c) and (d) are last resorts.

### How to verify the fix worked

From `C:\Users\mcwiz\Projects\AssemblyZero`:

```
poetry run python tools/dependabot_review.py --repo martymcenroe/Talos
```

The expected outcome, if the fix took effect, is that pytest no longer fails at collection. The four pull requests then either merge (if the dep upgrades pass their tests) or defer with a real, test-level failure that names the actual problem.

## Repository 3: dispatch

### Symptom

When the dependabot tool processes pull requests #123 through #127 in `martymcenroe/dispatch` (which propose bumping `idna`, `python-dotenv`, `urllib3`, `pillow`, and `lxml`), pytest fails with exit code 2 during test collection. The error tail reads `ModuleNotFoundError: No module named 'tools'` and names the failing file as `fiction/between-the-lines/tools/test_scene_originality_v2.py`.

### Shape of the problem

The failing test file is at `fiction/between-the-lines/tools/test_scene_originality_v2.py`. Its first import statement reads `from tools.scene_originality_v2 import (...)`. For that import to resolve, Python needs to be able to find a package named `tools` somewhere on `sys.path`. When you run pytest from `fiction/between-the-lines/`, the `tools/` subdirectory is right there and the import works. When the dependabot tool runs pytest from the dispatch repository root, `tools/` does not exist at the root; the only `tools` directory is the one buried inside `fiction/between-the-lines/`, which is not on the path.

The test was written under an unstated assumption about its working directory. pytest's automatic discovery does not honor that assumption; pytest sets its own `rootdir` based on configuration files and imports test modules relative to that. There is no pytest configuration in dispatch's `pyproject.toml`, so pytest uses the repository root as `rootdir`.

The shape of the problem, therefore, is "this test does not belong in dispatch's automatic-discovery scope as that scope is currently configured, and either the configuration or the assumption needs to change."

### Read-only investigation steps

Run each from `C:\Users\mcwiz\Projects\dispatch`. Every one is read-only.

1. Confirm a clean working tree.

   ```
   git -C /c/Users/mcwiz/Projects/dispatch status
   ```

   Note any modified or untracked file. If you find unfamiliar state, stop and surface it. Dispatch is your active writing repository; the chance of running into uncommitted fiction work is significant. The earlier 2026-05-30 incident in `docs/lessons-learned.md` is exactly this risk.

2. Locate every `test_*.py` file in the repository, excluding the `.git` directory.

   ```
   git -C /c/Users/mcwiz/Projects/dispatch ls-files '*test_*.py'
   ```

   The output tells you the full surface area pytest is trying to collect.

3. For each test file, read the top-level imports.

   ```
   git -C /c/Users/mcwiz/Projects/dispatch grep -n '^\(import \|from \)' -- '<full-path-from-step-2>'
   ```

   This shows which other files each test depends on, and whether any of those other files would be importable from the dispatch root.

4. Check whether dispatch has any pytest configuration at all.

   ```
   git -C /c/Users/mcwiz/Projects/dispatch grep -n '\[tool.pytest' -- pyproject.toml
   ls /c/Users/mcwiz/Projects/dispatch/pytest.ini 2>&1
   ls /c/Users/mcwiz/Projects/dispatch/setup.cfg 2>&1
   ```

   If all three commands return nothing or "No such file or directory", dispatch has no pytest configuration. That is part of why the test setup behaves the way it does.

5. Decide whether the fiction tests are supposed to be discovered from the dispatch root at all. Ask yourself: do you ever run `pytest` from the dispatch root? Do you intend the dependabot pipeline to test the fiction-tools test suite as part of a dependency-upgrade gate? If your answer to either is no, then the right fix is to exclude those tests from automatic discovery, not to make them importable from the root.

### Possible fixes, ranked by safety

**(a) Tell pytest not to discover the fiction directory.** Add the following block to dispatch's `pyproject.toml`, after any existing `[tool]` sections:

```
[tool.pytest.ini_options]
norecursedirs = ["fiction", ".git", "node_modules"]
```

This excludes fiction work from automatic discovery without changing anything about how you run those tests manually from inside the fiction directory. The dependabot tool runs pytest from the dispatch root, so with this configuration in place, pytest will report "no tests collected" and exit with code 5. The dependabot tool already treats exit code 5 as a pass; the dep-upgrade pull requests will merge.

This is the smallest possible change and it has the right semantics. The fiction tests exist to validate your fiction tooling, not to gate dependency upgrades. They should not block a dep bump.

**(b) Add the fiction directory to pytest's Python path.** Add to `pyproject.toml`:

```
[tool.pytest.ini_options]
pythonpath = ["fiction/between-the-lines"]
```

This makes the `from tools.scene_originality_v2 import (...)` statement resolve. It also has the side effect that pytest will actually collect and run every test in `fiction/between-the-lines/tools/`. That may or may not be what you want during a dependabot run, and it may slow the auto-merge cycle if those tests are slow or do real I/O.

**(c) Add a `conftest.py` at `fiction/between-the-lines/`** that modifies `sys.path` from inside that directory:

```
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

The effect is the same as (b), but the change is localized to the subdirectory rather than central. It is harder to discover later.

**(d) Rename the failing test files** so pytest no longer auto-discovers them. Move `test_*.py` to `_test_*.py` or similar. This is brittle. It works only as long as nobody renames them back.

Option (a) is the right answer if you do not want fiction tests run as part of the dependabot gate. Option (b) is the right answer if you do. The choice is yours.

### How to verify the fix worked

From `C:\Users\mcwiz\Projects\AssemblyZero`:

```
poetry run python tools/dependabot_review.py --repo martymcenroe/dispatch
```

The expected outcome, if the fix took effect, is a `merged` count of five for dispatch.

## Conditions under which you stop and bring the question back

For any of the three repositories, stop the investigation immediately if any of the following happens.

1. The working tree is not clean at the start of the investigation. Modified files you did not put there, untracked files you did not create, branches whose names do not look like your own work, stashes whose descriptions are unfamiliar, or worktrees in unexpected locations — any of these is operator work in progress. Do not change it. Do not delete it. Surface it.

2. The `grep` or `ls-files` step finds the pattern you are looking for in more than one place, and you cannot tell from inspection which one is the actual cause. The wrong place looks identical to the right place. Stop and read both before changing either.

3. The fix you are about to apply touches a file whose `git log` shows it is load-bearing for something other than tests. A module imported by production code, not just by tests, is a different kind of file than a fixture. Confirm the blast radius before changing it.

4. Any command refuses with a safety message. Read the message. Do not escalate to a flag that overrides the safety check. Investigate what the safety check is telling you. The plain command refusing is the safety check working.

5. You have made one attempt at the fix, it has not produced the expected behavior, and you are about to try a second attempt with no change in approach. This is the two-strike signal. The problem is in the model, not the parameters. Stop, write down what you observed, and re-read this document from the top.

6. The same pull request you are working on already exists on the remote with conflicting state. The dependabot pull requests are owned by the dependabot bot; you cannot rewrite their branches.

In any of these cases, stop and bring the question back to the operator. The cost of pausing to confirm is small. The cost of an unwanted action is high.

## After each fix lands

For every fix you apply to a repository, follow the universal merge process in `Projects/CLAUDE.md`. The key steps are:

1. File an issue in the relevant repository (the repository that contains the file you are changing) before opening any pull request. The pull request title and the pull request body must both contain `Closes #<issue-number>` literally; the commit message must contain it as well.

2. Make the change in a feature branch off `main`, not in `main` itself.

3. Wait for the mergeable state of the pull request to reach `clean` or `unstable`. Do not pass `--admin` to `gh pr merge`. Do not approve your own pull request; the Cerberus app does that for you after the pull-request sentinel passes.

4. Squash-merge with `gh pr merge <num> --squash --repo martymcenroe/<repo>`. Do not pass `--auto`. The repository's `allow_auto_merge` setting is false fleet-wide; the flag would silently no-op.

5. After the merge lands on origin, verify with `git fetch origin && git log --oneline origin/main | head -1` that the top commit on origin/main is your merge commit. Only then proceed to the cleanup.

6. Cleanup: fast-forward your local main with `git pull --ff-only origin main`, remove the feature worktree with `git worktree remove ../<repo>-<num>` (no `--force`), and delete the local feature branch with `git branch -d <branch-name>` (lowercase `-d`, never uppercase `-D`).

7. After the cleanup, re-run the dependabot drain from `C:\Users\mcwiz\Projects\AssemblyZero`:

   ```
   poetry run python tools/dependabot_review.py --fleet
   ```

   The expected result, for each fix that took effect, is that the previously deferred pull requests in that repository now merge. The drain is "clean" when every Python pull request across the fleet is either merged or has been left deferred for a documented, repository-side reason that is not in this list.

If at any point the merge sequence stalls, follow `AssemblyZero/docs/runbooks/0935-pr-stuck-recovery.md`. If `git branch -d` refuses after a successful squash merge, follow `AssemblyZero/docs/adrs/0217-squash-merge-orphan-graft-cleanup.md`. Do not reach for the uppercase `-D` even in these cases.
