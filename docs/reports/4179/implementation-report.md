# Implementation Report: new_repo.py from WSL (#4179, #4180)

## What happened

On 2026-10-21 the operator turned WSL interop off and ran `new-repo` from Ubuntu. It built the local scaffold and then stopped at the classic-PAT decrypt with "Inappropriate ioctl for device". Nothing was created on GitHub. At 12:30 PM Central he wrote "i intend to run new-repo from WSL", and at 12:33 PM that he gets a Linux pinentry on WSL "all day long" (session `8e548c76`, his typed words, checked in the transcript). That supersedes the Git Bash choice recorded in `docs/reports/4132/implementation-report.md`, whose won't-do on `GPG_TTY` this change reverses.

## Causes

| Issue | Cause |
|---|---|
| #4179 | gpg tells pinentry-curses which terminal to draw on from `GPG_TTY`, or else from its own stdin. `new_repo.py` replaces its stdin with the null device (#1806), nothing sets `GPG_TTY`, and so gpg had no terminal to name. |
| #4180 | `_sanitize_path` handed every path not starting with `/` to `Path.resolve()`. On Linux a `C:\...` string is a relative file name, so it came back joined to the current directory, and the change set off the traversal warning. `create_project_json` also wrote `str(project_path)`, the Linux path, into `PROJECT_ROOT_WINDOWS`. |

## What landed

| File | Change |
|---|---|
| `tools/new_repo.py` | `detach_stdin()` writes the terminal's name into `GPG_TTY` before it replaces stdin, when stdin is a terminal and `os.ttyname` exists. `project_json_content()` builds what `create_project_json()` writes: `PROJECT_ROOT_WINDOWS` is `_spellings(project_path)["windows"]`, and a new top-level key `unix_paths_from` (`git-bash` or `linux`) says whose spelling `PROJECT_ROOT` and `TOOLS_DIR` hold. |
| `tools/_pat_session.py` | `_no_prompt_advice()` replaces the "Run this from Git Bash" text. On Windows it names the dialog. On POSIX it says the run had no terminal, or names the terminal gpg was given and points at `pinentry-program` and `gpgconf --kill gpg-agent`. The module docstring allows a WSL terminal. |
| `tools/assemblyzero_config.py` | Off Windows, a path with a Windows drive is normalized with `PureWindowsPath` instead of `Path.resolve()`. On Windows nothing changes. |
| `docs/runbooks/0901-new-project-setup.md` (v2.9), `0927-new-repo-human-checklist.md` (v7.0) | Run from a WSL terminal or from Git Bash; the Git Bash-only instruction is superseded. |

`inherit_from` was not named in #4180, but it was the worse of the two fields. From WSL it held the AssemblyZero checkout path with `C:\Users\...\AssemblyZero` appended. It now holds the Windows path, the same as a Git Bash scaffold.

## Decisions taken

- **Where `GPG_TTY` is set.** In `detach_stdin()`, the one function that destroys the information, and in the process environment, so every gpg child inherits it. The four decrypt loops in `_pat_session.py` are unchanged. A landing script run without `detach_stdin()` still gives gpg a terminal on its stdin, as before.
- **#4180 requirement 3.** It asks that `project.json` say which Unix spelling it holds, and has no test or acceptance criterion. Each side keeps writing its own spelling (`/c/...` from Git Bash, `/mnt/c/...` from Ubuntu, per ADR-0004 rule 3), and the new `unix_paths_from` key records which. Nothing reads the key yet.

## Not addressed here

- #4182 carries #4179's test 3, the operator's own end-to-end run from WSL. An agent never runs a script that decrypts the classic PAT.
- #4181: a line typed while the script runs is still echoed on the terminal and left for the shell when it exits. #1806 keeps it out of the script only. Found while reading `detach_stdin()`.
- The new `_pat_session` tests live under `tests/unit/` because no CI step collects `tests/tools/` (#3453).
