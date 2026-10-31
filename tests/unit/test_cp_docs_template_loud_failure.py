"""templates/cp_docs.py under standard 0034, one test per sweep site (#3585).

N8 writes a CLI reference (the "c" document) for a new tool from the commands
its LLD shows. An LLD that showed none gave a Quick Reference row for
`poetry run python tools/tool.py` (137) and a usage block running
`tools/run_workflow.py --help` (159), neither of them the tool's; the
document read as written from the LLD. It now raises ValueError naming the
tool, the issue and what was searched, after an ERROR line, and writes
nothing.

Every test writes under a temporary directory. Line numbers in the names are
ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.templates import cp_docs

LLD = (
    "# CLI Tool\n\n```bash\n"
    "poetry run python tools/run_tool.py --help\n"
    "poetry run python tools/run_tool.py --issue 42\n"
    "```\n"
)


def _generate(tmp_path, lld: str):
    return cp_docs.generate_cli_doc(
        tool_name="Test Tool", lld_content=lld, issue_number=42, repo_root=tmp_path,
    )


class TestNoCommands:
    def test_137_an_lld_with_no_commands_raises_and_writes_nothing(self, tmp_path, capsys):
        with pytest.raises(ValueError, match="no command") as excinfo:
            _generate(tmp_path, "# Tool\n\nImplement a CLI tool.")

        assert "#42" in str(excinfo.value)
        skills = tmp_path / "docs" / "skills"
        assert not skills.exists() or not any(skills.iterdir())
        assert "ERROR" in capsys.readouterr().err

    def test_159_no_invented_usage_block_is_written(self, tmp_path):
        """The usage block's placeholder came from the same empty list; a
        code block with no tool command in it is no command either."""
        with pytest.raises(ValueError, match="no command"):
            _generate(tmp_path, "# Tool\n\n```bash\n# just a comment\nls -la\n```\n")


class TestKept:
    def test_the_lld_s_commands_are_the_reference(self, tmp_path, capsys, operator_alerts):
        path = _generate(tmp_path, LLD)

        content = path.read_text(encoding="utf-8")
        assert "| `poetry run python tools/run_tool.py --help` |" in content
        assert "poetry run python tools/run_tool.py --issue 42" in content
        assert "tools/tool.py" not in content
        assert "tools/run_workflow.py" not in content
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []
