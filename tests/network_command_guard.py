"""A dependabot unit test that starts `gh`, or `git` against a network remote, fails (#4743).

Two tests in `tests/unit/test_dependabot_review.py` drove `process_pr` with
most of its steps stubbed but not `_pr_changed_files`, so every run sent a real
`gh pr diff 42 --repo owner/repo --name-only` to GitHub. The call failed, the
code fell back to the Python gate, and the tests passed by accident: they
depended on the network and on `gh`, and asked GitHub about a repository that
does not exist. Nothing in the suite could have noticed.

## What it refuses

- any `gh` process, whatever its arguments: every `gh` command reaches GitHub;
- `git fetch`, `pull`, `push`, `ls-remote` or `clone` when an argument is a
  network URL (`http://`, `https://`, `ssh://`, `git://`, `git@...`), or when
  the remote it names (or, with none named, any remote the repository has) is
  configured with one.

Everything else runs. A test that builds a bare repository in `tmp_path` and
fetches from it, as `tests/unit/test_dependabot_fake_root_guard.py` does, is
local git and passes: the decision is made by URL, not by subcommand.

## Where it sits

It wraps `subprocess.Popen.__init__`, which every process start through the
`subprocess` module reaches: `subprocess.run`, `check_output`, `Popen` itself,
and `psutil.Popen`. That is the boundary `tools/dependabot_review.py` uses. It
wraps the constructor rather than rebinding the `subprocess.Popen` name, for
the reason `tests/model_call_guard.py` gives. A test that stubs the tool's
`run`, or `subprocess.run`, never reaches the constructor and is untouched.

## Why it raises AND records

It raises `NetworkCommandInUnitTest` (an `AssertionError`) before the process
starts, so nothing reaches the network. The code under test may swallow that
exception in a broad `except`, so it also records the command, and the fixture
in `tests/conftest.py` fails the test at teardown when anything was recorded.
"""
from __future__ import annotations

import inspect
import os
import shlex
import subprocess
from pathlib import Path

#: The GitHub CLI. Every subcommand reaches GitHub, so any start is refused.
GH_NAMES: frozenset[str] = frozenset({"gh", "gh.exe"})

#: The git executable.
GIT_NAMES: frozenset[str] = frozenset({"git", "git.exe"})

#: The git subcommands that talk to another repository.
REMOTE_SUBCOMMANDS: frozenset[str] = frozenset(
    {"fetch", "pull", "push", "ls-remote", "clone"})

#: The URL forms that reach a network host. Closed and authored: a `file://`
#: URL and a plain path are local.
NETWORK_URL_PREFIXES: tuple[str, ...] = (
    "http://", "https://", "ssh://", "git://", "git@")

#: git's global options that take their value as the NEXT argument. Closed:
#: from `git --help`. The `--opt=value` spelling needs no entry.
GIT_GLOBAL_OPTS_WITH_VALUE: frozenset[str] = frozenset(
    {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env",
     "--super-prefix"})

#: Captured at import, before any test can replace the name with a mock, so the
#: remote lookup below always starts a real `git config`.
_REAL_POPEN = subprocess.Popen


class NetworkCommandInUnitTest(AssertionError):
    """Raised when a guarded test tries to start `gh`, or git against a remote."""


def _argv(cmd) -> list[str]:
    """The command as an argument list, from any shape `subprocess` accepts."""
    if isinstance(cmd, (list, tuple)):
        return [os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a)
                for a in cmd]
    text = os.fsdecode(cmd) if isinstance(cmd, (bytes, os.PathLike)) else str(cmd)
    # Backslashes are path separators here on every platform: a Windows path
    # must not be read as shell escapes.
    text = text.replace("\\", "/")
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def _exe_name(arg0: str) -> str:
    return Path(arg0.replace("\\", "/")).name.lower()


def is_network_url(value: str) -> bool:
    return value.lower().startswith(NETWORK_URL_PREFIXES)


def _split_git(argv: list[str]) -> tuple[list[str], str, list[str]]:
    """(global options, subcommand, the arguments after the subcommand)."""
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in GIT_GLOBAL_OPTS_WITH_VALUE:
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        return argv[1:i], arg, argv[i + 1:]
    return argv[1:], "", []


