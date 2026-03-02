"""Tests for the core spelunking engine.

Issue #534: Spelunking Audits
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.spelunking.engine import run_all_probes, run_probe, run_spelunking
from assemblyzero.spelunking.models import (
    SpelunkingCheckpoint,
    VerificationStatus,
)


class TestRunSpelunking:
    """Tests for the run_spelunking engine function."""

    def test_T010_known_drift(self, tmp_path: Path) -> None:
        """T010: Document claiming '5 tools' with 3 actual tools -> drift_score < 100."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(3):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        doc = tmp_path / "inventory.md"
        doc.write_text("There are 5 tools in tools/")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims >= 1
        assert report.drift_score < 100.0
        # Should have MISMATCH findings
        mismatches = [
            r for r in report.results if r.status == VerificationStatus.MISMATCH
        ]
        assert len(mismatches) >= 1

    def test_T020_empty_document(self, tmp_path: Path) -> None:
        """T020: Empty document -> 0 claims, drift_score 100.0."""
        doc = tmp_path / "empty.md"
        doc.write_text("")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims == 0
        assert report.drift_score == 100.0

    def test_T030_checkpoints_override(self, tmp_path: Path) -> None:
        """T030: Provided checkpoints used instead of auto-extraction."""
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "a.py").write_text("# a")
        (tools / "b.py").write_text("# b")

        doc = tmp_path / "doc.md"
        doc.write_text("Irrelevant content")

        checkpoints = [
            SpelunkingCheckpoint(
                claim="2 tools exist",
                verify_command="path_exists tools/a.py",
                source_file="doc.md",
            ),
            SpelunkingCheckpoint(
                claim="tools/b.py exists",
                verify_command="path_exists tools/b.py",
                source_file="doc.md",
            ),
        ]

        report = run_spelunking(doc, tmp_path, checkpoints=checkpoints)

        assert len(report.results) == 2
        assert all(r.status == VerificationStatus.MATCH for r in report.results)

    def test_nonexistent_document(self, tmp_path: Path) -> None:
        """Nonexistent target document -> 0 claims, drift_score 100.0."""
        doc = tmp_path / "nonexistent.md"

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims == 0
        assert report.drift_score == 100.0

    def test_matching_claims(self, tmp_path: Path) -> None:
        """Document with accurate claims -> drift_score 100.0."""
        tools = tmp_path / "tools"
        tools.mkdir()
        for i in range(5):
            (tools / f"tool_{i}.py").write_text(f"# tool {i}")

        doc = tmp_path / "inventory.md"
        doc.write_text("There are 5 tools in tools/")

        report = run_spelunking(doc, tmp_path)

        assert report.total_claims >= 1
        assert report.drift_score == 100.0


class TestRunProbe:
    """Tests for the run_probe function."""

    def test_unknown_probe_raises(self, tmp_path: Path) -> None:
        """Unknown probe name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown probe"):
            run_probe("nonexistent_probe", tmp_path)

    def test_known_probe_runs(self, tmp_path: Path) -> None:
        """Known probe name runs without error."""
        result = run_probe("inventory_drift", tmp_path)

        assert result.probe_name == "inventory_drift"
        assert isinstance(result.execution_time_ms, float)

    def test_probe_measures_time(self, tmp_path: Path) -> None:
        """Probe execution time is measured."""
        result = run_probe("dead_references", tmp_path)

        assert result.execution_time_ms >= 0.0


class TestRunAllProbes:
    """Tests for the run_all_probes function."""

    def test_T340_all_probes_run(self, tmp_path: Path) -> None:
        """T340: All 6 probes run without crashing on empty repo."""
        results = run_all_probes(tmp_path)

        assert len(results) == 6
        # All should have probe names
        names = {r.probe_name for r in results}
        assert "inventory_drift" in names
        assert "dead_references" in names
        assert "adr_collision" in names
        assert "stale_timestamps" in names
        assert "readme_claims" in names
        assert "persona_status" in names

    def test_all_probes_have_timing(self, tmp_path: Path) -> None:
        """All probes report execution time."""
        results = run_all_probes(tmp_path)

        for result in results:
            assert result.execution_time_ms >= 0.0

    def test_all_probes_pass_on_empty_repo(self, tmp_path: Path) -> None:
        """Empty repo produces all passing probes (nothing to flag)."""
        results = run_all_probes(tmp_path)

        for result in results:
            assert result.passed is True, (
                f"Probe {result.probe_name} failed on empty repo: {result.summary}"
            )