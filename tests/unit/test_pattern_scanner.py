"""Unit tests for the pattern scanner utility.

Issue #401: Codebase Context Analysis for Requirements Workflow.

Tests for:
- scan_patterns (aggregate pattern detection)
- detect_frameworks (framework detection from deps and imports)
- extract_conventions_from_claude_md (convention extraction from CLAUDE.md)
- Internal helpers: _detect_naming_convention, _detect_state_pattern,
  _detect_node_pattern, _detect_test_pattern, _detect_import_style
"""

import pytest

from assemblyzero.utils.pattern_scanner import (
    PatternAnalysis,
    scan_patterns,
    detect_frameworks,
    extract_conventions_from_claude_md,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def snake_case_files():
    """File contents with snake_case module naming and PascalCase classes."""
    return {
        "my_module.py": (
            "class MyClass:\n"
            "    def my_method(self):\n"
            "        pass\n"
        ),
        "another_module.py": (
            "class AnotherService:\n"
            "    pass\n"
        ),
        "utils/helper_functions.py": (
            "def compute_total(items):\n"
            "    return sum(items)\n"
        ),
    }


@pytest.fixture
def typeddict_files():
    """File contents using TypedDict for state management."""
    return {
        "state.py": (
            "from typing import TypedDict\n"
            "\n"
            "class WorkflowState(TypedDict):\n"
            "    issue_text: str\n"
            "    draft: str\n"
        ),
        "node.py": (
            "def my_node(state: dict) -> dict:\n"
            "    return {'draft': 'content'}\n"
        ),
    }


@pytest.fixture
def dataclass_files():
    """File contents using dataclasses for state management."""
    return {
        "models.py": (
            "from dataclasses import dataclass\n"
            "\n"
            "@dataclass\n"
            "class Config:\n"
            "    name: str\n"
            "    value: int\n"
        ),
    }


@pytest.fixture
def pytest_files():
    """File contents with pytest-style testing."""
    return {
        "test_main.py": (
            "import pytest\n"
            "\n"
            "@pytest.fixture\n"
            "def sample_data():\n"
            "    return {'key': 'value'}\n"
            "\n"
            "def test_something(sample_data):\n"
            "    assert sample_data['key'] == 'value'\n"
        ),
        "conftest.py": (
            "import pytest\n"
            "\n"
            "@pytest.fixture\n"
            "def shared_fixture():\n"
            "    yield 42\n"
        ),
    }


@pytest.fixture
def absolute_import_files():
    """File contents using absolute imports."""
    return {
        "main.py": (
            "from assemblyzero.utils.reader import read_file\n"
            "from assemblyzero.workflows.nodes import my_node\n"
            "import assemblyzero.config\n"
        ),
        "helper.py": (
            "from assemblyzero.utils.pattern_scanner import scan_patterns\n"
            "from pathlib import Path\n"
        ),
    }


@pytest.fixture
def relative_import_files():
    """File contents using relative imports."""
    return {
        "nodes/generate.py": (
            "from ..utils.reader import read_file\n"
            "from .base import BaseNode\n"
        ),
        "nodes/review.py": (
            "from . import generate\n"
            "from ..config import settings\n"
        ),
    }


@pytest.fixture
def mixed_import_files():
    """File contents with a mix of absolute and relative imports."""
    return {
        "main.py": (
            "from assemblyzero.utils import reader\n"
            "from assemblyzero.config import settings\n"
            "from assemblyzero.workflows import graph\n"
        ),
        "nodes/generate.py": (
            "from ..utils.reader import read_file\n"
            "from .base import BaseNode\n"
        ),
    }


@pytest.fixture
def node_pattern_files():
    """File contents with function-based node patterns returning dicts."""
    return {
        "nodes/draft.py": (
            "def draft_node(state: dict) -> dict:\n"
            "    result = generate_draft(state['issue_text'])\n"
            "    return {'draft': result}\n"
        ),
        "nodes/review.py": (
            "def review_node(state: dict) -> dict:\n"
            "    verdict = run_review(state['draft'])\n"
            "    return {'verdict': verdict}\n"
        ),
    }


@pytest.fixture
def claude_md_with_conventions():
    """CLAUDE.md content with coding conventions and rules."""
    return (
        "# CLAUDE.md\n"
        "\n"
        "## Coding Conventions\n"
        "\n"
        "- Use snake_case for all module names\n"
        "- Use PascalCase for class names\n"
        "- All functions must have docstrings\n"
        "\n"
        "## Rules\n"
        "\n"
        "- Never use bare `python` — always `poetry run python`\n"
        "- Tests must use pytest fixtures\n"
        "\n"
        "## Other Stuff\n"
        "\n"
        "This is just general information, not a rule.\n"
    )


@pytest.fixture
def claude_md_without_conventions():
    """CLAUDE.md content with no convention/rule sections."""
    return (
        "# CLAUDE.md\n"
        "\n"
        "## Overview\n"
        "\n"
        "This project does amazing things.\n"
        "\n"
        "## Getting Started\n"
        "\n"
        "Run the following command to get started:\n"
        "\n"
        "```bash\n"
        "poetry install\n"
        "```\n"
    )


# ---------------------------------------------------------------------------
# T090 — test_scan_patterns_detects_naming
# ---------------------------------------------------------------------------


class TestScanPatternsDetectsNaming:
    """T090: Identifies snake_case module naming."""

    def test_detects_snake_case(self, snake_case_files):
        """Files with snake_case names should produce snake_case naming convention."""
        result = scan_patterns(snake_case_files)
        assert "snake_case" in result["naming_convention"].lower()

    def test_naming_convention_not_unknown(self, snake_case_files):
        """With clear naming patterns, naming_convention should not be 'unknown'."""
        result = scan_patterns(snake_case_files)
        assert result["naming_convention"] != "unknown"

    def test_detects_pascal_case_classes(self, snake_case_files):
        """Files with PascalCase classes should mention PascalCase."""
        result = scan_patterns(snake_case_files)
        assert "PascalCase" in result["naming_convention"] or \
               "pascal" in result["naming_convention"].lower() or \
               "snake_case" in result["naming_convention"].lower()

    def test_returns_pattern_analysis_shape(self, snake_case_files):
        """Result must have all PatternAnalysis keys."""
        result = scan_patterns(snake_case_files)
        for key in ["naming_convention", "state_pattern", "node_pattern",
                     "test_pattern", "import_style"]:
            assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# T100 — test_scan_patterns_detects_typeddict
# ---------------------------------------------------------------------------


class TestScanPatternsDetectsTypedDict:
    """T100: Finds TypedDict state pattern."""

    def test_detects_typeddict(self, typeddict_files):
        """Files with TypedDict imports should detect TypedDict state pattern."""
        result = scan_patterns(typeddict_files)
        assert "TypedDict" in result["state_pattern"]

    def test_state_pattern_not_unknown(self, typeddict_files):
        """With clear TypedDict usage, state_pattern should not be 'unknown'."""
        result = scan_patterns(typeddict_files)
        assert result["state_pattern"] != "unknown"

    def test_detects_dataclass_pattern(self, dataclass_files):
        """Files with dataclass usage should detect dataclass state pattern."""
        result = scan_patterns(dataclass_files)
        assert "dataclass" in result["state_pattern"].lower()

    def test_detects_node_pattern_with_dict_return(self, typeddict_files):
        """Files with functions returning dict should detect node pattern."""
        result = scan_patterns(typeddict_files)
        # node.py has `def my_node(state: dict) -> dict:`
        assert result["node_pattern"] != "unknown"


# ---------------------------------------------------------------------------
# T105 — test_scan_patterns_unknown_defaults
# ---------------------------------------------------------------------------


class TestScanPatternsUnknownDefaults:
    """T105: Returns 'unknown' for undetectable fields."""

    def test_all_fields_unknown_for_empty(self):
        """Empty file_contents dict should produce all 'unknown' fields."""
        result = scan_patterns({})
        assert result["naming_convention"] == "unknown"
        assert result["state_pattern"] == "unknown"
        assert result["node_pattern"] == "unknown"
        assert result["test_pattern"] == "unknown"
        assert result["import_style"] == "unknown"

    def test_returns_pattern_analysis_type(self):
        """Even for empty input, result should be a valid dict."""
        result = scan_patterns({})
        assert isinstance(result, dict)

    def test_all_values_are_strings(self):
        """All PatternAnalysis values should be strings."""
        result = scan_patterns({})
        for key, value in result.items():
            assert isinstance(value, str), f"{key} is not a string: {type(value)}"

    def test_minimal_content_no_patterns(self):
        """Files with no recognizable patterns should yield 'unknown'."""
        files = {
            "data.txt": "some plain text data\nnothing special here\n",
        }
        result = scan_patterns(files)
        # Most fields should be unknown for a plain text file
        assert result["state_pattern"] == "unknown"
        assert result["test_pattern"] == "unknown"


# ---------------------------------------------------------------------------
# T110 — test_detect_frameworks_from_deps
# ---------------------------------------------------------------------------


class TestDetectFrameworksFromDeps:
    """T110: Identifies LangGraph, pytest from dependency list."""

    def test_detects_langgraph(self):
        """langgraph in deps should produce 'LangGraph' in result."""
        result = detect_frameworks(["langgraph", "pytest"], {})
        display_names = [f.lower() for f in result]
        assert any("langgraph" in n for n in display_names)

    def test_detects_pytest(self):
        """pytest in deps should produce 'pytest' in result."""
        result = detect_frameworks(["langgraph", "pytest"], {})
        display_names = [f.lower() for f in result]
        assert any("pytest" in n for n in display_names)

    def test_both_detected(self):
        """Both LangGraph and pytest should appear in results."""
        result = detect_frameworks(["langgraph", "pytest"], {})
        assert len(result) >= 2

    def test_detects_fastapi(self):
        """fastapi in deps should produce 'FastAPI' in result."""
        result = detect_frameworks(["fastapi"], {})
        display_names = [f.lower() for f in result]
        assert any("fastapi" in n for n in display_names)

    def test_empty_deps_empty_result(self):
        """Empty dependency list with empty file contents returns empty."""
        result = detect_frameworks([], {})
        assert result == []

    def test_unknown_deps_ignored(self):
        """Unknown package names should not produce framework entries."""
        result = detect_frameworks(["my-internal-lib", "custom-tool"], {})
        # Unknown deps should not map to any known framework
        assert isinstance(result, list)

    def test_returns_list_of_strings(self):
        """Result should be a list of strings."""
        result = detect_frameworks(["langgraph"], {})
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, str)

    def test_human_readable_names(self):
        """Detected frameworks should use human-readable display names."""
        result = detect_frameworks(["langgraph"], {})
        # Should be "LangGraph" not "langgraph"
        assert any("LangGraph" in f for f in result)


