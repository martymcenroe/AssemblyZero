# Test report: #4701

## Targeted

`tests/unit/test_pat_session_named_prompt.py` (new):

- `TestBoxText::test_classic_pat_box_says_classic_pat_and_its_file`: the classic PAT's box text contains "classic PAT" and the file path, and equals the exact text. Built from the default path; the file is never opened.
- `test_the_reason_follows_the_name_and_file`.
- `test_every_session_asks_the_agent_with_its_name_and_file`, for all four sessions: the first call is `gpg-connect-agent` with the `GET_PASSPHRASE` line carrying that session's box text; the second is gpg with `--pinentry-mode loopback`, `--passphrase-fd` and `--no-symkey-cache`, and no passphrase in argv.
- `test_a_retry_box_says_the_passphrase_did_not_open_it`, `test_cancel_in_the_box_stops_before_gpg`.
- `TestRealGpg`, real gpg on a throwaway file encrypted in the test's own GNUPGHOME with a dummy passphrase, a stand-in pinentry that marks if called, and a stand-in for the box: the right passphrase decrypts for all four sessions with no box from gpg; five wrong passphrases fail cleanly with a `RuntimeError` holding no passphrase; the passphrase is in no argv, environment, stdout, stderr or error, and reaches gpg only through `--passphrase-fd`.

Existing files, adjusted for the agent call that now comes first: `tests/tools/test_pat_session.py` (an autouse stand-in for the box), `tests/unit/test_gpg_wait_has_no_timeout.py` and `tests/unit/test_pat_session_terminal.py` (both calls have no timeout and capture output; a fake agent answers the no-terminal case), `tests/unit/test_new_repo_post_create_hooks.py`, and `tests/unit/test_new_repo_safety.py` (a fake agent shows the box is drawn on the terminal `GPG_TTY` names after stdin is detached).

The six files: 76 passed.

## Real calls

No real passphrase box was opened and nothing under `~/.secrets` was read, touched or decrypted.

## Full suite

Not run, on the operator's instruction of 2026-11-11: this change lands on targeted tests, and CI is the full check.
