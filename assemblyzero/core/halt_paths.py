"""Where a halt's files live: one directory per repository, never shared (#4292).

A halt writes a state snapshot, a recovery plan, a resume contract and an
evidence bundle. They were named by workflow and issue number alone, in one
directory for the whole machine, and issue numbers are per repository: issue
#42 of one repository and issue #42 of another shared every file. A contract
left by a halt on one was read by the next spec run on the other. An
issue-type (brief) run has no number at all, so every brief shared issue 0.

Three things name a halt's files now, and this module is where all three are
decided, so the writers and the readers cannot disagree:

* the REPOSITORY, as the LLD approval cache already names it: the primary
  checkout's resolved path, so a run in a worktree and a run in its primary
  checkout are one repository. The directory is the primary's name for a
  human and a hash of its path for uniqueness, so two repositories called
  ``app`` do not collide, and nothing in it is unsafe on Windows;
* whether the run is a MOCK. A ``--mock`` run halts into a ``mock`` directory
  of its own, so a later real run can never read what a mock left;
* the RUN KEY: the issue number, or for a brief run a slug and hash of the
  brief file, so two briefs do not share one file set.

A halt that cannot be keyed raises ``UnkeyableRun`` naming what is missing. It
never falls back to the current directory or to issue 0: the workflows are
launched from the AssemblyZero checkout with ``--repo`` naming another
repository, so the working directory is exactly the wrong guess.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

#: Where the repository a run was against may be named, best first. The same
#: order the resume command uses: a resume is pointed at the repository, never
#: at a worktree the halt may have removed.
_REPO_KEYS = ("target_repo", "original_repo_root", "repo_root")

#: The subdirectory of a repository's halt directory a mock run uses.
MOCK_SUBDIR = "mock"

_NAME_LIMIT = 40


class UnkeyableRun(ValueError):
    """The run names no repository, or neither an issue nor a brief (#4292)."""


def _safe_part(text: str, limit: int = _NAME_LIMIT) -> str:
    """``text`` cut to characters safe in a file name on every platform."""
    cleaned = "".join(c if (c.isalnum() or c in "-_") else "-" for c in text)
    return cleaned.strip("-_")[:limit].strip("-_") or "x"


def _digest(text: str, length: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def repository_key(repo_root: Path | str) -> str:
    """The repository's identity: its primary checkout's resolved path.

    This is the key the LLD approval cache files its entries under, so the two
    agree on what one repository is. ``repo_root`` is a worktree or the
    primary checkout; either gives the same answer. A root that cannot be
    resolved raises, as that function does.
    """
    from assemblyzero.workflows.requirements.audit import _repo_key

    return _repo_key(Path(repo_root))


def repository_dirname(repo_root: Path | str) -> str:
    """A directory name for the repository: its name, then a hash of its key.

    The hash is what keeps two repositories of one name apart; the name is
    only for the operator who opens the directory.
    """
    key = repository_key(repo_root)
    return f"{_safe_part(Path(key).name)}-{_digest(key, 12)}"


def halt_directory(repo_root: Path | str, mock: bool, base: Path) -> Path:
    """The directory this repository's halts are written to, under ``base``."""
    directory = Path(base) / repository_dirname(repo_root)
    return directory / MOCK_SUBDIR if mock else directory


def state_is_mock(state: dict) -> bool:
    """Whether the run this state belongs to is a ``--mock`` run.

    The workflows spell it differently: the testing state carries
    ``mock_mode``, the requirements and spec states ``config_mock_mode``, and
    the orchestrator's state a ``config`` dict holding ``mock_mode``.
    """
    config = state.get("config")
    nested = bool(config.get("mock_mode")) if isinstance(config, dict) else False
    return bool(
        state.get("mock_mode") or state.get("config_mock_mode") or nested
    )


def state_repo_root(state: dict) -> str:
    """The repository the state's run was against; raises when it names none."""
    for key in _REPO_KEYS:
        if state.get(key):
            return str(state[key])
    raise UnkeyableRun(
        "the run's state names no repository (none of "
        + ", ".join(_REPO_KEYS)
        + " is set), so its halt files cannot be placed under a repository"
    )


def run_key(state: dict, issue: int | None = None) -> str:
    """The key a run's halt files carry: its issue number, or its brief's.

    A brief run has no issue number. Its key is ``brief-<slug>-<hash>``, the
    hash taken over the brief file's resolved path, so two briefs apart and
    one brief the same on a rerun. A run with neither raises.
    """
    number = int((state.get("issue_number", 0) if issue is None else issue) or 0)
    if number > 0:
        return str(number)
    brief = str(state.get("brief_file") or "")
    if not brief:
        raise UnkeyableRun(
            "the run has no issue number and no brief_file, so its halt "
            "files have no key that tells them from another run's"
        )
    path = Path(brief)
    if not path.is_absolute():
        path = Path(state_repo_root(state)) / path
    return f"brief-{_safe_part(path.stem)}-{_digest(path.resolve().as_posix(), 10)}"
