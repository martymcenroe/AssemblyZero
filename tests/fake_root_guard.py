"""No test writes into a fake absolute root (#4706).

Tests hand code fake absolute paths -- ``/tmp/repo``, ``/nonexistent``,
``/fake/...``, ``/path/that/does/not/exist``, ``/dev/null/...`` -- and some of
that code writes. On Windows each one is a real folder at the root of the
drive: ``/tmp/repo`` is ``C:\\tmp\\repo`` and ``/nonexistent`` is
``C:\\nonexistent``. Found at the root of the C: drive during a cleanup on
2026-11-11: 785 drafts under ``C:\\nonexistent``, a best-iteration snapshot
under ``C:\\tmp\\repo``, a 447 KB prompt-failure log under ``C:\\fake\\repo``,
the oldest from February 2026. On Ubuntu the same paths land in ``/tmp`` or
are refused by the OS, which is how they passed CI.

The guard is an audit hook (``sys.addaudithook``), not a look at the folders
once the run is over, for three reasons:

- it sees the attempt, so a write Ubuntu refuses (``/nonexistent`` is not
  writable there) fails the Ubuntu run too, instead of only the Windows run
  where the write succeeds;
- it names the test that wrote, which a folder's mtime cannot;
- it watches this process only, so another checkout's suite writing the same
  folders at the same time is never taken for this run's leak.

The hook refuses each such write with ``PermissionError``, which is what
Ubuntu does with most of them, so Windows and Ubuntu take the same path
through the code and nothing reaches the drive. It also records the write, and
``conftest.py`` fails the session at its end with every test and path named,
so a refusal some code swallows still fails the run.

What it cannot see is a child process other than a pytest one: the hook lives
in this interpreter, and a child pytest that loads this suite's ``conftest.py``
arms its own. A test that runs any other real child against a fake root is
outside it.

The roots are a closed set, authored on 2026-11-11, and every one is watched
on both platforms except as ``WINDOWS_ONLY_ROOTS`` and
``CHILDREN_ONLY_ON_POSIX`` say.
"""

from __future__ import annotations

import os
import sys
import tempfile

#: The fake absolute roots a test's write was found in, as the tests spell
#: them: on the C: drive on 2026-11-11, or by tracing every write of a full
#: Ubuntu run that day.
FAKE_ROOTS: tuple[str, ...] = (
    "/tmp/repo",
    "/tmp/audit",
    "/tmp/test_project",
    "/nonexistent",
    "/fake",
    "/path",
    "/dev/null",
)

#: Watched on Windows only. On Ubuntu ``/tmp`` is the system's temporary
#: directory, where pytest's own ``tmp_path`` and ``tempfile`` write, so only
#: the named folders above are watched there, and ``/dev`` holds the real
#: devices. On Windows nothing of the system's is at ``C:\tmp`` or
#: ``C:\dev``, so everything a test writes there is a leak, and a new fake
#: ``/tmp`` name is caught by the Windows run.
WINDOWS_ONLY_ROOTS: tuple[str, ...] = ("/tmp", "/dev")

#: Watched below the root only, on Ubuntu: ``/dev/null`` itself is the null
#: device, and writing it is how a process throws output away. On Windows
#: ``C:\dev\null`` is a file like any other, and the root counts too.
CHILDREN_ONLY_ON_POSIX: tuple[str, ...] = ("/dev/null",)

#: The audit events that change the filesystem, and which of their arguments
#: name the path changed. ``open`` is decided by its mode and flags below.
WRITTEN_ARGUMENTS: dict[str, tuple[int, ...]] = {
    "os.mkdir": (0,),
    "os.remove": (0,),
    "os.rmdir": (0,),
    "os.truncate": (0,),
    "os.chmod": (0,),
    "os.chown": (0,),
    "os.utime": (0,),
    "os.rename": (0, 1),
    "os.symlink": (1,),
    "os.link": (1,),
    "shutil.copyfile": (1,),
    "shutil.copytree": (1,),
    "shutil.copymode": (1,),
    "shutil.copystat": (1,),
    "shutil.move": (0, 1),
    "shutil.rmtree": (0,),
    "sqlite3.connect": (0,),
}

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
_WRITE_MODE_LETTERS = frozenset("wax+")

#: What the hook refused, as ``(test, event, path)``; ``conftest.py`` reports it.
RECORDS: list[tuple[str, str, str]] = []

#: The test running now, kept by ``enter`` and ``leave``.
CURRENT: list[str] = ["(outside any test)"]

_STATE: dict[str, object] = {"installed": False, "roots": (), "allowed": ()}


