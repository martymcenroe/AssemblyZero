"""Throw the Claude spend lock, in either direction (#3616).

The operator throws it week by week as his Anthropic quota exhausts, and he
does not edit files by hand. The lock has two halves:

- three entries in ``permissions.deny`` of ``~/.claude/settings.json``, which
  make Claude Code refuse a nested ``claude`` with a prompt flag from any
  agent's Bash;
- the file ``~/.claude/claude-spend.lock``, whose presence the shell guard and
  the AssemblyZero workflow read (#3615).

Dry run by default: the exact settings diff is printed and nothing is written.
``--apply`` writes, after copying the current settings to ``~/.claude/backups/``.
Nothing else in the settings file is touched.

    poetry run python tools/claude_spend_lock.py --status
    poetry run python tools/claude_spend_lock.py --lock --apply
    poetry run python tools/claude_spend_lock.py --unlock --apply
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SETTINGS = Path.home() / ".claude" / "settings.json"
LOCK_FILE = Path.home() / ".claude" / "claude-spend.lock"
BACKUP_DIR = Path.home() / ".claude" / "backups"

DENY_ENTRIES = (
    "Bash(claude -p:*)",
    "Bash(claude --print:*)",
    "Bash(claude --prompt:*)",
)

LOCK_TEXT = (
    "Placed by tools/claude_spend_lock.py (AssemblyZero #3616). While this file\n"
    "exists, no nested claude -p / --print / --prompt runs from any agent, and\n"
    "the AssemblyZero workflow refuses any claude: seat (#3615). Lift it with:\n"
    "    poetry run python tools/claude_spend_lock.py --unlock --apply\n"
)

EXIT_OK = 0
EXIT_BAD_JSON = 2
EXIT_VERIFY = 3


def render(obj: dict) -> str:
    """The settings text this tool writes: two-space JSON, one trailing newline."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def load(settings: Path) -> tuple[dict, str]:
    text = settings.read_text(encoding="utf-8")
    return json.loads(text), text


def deny_list(obj: dict) -> list:
    permissions = obj.setdefault("permissions", {})
    deny = permissions.setdefault("deny", [])
    if not isinstance(deny, list):
        raise ValueError("permissions.deny is not a list")
    return deny


def present(deny: list) -> list[str]:
    return [entry for entry in DENY_ENTRIES if entry in deny]


def with_lock(obj: dict) -> dict:
    """A copy of ``obj`` with the three entries appended to the deny list."""
    new = json.loads(json.dumps(obj))
    deny = deny_list(new)
    for entry in DENY_ENTRIES:
        if entry not in deny:
            deny.append(entry)
    return new


def without_lock(obj: dict) -> dict:
    """A copy of ``obj`` with exactly the three entries removed."""
    new = json.loads(json.dumps(obj))
    deny = deny_list(new)
    deny[:] = [entry for entry in deny if entry not in DENY_ENTRIES]
    return new


def status_lines(settings: Path, lock_file: Path) -> list[str]:
    lines = []
    try:
        obj, _ = load(settings)
        found = present(deny_list(obj))
        lines.append(f"settings deny entries: {len(found)} of {len(DENY_ENTRIES)} present ({settings})")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        lines.append(f"settings deny entries: unreadable ({settings}: {exc})")
    lines.append(
        f"lock file: {'present' if lock_file.is_file() else 'absent'} ({lock_file})"
    )
    return lines


def backup(settings: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backup_dir / f"{settings.name}.bak-{stamp}"
    target.write_bytes(settings.read_bytes())
    return target


def write_settings(settings: Path, text: str) -> None:
    """Stage beside the file, verify the staged text parses, then replace."""
    tmp = settings.with_name(settings.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))
    os.replace(tmp, settings)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Throw the Claude spend lock, in either direction.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--lock", action="store_true", help="add the deny entries and create the lock file")
    mode.add_argument("--unlock", action="store_true", help="remove the deny entries and delete the lock file")
    mode.add_argument("--status", action="store_true", help="report both halves and exit")
    ap.add_argument("--apply", action="store_true", help="write; without it, print what would change")
    ap.add_argument("--settings", type=Path, default=SETTINGS)
    ap.add_argument("--lock-file", type=Path, default=LOCK_FILE)
    ap.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    args = ap.parse_args(argv)

    if args.status:
        for line in status_lines(args.settings, args.lock_file):
            print(line)
        return EXIT_OK

    try:
        obj, text = load(args.settings)
        deny_list(obj)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"REFUSED: {args.settings} is not usable JSON ({exc}); nothing written")
        return EXIT_BAD_JSON

    new = with_lock(obj) if args.lock else without_lock(obj)
    new_text = render(new)
    settings_changed = new != obj
    lock_changed = args.lock != args.lock_file.is_file()

    if not settings_changed and not lock_changed:
        print(f"already {'locked' if args.lock else 'unlocked'}; nothing to change")
        return EXIT_OK

    if settings_changed:
        print("settings.json change:")
        for line in difflib.unified_diff(
            text.splitlines(), new_text.splitlines(),
            "settings.json (now)", "settings.json (after)", lineterm="", n=2,
        ):
            print(line)
    if lock_changed:
        print(f"lock file: {'create' if args.lock else 'delete'} {args.lock_file}")

    if not args.apply:
        print("\nDry run. Add --apply to do it.")
        return EXIT_OK

    if settings_changed:
        saved = backup(args.settings, args.backup_dir)
        write_settings(args.settings, new_text)
        check, _ = load(args.settings)
        if check != new:
            print(f"FAILED: {args.settings} did not read back as written; backup at {saved}")
            return EXIT_VERIFY
        print(f"updated {args.settings}; backup at {saved}")
    if lock_changed:
        if args.lock:
            args.lock_file.write_text(LOCK_TEXT, encoding="utf-8")
            print(f"created {args.lock_file}")
        else:
            args.lock_file.unlink()
            print(f"deleted {args.lock_file}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
