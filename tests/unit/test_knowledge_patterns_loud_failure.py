"""knowledge/patterns.py under standard 0034, one test per sweep site (#3585).

The test-type knowledge base lives in `types.yaml`, beside the module. A
missing file (24) and one that could not be read or parsed (30) were both
replaced, silently, by a shorter inline copy of the definitions, so N0 and
N1 detected test types and wrote guidance from data nobody had chosen. Each
now raises after an ERROR line naming the file: FileNotFoundError when it is
missing, KnowledgeBaseError (a ValueError) when it cannot be read, does not
parse, or holds no `test_types` mapping. The inline copy, which existed only
to stand in for those failures, is deleted.

Every test points the module at a file in a temporary directory. Line
numbers in the names are ledger 0908's, at its base `79e18ad1`.
"""
from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.knowledge import patterns


def _knowledge_base_error(excinfo) -> None:
    assert type(excinfo.value).__name__ == "KnowledgeBaseError", (
        f"expected KnowledgeBaseError, got {type(excinfo.value).__name__}: {excinfo.value}"
    )


class TestAMissingKnowledgeBase:
    def test_24_a_missing_types_yaml_raises_naming_it(self, tmp_path, monkeypatch, capsys):
        missing = tmp_path / "types.yaml"
        monkeypatch.setattr(patterns, "TYPES_YAML", missing, raising=False)

        with pytest.raises(FileNotFoundError) as excinfo:
            patterns.load_test_types()

        assert str(missing) in str(excinfo.value)
        assert "ERROR" in capsys.readouterr().err

    def test_24_no_detection_runs_on_data_nobody_chose(self, tmp_path, monkeypatch):
        monkeypatch.setattr(patterns, "TYPES_YAML", tmp_path / "types.yaml", raising=False)

        with pytest.raises(FileNotFoundError):
            patterns.detect_test_types("a function and a database")


class TestAnUnreadableKnowledgeBase:
    def test_30_a_types_yaml_that_does_not_parse_raises(self, tmp_path, monkeypatch, capsys):
        broken = tmp_path / "types.yaml"
        broken.write_text("test_types: [unclosed\n", encoding="utf-8")
        monkeypatch.setattr(patterns, "TYPES_YAML", broken, raising=False)

        with pytest.raises(ValueError) as excinfo:
            patterns.load_test_types()

        _knowledge_base_error(excinfo)
        assert str(broken) in str(excinfo.value)
        assert "ERROR" in capsys.readouterr().err

    @pytest.mark.parametrize("text", ["", "other: 1\n", "test_types: [unit]\n", "- a\n"])
    def test_30_a_types_yaml_without_a_test_types_mapping_raises(self, tmp_path, monkeypatch, text):
        bad = tmp_path / "types.yaml"
        bad.write_text(text, encoding="utf-8")
        monkeypatch.setattr(patterns, "TYPES_YAML", bad, raising=False)

        with pytest.raises(ValueError) as excinfo:
            patterns.load_test_types()

        _knowledge_base_error(excinfo)

    def test_30_the_inline_stand_in_is_gone(self):
        assert not hasattr(patterns, "_default_test_types")


class TestTheShippedKnowledgeBase:
    def test_the_shipped_types_yaml_loads_quietly(self, capsys, operator_alerts):
        """Kept: the file beside the module is the knowledge base."""
        types = patterns.load_test_types()

        assert {"unit", "integration", "browser"} <= set(types)
        assert "ERROR" not in capsys.readouterr().err
        assert operator_alerts == []

    def test_detection_reads_it(self):
        detected = patterns.detect_test_types("the command reads its flags with argparse")
        assert {"terminal", "unit"} <= set(detected)