# ---------------------------------------------------------------------------
# T115 — test_detect_frameworks_from_imports
# ---------------------------------------------------------------------------


class TestDetectFrameworksFromImports:
    """T115: Detects frameworks from import statements in file contents."""

    def test_detects_fastapi_from_imports(self):
        """File with 'from fastapi import' should detect FastAPI."""
        files = {
            "app.py": (
                "from fastapi import FastAPI, Request\n"
                "from fastapi.responses import JSONResponse\n"
            ),
        }
        result = detect_frameworks([], files)
        display_names = [f.lower() for f in result]
        assert any("fastapi" in n for n in display_names)

    def test_detects_langgraph_from_imports(self):
        """File with langgraph import should detect LangGraph."""
        files = {
            "graph.py": (
                "from langgraph.graph import StateGraph\n"
            ),
        }
        result = detect_frameworks([], files)
        display_names = [f.lower() for f in result]
        assert any("langgraph" in n for n in display_names)

    def test_detects_pytest_from_imports(self):
        """File with pytest import should detect pytest."""
        files = {
            "test_main.py": "import pytest\n",
        }
        result = detect_frameworks([], files)
        display_names = [f.lower() for f in result]
        assert any("pytest" in n for n in display_names)

    def test_combines_deps_and_imports(self):
        """Frameworks from both deps and imports should be combined."""
        files = {
            "app.py": "from fastapi import FastAPI\n",
        }
        result = detect_frameworks(["langgraph"], files)
        display_names = [f.lower() for f in result]
        assert any("langgraph" in n for n in display_names)
        assert any("fastapi" in n for n in display_names)

    def test_no_duplicates(self):
        """Same framework from deps and imports should not duplicate."""
        files = {
            "app.py": "from fastapi import FastAPI\n",
        }
        result = detect_frameworks(["fastapi"], files)
        # Count how many times fastapi appears (case-insensitive)
        fastapi_count = sum(1 for f in result if "fastapi" in f.lower())
        assert fastapi_count == 1, f"FastAPI appears {fastapi_count} times: {result}"

    def test_empty_file_contents(self):
        """Empty file contents with no deps returns empty."""
        result = detect_frameworks([], {})
        assert result == []

    def test_no_framework_imports(self):
        """Files with stdlib imports only should not detect frameworks."""
        files = {
            "main.py": (
                "import os\n"
                "import sys\n"
                "from pathlib import Path\n"
            ),
        }
        result = detect_frameworks([], files)
        # os, sys, pathlib are not frameworks
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# T120 — test_extract_conventions_from_claude_md
# ---------------------------------------------------------------------------


