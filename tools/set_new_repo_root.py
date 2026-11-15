#!/usr/bin/env python3
"""Set where new_repo.py creates a new repository: one value in the config file (#4768).

#4763 gave `~/.assemblyzero/config.json` a `new_repo_root` setting, read by
`AssemblyZeroConfig.new_repo_root()`. That file is outside the Projects tree, where
the guard refuses every agent write, so the setting is changed only by the operator's
own hand. This program is that hand's checked way to do it, following the fleet's
pattern for programs the operator runs: one tracked file, landed through a PR, a dry
run by default.

Only the operator runs it with --apply, in his own terminal. An agent never does: a
program an agent ran with --apply would be the same refused write. An agent may run
it bare, which only reads.

## Usage

In bash, from any folder. `<AssemblyZero>` stands for the absolute path of the
AssemblyZero checkout; this file does not spell it (a test forbids spelling the
Projects root, #3609), and the dry run prints the --apply command with it filled in.

    poetry -C <AssemblyZero> run python <AssemblyZero>/tools/set_new_repo_root.py --root /home/mcwiz/Projects
    poetry -C <AssemblyZero> run python <AssemblyZero>/tools/set_new_repo_root.py --root /home/mcwiz/Projects --apply

The first prints the plan and changes nothing. The second makes the change.

## What one run does

It sets the key's spelling for the OS it runs on: `unix` on Ubuntu, `windows` on
Windows. A spelling the key already carries for the other OS is kept, and so is every
other key in the file. Each step prints one line.

  1. Refuses to run as root.
  2. Checks that --root is an absolute path to an existing directory, with no `..` in
     it (the loader blanks any path holding `..`).
  3. Reads the config file. An absent file starts from
     `{"version": "1.0", "paths": {}}`. A present one must parse as JSON and must pass
     the loader: a fresh `AssemblyZeroConfig()` must report no `load_error`.
  4. Records `projects_root`, `assemblyzero_root` and `user_claude_dir`, as this OS
     reads them, before the change.
  5. If the key already holds the root for this OS, says so and ends
     `OK: already set ...`, changing nothing.
  6. Prints the plan: the file, the key, the format, the old value and the new one,
     and the dated copy it will make.
  7. Without --apply, ends `OK: dry run, nothing changed`.
  8. With --apply: makes the folder if it is missing; copies an existing file to
     `config.json.<YYYYMMDD-HHMMSS>.bak` beside it; writes the merged file to
     `config.json.tmp` in the same folder and renames it into place.
  9. Proves the change: a fresh `AssemblyZeroConfig()` reports no `load_error`, its
     `new_repo_root(fmt='auto')` is the root, and the three paths recorded in step 4
     are unchanged.

It deletes nothing and moves nothing: the old file survives as the dated copy, and the
only rename is the new file's own `.tmp` taking its place. A refused step changes
nothing.

The last line is `OK: ...` with exit 0, or
`FAILED: <step>: <reason>. Nothing after this step was done. Paste this output to the
agent.` with exit 1.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import assemblyzero_config
except ImportError:
    # Fallback if running from a different directory
    sys.path.insert(0, str(Path(__file__).parent))
    import assemblyzero_config

KEY = assemblyzero_config.NEW_REPO_ROOT_KEY
OTHER_PATHS = ("projects_root", "assemblyzero_root", "user_claude_dir")


class Refused(Exception):
    """A step that cannot go on. Carries the step's name and the reason."""

    def __init__(self, step: str, reason: str) -> None:
        super().__init__(f"{step}: {reason}")
        self.step = step
        self.reason = reason


def _format() -> str:
    return "windows" if platform.system() == "Windows" else "unix"


def _check_user() -> str:
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        return "this OS has no user id to check; not root"
    uid = geteuid()
    if uid == 0:
        raise Refused("refuse root", "running as root; run it as yourself, without sudo")
    return f"running as user id {uid}, not root"


def _check_root(given: str) -> str:
    path = Path(given)
    if not path.is_absolute():
        raise Refused("check --root", f"{given} is not an absolute path")
    if ".." in str(path):
        raise Refused("check --root", f"{given} holds '..', which the config loader blanks")
    if not path.is_dir():
        raise Refused("check --root", f"{given} is not an existing directory")
    return str(path)


