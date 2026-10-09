"""The red-phase import names each module from the plan file that defines it (#4148).

boostgauge #2's run 59 (run-issue2-063235, 2026-10-07) stalled at 12 passed /
10 failed for five iterations: the contract suite imported `GaugeWidget` and
the test helper `get_test_config` from `boostgauge.formatters`, the first Add
file, while the spec defines `GaugeWidget` in `gauge.py` and the helper in
`tests/unit/test_gauge.py`. The implementer stubbed both into formatters.py,
and the frozen suite tested the stub.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_plan_code,
    extract_spec_test_functions,
)
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    ScaffoldImportError,
    generate_spec_test_file_content,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

PLAN = [
    {"path": "src/pkg/a.py", "change_type": "Add"},
    {"path": "src/pkg/b.py", "change_type": "Add"},
    {"path": "tests/unit/test_b.py", "change_type": "Add"},
]


def _spec(section6: str, tests: str) -> str:
    return (
        "# Spec\n\n## 6. Change Instructions\n\n" + section6
        + "\n## 10. Test Mapping\n\n### 10.1 Per-criterion test functions\n\n"
        + "```python\n" + tests + "```\n"
    )


A = "### 6.1 `src/pkg/a.py` (Add)\n\n```python\ndef format_x(v):\n    return str(v)\n```\n\n"
B = "### 6.2 `src/pkg/b.py` (Add)\n\n```python\nclass Widget:\n    pass\n```\n\n"
TEST_B = (
    "### 6.3 `tests/unit/test_b.py` (Add)\n\n```python\n"
    "import json\nfrom pkg.b import Widget\n\n"
    "def make_config():\n    return json.loads('{\"k\": 1}')\n```\n\n"
)
TESTS = (
    "def test_req_1():\n    assert format_x(1) == '1'\n\n"
    "def test_req_2():\n    assert Widget() is not None\n"
)


def _emit(spec: str, plan=PLAN) -> str:
    suite = extract_spec_test_functions(spec)
    return generate_spec_test_file_content(suite, 4148, plan)


def _import_lines(content: str) -> list[str]:
    return [line for line in content.splitlines() if line.startswith(("from ", "import "))]


def test_t1_each_name_comes_from_its_defining_file():
    content = _emit(_spec(A + B, TESTS))
    lines = _import_lines(content)
    assert "from pkg.a import format_x  # noqa: F401" in lines
    assert "from pkg.b import Widget  # noqa: F401" in lines
    assert not any(line.startswith("from pkg.a") and "Widget" in line for line in lines)


def test_t2_a_test_helper_is_copied_never_imported_from_the_implementation():
    tests = TESTS + "\ndef test_req_3():\n    assert make_config() == {'k': 1}\n"
    content = _emit(_spec(A + B + TEST_B, tests))
    lines = _import_lines(content)
    assert not any("make_config" in line for line in lines)
    assert "def make_config():" in content
    assert "import json" in lines  # the helper's own import came with it
    compile(content, "test_issue_4148.py", "exec")


def test_t3_a_name_defined_in_two_files_stops_the_scaffold():
    both = A + B.replace("class Widget:\n    pass", "class Widget:\n    pass\n\ndef format_x(v):\n    return v")
    with pytest.raises(ScaffoldImportError) as exc:
        _emit(_spec(A + both, TESTS))
    assert "format_x" in str(exc.value)
    assert "src/pkg/a.py" in str(exc.value)
    assert "src/pkg/b.py" in str(exc.value)


def test_t3_an_add_file_whose_code_does_not_parse_stops_the_scaffold():
    broken = "### 6.2 `src/pkg/b.py` (Add)\n\n```python\nclass Widget(:\n    pass\n```\n\n"
    with pytest.raises(ScaffoldImportError, match="src/pkg/b.py.*does not parse"):
        _emit(_spec(A + broken, TESTS))


def test_t3_a_name_defined_nowhere_stops_the_scaffold():
    with pytest.raises(ScaffoldImportError, match="`Widget`.*no planned file"):
        _emit(_spec(A, TESTS))


def test_t4_the_suite_fails_at_collection_before_the_implementation(tmp_path):
    (tmp_path / "test_issue_4148.py").write_text(_emit(_spec(A + B, TESTS)), encoding="utf-8")
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         str(tmp_path / "test_issue_4148.py")],
        capture_output=True, text=True, cwd=tmp_path, check=False,
    )
    assert run.returncode != 0
    assert "ModuleNotFoundError" in run.stdout + run.stderr


def test_t4_a_plan_of_only_modified_files_still_imports_an_added_module():
    plan = [{"path": "src/pkg/a.py", "change_type": "Modify"},
            {"path": "src/pkg/new.py", "change_type": "Add"}]
    lines = _import_lines(_emit(_spec(A, "def test_req_1():\n    assert format_x(1)\n"), plan))
    assert "import pkg.new  # noqa: F401" in lines


BOOSTGAUGE_PLAN = [
    {"path": "src/boostgauge/formatters.py", "change_type": "Add"},
    {"path": "src/boostgauge/gauge.py", "change_type": "Add"},
    {"path": "tests/unit/test_formatters.py", "change_type": "Add"},
    {"path": "tests/unit/test_gauge.py", "change_type": "Add"},
    {"path": "tests/visual/test_telltale_render.py", "change_type": "Add"},
]


def test_t5_boostgauge_2_imports_gauge_widget_from_gauge():
    spec = (FIXTURES / "boostgauge-2-spec-0002-final-spec.md").read_text(encoding="utf-8")
    content = _emit(spec, BOOSTGAUGE_PLAN)
    lines = _import_lines(content)

    assert any(
        line.startswith("from boostgauge.gauge import ") and "GaugeWidget" in line
        for line in lines
    ), lines
    formatters = [line for line in lines if line.startswith("from boostgauge.formatters")]
    assert not any("GaugeWidget" in line or "get_test_config" in line for line in formatters)
    assert "def get_test_config()" in content


def test_section_6_is_read_per_file():
    spec = _spec(A + B + TEST_B, TESTS)
    assert set(extract_plan_code(spec)) == {"src/pkg/a.py", "src/pkg/b.py", "tests/unit/test_b.py"}