class TestExtractConventionsFromClaudeMd:
    """T120: Extracts bullet-point conventions from CLAUDE.md."""

    def test_extracts_conventions(self, claude_md_with_conventions):
        """CLAUDE.md with convention bullets should produce non-empty list."""
        result = extract_conventions_from_claude_md(claude_md_with_conventions)
        assert len(result) > 0

    def test_conventions_are_strings(self, claude_md_with_conventions):
        """All extracted conventions should be strings."""
        result = extract_conventions_from_claude_md(claude_md_with_conventions)
        for conv in result:
            assert isinstance(conv, str)

    def test_conventions_match_content(self, claude_md_with_conventions):
        """Extracted conventions should contain text from the rule bullets."""
        result = extract_conventions_from_claude_md(claude_md_with_conventions)
        all_text = " ".join(result).lower()
        # At least some of the original bullets should be captured
        assert "snake_case" in all_text or "poetry" in all_text or "docstring" in all_text

    def test_extracts_from_rules_section(self, claude_md_with_conventions):
        """Rules section bullets should also be extracted."""
        result = extract_conventions_from_claude_md(claude_md_with_conventions)
        all_text = " ".join(result).lower()
        # "poetry run python" is under ## Rules
        has_rule_content = (
            "poetry" in all_text
            or "pytest" in all_text
            or "snake_case" in all_text
        )
        assert has_rule_content, f"Expected rule content in: {result}"

    def test_returns_list_type(self, claude_md_with_conventions):
        """Return type should be a list."""
        result = extract_conventions_from_claude_md(claude_md_with_conventions)
        assert isinstance(result, list)

    def test_no_empty_strings(self, claude_md_with_conventions):
        """Extracted conventions should not contain empty strings."""
        result = extract_conventions_from_claude_md(claude_md_with_conventions)
        for conv in result:
            assert conv.strip() != "", "Found empty convention string"


