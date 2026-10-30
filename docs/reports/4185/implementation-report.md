# Implementation Report: the scaffold's branch is main on WSL (#4185)

## What happened

On 2026-10-21 at 2:42 PM Central, after #4179 and #4180 landed, the operator ran `new-repo Theatron` from WSL. The passphrase prompt worked and the GitHub repository was created, but the run failed: push, repo settings, branch protection, and GitHub-side verification (0/4).

## Cause

`_create_repo()` ran a bare `git init`, so the branch name came from the machine's git configuration. Git for Windows sets `init.defaultBranch = main` in its system config, so every Git Bash run got `main`. WSL's git (2.53.0) sets nothing, so it used git's built-in default, `master`. The push is `git push -u origin main`, which failed because no `main` existed, and every later step is gated on that push.

## What landed

| File | Change |
|---|---|
| `tools/new_repo.py` | Step 2 runs `git init --initial-branch=main`. |
| `tests/unit/test_new_repo.py` | One test: the init command `main()` issues, run for real with an empty git configuration, leaves the repository on `main`. |

## Not addressed here

- #4186: a WSL run runs no post-create hooks, because the hook list and the token its one hook decrypts exist only on the Windows side. It needs the operator's ruling on how the token reaches Ubuntu.
- #4184: after a failure the script says a rerun resumes, but a rerun refuses because the directory exists. The Theatron leftovers (the local folder and the empty GitHub repository) must be removed before `new-repo Theatron` runs again.
