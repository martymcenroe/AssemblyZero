"""#2336: a generated test must not import a symbol that does not exist.

`run-issue7-192332` ran opus for 194.1s to add 12 coverage-targeting tests.
The import block asked for `default_config_path`; the module exports
`get_default_config_path`. One name, one shared import statement, and
collection died for the whole file -- 0 tests ran, the 23 already passing
were destroyed with it, and the stage ended.

Correcting only that name in the generated file gives 34 passed and 100%
coverage on the target module, past the 95% gate. The work was substantially
correct; the stage died on a name.

The fixture is the real generated file, preserved from boostgauge's
`graveyard/issue-7-20260814T002812Z` checkpoint chain.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.augment_tests import (
    MAX_GENERATION_ATTEMPTS,
    build_revision_prompt,
)
from assemblyzero.workflows.testing.symbol_validator import (
    exported_names,
    module_source_path,
    validate_test_imports,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "issue7_run192332"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A src-layout repo whose config module mirrors the real one."""
    pkg = tmp_path / "src" / "boostgauge"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "config.py").write_text(
        "import json\n"
        "DEFAULT_SIZE = 300\n"
        "def get_default_config_path():\n    return None\n"
        "def get_default_config():\n    return {}\n"
        "def load_config(p):\n    return {}\n"
        "class Threshold:\n    pass\n",
        encoding="utf-8",
    )
    return tmp_path


def test_the_real_hallucination_is_caught(repo: Path) -> None:
    """The exact import block that killed the stage."""
    source = (FIXTURES / "n4c_generated_tests.py").read_text(encoding="utf-8")

    errors = validate_test_imports(source, repo)

    assert errors, "the bad symbol must be reported"
    joined = "\n".join(errors)
    assert "default_config_path" in joined
    assert "get_default_config_path" in joined, (
        "a near-miss must be offered, not just the failure"
    )


def test_valid_imports_produce_no_findings(repo: Path) -> None:
    source = (
        "from boostgauge.config import get_default_config_path, load_config\n"
        "def test_x():\n    assert get_default_config_path() is None\n"
    )
    assert validate_test_imports(source, repo) == []


def test_constants_and_classes_count_as_exports(repo: Path) -> None:
    source = "from boostgauge.config import DEFAULT_SIZE, Threshold\n"
    assert validate_test_imports(source, repo) == []


def test_reexported_imports_count(repo: Path) -> None:
    """`config` imports json, so `from boostgauge.config import json` works."""
    assert validate_test_imports(
        "from boostgauge.config import json\n", repo,
    ) == []


@pytest.mark.parametrize("source", [
    "import pytest\n",                          # plain import, not checked
    "from unittest.mock import patch\n",        # third-party / stdlib
    "from boostgauge.config import *\n",        # star import
    "from . import sibling\n",                  # relative
    "def test_broken(:\n",                      # unparseable
    "",
])
def test_never_invents_a_finding(repo: Path, source: str) -> None:
    """Anything it cannot decide must produce no finding, never a guess."""
    assert validate_test_imports(source, repo) == []


def test_unreadable_module_is_not_evidence(tmp_path: Path) -> None:
    pkg = tmp_path / "src" / "boostgauge"
    pkg.mkdir(parents=True)
    (pkg / "config.py").write_text("def broken(:\n", encoding="utf-8")

    assert exported_names(pkg / "config.py") is None
    assert validate_test_imports(
        "from boostgauge.config import anything\n", tmp_path,
    ) == []


def test_module_outside_the_repo_is_skipped(repo: Path) -> None:
    assert module_source_path("numpy.linalg", repo) is None
    assert validate_test_imports(
        "from numpy.linalg import solve\n", repo,
    ) == []


def test_flat_layout_is_found(tmp_path: Path) -> None:
    """Not every repo is src-layout."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "thing.py").write_text("def real():\n    pass\n", encoding="utf-8")

    assert validate_test_imports(
        "from mypkg.thing import real\n", tmp_path,
    ) == []
    assert validate_test_imports(
        "from mypkg.thing import imaginary\n", tmp_path,
    )


def test_revision_prompt_names_the_problem_and_keeps_the_work() -> None:
    """The failure is one wrong name in an otherwise usable file."""
    prompt = build_revision_prompt(
        "original request",
        "from boostgauge.config import default_config_path\n",
        ["boostgauge.config has no 'default_config_path'. "
         "Did you mean: get_default_config_path?"],
    )

    assert "REJECTED before it ran" in prompt
    assert "default_config_path" in prompt
    assert "get_default_config_path" in prompt
    assert "Keep everything else about the tests the same" in prompt, (
        "a fresh start would discard work that was substantially correct"
    )
    assert "original request" in prompt


def test_a_bounded_number_of_attempts() -> None:
    """Another 194-second call is worth less than the passing suite."""
    assert MAX_GENERATION_ATTEMPTS == 2