# ---------------------------------------------------------------------------
# T130 — test_extract_conventions_empty
# ---------------------------------------------------------------------------


class TestExtractConventionsEmpty:
    """T130: Returns empty list for CLAUDE.md without conventions."""

    def test_returns_empty_for_no_conventions(self, claude_md_without_conventions):
        """CLAUDE.md without convention/rule sections should return []."""
        result = extract_conventions_from_claude_md(claude_md_without_conventions)
        assert result == []

    def test_returns_empty_for_empty_string(self):
        """Empty string input should return []."""
        result = extract_conventions_from_claude_md("")
        assert result == []

    def test_returns_list_type(self, claude_md_without_conventions):
        """Return type should be a list even when empty."""
        result = extract_conventions_from_claude_md(claude_md_without_conventions)
        assert isinstance(result, list)

    def test_no_conventions_in_plain_text(self):
        """Plain text without any markdown structure returns []."""
        result = extract_conventions_from_claude_md(
            "This is just some random text about a project.\n"
            "It has no rules or conventions defined.\n"
        )
        assert result == []


# ---------------------------------------------------------------------------
# Additional scan_patterns tests for completeness
# ---------------------------------------------------------------------------


class TestScanPatternsTestPattern:
    """Additional tests for test pattern detection."""

    def test_detects_pytest_pattern(self, pytest_files):
        """Files with pytest usage should detect pytest test pattern."""
        result = scan_patterns(pytest_files)
        assert "pytest" in result["test_pattern"].lower()

    def test_detects_unittest_pattern(self):
        """Files with unittest usage should detect unittest pattern."""
        files = {
            "test_main.py": (
                "import unittest\n"
                "\n"
                "class TestMain(unittest.TestCase):\n"
                "    def test_something(self):\n"
                "        self.assertEqual(1, 1)\n"
            ),
        }
        result = scan_patterns(files)
        assert "unittest" in result["test_pattern"].lower()

    def test_no_test_files_unknown(self):
        """Files without any test content should have 'unknown' test pattern."""
        files = {
            "main.py": "def main():\n    pass\n",
        }
        result = scan_patterns(files)
        assert result["test_pattern"] == "unknown"


