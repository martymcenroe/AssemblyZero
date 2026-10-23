# Implementation Report: #4204

`tools/_pat_session.py` gave every gpg decrypt a 180-second timeout. gpg waits inside pinentry for the operator's passphrase, so a run whose operator was not at the prompt within three minutes was killed under him. On 2026-10-22 that stopped a `new_repo.py` run after the local scaffold and before the GitHub repository existed.

`GPG_TIMEOUT_S` is now `None` in `tools/_pat_session.py` and `tools/verify_encrypted_secret.py`, so the wait has no limit, as the law requires ("No timeouts that override the human"). A prompt that never reaches him still fails at once through `PinentryUnavailable` (#4135). The four docstrings that promised a `subprocess.TimeoutExpired` from the wait now say there is no limit.
