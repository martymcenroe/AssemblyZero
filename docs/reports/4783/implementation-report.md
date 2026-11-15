# Implementation report: #4783

## The defect

An operator-configured post-create hook sets a repository secret with `set_secret(repo, name, value, pat, scope)`, which it imported from the per-repository secret deploy tool. PR #4731 retired that tool and removed the file, and `set_secret` went with it. Nothing in AssemblyZero recorded that a hook depended on the function, so no test failed. On the operator's Ubuntu run of 2026-11-14 the hook failed with `ModuleNotFoundError` before it could ask for its passphrase, and the run asked for one passphrase of the three it owed.

## R1: `tools/gh_actions_secret.py`

`set_secret(repo, name, value, pat, scope="actions", *, owner=GITHUB_USER) -> bool` is carried over from the removed tool unchanged in behaviour, with its two helpers:

- `_get_public_key` GETs `/repos/<owner>/<repo>/<scope>/secrets/public-key` and returns `(key_id, key)`, or None on a request exception or a status of 300 or above.
- `_encrypt_secret` seals the value against that key with PyNaCl's `SealedBox` and returns it base64.
- `set_secret` PUTs `{"encrypted_value", "key_id"}` to `/repos/<owner>/<repo>/<scope>/secrets/<name>` and returns True on a status below 300; False on a failed key fetch, a request exception or any other status.

Both calls go through the shared `tools/_gh_retry.py` `request_with_retry`, which the removed tool also used. `GITHUB_USER = "martymcenroe"` is the removed tool's owner constant; `owner=` is a new keyword-only argument defaulting to it, so the positional call the hook makes is unchanged. `SCOPES = ("actions", "dependabot")` names the two stores. The module has no CLI, no fleet loop and nothing specific to any one secret.

PyNaCl was only a transitive dependency (through PyGithub). It is now a direct one, `pynacl (>=1.6,<2)` in `pyproject.toml`. The lock keeps pynacl 1.6.2; only its `content-hash` changed.

## R2: the hook contract

`tools/new_repo.py` gains a module-level `HOOK_IMPORTABLE`, placed just above `run_post_create_hooks`:

```python
HOOK_IMPORTABLE: dict[str, tuple[str, ...]] = {
    "_pat_session": ("gpg_secret_session",),
    "gh_actions_secret": ("set_secret",),
}
```

`run_post_create_hooks`'s docstring says a hook may import from `tools/` only what `HOOK_IMPORTABLE` names, and names both. Nothing else in `new_repo.py` changed.

Runbook 0927's "handles automatically" list gains a "Post-create hooks" item naming the same contract. The paragraph about passphrase prompts is untouched, and the runbook's version and history table are left alone, since another change edits the same file.

## R3: the contract test

`tests/unit/test_gh_actions_secret.py::TestHookImportContract` pins the contract's content, imports every module it names from `tools/` and checks each name is callable, and runs a hook file that imports the whole contract through `run_post_create_hooks`. Removing either module fails the import of the test module or the parametrised import test.

## R4

The hook's own import lives in another repository and is changed there as its own change.

## Ruff

`ruff check` on `tools/gh_actions_secret.py` and `tests/unit/test_gh_actions_secret.py`: `All checks passed!`. On `tools/new_repo.py`, 20 findings before and after, the same counts per rule; none is on a changed line.