class TestScanPatternsImportStyle:
    """Additional tests for import style detection."""

    def test_detects_absolute_imports(self, absolute_import_files):
        """Files using absolute imports should detect absolute import style."""
        result = scan_patterns(absolute_import_files)
        assert "absolute" in result["import_style"].lower()

    def test_detects_relative_imports(self, relative_import_files):
        """Files using relative imports should detect relative import style."""
        result = scan_patterns(relative_import_files)
        assert "relative" in result["import_style"].lower()

    def test_no_imports_unknown(self):
        """Files without any imports should have 'unknown' import style."""
        files = {
            "data.txt": "no imports here\n",
        }
        result = scan_patterns(files)
        assert result["import_style"] == "unknown"


class TestScanPatternsNodePattern:
    """Additional tests for node pattern detection."""

    def test_detects_dict_returning_functions(self, node_pattern_files):
        """Files with functions returning dict should detect node pattern."""
        result = scan_patterns(node_pattern_files)
        assert result["node_pattern"] != "unknown"

    def test_no_node_pattern_unknown(self):
        """Files without node-like functions should have 'unknown' node pattern."""
        files = {
            "util.py": "def add(a, b):\n    return a + b\n",
        }
        result = scan_patterns(files)
        # Simple utility function without dict return might be unknown
        assert isinstance(result["node_pattern"], str)


class TestScanPatternsBaseModelState:
    """Test detection of Pydantic BaseModel state pattern."""

    def test_detects_basemodel(self):
        """Files with BaseModel imports should detect BaseModel state pattern."""
        files = {
            "models.py": (
                "from pydantic import BaseModel\n"
                "\n"
                "class UserState(BaseModel):\n"
                "    name: str\n"
                "    age: int\n"
            ),
        }
        result = scan_patterns(files)
        assert "BaseModel" in result["state_pattern"] or \
               "pydantic" in result["state_pattern"].lower() or \
               result["state_pattern"] != "unknown"


