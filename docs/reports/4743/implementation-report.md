# Implementation report: #4743

## The defect, and the part the issue did not know

`test_deferred_install_fail_path_calls_cleanup_worktree` and `test_deferred_test_fail_path_calls_cleanup_worktree` stubbed neither `run` nor `_pr_changed_files`, so `process_pr` sent a real `gh pr diff 42 --repo owner/repo --name-only` to GitHub. The call failed, the code fell back to the Python gate, and the tests passed by accident, as #4743 reported.

The guard found three more. `TestProcessPrDeferralStaleBranchPriority` in `tests/tools/test_dependabot_review.py` sent the same `gh pr diff`, and its three tests then went on to post a review with a real `gh pr review 42 --repo owner/repo --comment --body-file ...`, because `review_comment_on_pr` was not stubbed either. That call failed too, since `owner/repo` does not exist, so nothing was posted, but every run tried.

## `tests/network_command_guard.py` (new)

It wraps `subprocess.Popen.__init__`, which every process start through the `subprocess` module reaches: `subprocess.run`, `Popen` itself and `psutil.Popen`. `tools/dependabot_review.py` starts every process that way. It wraps the constructor, not the `subprocess.Popen` name, for the reason `tests/model_call_guard.py` gives, and it reads the call's `cwd` and `env` from `Popen`'s documented argument order, because the constructor it wraps may already be another guard's `(*args, **kwargs)` wrapper.

It refuses:

- any `gh`, by the executable's name (`gh` or `gh.exe`, bare or as a full path, Windows or POSIX);
- `git fetch`, `pull`, `push`, `ls-remote` or `clone` when an argument is a network URL (`http://`, `https://`, `ssh://`, `git://`, `git@...`), including the `--repo=URL` form;
- the same subcommands when the remote they name is configured with such a URL, or, when none is named and no local path or `file://` URL is given, when any remote the repository has is. The URLs come from `git <the same global options> config --list`, run in the call's own cwd and environment, so `-C` and `-c remote.x.url=...` are honoured. A lookup that hangs past 30 seconds refuses the command rather than guessing.

Everything else runs, so the decision is made by URL, not by subcommand. The bare repositories in `tmp_path` that `tests/unit/test_dependabot_fake_root_guard.py` clones and fetches from pass.

A refused command raises `NetworkCommandInUnitTest`, an `AssertionError`, before the process starts. The code under test may swallow that in a broad `except`, so the command is also recorded, and the fixture fails the test at teardown when anything was.

## The fixture, and the files that use it

`no_network_commands` in `tests/conftest.py` installs the guard for one test. Each of the seven test files that loads the tool opts in with `pytestmark = pytest.mark.usefixtures("no_network_commands")`:

- `tests/unit/test_dependabot_review.py`
- `tests/unit/test_dependabot_outcomes.py`
- `tests/unit/test_dependabot_public_only.py`
- `tests/unit/test_dependabot_fake_root_guard.py`
- `tests/unit/test_npm_manifest.py`, one of whose tests loads the tool
- `tests/tools/test_dependabot_review.py`
- `tests/tools/test_dependabot_worktree_guard.py`

`test_every_test_file_that_loads_the_tool_runs_under_the_guard` reads every `tests/**/test_*.py` with `ast`, finds each that imports `dependabot_review` or passes `dependabot_review.py` to `spec_from_file_location`, and fails if one lacks the opt-in. It also fails if it stops finding the seven above, so the detector cannot go blind.

## What the guard caught, and the stubs (R2)

Before the stubs, the seven files with the guard on: `5 failed, 290 passed, 5 errors`. Each failure and each teardown error named the `gh` command.

- The two tests #4743 names: `_pr_changed_files` is stubbed to return `["poetry.lock"]`, so the test chooses the Python gate the failed `gh pr diff` used to choose. `["poetry.lock"]` is the value the stubs in `test_dependabot_outcomes.py` and `test_dependabot_public_only.py` already use.
- `TestProcessPrDeferralStaleBranchPriority._stub_pipeline`, used by its three tests: the same `_pr_changed_files` stub, and `review_comment_on_pr` stubbed to return True. No call site reads its return value.

No assertion changed. `tools/dependabot_review.py` did not change.

## Tests

In `tests/unit/test_dependabot_network_guard.py` (new):

- `test_guard_refuses_a_real_gh_start` (Test 1)
- `test_guard_refuses_git_fetch_from_an_https_url` (Test 1)
- `test_guard_refuses_git_against_a_remote_configured_with_a_network_url`: by name, through `-C`, as the default remote, a `git@` remote, `push` and `ls-remote`
- `test_guard_allows_local_git_against_a_tmp_path_repository`: `clone`, `push`, `fetch`, `pull`, `ls-remote` and a `file://` fetch against a bare repository in `tmp_path`
- `test_a_swallowed_refusal_still_fails_the_test`
- `test_network_reason_names_each_network_form`, eight cases
- `test_network_reason_passes_what_stays_local`, six cases
- `test_every_test_file_that_loads_the_tool_runs_under_the_guard` (AC1)

Where a refused command must be shown not to start, the constructor under the guard is replaced first with a recorder that starts nothing, and the test asserts the recorder saw nothing.

Test 2 is the two named tests passing in the run below, with the guard on.

## The run

The seven files above, the new test file, `tests/unit/test_loud_failure_check.py`, and the four other files that name the tool (`test_cascade_events.py`, `test_child_process_encoding.py`, `test_rmtree_sites_are_gated.py`, `test_worktree_relative_paths.py`), on Ubuntu, 2026-11-13: `387 passed, 1 skipped`. The skip is `test_child_process_encoding.py:264`, which runs only under a cp1252 locale.

`ruff check` passes on both new files. On each changed file it reports the same findings as at HEAD, none added.

## What it cannot see

A process started other than through `subprocess.Popen` in this interpreter, such as `os.system`; the tool uses none. A test that replaces `Popen.__init__` outright removes the guard for its own duration, as with `tests/model_call_guard.py`.

## Left alone

`TestProcessPrDeferralStaleBranchPriority` still runs the real `cleanup_worktree`, which starts local `git -C /tmp/main worktree remove /tmp/fake` and `branch -d`. Both fail at once because the directory does not exist, and neither reaches a remote, so it is outside #4743.
