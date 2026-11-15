#!/usr/bin/env python3
"""Set where the fleet's Projects roots setting is: one pointer in the config file (#4773).

`assemblyzero.core.projects_root` reads every Projects root from one setting that
lives in a private repository. This public repository never names it; the operator's
`~/.assemblyzero/config.json` points at it with `paths.projects_roots_file`. That file
is outside the Projects tree, where the guard refuses every agent write, so this
program is the operator's checked way to set the pointer, following
`tools/set_new_repo_root.py`'s pattern: one tracked file, a dry run by default.

Only the operator runs it with --apply, in his own terminal. An agent never does. An
agent may run it bare, which only reads.

## Usage

In bash, from any folder. `<AssemblyZero>` stands for the absolute path of the
AssemblyZero checkout (a test forbids spelling the Projects root, #3609), and
`<setting>` for the absolute path of the roots setting. The dry run prints the
--apply command with both filled in.

    poetry -C <AssemblyZero> run python <AssemblyZero>/tools/set_projects_roots_file.py --file <setting>
    poetry -C <AssemblyZero> run python <AssemblyZero>/tools/set_projects_roots_file.py --file <setting> --apply

## What one run does

It sets the key's spelling for the OS it runs on: `unix` on Ubuntu, `windows` on
Windows. A spelling for the other OS, and every other key, are kept.

  1. Refuses to run as root.
  2. Checks that --file is an absolute path to an existing file, with no `..`, that
     parses as a roots setting by `projects_root.read_roots_setting`.
  3. Checks that every root the setting names exists on this side, spelled for it.
  4. Reads the config file; a fresh `AssemblyZeroConfig()` must report no `load_error`.
  5. Records `projects_root`, `assemblyzero_root`, `user_claude_dir` and `new_repo_root`.
  6. If the key already holds the file for this OS, ends `OK: already set ...`.
  7. Prints the plan and the dated copy it will make.
  8. Without --apply, ends `OK: dry run, nothing changed`.
  9. With --apply: makes the folder; copies an existing file to
     `config.json.<YYYYMMDD-HHMMSS>.bak`; writes `config.json.tmp` and renames it into place.
  10. Proves the change: a fresh `projects_roots()` equals the setting's roots spelled for
     this side, and the four paths recorded in step 5 are unchanged.

The last line is `OK: ...` with exit 0, or
`FAILED: <step>: <reason>. Nothing after this step was done. Paste this output to the
agent.` with exit 1.

The write, copy and prove steps are duplicated from set_new_repo_root.py rather than
shared: its test holds that it imports only the standard library and the loader.
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

    from assemblyzero.core import projects_root
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import assemblyzero_config

    from assemblyzero.core import projects_root

KEY = assemblyzero_config.PROJECTS_ROOTS_FILE_KEY
OTHER_PATHS = ("projects_root", "assemblyzero_root", "user_claude_dir", "new_repo_root")


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


def _check_file(given: str, windows: bool) -> tuple[str, list[Path]]:
    path = Path(given)
    if not path.is_absolute():
        raise Refused("check --file", f"{given} is not an absolute path")
    if ".." in path.parts:
        raise Refused("check --file", f"{given} holds '..'")
    if not path.is_file():
        raise Refused("check --file", f"{given} is not an existing file")
    try:
        roots = projects_root.read_roots_setting(path, windows=windows)
    except RuntimeError as e:
        raise Refused("check --file", str(e)) from e
    return str(path), roots


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
        description="Set projects_roots_file in ~/.assemblyzero/config.json (#4773). Dry run unless --apply."
    )
    parser.add_argument("--file", required=True, help="absolute path of the fleet's roots setting")
    parser.add_argument("--apply", action="store_true", help="make the change (the operator only)")
    args = parser.parse_args(argv)

    config_path = Path(assemblyzero_config.CONFIG_PATH)
    fmt = _format()
    windows = fmt == "windows"

    try:
        print(f"Step 1, user: {_check_user()}.")
        setting, roots = _check_file(args.file, windows)
        print(f"Step 2, --file: {setting} is a roots setting naming {len(roots)} root(s).")
        missing = projects_root.missing_roots(roots)
        if missing:
            raise Refused(
                "check the roots",
                "the setting names a root that does not exist on this side: "
                + ", ".join(str(root) for root in missing),
            )
        print("Step 3, roots: every root exists here: " + ", ".join(str(root) for root in roots) + ".")
        data, loaded, said = _read(config_path)
        print(f"Step 4, read: {said}.")
    except Refused as r:
        return _fail(r.step, r.reason)

    before = {name: getattr(loaded, name)(fmt="auto") for name in OTHER_PATHS}
    print("Step 5, record: " + ", ".join(f"{name} is {value}" for name, value in before.items()) + ".")

    entry = data["paths"].get(KEY, {})
    old = entry.get(fmt)
    if old == setting:
        print(f"Step 6, compare: paths.{KEY}.{fmt} already holds {setting}.")
        print(f"OK: already set: {KEY} is {setting} in {config_path}; nothing changed")
        return 0
    shown_old = old if old is not None else "(not set: the one root is AssemblyZero's parent)"
    print(f"Step 6, compare: paths.{KEY}.{fmt} is {shown_old}; it will change.")

    stamp = datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S")  # local time
    backup = config_path.with_name(f"{config_path.name}.{stamp}.bak")
    tmp = config_path.with_name(f"{config_path.name}.tmp")
    copy = f"copy the file first to {backup}" if config_path.exists() else "no copy: the file does not exist yet"
    print(
        f"Step 7, plan: in {config_path}, set paths.{KEY}.{fmt} (format {fmt}): "
        f"{shown_old} -> {setting}; {copy}."
    )

    if not args.apply:
        this = Path(__file__).resolve()
        print(
            "Step 8, dry run: to make the change, the operator runs, in bash: "
            f"poetry -C {this.parents[1]} run python {this} --file {setting} --apply"
        )
        print("OK: dry run, nothing changed")
        return 0

    merged = dict(entry)
    merged[fmt] = setting
    data["paths"][KEY] = merged
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return _fail("make the folder", f"{config_path.parent} could not be made ({e})")
    print(f"Step 9a, folder: {config_path.parent} exists.")

    if config_path.exists():
        if backup.exists():
            return _fail("copy the file", f"{backup} already exists; run it again in a second")
        try:
            shutil.copy2(config_path, backup)
        except OSError as e:
            return _fail("copy the file", f"{config_path} could not be copied to {backup} ({e})")
        print(f"Step 9b, copy: {config_path} copied to {backup}.")
    else:
        print("Step 9b, copy: no file to copy.")

    try:
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, config_path)
    except OSError as e:
        return _fail("write the file", f"{config_path} could not be written through {tmp} ({e})")
    print(f"Step 9c, write: {config_path} written through {tmp}.")

    proof = assemblyzero_config.AssemblyZeroConfig()
    problems = []
    if proof.load_error is not None:
        problems.append(f"the loader refuses the new file: {proof.load_error}")
    else:
        try:
            got = projects_root.projects_roots(windows=windows)
        except RuntimeError as e:
            got = [f"(raised: {e})"]
        if got != roots:
            problems.append(
                "projects_roots() reads back as " + ", ".join(str(g) for g in got)
                + ", not " + ", ".join(str(r) for r in roots)
            )
        for name, value in before.items():
            now = getattr(proof, name)(fmt="auto")
            if now != value:
                problems.append(f"{name} moved from {value} to {now}")
    if problems:
        kept = f"the old file is kept at {backup}" if backup.exists() else "there was no old file"
        return _fail("prove the change", "; ".join(problems) + f"; {kept}")
    print(f"Step 10, prove: projects_roots() reads the setting's {len(roots)} root(s), and the other four paths are unchanged.")
    print(f"OK: {KEY} is {setting} in {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
