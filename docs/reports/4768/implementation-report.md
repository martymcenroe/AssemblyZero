# Implementation report: #4768

## The defect

#4763 put `new_repo_root` in `~/.assemblyzero/config.json`. That file is outside the Projects tree, where the guard refuses every agent write, so only the operator can change the setting, and nothing gave him a checked way to do it.

## The program (R1 to R7)

`tools/set_new_repo_root.py` follows the fleet's pattern for programs the operator runs: one tracked file, a dry run by default, `--apply` to change anything, and only the operator runs it with `--apply`.

- It sets `paths.new_repo_root.unix` on Ubuntu and `paths.new_repo_root.windows` on Windows, chosen by `platform.system()`, the loader's own test. A spelling for the other OS, and every other key in the file, are kept (R1, R3).
- Steps 1 to 3 refuse before anything is written: running as root, a `--root` that is not an absolute path to an existing directory, and a config file that is not valid JSON, is not UTF-8, or that a fresh `AssemblyZeroConfig()` reports a `load_error` for (R4). A root holding `..` is refused too, because the loader blanks any such path and the proof would fail only after the write.
- A key that already holds the root ends `OK: already set ...` and changes nothing (R5). `--root` is normalized through `Path`, so a trailing slash is the same root.
- With `--apply`, it makes the folder, copies an existing file with `shutil.copy2` to `config.json.<YYYYMMDD-HHMMSS>.bak`, writes `config.json.tmp` in the same folder and renames it into place with `os.replace` (R3). A dated copy that already exists stops the run before it is overwritten.
- A fresh `AssemblyZeroConfig()` then proves the change: no `load_error`, `new_repo_root(fmt='auto')` is the root, and `projects_root`, `assemblyzero_root` and `user_claude_dir` are what step 4 recorded (R6).
- The last line is `OK: ...` with exit 0, or `FAILED: <step>: <reason>. Nothing after this step was done. Paste this output to the agent.` with exit 1 (R7).

It deletes nothing and imports only the standard library and `assemblyzero_config`; a test parses the file and holds both.

## The header's command

The coordinator's order named the command with the checkout's absolute path. `tests/unit/test_no_spelled_projects_root.py` forbids spelling that path anywhere under `tools/` (#3609), so the header writes `<AssemblyZero>` in its place and says why, and the dry run prints the full `--apply` command with the path derived from the program's own location.

## The run against the real path

Run bare in the worktree on 2026-11-14, it read `~/.assemblyzero/config.json` as absent, planned `paths.new_repo_root.unix: (not set) -> /home/mcwiz/Projects` with no copy, and ended `OK: dry run, nothing changed`. Nothing was written. No agent ran it with `--apply`.

## Tests

`tests/unit/test_set_new_repo_root.py`, 23 tests; the test report maps them to T1 to T6.

## Ruff

`ruff check tools/set_new_repo_root.py tests/unit/test_set_new_repo_root.py`: all checks passed.
