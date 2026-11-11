# Implementation report: #4701

`tools/_pat_session.py`, its tests, and two sentences of ADR-0216 section 3.

## The box names its secret

gpg's own pinentry box for a passphrase-only file says only "Please enter the passphrase for decryption." Every session in the module (`classic_pat_session`, `cerberus_pem_session`, `pr_sentinel_app_session`, `gpg_secret_session`) now asks gpg-agent for the passphrase itself, so the box carries the module's own words. The mechanism is copied from a working prompt in a private tool:

- `_box_text(secret_name, path, reason)` builds the box text: the secret's name, then `The passphrase for the file <path>.`, then `For: <reason>.` when the caller gave one.
- `_ask_passphrase(text, error, secret_name)` sends `GET_PASSPHRASE X <error|X> Passphrase: <text>` to `gpg-connect-agent`, cache id X so nothing is cached, after `OPTION ttyname` and `OPTION ttytype` when the run has a terminal (`GPG_TTY`, else stdin's; `new_repo.py` records `GPG_TTY` before it detaches stdin). The answer, the passphrase in hex, stays in the process. An `ERR` that means pinentry never reached him raises `PinentryUnavailable`, as before; Cancel raises `RuntimeError("decrypt declined by operator (pinentry cancelled)")` and gpg does not run.
- `_run_gpg(path, passphrase)` runs `gpg --batch --quiet --pinentry-mode loopback --no-symkey-cache --passphrase-fd <fd> --decrypt <path>`, the passphrase written to an `os.pipe()` passed with `pass_fds` (fd 0 with `input` on Windows). Never argv, the environment or a file.
- After a failed try the next box shows `That passphrase did not open it (try N of 5).` above its text.

The banner keeps its fields; its first line now reads `PASSPHRASE NEEDED -- a box named "<secret>" is about to ask`. The wait still has no limit (#4204).

For the classic PAT, the box reads:

```
GitHub classic PAT (admin scope)

The passphrase for the file /home/<user>/.secrets/classic-pat.gpg.
```

## The superseded draft

An earlier uncommitted draft on this branch asked in a `getpass` terminal prompt instead. It was reverted file by file before this change, and none of its runbook or `new_repo.py` edits are in this commit.

## Lint

`ruff check` on the changed files reports only findings on lines this change does not touch (`UP035` on the module's `typing` import, `RUF100` and `SIM117` in the older test files). The new code and the new test file are clean.
