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
each test, and most did not do it. Two pieces here:

- ``redirect``: the autouse fixture's body. Every binding that resolves into
  the two paths is pointed at a per-test directory. Four bindings, because
  ``resume_contract`` and ``halt_node`` import ``STATE_DIR`` by name and hold
  their own copy.
- ``snapshot`` / ``changes``: the session guard. ``conftest.py`` snapshots
  the real paths at session start and compares at session end; a difference
  fails the session with the paths named, so a new writer nobody redirected
  is caught by the run it first appears in, not by the operator opening the
  directory.
"""

from __future__ import annotations

from pathlib import Path

#: What a real run writes under the home directory and a test must not.
GUARDED_PATHS: tuple[Path, ...] = (
    Path.home() / ".assemblyzero" / "workflow_state",
    Path.home() / ".claude" / "assemblyzero" / "workflow-audit.jsonl",
)


def real_bindings() -> dict[str, Path]:
    """The bindings as the modules define them, before any redirect.

    For a test that asserts the DESIGN of a constant (absolute, under
    ``~/.claude``, #1151) rather than where this test's writes go: the
    autouse fixture has replaced the module attribute by the time a test body
    runs, so the attribute no longer says what the module says.
    """
    return dict(_REAL)


_REAL: dict[str, Path] = {}


def snapshot(paths: tuple[Path, ...] = GUARDED_PATHS) -> dict[str, tuple[int, int]]:
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

    ``root / "workflow_state"`` takes the snapshots and contracts and
    ``root / "workflow-audit.jsonl"`` the audit lines. A test that patches one
    of these itself still wins: its monkeypatch runs after this one.
    """
    from assemblyzero.core import halt_node, resume_contract, state_persistence
    from assemblyzero.workflows.testing import audit as testing_audit

    if not _REAL:
        _REAL["STATE_DIR"] = Path(state_persistence.STATE_DIR)
        _REAL["WORKFLOW_AUDIT_FILE"] = Path(testing_audit.WORKFLOW_AUDIT_FILE)

    state = root / "workflow_state"
    monkeypatch.setattr(state_persistence, "STATE_DIR", state)
    monkeypatch.setattr(resume_contract, "STATE_DIR", state)
    monkeypatch.setattr(halt_node, "STATE_DIR", state)
    monkeypatch.setattr(
        testing_audit, "WORKFLOW_AUDIT_FILE", root / "workflow-audit.jsonl"
    )
