# Test report: #4766

## Tests

All in `tests/unit/test_pat_session_named_prompt.py`. Every gpg home is under pytest's temporary folder; no test reads or touches the real gpg home or `~/.secrets`.

| Test | Tests |
|---|---|
| T1 (R1, R3) | `TestRealGpg`, unchanged: `test_the_right_passphrase_decrypts_with_no_box_from_gpg` (`classic_pat`, `cerberus_pem`, `pr_sentinel_app`, `gpg_secret`), `test_a_wrong_passphrase_fails_cleanly`, `test_the_passphrase_is_never_in_argv_env_output_or_errors`, now with the fixture's short gpg home and real gpg |
| T2 (R2) | `TestGpgHomeLength::test_a_home_too_long_for_gpg_agent_fails_naming_the_path_and_its_length`: a home whose browser socket is far over the limit fails the check, and the message names that socket path, its length in bytes and the limit |
| The limit, against real gpg | `TestGpgHomeLength::test_the_limit_is_where_real_gpg_agent_stops_starting`: in homes built so the browser socket is exactly 106 and 107 bytes, the check passes at 106 and real gpg-agent starts; the check fails at 107 and real gpg-agent exits non-zero with `is too long`. It skips where gpg keeps its sockets outside the gpg home |

## Targeted runs, 2026-11-15

Ubuntu, in an agent session, `TMPDIR=/home/mcwiz/agent-tmp/claude-pid-2292220`.

- Before, at a4a0dc52: `6 failed, 8 passed, 1 warning in 22.98s`. All six are `TestRealGpg`, each with `General error`.
- After: `16 passed, 1 warning in 18.40s`, nothing skipped. The warning is the pydantic one on Python 3.14, the same as before.
- No gpg-agent from the run was left running.

## Not covered here

The unit tier on Ubuntu is run separately, before the change lands.
