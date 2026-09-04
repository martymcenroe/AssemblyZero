"""A unit test that reaches a real model call fails instantly (#2703).

On 2026-09-02 the first version of `test_edit_script_reaches_the_mid_arc_fix.py`
stubbed the edit-script path and not the full-rewrite fallback. The fallback
called Claude twice, for 96 seconds, at real cost, and the only signal was that
the test felt slow. Nothing in the suite could have stopped it: `conftest.py`
intercepted no model transport of any kind.

The suite is nine and a half thousand tests and drives real graph nodes in mock
mode on purpose. Each one is a single missed stub away from spending money, and
on a CI runner nobody is watching the clock at all.

## Why this guards the COMMAND and not the call site

All three transports reach a model the same way -- `subprocess.Popen` on a CLI
-- and two of them do it from `llm_provider.py`, one from `gemini_client.py`.
Patching those modules would guard three sites and miss the fourth someone adds.
Patching `subprocess.Popen` outright would break the hundreds of tests that
legitimately run `git`.

So the guard reads the command. `claude`, `agy` and `gemini` are model CLIs;
everything else is somebody's tooling and passes through untouched. A new
transport is caught by the name it invokes, which is the thing that costs money.

## Why it raises rather than returning a canned answer

A stub that answers would let the test pass while exercising a path the author
believed was stubbed -- the same silent-substitution failure the fixture set in
`ScriptedProvider` refuses. The point is to fail, in under a second, saying
which test and which command.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

#: The CLIs that reach a model and cost money. Closed and authored: a new
#: transport is added here deliberately, the same rule the gate registry's
#: pattern set follows. Matched on the executable's stem, so `claude.exe`,
#: `claude.cmd` and a full path to it are all the same name.
MODEL_CLI_NAMES: frozenset[str] = frozenset({"claude", "agy", "gemini"})


class LiveModelCallInUnitTest(AssertionError):
    """Raised when a unit test tries to spawn a model CLI."""


def model_cli_name(cmd) -> str:
    """The model CLI this command would run, or "".

    Accepts the shapes `subprocess` accepts: a list, a tuple, a string, or a
    `Path`. A shell string is read up to its first space, which is enough for
    the argv-list form every transport here actually uses and does not pretend
    to parse a shell.
    """
    if isinstance(cmd, (list, tuple)):
        if not cmd:
            return ""
        head = cmd[0]
    else:
        head = cmd
    text = str(head or "").strip()
    if not text:
        return ""
    if " " in text and not Path(text).exists():
        text = text.split(" ", 1)[0]
    stem = Path(text).stem.lower()
    return stem if stem in MODEL_CLI_NAMES else ""


def refuse(cmd, test_name: str) -> None:
    """Raise if this command would reach a model. No-op otherwise."""
    name = model_cli_name(cmd)
    if not name:
        return
    raise LiveModelCallInUnitTest(
        f"{test_name} tried to run the model CLI {name!r}.\n"
        f"  command: {cmd!r}\n"
        f"A unit test must never reach a model: it costs money, takes minutes, "
        f"and on a CI runner nobody is watching the clock (#2703). Stub the "
        f"transport -- and check the FALLBACK path too, which is what was "
        f"missed on 2026-09-02: the edit-script path was stubbed, the "
        f"full-rewrite fallback was not, and it called Claude twice for 96s.\n"
        f"If this test is meant to reach a real model, it belongs in "
        f"tests/integration/ behind the `integration` marker, not here."
    )


def install(monkeypatch, test_name: str) -> None:
    """Wrap `Popen.__init__` and `subprocess.run` for one unit test.

    Both, because the transports use `Popen` and a future one may not, and the
    cost of guarding the cheaper call is one string comparison per subprocess.

    The `Popen` half wraps the CONSTRUCTOR rather than rebinding the
    `subprocess.Popen` name, which is the same technique `no_console.install`
    uses and is not a stylistic echo. Rebinding the name replaces the class with
    a function, and a test that patches `subprocess.Popen.__init__` -- which
    `test_no_console_global.py` does, five times -- then sets an attribute on
    that function and watches its own patch do nothing. Five tests failed that
    way before this was written as a constructor wrap.

    A test that overwrites `__init__` outright therefore removes this guard for
    its own duration. That is accepted: the guard is a safety net for a stub
    someone forgot, not a boundary against a test that has deliberately taken
    the constructor apart.
    """
    original_init = subprocess.Popen.__init__
    real_run = subprocess.run

    def _init(self, cmd, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        refuse(cmd, test_name)
        return original_init(self, cmd, *args, **kwargs)

    def _run(cmd, *args, **kwargs):
        refuse(cmd, test_name)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(subprocess.Popen, "__init__", _init)
    monkeypatch.setattr(subprocess, "run", _run)
