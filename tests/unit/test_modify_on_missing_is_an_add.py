"""A plan's "Modify" for a file the base does not have is an Add (#2879).

boostgauge #4, `run-issue4-193821`: the requirements gate, the design and the
spec all passed, and the implementation stage halted in 5.2 seconds:

    [GUARD] Modify target does not exist: src/boostgauge/collector.py
    [GUARD] Modify target does not exist: src/boostgauge/collectors/windows.py
    [GUARD] Modify target does not exist: tests/unit/test_collector.py
    [GUARD] Modify target does not exist: tests/integration/test_windows_sweep_crosscheck.py
    [GUARD] Modify target does not exist: tests/benchmark/test_sweep_cost.py

The base, `hardening-run-20`, is Phase 2's from-seed branch and has none of
the five; they are #4's own deliverable. The operator ruled (#2736) that the
LLD's file list is a plan, not a contract. The change type is the same kind
of claim, and the truth is on disk -- the inverse of `resolve_change_type`,
which turns an Add whose file the base ships into a Modify.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.implementation import orchestrator

RUN_26_PLAN = [
    {"path": "src/boostgauge/collector.py", "change_type": "Modify"},
    {"path": "src/boostgauge/collectors/windows.py", "change_type": "Modify"},
    {"path": "tests/unit/test_collector.py", "change_type": "Modify"},
    {"path": "tests/integration/test_windows_sweep_crosscheck.py", "change_type": "Modify"},
    {"path": "tests/benchmark/test_sweep_cost.py", "change_type": "Modify"},
]


@pytest.fixture
def seed_base(tmp_path):
    """hardening-run-20's shape: config, telltale, a skin, no collector."""
    (tmp_path / "src" / "boostgauge" / "skins").mkdir(parents=True)
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    for rel in ("src/boostgauge/__init__.py", "src/boostgauge/config.py",
                "src/boostgauge/telltale.py", "src/boostgauge/skins/stingray.py",
                "tests/unit/test_config.py"):
        (tmp_path / rel).write_text("# base\n", encoding="utf-8")
    return tmp_path


class TestTheGuard:
    def test_the_five_modifies_become_adds_with_no_error(self, seed_base, capsys):
        plan = [dict(spec) for spec in RUN_26_PLAN]

        errors = orchestrator.validate_files_to_modify(plan, seed_base)

        assert errors == [], errors
        assert [spec["change_type"] for spec in plan] == ["Add"] * 5
        out = capsys.readouterr().out
        assert out.count("says Modify but the base has no") == 5
        assert "#2736" in out

    def test_parent_directories_are_created_for_the_coerced_adds(self, seed_base):
        plan = [dict(spec) for spec in RUN_26_PLAN]

        orchestrator.validate_files_to_modify(plan, seed_base)

        assert (seed_base / "src" / "boostgauge" / "collectors").is_dir()
        assert (seed_base / "tests" / "integration").is_dir()
        assert (seed_base / "tests" / "benchmark").is_dir()

    def test_a_modify_whose_file_exists_stays_a_modify(self, seed_base, capsys):
        plan = [{"path": "src/boostgauge/telltale.py", "change_type": "Modify"}]

        errors = orchestrator.validate_files_to_modify(plan, seed_base)

        assert errors == []
        assert plan[0]["change_type"] == "Modify"
        assert "says Modify" not in capsys.readouterr().out

    def test_a_delete_whose_target_is_missing_is_still_an_error(self, seed_base):
        """Unchanged: there is nothing to coerce a Delete into."""
        plan = [{"path": "src/boostgauge/gone.py", "change_type": "Delete"}]

        errors = orchestrator.validate_files_to_modify(plan, seed_base)

        assert errors == ["Delete target does not exist: src/boostgauge/gone.py"]


class TestTheStageNoLongerHaltsOnIt:
    def test_implement_code_proceeds_to_generation(self, seed_base, capsys):
        generated: list[str] = []

        def fake_regen(filepath, **kwargs):
            generated.append(filepath)
            return "# generated\n", True

        state = {
            "repo_root": str(seed_base),
            "lld_content": "## 2.1 Files\n",
            "files_to_modify": [dict(spec) for spec in RUN_26_PLAN],
            "test_files": ["tests/unit/test_collector.py"],
            "iteration_count": 0,
            "audit_dir": str(seed_base / "audit"),
        }
        with patch.object(orchestrator, "generate_file_with_retry", fake_regen), \
             patch.object(orchestrator, "record_iteration_cost", return_value=0), \
             patch.object(orchestrator, "get_cumulative_cost", return_value=0.0):
            try:
                result = orchestrator.implement_code(state)
            except Exception:
                result = {}

        out = capsys.readouterr().out
        assert "GUARD:" not in str(result.get("error_message", ""))
        assert "file path(s) in LLD do not match" not in out
        assert generated, "the stage must reach generation instead of halting on the guard"
