# Implementation report: #4766

## The defect

The six tests in `tests/unit/test_pat_session_named_prompt.py::TestRealGpg` failed on Ubuntu with gpg's `General error`: gpg-agent would not start in the test's gpg home. The `pinentry_marker` fixture made that home at `tmp_path / "g"`, and `tmp_path` carries the test's name.

## What was measured

Ubuntu (WSL), gpg 2.4.8, `TMPDIR=/home/mcwiz/agent-tmp/claude-pid-2292220`. `/run/user/1000` does not exist, so `gpgconf --list-dirs socketdir` reports the gpg home itself, and gpg-agent puts its sockets there.

- A failing test's home was `/home/mcwiz/agent-tmp/claude-pid-2292220/pytest-of-mcwiz/pytest-88/test_the_right_passphrase_decr0/g`, 100 characters. Its sockets would be `S.gpg-agent` at 112, `S.gpg-agent.ssh` at 116, `S.gpg-agent.extra` at 118 and `S.gpg-agent.browser` at 120.
- `gpg-agent --homedir <home> --daemon`, started by hand in a throwaway home of the same length under `$TMPDIR`, exited 2 with `socket name '<home>/S.gpg-agent' is too long`.
- In a throwaway home of 55 characters (browser socket 75) it started: `gpg-agent (GnuPG) 2.4.8 started`, and `GETINFO version` answered `2.4.8`.
- The boundary, with the browser socket at an exact length: 106 started; 107 and 108 exited 2 with `socket name '<home>/S.gpg-agent.browser' is too long`. gpg-agent refuses a socket path of 107 bytes or more.

Every agent started by hand was stopped with `gpgconf --kill gpg-agent` for its own home.

## The change

All of it is in `tests/unit/test_pat_session_named_prompt.py`; `tools/_pat_session.py` is unchanged.

- The fixture's home is `tmp_path_factory.mktemp("g")`: still under pytest's own temporary folder, with no test name in its path. Under the same `TMPDIR` its browser socket path is 89 bytes, counted in a run's own homes (`pytest-91/g0` through `g5`).
- `GPG_SOCKET_LIMIT = 107`, the measured limit.
- `_socket_dir(home)` asks `gpgconf --list-dirs socketdir` where the sockets go, so a machine that has `/run/user/<uid>` is checked where gpg really puts them.
- `_check_socket_paths(socket_dir)` fails the test, before gpg runs, when the longest of `S.gpg-agent`, `.extra`, `.browser` and `.ssh` is 107 bytes or more. The message names the socket path, its length in bytes and the limit, and says to shorten `TMPDIR` (R2). The fixture calls it.
- The tests still run real gpg and real gpg-agent (R3).

## Tests

`TestGpgHomeLength` holds two new tests; the test report maps them to the issue's tests.

## Not covered

A gpg-agent that fails to start for some cause other than a socket path's length still surfaces only gpg's own message.

## Ruff

`ruff check tests/unit/test_pat_session_named_prompt.py`: `All checks passed!`