def written_paths(event: str, args: tuple) -> tuple:
    """The path arguments ``event`` changes, or ``()`` when it changes none."""
    if event == "open":
        if len(args) < 3:
            return ()
        path, mode, flags = args[0], args[1], args[2]
        if isinstance(mode, str):
            if not _WRITE_MODE_LETTERS.intersection(mode):
                return ()
        elif not (flags or 0) & _WRITE_FLAGS:
            return ()
        return (path,)
    indices = WRITTEN_ARGUMENTS.get(event)
    if not indices:
        return ()
    return tuple(args[i] for i in indices if i < len(args))


def normalize(raw: object) -> str | None:
    """``raw`` as a normalised absolute path, or None when it names no rooted path.

    A file descriptor, a relative path and anything that is not a path give
    None: a relative path resolves under the working directory, which is the
    checkout's business (``checkout_telemetry_guard``), never a drive root.
    """
    if raw is None or isinstance(raw, int):
        return None
    try:
        text = os.fsdecode(os.fspath(raw))
    except TypeError:
        return None
    rooted = text.startswith(("/", "\\")) or (len(text) > 1 and text[1] == ":")
    if not rooted:
        return None
    return os.path.normcase(os.path.abspath(text))


def roots_for_this_machine(on_windows: bool | None = None) -> tuple[tuple[str, bool], ...]:
    """``(root, the root itself counts)`` for every watched root, normalised here."""
    if on_windows is None:
        on_windows = sys.platform == "win32"
    spelled = FAKE_ROOTS + (WINDOWS_ONLY_ROOTS if on_windows else ())
    roots: list[tuple[str, bool]] = []
    for root in dict.fromkeys(spelled):
        itself = on_windows or root not in CHILDREN_ONLY_ON_POSIX
        normalized = normalize(root)
        if normalized is not None:
            roots.append((normalized, itself))
    return tuple(roots)


def _under(path: str, root: str) -> bool:
    return path.startswith(root.rstrip(os.sep) + os.sep)


def is_leak(path: str, roots, allowed=()) -> bool:
    """True when the normalised ``path`` is in a watched root and no allowed one."""
    for root in allowed:
        if path == root or _under(path, root):
            return False
    for root, itself in roots:
        if (itself and path == root) or _under(path, root):
            return True
    return False


def _hook(event: str, args: tuple) -> None:
    if event != "open" and event not in WRITTEN_ARGUMENTS:
        return
    refused = None
    try:
        for raw in written_paths(event, args):
            path = normalize(raw)
            if path is not None and is_leak(path, _STATE["roots"], _STATE["allowed"]):
                RECORDS.append((CURRENT[0], event, path))
                refused = path
                break
    except Exception:  # noqa: BLE001 - the hook must never break a write it does not judge
        return
    if refused is not None:
        raise PermissionError(
            13,
            "a test wrote into a fake absolute root; write under tmp_path "
            "instead (tests/fake_root_guard.py, #4706)",
            refused,
        )


def install(roots=None) -> None:
    """Arm the hook for this process, once. ``roots`` replaces the watched
    roots, as ``(normalised root, the root itself counts)`` pairs, for the
    guard's own test, which watches a folder under its tmp_path."""
    _STATE["roots"] = tuple(roots) if roots is not None else roots_for_this_machine()
    allowed: tuple[str, ...] = ()
    if sys.platform == "win32":
        # #4706: a machine whose temporary directory is C:\tmp keeps pytest's
        # tmp_path there; that is the allowed store, not a leak.
        allowed = (os.path.normcase(os.path.abspath(tempfile.gettempdir())),)
    _STATE["allowed"] = allowed
    if not _STATE["installed"]:
        sys.addaudithook(_hook)
        _STATE["installed"] = True


def installed() -> bool:
    return bool(_STATE["installed"])


def armed_roots() -> tuple[tuple[str, bool], ...]:
    return tuple(_STATE["roots"])


def enter(nodeid: str) -> None:
    CURRENT[0] = nodeid


def leave() -> None:
    CURRENT[0] = "(between tests)"


def report() -> list[str]:
    """One line per test, event and path the hook refused, in order, once each."""
    return [f"{test}: {event} {path}" for test, event, path in dict.fromkeys(RECORDS)]


HEADLINE = (
    "FAIL: a test wrote into a fake absolute root, which on Windows is a real "
    "folder at the root of the drive (#4706). The guard refused each write; "
    "send it under the test's tmp_path (tests/fake_root_guard.py):"
)


def fail_session_on_leaks(session) -> None:
    """``pytest_sessionfinish``'s part: name every refused write and fail the
    session, even where the code under test swallowed the refusal."""
    lines = report()
    if not lines:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line("")
        reporter.write_line(HEADLINE)
        for line in lines:
            reporter.write_line("  " + line)
    session.exitstatus = 1
