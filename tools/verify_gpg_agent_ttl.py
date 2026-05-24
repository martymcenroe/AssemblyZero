#!/usr/bin/env python3
"""verify_gpg_agent_ttl.py -- confirm gpg-agent cache TTL=0 per ADR-0216 sec 6.2.

Two-layer check:
  1. gpg-agent.conf contains all four cache-ttl directives explicitly set to 0
  2. The running gpg-agent reports current value 0 on all four

Exit 0 = both layers pass.
Exit 1 = at least one layer reports a non-compliant TTL; remediation printed.
Exit 2 = infrastructure problem (gpgconf missing, homedir not found, etc.).

Run from anywhere; the script touches no state. The conf file path is
discovered via `gpgconf --list-dirs homedir`, so it works on any host where
GnuPG is installed.

See docs/runbooks/0938-verify-gpg-agent-ttl.md for the operator-facing guide.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

REQUIRED = (
    "default-cache-ttl",
    "max-cache-ttl",
    "default-cache-ttl-ssh",
    "max-cache-ttl-ssh",
)


def die(msg: str) -> NoReturn:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(2)


def _msys_to_windows(p: str) -> str:
    """Convert MSYS-style /c/Users/... into Windows-native C:\\Users\\... .

    gpgconf on Windows ships in the Git for Windows MSYS bundle and emits
    POSIX-style paths (`/c/...`) regardless of the invoking shell. Python's
    `pathlib.Path` on Windows does not recognize that drive-letter idiom,
    so we normalize before constructing the Path.
    """
    if sys.platform != "win32":
        return p
    if len(p) >= 3 and p[0] == "/" and p[1].isalpha() and p[2] == "/":
        return p[1].upper() + ":" + p[2:].replace("/", "\\")
    return p


def gpg_homedir() -> Path:
    if not shutil.which("gpgconf"):
        die("gpgconf not on PATH (need GnuPG; on Windows it ships with Git for Windows)")
    out = subprocess.run(
        ["gpgconf", "--list-dirs", "homedir"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not out:
        die("gpgconf --list-dirs homedir returned an empty path")
    return Path(_msys_to_windows(out))


def read_conf(conf_path: Path) -> dict[str, str]:
    """Return {directive: value} parsed from gpg-agent.conf."""
    if not conf_path.exists():
        die(f"conf file does not exist: {conf_path}")
    found: dict[str, str] = {}
    for raw in conf_path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split(None, 1)
        if len(parts) != 2:
            continue
        directive, value = parts[0], parts[1].strip()
        if directive in REQUIRED:
            found[directive] = value
    return found


def query_running_agent() -> dict[str, str]:
    """Return {option: current_value} from `gpgconf --list-options gpg-agent`.

    Each line is colon-separated; the LAST field is the configured value
    (empty string = unconfigured, agent uses compiled-in default).
    """
    out = subprocess.run(
        ["gpgconf", "--list-options", "gpg-agent"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    found: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split(":")
        if not parts:
            continue
        name = parts[0]
        if name in REQUIRED:
            found[name] = parts[-1]
    return found


def main() -> int:
    home = gpg_homedir()
    conf = home / "gpg-agent.conf"
    failures: list[str] = []

    print(f"gpg homedir: {home}")
    print(f"conf file:   {conf}")
    print()

    print("[1/2] gpg-agent.conf:")
    conf_vals = read_conf(conf)
    for d in REQUIRED:
        v = conf_vals.get(d)
        if v == "0":
            print(f"  OK    {d} = 0")
        elif v is None:
            print(f"  FAIL  {d} = (missing)")
            failures.append(f"add `{d} 0` to {conf}")
        else:
            print(f"  FAIL  {d} = {v} (want 0)")
            failures.append(f"change `{d} {v}` to `{d} 0` in {conf}")

    print()
    print("[2/2] running gpg-agent:")
    agent_vals = query_running_agent()
    for d in REQUIRED:
        v = agent_vals.get(d)
        if v == "0":
            print(f"  OK    {d} = 0")
        elif not v:
            print(f"  FAIL  {d} = (unconfigured; agent uses non-zero default)")
            failures.append(
                "run `gpgconf --kill gpg-agent` so the next gpg call spawns a fresh "
                "agent that reads the updated conf"
            )
        else:
            print(f"  FAIL  {d} = {v} (want 0)")
            failures.append(
                "run `gpgconf --kill gpg-agent` so the next gpg call spawns a fresh "
                "agent that reads the updated conf"
            )

    print()
    if failures:
        print("Remediation:")
        for f in sorted(set(failures)):
            print(f"  - {f}")
        return 1

    print("PASS: all four cache-TTL directives are 0 in both conf and running agent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
