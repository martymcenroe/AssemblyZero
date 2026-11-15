"""Where this checkout is, and every Projects root the fleet keeps (#3609, #4773).

AssemblyZero runs unchanged on Windows and on Ubuntu (WSL), where the same
Projects tree is ``C:\\Users\\<user>\\Projects`` on one side and
``/mnt/c/Users/<user>/Projects`` on the other. Code therefore never writes a
root out: ``REPO_ROOT`` is taken from where this file sits.

The fleet keeps repositories under more than one Projects root (one on the
Windows drive, one on Ubuntu's own disk). Every root is listed in one setting,
a JSON object whose ``roots`` key is a list of absolute paths in Ubuntu's
spelling. That setting lives outside this public repository; the operator's
``~/.assemblyzero/config.json`` points at it with
``paths.projects_roots_file`` (``{"unix": ..., "windows": ...}``), which he
sets with ``tools/set_projects_roots_file.py``. With no pointer, the one root
is the checkout's parent, as before.

``PROJECTS_ROOTS`` (every root) and ``PROJECTS`` (the first) are read when they
are asked for, never at import: a tool that imports this module only for
``REPO_ROOT`` or ``spellings`` reads no config, and a broken pointer stops only
the tools that need the roots.

``spellings(path)`` gives the three ways a drive path is written in text the
fleet reads (handoffs, transcripts, CLAUDE.md files), for the few tools that
must recognise a path inside text rather than open one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

#: The AssemblyZero checkout this module belongs to.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The operator's AssemblyZero config, whose paths.projects_roots_file points at
#: the fleet's roots setting. Read only when the roots are asked for.
CONFIG_PATH = Path.home() / ".assemblyzero" / "config.json"

#: The pointer's key under ``paths`` (``tools/assemblyzero_config.py`` names it too).
PROJECTS_ROOTS_FILE_KEY = "projects_roots_file"

#: The Ubuntu distribution Windows reaches through ``//wsl.localhost/<distro>``.
WSL_DISTRO = "Ubuntu"

#: What ``roots_source()`` says when no pointer is configured for this side.
DERIVED = "derived from AssemblyZero's location (no projects_roots_file configured)"


def _windows() -> bool:
    """True on Windows, where each root takes its Windows spelling."""
    return sys.platform == "win32"


def _side(windows: bool | None) -> bool:
    return _windows() if windows is None else windows


def spell_root(root: str, windows: bool) -> str:
    """One root from the setting (Ubuntu's spelling), as the given side writes it.

    On Ubuntu a root is used as written. On Windows ``/mnt/<d>/rest`` becomes
    ``<D>:/rest``, and any other absolute path is reached through WSL as
    ``//wsl.localhost/<WSL_DISTRO>/rest``.
    """
    if not windows:
        return root
    parts = root.split("/")
    if len(parts) >= 3 and parts[0] == "" and parts[1] == "mnt" and len(parts[2]) == 1 and parts[2].isalpha():
        return f"{parts[2].upper()}:/" + "/".join(parts[3:])
    return f"//wsl.localhost/{WSL_DISTRO}{root}"


def _roots_as_written(setting: Path) -> list[str]:
    """The roots a setting lists, in Ubuntu's spelling, or RuntimeError naming the file and the reason."""

    def broken(reason: str) -> RuntimeError:
        return RuntimeError(f"the Projects roots setting {setting} {reason}")

    try:
        text = setting.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise broken("is not UTF-8 text") from e
    except OSError as e:
        raise broken(f"could not be read ({e.strerror or type(e).__name__})") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise broken(f"is not valid JSON (line {e.lineno}, column {e.colno})") from e
    if not isinstance(data, dict):
        raise broken("is not a JSON object")
    if "roots" not in data:
        raise broken("has no 'roots' key")
    roots = data["roots"]
    if not isinstance(roots, list):
        raise broken("holds 'roots' that is not a list")
    if not roots:
        raise broken("holds 'roots' that is empty")
    seen: list[str] = []
    for entry in roots:
        if not isinstance(entry, str):
            raise broken(f"holds a root that is not a string: {entry!r}")
        if not entry.startswith("/"):
            raise broken(f"holds a root that is not an absolute path in Ubuntu's spelling: {entry!r}")
        normal = str(PurePosixPath(entry))
        if normal in seen:
            raise broken(f"names the root {normal} more than once")
        seen.append(normal)
    return seen


def read_roots_setting(setting: Path | str, windows: bool | None = None) -> list[Path]:
    """Read and validate a roots setting, and give its roots spelled for one side.

    ``windows`` picks the side; ``None`` is the side this runs on. A setting
    that cannot be read, is not JSON, or does not hold ``roots`` as a non-empty
    list of distinct absolute Ubuntu paths raises RuntimeError naming the file
    and the reason.
    """
    side = _side(windows)
    return [Path(spell_root(root, side)) for root in _roots_as_written(Path(setting))]


def projects_roots_file(windows: bool | None = None) -> Path | None:
    """The roots setting's path, from the config's ``paths.projects_roots_file``, for one side.

    ``None`` when the config file, the key, or this side's format (``unix`` on
    Ubuntu, ``windows`` on Windows) is absent; the other side's value is never
    used. A config that cannot be read, or a pointer that is not an object of
    absolute paths, raises RuntimeError naming the config file and the reason.
    """
    fmt = "windows" if _side(windows) else "unix"
    config = CONFIG_PATH

    def broken(reason: str) -> RuntimeError:
        return RuntimeError(f"{config} {reason}")

    if not config.exists():
        return None
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except UnicodeDecodeError as e:
        raise broken("is not UTF-8 text, so paths.projects_roots_file cannot be read") from e
    except OSError as e:
        raise broken(f"could not be read ({e.strerror or type(e).__name__})") from e
    except json.JSONDecodeError as e:
        raise broken(
            f"is not valid JSON (line {e.lineno}, column {e.colno}), so paths.projects_roots_file cannot be read"
        ) from e
    if not isinstance(data, dict):
        raise broken("is not a JSON object, so paths.projects_roots_file cannot be read")
    paths = data.get("paths")
    if paths is None:
        return None
    if not isinstance(paths, dict):
        raise broken("holds 'paths' that is not an object; 'paths' must be an object")
    if PROJECTS_ROOTS_FILE_KEY not in paths:
        return None
    entry = paths[PROJECTS_ROOTS_FILE_KEY]
    where = f"paths.{PROJECTS_ROOTS_FILE_KEY}"
    if not isinstance(entry, dict):
        raise broken(f"holds {where} that is not an object; it must be an object like {{\"unix\": ...}}")
    if "unix" not in entry and "windows" not in entry:
        raise broken(f"holds {where} that carries neither 'windows' nor 'unix'")
    if fmt not in entry:
        return None
    value = entry[fmt]
    if not isinstance(value, str):
        raise broken(f"holds {where}.{fmt} that is not a string; it must be a string")
    if ".." in Path(value).parts:
        raise broken(f"holds {where}.{fmt} = {value}, which holds '..'")
    if not Path(value).is_absolute():
        raise broken(f"holds {where}.{fmt} = {value}, which is not an absolute path")
    return Path(value)


def _resolve(windows: bool | None) -> tuple[list[Path], str]:
    """(the roots for one side, where they came from)."""
    side = _side(windows)
    setting = projects_roots_file(side)
    if setting is None:
        return [REPO_ROOT.parent], DERIVED
    try:
        roots = read_roots_setting(setting, side)
    except RuntimeError as e:
        raise RuntimeError(
            f"{CONFIG_PATH} paths.{PROJECTS_ROOTS_FILE_KEY} names a broken setting: {e}"
        ) from e
    return roots, str(setting)


def projects_roots(windows: bool | None = None) -> list[Path]:
    """Every Projects root, in order, spelled for one side (``None``: this side).

    From the setting the pointer names when it is set; ``[REPO_ROOT.parent]``
    when it is not. A pointer that is set but broken raises RuntimeError naming
    the config file, the setting and the reason.
    """
    return _resolve(windows)[0]


def roots_source(windows: bool | None = None) -> str:
    """Where ``projects_roots()`` came from: the setting's path, or ``DERIVED``."""
    return _resolve(windows)[1]


def missing_roots(roots: list[Path] | list[str]) -> list[Path]:
    """The roots, in order, that are not an existing directory."""
    return [Path(root) for root in roots if not Path(root).is_dir()]


def _require_all(roots: list[Path]) -> None:
    missing = missing_roots(roots)
    if missing:
        raise RuntimeError(
            "a Projects root does not exist, so no root is walked: "
            + ", ".join(str(root) for root in missing)
            + "; restore it or take it out of the roots setting"
        )


def repositories(roots: list[Path] | list[str] | None = None) -> tuple[list[Path], dict[str, list[Path]]]:
    """Every primary checkout under every root, and every name held under more than one.

    Returns ``(found, twice)``. ``found`` lists each folder whose ``.git`` is a
    directory, in root order and sorted by name within a root, leaving out any
    name held under two or more roots. ``twice`` maps each such name to the
    roots holding it: no tool judges it until the operator removes one copy.

    ``roots`` defaults to ``projects_roots()``; with no pointer configured, one
    line saying so goes to stderr. Any missing root raises RuntimeError naming
    every missing root before anything is listed.
    """
    if roots is None:
        given, source = _resolve(None)
        if source == DERIVED:
            print(f"one Projects root in use: {given[0]} ({source})", file=sys.stderr)
    else:
        given = [Path(root) for root in roots]
    _require_all(given)
    per_root: list[list[Path]] = []
    held: dict[str, list[Path]] = {}
    for root in given:
        here = sorted(
            (child for child in root.iterdir() if child.is_dir() and (child / ".git").is_dir()),
            key=lambda child: child.name,
        )
        per_root.append(here)
        for child in here:
            held.setdefault(child.name, []).append(root)
    twice = {name: where for name, where in held.items() if len(where) > 1}
    found = [child for here in per_root for child in here if child.name not in twice]
    return found, twice


def locate_repo(name: str, roots: list[Path] | list[str] | None = None) -> Path:
    """The one path holding ``name`` under the roots.

    Held under one root: that path. Under none: ``roots[0] / name``, so a
    caller's own missing-repository check still speaks. Under more than one:
    RuntimeError naming every copy. A missing root raises too, since a second
    copy could be under it.
    """
    given = projects_roots() if roots is None else [Path(root) for root in roots]
    _require_all(given)
    copies = [root / name for root in given if (root / name).exists()]
    if len(copies) > 1:
        raise RuntimeError(
            f"the repository {name} is under more than one Projects root: "
            + ", ".join(str(copy) for copy in copies)
            + "; no tool judges it until one copy is removed"
        )
    return copies[0] if copies else given[0] / name


def __getattr__(name: str):
    """``PROJECTS_ROOTS`` and ``PROJECTS``, read from the config on every access (PEP 562)."""
    if name == "PROJECTS_ROOTS":
        return projects_roots()
    if name == "PROJECTS":
        return projects_roots()[0]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def spellings(path: Path | str = REPO_ROOT.parent) -> dict[str, str]:
    """The Windows, Git Bash and WSL spellings of ``path``.

    A drive path (``C:\\...``, ``/c/...`` or ``/mnt/c/...``) yields all three:
    ``{"windows": "C:\\\\a\\\\b", "git_bash": "/c/a/b", "wsl": "/mnt/c/a/b"}``.
    A path on no drive (an ext4 home, a CI runner) has one spelling, so all
    three keys hold the POSIX path. The default is the checkout's parent, read
    without the config.
    """
    text = str(path).replace("\\", "/")
    drive, rest = "", ""
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        drive, rest = text[0], text[2:]
    elif text.startswith("/mnt/") and len(text) >= 6 and text[5].isalpha() and text[6:7] in ("", "/"):
        drive, rest = text[5], text[6:]
    elif len(text) >= 2 and text[0] == "/" and text[1].isalpha() and text[2:3] in ("", "/"):
        drive, rest = text[1], text[2:]
    if not drive:
        posix = str(PurePosixPath(text))
        return {"windows": posix, "git_bash": posix, "wsl": posix}
    rest = rest.rstrip("/") or ""
    letter = drive.lower()
    return {
        "windows": str(PureWindowsPath(f"{drive.upper()}:{rest or '/'}")),
        "git_bash": f"/{letter}{rest}",
        "wsl": f"/mnt/{letter}{rest}",
    }