def _read(config_path: Path) -> tuple[dict, assemblyzero_config.AssemblyZeroConfig, str]:
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise Refused(
                "read the config",
                f"{config_path} is not valid JSON (line {e.lineno}, column {e.colno})",
            ) from e
        except UnicodeDecodeError as e:
            raise Refused("read the config", f"{config_path} is not UTF-8 text") from e
        except OSError as e:
            raise Refused(
                "read the config", f"{config_path} could not be read ({e.strerror or type(e).__name__})"
            ) from e
        said = f"{config_path} exists and parses as JSON"
    else:
        data = {"version": "1.0", "paths": {}}
        said = f'{config_path} does not exist; starting from {{"version": "1.0", "paths": {{}}}}'
    loaded = assemblyzero_config.AssemblyZeroConfig()
    if loaded.load_error is not None:
        raise Refused("read the config", loaded.load_error)
    return data, loaded, said + ", and the loader accepts it"


def _fail(step: str, reason: str) -> int:
    print(f"FAILED: {step}: {reason}. Nothing after this step was done. Paste this output to the agent.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Set new_repo_root in ~/.assemblyzero/config.json (#4768). Dry run unless --apply."
    )
    parser.add_argument("--root", required=True, help="absolute path of an existing directory")
    parser.add_argument("--apply", action="store_true", help="make the change (the operator only)")
    args = parser.parse_args(argv)

    config_path = Path(assemblyzero_config.CONFIG_PATH)
    fmt = _format()

    try:
        print(f"Step 1, user: {_check_user()}.")
        root = _check_root(args.root)
        print(f"Step 2, --root: {root} is an absolute path to an existing directory.")
        data, loaded, said = _read(config_path)
        print(f"Step 3, read: {said}.")
    except Refused as r:
        return _fail(r.step, r.reason)

    before = {name: getattr(loaded, name)(fmt="auto") for name in OTHER_PATHS}
    print("Step 4, record: " + ", ".join(f"{name} is {value}" for name, value in before.items()) + ".")

    entry = data["paths"].get(KEY, {})
    old = entry.get(fmt)
    if old == root:
        print(f"Step 5, compare: paths.{KEY}.{fmt} already holds {root}.")
        print(f"OK: already set: new_repo_root is {root} in {config_path}; nothing changed")
        return 0
    shown_old = old if old is not None else f"(not set: new repositories go under projects_root, {before['projects_root']})"
    print(f"Step 5, compare: paths.{KEY}.{fmt} is {shown_old}; it will change.")

    stamp = datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S")  # local time
    backup = config_path.with_name(f"{config_path.name}.{stamp}.bak")
    tmp = config_path.with_name(f"{config_path.name}.tmp")
    copy = f"copy the file first to {backup}" if config_path.exists() else "no copy: the file does not exist yet"
    print(
        f"Step 6, plan: in {config_path}, set paths.{KEY}.{fmt} (format {fmt}): "
        f"{shown_old} -> {root}; {copy}."
    )

    if not args.apply:
        this = Path(__file__).resolve()
        print(
            "Step 7, dry run: to make the change, the operator runs, in bash: "
            f"poetry -C {this.parents[1]} run python {this} --root {root} --apply"
        )
        print("OK: dry run, nothing changed")
        return 0

    merged = dict(entry)
    merged[fmt] = root
    data["paths"][KEY] = merged
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return _fail("make the folder", f"{config_path.parent} could not be made ({e})")
    print(f"Step 8a, folder: {config_path.parent} exists.")

    if config_path.exists():
        if backup.exists():
            return _fail("copy the file", f"{backup} already exists; run it again in a second")
        try:
            shutil.copy2(config_path, backup)
        except OSError as e:
            return _fail("copy the file", f"{config_path} could not be copied to {backup} ({e})")
        print(f"Step 8b, copy: {config_path} copied to {backup}.")
    else:
        print("Step 8b, copy: no file to copy.")

    try:
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, config_path)
    except OSError as e:
        return _fail("write the file", f"{config_path} could not be written through {tmp} ({e})")
    print(f"Step 8c, write: {config_path} written through {tmp}.")

    proof = assemblyzero_config.AssemblyZeroConfig()
    problems = []
    if proof.load_error is not None:
        problems.append(f"the loader refuses the new file: {proof.load_error}")
    else:
        got = proof.new_repo_root(fmt="auto")
        if got != root:
            problems.append(f"new_repo_root reads back as {got}, not {root}")
        for name, value in before.items():
            now = getattr(proof, name)(fmt="auto")
            if now != value:
                problems.append(f"{name} moved from {value} to {now}")
    if problems:
        kept = f"the old file is kept at {backup}" if backup.exists() else "there was no old file"
        return _fail("prove the change", "; ".join(problems) + f"; {kept}")
    print(f"Step 9, prove: the loader reads new_repo_root as {root}, and the other three paths are unchanged.")
    print(f"OK: new_repo_root is {root} in {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
