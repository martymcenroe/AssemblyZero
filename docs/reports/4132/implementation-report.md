# Implementation Report: new_repo.py from Ubuntu (#4132, #4135, #4136, #4137)

## What happened

The first `new_repo.py` run from Ubuntu, on 2026-10-07 at 6:42 PM Central, created `IEEE-TF-DC` at `AssemblyZero/C:\Users\mcwiz\Projects/IEEE-TF-DC`. gpg failed five times without showing a prompt. The run then printed `[SUCCESS]`, although the GitHub repo, the push, the repo settings, branch protection and the hook install had all failed. On the operator's order, the stranded scaffold was discarded. It was never pushed, and no GitHub repo exists.

## Causes

| Issue | Cause |
|---|---|
| #4132 | `config.projects_root()` defaults to the Windows spelling. On Linux that is a relative path; `_sanitize_path` resolves it against the current directory, and the Ubuntu `new_repo` shell function always runs from AssemblyZero. |
| #4135 | `pinentry-curses` is the only pinentry on Ubuntu, and `new_repo.py` detaches its stdin by design (#1806), so gpg failed with "problem with the agent: Inappropriate ioctl for device" before any prompt. The retry loop retried that four more times and then told the operator to retype a passphrase he was never asked for. |
| #4136 | `[SUCCESS]` was printed unconditionally. A missing hook source was a warning. A failed classic-PAT session fell through to push advice that named other causes. |
| #4137 | PR #3685 removed `secret-file-guard.sh` from AssemblyZero, because the guard is registered centrally. `new_repo.py` still copied it, and still registered it in every new repo's `settings.json`, where a missing hook script refuses every file tool (#3684). |

## What landed

| File | Change |
|---|---|
| `tools/new_repo.py` | `resolve_project_path`: `fmt='auto'`, and it refuses a root that is not an existing absolute directory. `failed_steps`: `[SUCCESS]` and exit 0 only when no step failed; otherwise `[FAILED]` on stderr, `alert_operator`, exit 1. `main`'s catch-all handler alerts. `pat_failure` replaces the push advice when the PAT session never opened. Step 5b and `deploy_canonical_hooks` are removed. `create_settings_json` writes `{}` and strips only a stale guard registration (`_strip_stale_guard`). Local verification checks that no repo-local guard is registered. The audit reads the decisions file with `fmt='auto'`. |
| `tools/_pat_session.py` | `PinentryUnavailable(RuntimeError)` and `_stop_if_no_prompt`, called in all four decrypt loops. They match a closed set of three gpg phrases. |
| `tests/fixtures/loud_failure_baseline.json`, `tests/unit/test_loud_failure_check.py` | 324 to 323: `main`'s handler now alerts. |
| `docs/audits/0908-loud-failure-sweep-ledger.md` | Nine `new_repo.py` rows marked fixed. |
| `docs/runbooks/0901-new-project-setup.md` (v2.8), `0933-workflow-readiness-audit.md` | No per-repo hook; run from Git Bash. |

## Won't do, recorded

#4135 R1 and R3 asked for the decrypt to work on Ubuntu, for example by setting `GPG_TTY`. That is not done. #1806 refuses a terminal-based pinentry on purpose, and the operator has chosen to run `new_repo.py` from Git Bash. On Ubuntu the script now stops on the first such failure and says to use Git Bash.

## Not addressed here

The other `new_repo.py` sites in ledger 0908 whose fix is "raise" at the point of failure, rather than exit 1 at the end of the run, stay open. They are tracked by the module's issue under #3581.