def _remote_urls(argv0: str, global_opts: list[str], cwd,
                 env) -> dict[str, list[str]] | None:
    """Each configured remote's url and pushurl, as git itself resolves them.

    Runs `git <the same global options> config --list` in the same cwd and
    environment, so `-C`, `--git-dir` and `-c remote.x.url=...` are all
    honoured. Where git cannot start or cannot read the repository there are
    no remotes: the real command then fails the same way, locally. A lookup
    that hangs returns None, and the command is refused rather than guessed.
    """
    try:
        proc = _REAL_POPEN(
            [argv0, *global_opts, "config", "--list"], cwd=cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return {}
    try:
        out, _ = proc.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        return None
    if proc.returncode != 0:
        return {}
    remotes: dict[str, list[str]] = {}
    for line in out.splitlines():
        key, sep, value = line.partition("=")
        if not sep or not key.startswith("remote."):
            continue
        name, _, leaf = key[len("remote."):].rpartition(".")
        if name and leaf in ("url", "pushurl"):
            remotes.setdefault(name, []).append(value)
    return remotes


def network_reason(cmd, cwd=None, env=None) -> str:
    """Why this command would reach the network, or "" when it would not."""
    argv = _argv(cmd)
    if not argv:
        return ""
    name = _exe_name(argv[0])
    if name in GH_NAMES:
        return "the GitHub CLI reaches GitHub"
    if name not in GIT_NAMES:
        return ""
    global_opts, sub, rest = _split_git(argv)
    if sub not in REMOTE_SUBCOMMANDS:
        return ""
    for arg in rest:
        value = arg.split("=", 1)[1] if arg.startswith("--") and "=" in arg else arg
        if is_network_url(value):
            return f"`git {sub}` names the network URL {value!r}"
    if sub == "clone":
        return ""  # its source is a positional, and none above was a URL
    remotes = _remote_urls(argv[0], global_opts, cwd, env)
    if remotes is None:
        return f"`git {sub}`: its remotes could not be read within 30s"
    named = [arg for arg in rest if arg in remotes]
    if not named:
        # A local path or file:// URL is the repository; otherwise git uses
        # the default remote, so every remote this repository has is checked.
        base = Path(cwd) if cwd else Path.cwd()
        for arg in rest:
            if arg.startswith("-"):
                continue
            if arg.lower().startswith("file://") or (base / arg).is_dir():
                return ""
        named = list(remotes)
    for remote in named:
        for url in remotes[remote]:
            if is_network_url(url):
                return f"`git {sub}` uses remote {remote!r}, configured as {url!r}"
    return ""


def refuse(cmd, test_name: str, caught: list[str], cwd=None, env=None) -> None:
    """Record and raise if this command would reach the network."""
    reason = network_reason(cmd, cwd, env)
    if not reason:
        return
    caught.append(f"{cmd!r} ({reason})")
    raise NetworkCommandInUnitTest(
        f"{test_name} tried to start a command that reaches the network: "
        f"{reason}.\n  command: {cmd!r}\n"
        f"A dependabot unit test must stub every command on its path (#4743): "
        f"patch the tool's `run`, or the helper that calls it (for example "
        f"`_pr_changed_files` or `is_pr_branch_stale`), or run git against a "
        f"repository in tmp_path."
    )


def _popen_arguments(args, bufsize=-1, executable=None, stdin=None,
                     stdout=None, stderr=None, preexec_fn=None,
                     close_fds=True, shell=False, cwd=None, env=None,
                     *_rest, **_kwargs):
    """`Popen`'s documented positional order, for binding a call's arguments.

    Bound against this rather than `inspect.signature(Popen.__init__)`,
    because the constructor may already be another guard's `(*args,
    **kwargs)` wrapper (`no_console.install`, `model_call_guard.install`),
    whose signature names nothing.
    """


_POPEN_SIGNATURE = inspect.signature(_popen_arguments)


def install(monkeypatch, test_name: str) -> list[str]:
    """Wrap `Popen.__init__` for one test. Returns the list it records into."""
    caught: list[str] = []
    original_init = subprocess.Popen.__init__

    def _init(self, *args, **kwargs):
        try:
            bound = _POPEN_SIGNATURE.bind(*args, **kwargs).arguments
        except TypeError:
            bound = {"args": args[0] if args else kwargs.get("args", [])}
        refuse(bound.get("args"), test_name, caught,
               cwd=bound.get("cwd"), env=bound.get("env"))
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", _init)
    return caught


def fail_if_caught(caught: list[str], test_name: str) -> None:
    """Fail the test when any refused command was recorded, even if swallowed."""
    if caught:
        raise NetworkCommandInUnitTest(
            f"{test_name} tried to start {len(caught)} network command(s); the "
            f"code under test may have caught the refusal, so it is reported "
            f"here (#4743):\n  " + "\n  ".join(caught)
        )
