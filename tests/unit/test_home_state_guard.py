"""The suite keeps out of the operator's home state (#3531).

Found 2026-09-24: a unit test that drove the testing workflow into a halt
wrote `~/.assemblyzero/workflow_state/testing-42.json`, the directory held
files for fixture issue 4242 from two days earlier, and 46,308 of the
59,609 lines in `~/.claude/assemblyzero/workflow-audit.jsonl` named a target
under the OS temp directory. Nothing in `conftest.py` redirected either
path, so isolation was left to each test.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

from tests import home_state_guard as guard

ROOT = Path(__file__).resolve().parents[2]


class TestEveryBindingIsRedirected:
    """Requirement 1: the autouse fixture in conftest.py points every writer
    at the test's own directory. Four bindings, because two modules import
    STATE_DIR by name and hold their own copy."""

    def test_the_four_bindings_point_under_tmp_path(self, tmp_path):
        from assemblyzero.core import halt_node, resume_contract, state_persistence
        from assemblyzero.workflows.testing import audit as testing_audit

        for binding in (
            state_persistence.STATE_DIR,
            resume_contract.STATE_DIR,
            halt_node.STATE_DIR,
            testing_audit.WORKFLOW_AUDIT_FILE,
        ):
            assert Path(binding).is_relative_to(tmp_path), binding

    def test_a_halt_snapshot_lands_under_tmp_path_and_home_is_untouched(self, tmp_path):
        from assemblyzero.core.state_persistence import save_state_snapshot

        before = guard.snapshot()
        written = save_state_snapshot("testing", 4242, {"k": 1}, trigger="halt")

        assert written.is_relative_to(tmp_path)
        assert written.name == "testing-4242.json"
        assert guard.snapshot() == before

    def test_a_resume_contract_lands_under_tmp_path(self, tmp_path):
        from assemblyzero.core.resume_contract import contract_path

        assert contract_path("testing", 4242).is_relative_to(tmp_path)

    def test_the_halt_node_binding_is_the_same_directory(self):
        from assemblyzero.core import halt_node, state_persistence

        assert halt_node.STATE_DIR == state_persistence.STATE_DIR

    def test_an_audit_append_lands_under_tmp_path_and_home_is_untouched(self, tmp_path):
        from assemblyzero.workflows.testing.audit import log_workflow_execution

        before = guard.snapshot()
        log_workflow_execution(tmp_path / "repo", 4242, "testing", "start")

        appended = tmp_path / "home-state" / "workflow-audit.jsonl"
        assert appended.exists()
        assert '"issue_number": 4242' in appended.read_text(encoding="utf-8")
        assert guard.snapshot() == before

    def test_a_test_that_patches_the_binding_itself_still_wins(self, tmp_path, monkeypatch):
        """The existing per-test patches (test_halt_node.py and the mock-run
        tests) keep working: theirs runs after the autouse one."""
        from assemblyzero.core import halt_node

        mine = tmp_path / "mine"
        monkeypatch.setattr(halt_node, "STATE_DIR", mine)

        assert halt_node.STATE_DIR == mine


class TestTheSessionGuard:
    """Requirement 2: the session compares the real paths before and after,
    and fails when anything under them was added, removed or rewritten."""

    def test_the_guarded_paths_are_the_two_the_issue_names(self):
        assert guard.GUARDED_PATHS == (
            Path.home() / ".assemblyzero" / "workflow_state",
            Path.home() / ".claude" / "assemblyzero" / "workflow-audit.jsonl",
        )

    def test_a_missing_root_contributes_nothing(self, tmp_path):
        assert guard.snapshot((tmp_path / "absent",)) == {}

    def test_the_snapshot_sees_added_removed_and_changed_files(self, tmp_path):
        state = tmp_path / "state"
        state.mkdir()
        (state / "a.json").write_text("1", encoding="utf-8")
        log = tmp_path / "audit.jsonl"
        log.write_text("x\n", encoding="utf-8")
        before = guard.snapshot((state, log))

        (state / "b.json").write_text("2", encoding="utf-8")
        (state / "a.json").unlink()
        log.write_text("x\ny\n", encoding="utf-8")

        lines = guard.changes(before, guard.snapshot((state, log)))

        kinds = sorted(line.split(":")[0] for line in lines)
        assert kinds == ["added", "changed", "removed"]
        assert any(
            line.startswith("changed:") and line.split(": ", 1)[1].startswith(str(log))
            for line in lines
        ), lines

    def test_the_real_bindings_are_remembered_before_the_redirect(self):
        """`test_path_constants_absolute.py` asserts where the module puts the
        audit log by design; the redirected attribute cannot answer that."""
        real = guard.real_bindings()

        assert real["WORKFLOW_AUDIT_FILE"] == guard.GUARDED_PATHS[1]
        assert real["STATE_DIR"] == guard.GUARDED_PATHS[0]

    def test_an_unchanged_tree_reports_nothing(self, tmp_path):
        state = tmp_path / "state"
        state.mkdir()
        (state / "a.json").write_text("1", encoding="utf-8")

        assert guard.changes(guard.snapshot((state,)), guard.snapshot((state,))) == []

    def test_the_hooks_are_wired_in_conftest(self):
        import tests.conftest as conftest

        assert callable(conftest.pytest_sessionstart)
        assert callable(conftest.pytest_sessionfinish)

    def test_a_session_that_writes_into_home_fails_with_the_path_named(self, tmp_path):
        """End to end, in a subprocess whose home is a directory under
        tmp_path: one test writes a halt snapshot into that home by the raw
        path, bypassing every binding, and the session exits 1 naming it.
        This is what fails today when a halting test runs without its own
        patch."""
        home = tmp_path / "home"
        (home / ".assemblyzero" / "workflow_state").mkdir(parents=True)
        suite = tmp_path / "suite"
        suite.mkdir()
        (suite / "conftest.py").write_text(textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(ROOT)!r})
            from tests.conftest import pytest_sessionfinish, pytest_sessionstart  # noqa: F401
            """), encoding="utf-8")
        (suite / "test_writes.py").write_text(textwrap.dedent("""
            from pathlib import Path

            def test_writes_a_snapshot_by_the_raw_path():
                target = Path.home() / ".assemblyzero" / "workflow_state" / "testing-1.json"
                target.write_text("{}", encoding="utf-8")
            """), encoding="utf-8")
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
        env["PYTHONPATH"] = str(ROOT)

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(suite), "--rootdir", str(suite),
             "-p", "no:cacheprovider", "-q"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env, cwd=str(suite), timeout=300,
        )

        assert result.returncode == 1, result.stdout + result.stderr
        assert "1 passed" in result.stdout, result.stdout
        assert "wrote into the operator's home state" in result.stdout, result.stdout
        assert "testing-1.json" in result.stdout, result.stdout
