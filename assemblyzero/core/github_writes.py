"""One switch that makes every GitHub write inert (#2826).

A replay runs the real graph against a throwaway clone whose ``origin`` is
the real target repository. On 2026-09-04 a replay of a halted run reached
the spec review's BLOCKED path and ``file_must_resolve`` wrote a real
issue -- boostgauge #434, a copy of a question the operator had already
ruled on and closed -- and the next authorised launch was refused by it.

The graph has no single place where "this is a replay" is known, and the
writes are scattered: ``git push`` in four modules, ``gh pr create`` in two,
``gh pr merge``, ``gh issue create`` and ``gh issue comment``. Guarding each
site is a list that drifts. Guarding the two process runners everything
funnels through -- ``assemblyzero.utils.shell.run_command`` and the
must-resolve filer's runner -- is one predicate, and a site added tomorrow
is covered the day it is written.

The switch is an environment variable so it crosses every boundary the
graph does (nodes, helper modules, the provider) without threading a flag
through state. It is set only by ``inert_github_writes(...)``, which
restores the previous value on exit, and never by a live roll.

What counts as a write is a closed set, listed in ``_WRITE_VERBS``: every
entry is a command that changes something on GitHub. Reads (``gh pr view``,
``gh issue list``, ``git fetch``) stay live, because a replay that cannot
read the board would diverge from the recording for a reason that has
nothing to do with the gate under test.
"""

from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from typing import Iterator, Sequence

#: The switch. Empty (or unset) means live; any other value is the reason
#: writes are inert, and it is printed on every suppressed write.
INERT_ENV = "ASSEMBLYZERO_GITHUB_WRITES_INERT"

#: What a suppressed write's stdout starts with, so a caller that echoes the
#: "URL" it got back prints something a reader can recognise.
SUPPRESSED_MARK = "(inert:"

# Closed set. (program, first subcommand or None, second subcommand or None).
# ``git push`` is a write whatever follows it. ``gh`` writes are named by
# their verb; everything else under ``gh`` is a read.
_WRITE_VERBS: frozenset[tuple[str, str | None, str | None]] = frozenset({
    ("git", "push", None),
    ("gh", "pr", "create"),
    ("gh", "pr", "merge"),
    ("gh", "pr", "close"),
    ("gh", "pr", "edit"),
    ("gh", "pr", "comment"),
    ("gh", "pr", "review"),
    ("gh", "pr", "ready"),
    ("gh", "issue", "create"),
    ("gh", "issue", "comment"),
    ("gh", "issue", "edit"),
    ("gh", "issue", "close"),
    ("gh", "issue", "reopen"),
    ("gh", "label", "create"),
    ("gh", "release", "create"),
})


def inert_reason() -> str:
    """Why writes are inert, or "" when they are live."""
    return os.environ.get(INERT_ENV, "").strip()


@contextmanager
def inert_github_writes(reason: str) -> Iterator[None]:
    """Make every GitHub write inert for the duration, then restore.

    ``reason`` is what a suppressed write prints and what the must-resolve
    ledger records; "replay" is the one caller today.
    """
    if not reason.strip():
        raise ValueError("inert_github_writes needs a reason; a blank one reads as live")
    previous = os.environ.get(INERT_ENV)
    os.environ[INERT_ENV] = reason.strip()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(INERT_ENV, None)
        else:
            os.environ[INERT_ENV] = previous


def _words(args: Sequence[str] | str) -> list[str]:
    if isinstance(args, str):
        return args.split()
    return [str(a) for a in args]


def is_github_write(args: Sequence[str] | str) -> bool:
    """Whether this argv would change something on GitHub.

    ``git -C <path> push ...`` counts: global ``-C``/``-c`` options before the
    verb are skipped so the verb is read wherever it sits.
    """
    words = _words(args)
    if not words:
        return False
    program = os.path.basename(words[0]).lower()
    if program.endswith(".exe"):
        program = program[:-4]
    rest = words[1:]
    # Skip git's global options that take a value.
    while program == "git" and len(rest) >= 2 and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
        rest = rest[2:]
    first = rest[0] if rest else None
    second = rest[1] if len(rest) > 1 else None
    if (program, first, None) in _WRITE_VERBS:
        return True
    return (program, first, second) in _WRITE_VERBS


def suppressed_result(args: Sequence[str] | str, reason: str) -> subprocess.CompletedProcess:
    """What a suppressed write returns: success, with stdout that says so.

    Callers read the URL of a created PR out of stdout. Under a replay that
    URL is this string, which begins with ``SUPPRESSED_MARK`` so that a log
    line or a report carrying it cannot be mistaken for a real URL.
    """
    words = _words(args)
    return subprocess.CompletedProcess(
        list(words), 0,
        f"{SUPPRESSED_MARK}{reason}) {' '.join(words[:3])} not run",
        "",
    )


def suppress_if_inert(
    args: Sequence[str] | str, *, log=print
) -> subprocess.CompletedProcess | None:
    """The one call a runner makes: a fake success when the write is inert,
    None when the command should run for real."""
    reason = inert_reason()
    if not reason or not is_github_write(args):
        return None
    words = _words(args)
    log(f"    [{reason}] GitHub write suppressed: {' '.join(words[:4])}")
    return suppressed_result(words, reason)
