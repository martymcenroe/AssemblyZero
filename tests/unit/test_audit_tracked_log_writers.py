"""Tests for tools/audit_tracked_log_writers.py (#1151)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "audit_tracked_log_writers", TOOLS_DIR / "audit_tracked_log_writers.py",
)
audit = importlib.util.module_from_spec(_spec)
sys.modules["audit_tracked_log_writers"] = audit
_spec.loader.exec_module(audit)


class TestIsPathRelative:
    def test_relative_simple(self):
        assert audit.is_path_relative("data/foo.json") is True

    def test_relative_no_slash(self):
        assert audit.is_path_relative("foo.json") is True

    def test_absolute_unix(self):
        assert audit.is_path_relative("/abs/path.json") is False

    def test_absolute_windows_drive(self):
        assert audit.is_path_relative("C:/Users/foo.json") is False

    def test_home_expansion(self):
        assert audit.is_path_relative("~/.claude/foo.json") is False

    def test_backslash_absolute_treated_absolute(self):
        assert audit.is_path_relative("\\\\server\\share\\file") is False


class TestFindPathConstants:
    def test_finds_relative_jsonl_constant(self, tmp_path):
        src = tmp_path / "mod.py"
        src.write_text(
            'FOO_LOG = Path("data/foo.jsonl")\n'
            'BAR = "tmp/bar.json"\n'
            'NOT_A_LOG = "src/something.py"\n',  # filtered out by LOG_PATH_HINTS
            encoding="utf-8",
        )
        results = audit.find_path_constants(src)
        names = {n for _, n, _ in results}
        # FOO_LOG matches; BAR matches (tmp/ hint); NOT_A_LOG doesn't (no log hint)
        assert "FOO_LOG" in names
        assert "BAR" in names
        assert "NOT_A_LOG" not in names

    def test_skips_non_uppercase_constants(self, tmp_path):
        """Heuristic: only flag ALL_CAPS module-level constants. Local
        variables (lowercase) aren't the bug shape."""
        src = tmp_path / "mod.py"
        src.write_text(
            'mylog = "data/foo.jsonl"\n'  # lowercase, ignored
            'MY_LOG = "data/bar.jsonl"\n',  # ALL_CAPS, flagged
            encoding="utf-8",
        )
        results = audit.find_path_constants(src)
        names = {n for _, n, _ in results}
        assert "mylog" not in names
        assert "MY_LOG" in names

    def test_path_wrapper_form(self, tmp_path):
        """`NAME = Path("...")` form should be matched too."""
        src = tmp_path / "mod.py"
        src.write_text(
            'AUDIT_LOG = Path("docs/audit.jsonl")\n',
            encoding="utf-8",
        )
        results = audit.find_path_constants(src)
        assert any(name == "AUDIT_LOG" for _, name, _ in results)

    def test_log_hints_filter(self, tmp_path):
        """LOG_PATH_HINTS keeps the scan focused. .py / .md without log
        directory prefix should NOT match."""
        src = tmp_path / "mod.py"
        src.write_text(
            'TEMPLATE = "templates/foo.md"\n'   # neither log-name nor log-dir
            'OUT_LOG = "logs/foo.txt"\n',
            encoding="utf-8",
        )
        results = audit.find_path_constants(src)
        names = {n for _, n, _ in results}
        assert "TEMPLATE" not in names
        assert "OUT_LOG" in names


class TestFindingClassification:
    def test_relative_plus_tracked_is_bug(self):
        f = audit.Finding(
            source_file="x.py", line_no=1, name="LOG", target_path="data/log.jsonl",
            is_relative=True, is_tracked=True,
        )
        assert f.is_bug_shape is True
        assert "BUG" in f.tsv_row()

    def test_relative_but_untracked_is_not_bug(self):
        f = audit.Finding(
            source_file="x.py", line_no=1, name="LOG", target_path="tmp/log.jsonl",
            is_relative=True, is_tracked=False,
        )
        assert f.is_bug_shape is False
        assert "RELATIVE_BUT_UNTRACKED" in f.tsv_row()

    def test_absolute_is_ok(self):
        f = audit.Finding(
            source_file="x.py", line_no=1, name="LOG",
            target_path="/abs/log.jsonl",
            is_relative=False, is_tracked=False,
        )
        assert f.is_bug_shape is False
        assert "\tOK" in f.tsv_row()


class TestIterPythonSources:
    def test_skips_cache_and_venv_dirs(self, tmp_path):
        (tmp_path / "src.py").write_text("")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cached.py").write_text("")
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv" / "venv_lib.py").write_text("")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.py").write_text("")
        sources = audit.iter_python_sources(tmp_path)
        names = [s.name for s in sources]
        assert "src.py" in names
        assert "cached.py" not in names
        assert "venv_lib.py" not in names
        assert "pkg.py" not in names

    def test_skips_lineage_done(self, tmp_path):
        """docs/lineage/done/ contains historical scaffolds; not part of
        active code surface."""
        (tmp_path / "src.py").write_text("")
        done_dir = tmp_path / "docs" / "lineage" / "done" / "535-testing"
        done_dir.mkdir(parents=True)
        (done_dir / "scaffold.py").write_text("")
        sources = audit.iter_python_sources(tmp_path)
        names = [s.name for s in sources]
        assert "src.py" in names
        assert "scaffold.py" not in names


class TestAuditIntegration:
    def test_audit_flags_bug_shape(self, tmp_path):
        """End-to-end: a fake repo with one bug-shape writer is detected
        and flagged."""
        # Set up fake repo tree
        src_dir = tmp_path / "assemblyzero"
        src_dir.mkdir()
        (src_dir / "mod.py").write_text(
            'from pathlib import Path\n'
            'HISTORY_PATH = "data/history.json"\n'
            'AUDIT_LOG = Path("/abs/audit.jsonl")\n',  # absolute -- not bug
            encoding="utf-8",
        )
        # Fake .git so the script doesn't bail
        (tmp_path / ".git").mkdir()

        # Mock tracked_paths to claim data/history.json is tracked
        import unittest.mock as mock
        with mock.patch.object(audit, "tracked_paths",
                               return_value={"data/history.json"}):
            findings = audit.audit(tmp_path)

        bugs = [f for f in findings if f.is_bug_shape]
        assert len(bugs) == 1
        assert bugs[0].name == "HISTORY_PATH"

    def test_audit_absolute_path_not_bug(self, tmp_path):
        """Absolute path constants should never be bug-shape."""
        src_dir = tmp_path / "assemblyzero"
        src_dir.mkdir()
        (src_dir / "mod.py").write_text(
            'LOG_PATH = Path("/abs/path/foo.jsonl")\n',
            encoding="utf-8",
        )
        (tmp_path / ".git").mkdir()
        findings = audit.audit(tmp_path)
        assert all(not f.is_bug_shape for f in findings)