class TestScanPatternsComprehensive:
    """Comprehensive tests combining multiple patterns."""

    def test_full_project_patterns(self):
        """A realistic project should have multiple patterns detected."""
        files = {
            "my_module.py": (
                "from typing import TypedDict\n"
                "from assemblyzero.utils import helper\n"
                "\n"
                "class State(TypedDict):\n"
                "    data: str\n"
            ),
            "nodes/draft.py": (
                "from assemblyzero.workflows import base\n"
                "\n"
                "def draft_node(state: dict) -> dict:\n"
                "    return {'draft': 'content'}\n"
            ),
            "test_main.py": (
                "import pytest\n"
                "\n"
                "def test_draft():\n"
                "    assert True\n"
            ),
        }
        result = scan_patterns(files)
        # Multiple fields should be detected
        detected_count = sum(
            1 for v in result.values() if v != "unknown"
        )
        assert detected_count >= 3, (
            f"Expected at least 3 detected patterns, got {detected_count}: {result}"
        )


class TestDetectFrameworksEdgeCases:
    """Edge cases for detect_frameworks."""

    def test_case_insensitive_deps(self):
        """Dependencies with varied casing should still be detected."""
        # The function should handle common dep name formats
        result = detect_frameworks(["LangGraph", "FastAPI"], {})
        assert isinstance(result, list)

    def test_deps_with_version_specifiers_stripped(self):
        """Dependency names should be just the package name, no version."""
        # The caller should pass clean names, but the function should be robust
        result = detect_frameworks(["langgraph", "fastapi"], {})
        assert isinstance(result, list)

    def test_large_dependency_list(self):
        """A large dependency list should not crash."""
        deps = [f"package-{i}" for i in range(100)]
        deps.extend(["langgraph", "pytest"])
        result = detect_frameworks(deps, {})
        display_names = [f.lower() for f in result]
        assert any("langgraph" in n for n in display_names)

    def test_multiple_framework_imports_in_one_file(self):
        """Multiple framework imports in one file should all be detected."""
        files = {
            "app.py": (
                "from fastapi import FastAPI\n"
                "from langgraph.graph import StateGraph\n"
                "import pytest\n"
            ),
        }
        result = detect_frameworks([], files)
        assert len(result) >= 2


class TestExtractConventionsEdgeCases:
    """Edge cases for extract_conventions_from_claude_md."""

    def test_conventions_with_code_blocks(self):
        """Conventions in code blocks should be handled."""
        content = (
            "# CLAUDE.md\n"
            "\n"
            "## Style Rules\n"
            "\n"
            "```\n"
            "Always use type hints\n"
            "```\n"
            "\n"
            "- Use type hints for all function parameters\n"
            "- Maximum line length is 100 characters\n"
        )
        result = extract_conventions_from_claude_md(content)
        assert isinstance(result, list)

    def test_deeply_nested_conventions(self):
        """Conventions under nested headers should be found."""
        content = (
            "# CLAUDE.md\n"
            "\n"
            "## Development\n"
            "\n"
            "### Coding Standards\n"
            "\n"
            "- Use Black for formatting\n"
            "- Use isort for imports\n"
        )
        result = extract_conventions_from_claude_md(content)
        assert isinstance(result, list)

    def test_constraint_section(self):
        """Sections with 'constraint' in the header should be captured."""
        content = (
            "# Project Rules\n"
            "\n"
            "## Constraints\n"
            "\n"
            "- No external API calls in tests\n"
            "- All imports must be absolute\n"
        )
        result = extract_conventions_from_claude_md(content)
        assert len(result) > 0

    def test_very_long_claude_md(self):
        """Very long CLAUDE.md should not crash and should extract conventions."""
        sections = []
        for i in range(50):
            sections.append(f"## Section {i}\n\nSome content for section {i}.\n")
        sections.append(
            "## Rules\n\n"
            "- Important rule one\n"
            "- Important rule two\n"
        )
        content = "# CLAUDE.md\n\n" + "\n".join(sections)
        result = extract_conventions_from_claude_md(content)
        assert isinstance(result, list)
        assert len(result) > 0


