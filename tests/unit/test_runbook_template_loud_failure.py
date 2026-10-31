"""templates/runbook.py under standard 0034, one test per sweep site (#3585).

N8 writes an operational runbook from the LLD. When the LLD gave it no
prerequisites (172), no procedure (200) or no verification steps (210), the
template wrote invented ones in their place -- "Standard AssemblyZero
environment", "*Procedure steps to be documented.*", "| Feature works |
`run feature` | Success |" -- and the runbook read as written from the LLD.
It now raises ValueError naming the feature, the issue and every section the
LLD lacks, after an ERROR line, and writes nothing.

Every test writes under a temporary directory. Line numbers in the names are
ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.templates import runbook

PREREQUISITES = "## Prerequisites\n\n- Python 3.11+\n- Poetry installed\n\n"
PROCEDURE = "## Procedure\n\n1. Load configuration\n2. Execute workflow\n\n"
VERIFICATION = "## Verification\n\n- The status file says success\n- The log names the run\n\n"


def _generate(tmp_path, lld: str):
    return runbook.generate_runbook(
        feature_name="Workflow Feature", lld_content=lld, issue_number=42,
        repo_root=tmp_path, implementation_files=["tools/run_workflow.py"],
    )


def _nothing_written(tmp_path) -> bool:
    runbooks = tmp_path / "docs" / "runbooks"
    return not runbooks.exists() or not any(runbooks.iterdir())


class TestMissingSections:
    def test_172_no_prerequisites_raises_and_writes_nothing(self, tmp_path, capsys):
        with pytest.raises(ValueError, match="prerequisites") as excinfo:
            _generate(tmp_path, "# Workflow Feature\n\n" + PROCEDURE + VERIFICATION)

        assert "#42" in str(excinfo.value)
        assert _nothing_written(tmp_path)
        assert "ERROR" in capsys.readouterr().err

    def test_200_no_procedure_raises_and_writes_nothing(self, tmp_path, capsys):
        with pytest.raises(ValueError, match="procedure"):
            _generate(tmp_path, "# Workflow Feature\n\n" + PREREQUISITES + VERIFICATION)

        assert _nothing_written(tmp_path)
        assert "ERROR" in capsys.readouterr().err

    def test_210_no_verification_raises_and_writes_nothing(self, tmp_path, capsys):
        with pytest.raises(ValueError, match="verification"):
            _generate(tmp_path, "# Workflow Feature\n\n" + PREREQUISITES + PROCEDURE)

        assert _nothing_written(tmp_path)
        assert "ERROR" in capsys.readouterr().err

    def test_every_missing_section_is_named_at_once(self, tmp_path):
        with pytest.raises(ValueError) as excinfo:
            _generate(tmp_path, "# Workflow Feature\n\nSimple description.")

        message = str(excinfo.value)
        for section in ("prerequisites", "procedure", "verification"):
            assert section in message


class TestKept:
    def test_a_runbook_is_written_from_the_lld_alone(self, tmp_path, capsys, operator_alerts):
        path = _generate(tmp_path, "# Workflow Feature\n\n" + PREREQUISITES + PROCEDURE + VERIFICATION)

        content = path.read_text(encoding="utf-8")
        assert "| Python 3.11+ | `verify` |" in content
        assert "Load configuration" in content
        assert "The status file says success" in content
        for invented in (
            "Standard AssemblyZero environment",
            "Procedure steps to be documented",
            "`run feature`",
        ):
            assert invented not in content
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []
