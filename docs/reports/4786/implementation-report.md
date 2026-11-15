# Implementation report: #4786

## The defect

Before its GitHub steps, `tools/new_repo.py` printed "Single pinentry prompt". A run asks for up to three passphrases: the classic PAT, one for each post-create hook that decrypts a secret of its own, and the pr-sentinel App credential. On 2026-11-14 at 11:54 PM Central the operator was asked once where three were expected, and nothing said how many to expect or why two never came.

## What changed in `tools/new_repo.py`

- The GITHUB REMOTE banner no longer says "Single pinentry prompt". Its title is unchanged, so the #1533 anchor test still finds it.
- Right after the banner, before the classic PAT's prompt, the run loads the listed hooks once and prints a block: `PASSPHRASES THIS RUN WILL ASK FOR: N`, then each passphrase numbered, in the order the run asks: the classic PAT and its file, each hook's declared passphrases and the hook that asks, and the pr-sentinel App credential and its file when the file exists.
- Under it, `Expected and NOT asked: M` names each passphrase the run expected and will not ask for, with the reason: the pr-sentinel key file is missing (named, with `tools/store_pr_sentinel_app_key.py`), a hook cannot load (named, with the exception), or the hook list is missing. When the classic PAT's file is missing, the count is 0 and every other entry is marked not reached.
- A hook without `PASSPHRASES` is listed as `Not counted: the hook <path> declares no passphrases; it may still ask`.
- New: `HookLoadError`, `LoadedHook` (path, module or None, error or None, passphrases or None), `load_post_create_hooks(paths)`, `passphrase_plan()` and `passphrase_block()`.
- `run_post_create_hooks` takes the loaded hooks, so each hook module executes once per run; given paths, it loads them itself. It keeps exactly one broad `except Exception`, around the `post_create` call. Loading re-raises any exception from a hook's top level as `HookLoadError`, which the loader catches narrowly; the loud-failure baseline is unchanged.
- The hook contract gains an optional `PASSPHRASES: tuple[str, ...]`, stated in `run_post_create_hooks`'s docstring next to `HOOK_IMPORTABLE`. Anything other than a tuple of non-empty strings is a load error that names the hook, and the hook does not run. The error names the wrong type, never the value.
- The run calls `classic_pat_session(DEFAULT_PAT_PATH)` with the path the block names, and the pr-sentinel check uses the bundle path the block names, so the list and the prompts read the same files.
- No control flow changed: the block is printed and nothing stops on it.

## Other files

- `tools/_pat_session.py`: `pr_sentinel_app_session`'s docstring no longer says callers treat a missing file or a cancel as unverifiable. Since #4785 a missing file fails the check, a cancel is declined and a failed decrypt fails.
- `docs/runbooks/0927-new-repo-human-checklist.md`: the post-create hooks bullet states `PASSPHRASES` and the block.

## Left as it was

- Runbook 0927's paragraph on passphrase prompts still names only the classic PAT and the pr-sentinel bundle, not a hook's passphrases. The work order limited the runbook change to the hooks bullet.
- `tests/unit/test_cerberus_after_auto_review.py` drives `main()` without patching `DEFAULT_PAT_PATH` or `DEFAULT_PR_SENTINEL_APP_GPG`, so its run of the block checks whether the real files exist (a stat, never a read). That file was outside this change.