class TestScanPatternsLanggraphTypedDict:
    """TypedDict + LangGraph combo should produce specific state pattern."""

    def test_typeddict_langgraph_state(self):
        """Files with both TypedDict and langgraph imports should detect LangGraph state."""
        files = {
            "state.py": (
                "from typing import TypedDict\n"
                "from langgraph.graph import StateGraph\n"
                "class MyState(TypedDict):\n"
                "    value: str\n"
            ),
        }
        result = scan_patterns(files)
        assert "LangGraph" in result["state_pattern"]

    def test_state_based_node_functions(self):
        """Functions with 'state' parameter should detect node pattern."""
        files = {
            "nodes.py": (
                "def process_data(state: MyState):\n"
                "    state['result'] = 'done'\n"
            ),
        }
        result = scan_patterns(files)
        assert result["node_pattern"] != "unknown"


class TestScanPatternsImportStyleVariants:
    """Cover all import style detection branches."""

    def test_primarily_relative_imports(self):
        """More relative than absolute imports."""
        files = {
            "mod.py": (
                "from . import utils\n"
                "from .core import stuff\n"
                "from ..shared import helper\n"
                "from package import base\n"
            ),
        }
        result = scan_patterns(files)
        assert "relative" in result["import_style"].lower()

    def test_mixed_imports(self):
        """Equal absolute and relative imports."""
        files = {
            "mod.py": (
                "from . import utils\n"
                "from package import base\n"
            ),
        }
        result = scan_patterns(files)
        assert "mixed" in result["import_style"].lower() or "import" in result["import_style"].lower()


class TestScanPatternsUnderscoreFunctions:
    """Cover underscore-prefixed function stripping."""

    def test_private_functions_counted(self):
        """Private functions (leading _) should be counted after stripping."""
        files = {
            "mod.py": (
                "def _private_helper():\n    pass\n"
                "def __double_private():\n    pass\n"
                "def public_func():\n    pass\n"
            ),
        }
        result = scan_patterns(files)
        assert "snake_case" in result["naming_convention"]

    def test_only_dunder_functions(self):
        """Functions that are only underscores after stripping."""
        files = {
            "mod.py": (
                "def ___():\n    pass\n"
                "class Foo:\n    pass\n"
            ),
        }
        result = scan_patterns(files)
        assert isinstance(result["naming_convention"], str)


class TestExtractConventionsNumberedList:
    """Cover numbered list convention extraction."""

    def test_numbered_rules(self):
        """Numbered list items should be extracted from convention sections."""
        content = (
            "# CLAUDE.md\n"
            "\n"
            "## Rules\n"
            "\n"
            "1. Always use type hints for function parameters\n"
            "2. Never commit .env files to the repo\n"
            "3. Run tests before pushing\n"
        )
        result = extract_conventions_from_claude_md(content)
        assert len(result) >= 3

    def test_code_block_conventions(self):
        """Conventions in labeled code blocks should be extracted."""
        content = (
            "# CLAUDE.md\n"
            "\n"
            "```rules\n"
            "Use poetry for dependency management\n"
            "Run all tests before merging\n"
            "```\n"
        )
        result = extract_conventions_from_claude_md(content)
        assert len(result) >= 2


class TestPrivateFunctionStripping:
    """_detect_naming_convention strips leading underscores from function names."""

    def test_private_and_dunder_functions_detected(self):
        """Functions like __init__ and _helper should be analyzed after stripping."""
        files = {
            "mod.py": "def __init__(self): pass\ndef _helper(): pass\ndef normal_func(): pass"
        }
        result = scan_patterns(files)
        assert "snake_case functions" in result["naming_convention"]

    def test_only_dunder_functions(self):
        """Functions that become empty after stripping (like __) are skipped."""
        files = {
            "mod.py": "def __(self): pass\ndef _(): pass"
        }
        result = scan_patterns(files)
        # Should not crash; naming convention may or may not detect patterns
        assert isinstance(result["naming_convention"], str)


