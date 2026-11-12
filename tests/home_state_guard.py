"""No test writes into the operator's home state (#3531).

Two things under the home directory are a real run's memory:

- ``~/.assemblyzero/workflow_state/``: the halt snapshots and resume
  contracts a real ``--resume`` reads. ``check_and_consume("testing", N)``
  would find a contract a test wrote if a real issue ever carried the
  fixture number (4242 is one such number, and the files were there).
- ``~/.claude/assemblyzero/workflow-audit.jsonl``: the append-only audit
  log. On 2026-09-24, 46,308 of its 59,609 lines named a target under the OS
  temp directory; the operator's workflow audit log was mostly test runs.

Nothing in ``conftest.py`` redirected either one, so isolation was left to
each test, and most did not do it.

#4708 added two more, found by tracing every write of a full run:

- ``~/.assemblyzero/telemetry-buffer/``: the offline buffer
  ``assemblyzero.telemetry.emitter`` appends to and ``flush`` uploads from.
  Sixteen test files emitted into it, and a test's event there reads as a
  real run's.
- ``~/.claude/assemblyzero/hourglass/``: DEATH's age meter and history
  (``assemblyzero.workflows.death``). ``test_report_flow_completes`` wrote
  ``history.json`` there, which made a test's history the real one.

Two pieces here:

- ``redirect``: the autouse fixture's body. Every binding that resolves into
  the guarded paths is pointed at a per-test directory. ``resume_contract``
  and ``halt_node`` import ``STATE_DIR`` by name and hold their own copy, and
  so does ``hourglass`` with ``HISTORY_PATH``. The age meter's path is a
  default argument of ``load_age_meter_state`` and ``save_age_meter_state``,
  bound when the functions were defined, so the defaults themselves are
  replaced. ``death.constants`` is left alone: it is the design record, and
  ``test_path_constants_absolute`` asserts on it.
- ``snapshot`` / ``changes``: the session guard. ``conftest.py`` snapshots
  the real paths at session start and compares at session end; a difference
  fails the session with the paths named, so a new writer nobody redirected
  is caught by the run it first appears in, not by the operator opening the
  directory.
"""

from __future__ import annotations

from pathlib import Path

#: What a real run writes under the home directory and a test must not: the
#: two paths #3531 named.
GUARDED_PATHS: tuple[Path, ...] = (
    Path.home() / ".assemblyzero" / "workflow_state",
    Path.home() / ".claude" / "assemblyzero" / "workflow-audit.jsonl",
)

#: The two more that tracing every write of a full run found (#4708).
TRACED_PATHS: tuple[Path, ...] = (
    Path.home() / ".assemblyzero" / "telemetry-buffer",
    Path.home() / ".claude" / "assemblyzero" / "hourglass",
)

#: Everything the session guard snapshots: a writer into any of these fails
#: the run that adds it.
WATCHED_PATHS: tuple[Path, ...] = GUARDED_PATHS + TRACED_PATHS


def real_bindings() -> dict[str, Path]:
    """The bindings as the modules define them, before any redirect.

    For a test that asserts the DESIGN of a constant (absolute, under
    ``~/.claude``, #1151) rather than where this test's writes go: the
    autouse fixture has replaced the module attribute by the time a test body
    runs, so the attribute no longer says what the module says.
    """
    return dict(_REAL)


_REAL: dict[str, Path] = {}


def snapshot(paths: tuple[Path, ...] = WATCHED_PATHS) -> dict[str, tuple[int, int]]:
    """``{path: (size, mtime_ns)}`` for every file under ``paths``.

    A path that does not exist contributes nothing, so its later appearance
    is a change like any other. Size and mtime together: an append changes
    both, an in-place rewrite of the same length changes the mtime.
    """
    seen: dict[str, tuple[int, int]] = {}
    for root in paths:
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = sorted(p for p in root.rglob("*") if p.is_file())
        else:
            continue
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            seen[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return seen


def changes(before: dict[str, tuple[int, int]],
            after: dict[str, tuple[int, int]]) -> list[str]:
    """One line per path whose presence, size or mtime differs."""
    lines: list[str] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        if path not in before:
            lines.append(f"added:   {path}")
        elif path not in after:
            lines.append(f"removed: {path}")
        else:
            lines.append(
                f"changed: {path} (size {before[path][0]} -> {after[path][0]})"
            )
    return lines


def redirect(monkeypatch, root: Path) -> None:
    """Point every binding that writes into the guarded paths at ``root``.

    ``root / "workflow_state"`` takes the snapshots and contracts,
    ``root / "workflow-audit.jsonl"`` the audit lines,
    ``root / "telemetry-buffer"`` the buffered telemetry events and
    ``root / "hourglass"`` the age meter and history (#4708). A test that
    patches one of these itself still wins: its monkeypatch runs after this
    one.
    """
    from assemblyzero.core import halt_node, resume_contract, state_persistence
    from assemblyzero.telemetry import emitter
    from assemblyzero.workflows.death import age_meter, hourglass
    from assemblyzero.workflows.testing import audit as testing_audit

    if not _REAL:
        _REAL["STATE_DIR"] = Path(state_persistence.STATE_DIR)
        _REAL["WORKFLOW_AUDIT_FILE"] = Path(testing_audit.WORKFLOW_AUDIT_FILE)
        _REAL["TELEMETRY_BUFFER_DIR"] = Path(emitter._BUFFER_DIR)
        _REAL["HISTORY_PATH"] = Path(hourglass.HISTORY_PATH)
        _REAL["AGE_METER_STATE_PATH"] = Path(
            age_meter.save_age_meter_state.__defaults__[0]
        )

    state = root / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)
    monkeypatch.setattr(halt_node, "STATE_DIR", state)
    monkeypatch.setattr(
        testing_audit, "WORKFLOW_AUDIT_FILE", root / "workflow-audit.jsonl"
    )
    monkeypatch.setattr(emitter, "_BUFFER_DIR", root / "telemetry-buffer")
    hourglass_dir = root / "hourglass"
    monkeypatch.setattr(hourglass, "HISTORY_PATH", str(hourglass_dir / "history.json"))
    age_meter_path = str(hourglass_dir / "age_meter.json")
    monkeypatch.setattr(age_meter, "AGE_METER_STATE_PATH", age_meter_path)
    for function in (age_meter.load_age_meter_state, age_meter.save_age_meter_state):
        monkeypatch.setattr(function, "__defaults__", (age_meter_path,))
