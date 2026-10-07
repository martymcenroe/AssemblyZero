"""Where this checkout and the Projects tree are, derived, never spelled (#3609).

AssemblyZero runs unchanged on Windows and on Ubuntu (WSL), where the same
Projects tree is ``C:\\Users\\<user>\\Projects`` on one side and
``/mnt/c/Users/<user>/Projects`` on the other. Code therefore never writes the
root out: it takes it from where this file sits.

``spellings(path)`` gives the three ways that tree is written in text the fleet
reads (handoffs, transcripts, CLAUDE.md files), for the few tools that must
recognise a path inside text rather than open one.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath

#: The AssemblyZero checkout this module belongs to.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The directory holding every repository: the checkout's parent.
PROJECTS = REPO_ROOT.parent


def spellings(path: Path | str = PROJECTS) -> dict[str, str]:
    """The Windows, Git Bash and WSL spellings of ``path``.

    A drive path (``C:\\...``, ``/c/...`` or ``/mnt/c/...``) yields all three:
    ``{"windows": "C:\\\\a\\\\b", "git_bash": "/c/a/b", "wsl": "/mnt/c/a/b"}``.
    A path on no drive (an ext4 home, a CI runner) has one spelling, so all
    three keys hold the POSIX path.
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