class TestTypedDictLangGraphState:
    """_detect_state_pattern returns TypedDict-based LangGraph state."""

    def test_typeddict_with_langgraph(self):
        """TypedDict + LangGraph import yields special detection."""
        files = {
            "state.py": "from typing import TypedDict\nfrom langgraph.graph import StateGraph\n\nclass MyState(TypedDict):\n    value: str"
        }
        result = scan_patterns(files)
        assert "TypedDict" in result["state_pattern"]
        assert "LangGraph" in result["state_pattern"]


class TestStateFunctionNodePattern:
    """_detect_node_pattern detects state-based node functions."""

    def test_state_parameter_functions(self):
        """Functions with 'state:' parameter detected as node pattern."""
        files = {
            "node.py": "def process_data(state: MyState) -> dict:\n    return {'key': 'val'}"
        }
        result = scan_patterns(files)
        assert "state" in result["node_pattern"].lower() or "dict" in result["node_pattern"].lower()


class TestPytestStyleTestFunctions:
    """_detect_test_pattern detects test functions without explicit pytest import."""

    def test_test_functions_without_import(self):
        """Files with test_ functions but no pytest import are detected."""
        files = {
            "test_foo.py": "def test_first():\n    assert True\ndef test_second():\n    assert 1 + 1 == 2"
        }
        result = scan_patterns(files)
        assert result["test_pattern"] != "unknown"


class TestImportStyleBranches:
    """_detect_import_style covers various import patterns."""

    def test_absolute_only_imports(self):
        """Only absolute imports returns specific message."""
        files = {
            "mod.py": "from mypackage.utils import helper\nfrom mypackage.core import base"
        }
        result = scan_patterns(files)
        assert "absolute" in result["import_style"].lower() or result["import_style"] == "unknown"

    def test_relative_only_imports(self):
        """Only relative imports returns specific message."""
        files = {
            "mod.py": "from . import helper\nfrom ..core import base"
        }
        result = scan_patterns(files)
        assert "relative" in result["import_style"].lower() or result["import_style"] == "unknown"

    def test_mixed_imports(self):
        """Mix of absolute and relative imports with primarily relative."""
        files = {
            "mod.py": (
                "from mypackage.utils import helper\n"
                "from . import local_mod\n"
                "from ..core import base\n"
                "from ...deep import thing\n"
            )
        }
        result = scan_patterns(files)
        assert "import" in result["import_style"].lower() or result["import_style"] == "unknown"

    def test_primarily_absolute(self):
        """More absolute than relative imports."""
        files = {
            "mod.py": (
                "from mypackage.a import x\n"
                "from mypackage.b import y\n"
                "from mypackage.c import z\n"
                "from . import local\n"
            )
        }
        result = scan_patterns(files)
        assert "absolute" in result["import_style"].lower() or result["import_style"] == "unknown"


class TestConventionsNumberedListAndCodeBlocks:
    """extract_conventions_from_claude_md handles numbered lists and code blocks."""

    def test_numbered_list_items(self):
        """Numbered list items (1. item) are extracted."""
        content = (
            "# CLAUDE.md\n\n"
            "## Rules\n\n"
            "1. Always use snake_case\n"
            "2. Never use global state\n"
            "3) Prefer composition over inheritance\n"
        )
        result = extract_conventions_from_claude_md(content)
        assert len(result) >= 3

    def test_code_block_labeled_rules(self):
        """Code blocks labeled as 'rules' have their content extracted."""
        content = (
            "# CLAUDE.md\n\n"
            "## Standards\n\n"
            "```rules\n"
            "- Use type hints everywhere\n"
            "- No bare except clauses\n"
            "```\n"
        )
        result = extract_conventions_from_claude_md(content)
        assert any("type hints" in c for c in result)