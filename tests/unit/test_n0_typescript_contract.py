"""N0's contract holds a spec's TypeScript tests beside its Python ones (#4680).

A spec for a target with a Python suite at its root and a Vitest suite in
`web/` carried both in Section 10: a Python fence with 5 `def test_`
functions and a TypeScript fence with 8 Vitest `it` calls, for 10
requirements. N0 took the 5 Python functions as the whole contract, and N1's
ratio gate refused the run: "Only 5 scenario(s) for 10 requirement(s)".

The TypeScript calls are read with the #4551 reader. Section 6's planned test
file restates them, and is not counted again.
"""

from __future__ import annotations

import json
from pathlib import Path

from assemblyzero.workflows.testing.nodes.load_lld import (
    extract_test_plan_section,
    load_lld,
    parse_test_scenarios,
)
from assemblyzero.workflows.testing.nodes.review_test_plan import (
    _run_mechanical_gates,
    check_requirement_coverage,
)

#: The Vitest suite, as the spec writes it in Section 6 and Section 10: two
#: tests that run, one inside a `describe`, and a skip and a todo, which
#: cover nothing.
VITEST = """\
import { describe, it, expect } from "vitest";
describe("REQ-3 web ledger", () => {
  it("shows the total", () => {
    expect(1).toBe(1);
  });
});
it("satisfies REQ-4: replays bit-identically", () => {
  expect(1).toBe(1);
});
it.skip("satisfies REQ-4: a skipped test covers nothing", () => {});
it.todo("satisfies REQ-4: a todo covers nothing");
"""

PYTHON = '''\
from ledger import total


def test_req_1_sums_entries():
    """REQ-1: the ledger sums its entries."""
    assert total([1, 2]) == 3


def test_req_2_refuses_negative():
    """REQ-2: the ledger refuses a negative entry."""
    assert total([-1]) is None
'''

HEAD = """# 9 - Ledger totals

**Status:** APPROVED

## 2. Files to Implement

| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `src/ledger.py` | Modify | The ledger |
| 2 | `tests/test_ledger.py` | Add | Its Python tests |
| 3 | `web/src/ledger.ts` | Modify | The web ledger |
| 4 | `web/tests/replay.test.ts` | Modify | Its Vitest tests |

## 3. Requirements

1. REQ-1: The ledger sums its entries.
2. REQ-2: The ledger refuses a negative entry.
3. REQ-3: The web ledger shows the total.
4. REQ-4: The web ledger replays bit-identically.

## 6. Change Instructions

### 6.1 `web/tests/replay.test.ts` (Modify)

```typescript
{vitest}```

## 10. Test Plan

"""

#: Section 10 with both suites.
MIXED = HEAD + """### 10.1 Per-criterion test functions

```python
{python}```

```typescript
// web/tests/replay.test.ts
{vitest}```
"""

#: Section 10 with the Vitest suite and no Python functions: the table path.
TYPESCRIPT_ONLY = HEAD + """### test_the_ledger_sums_its_entries
Verify that the ledger sums its entries.
Requirement: REQ-1

```typescript
// web/tests/replay.test.ts
{vitest}```
"""

TYPESCRIPT_TITLES = ["shows the total", "satisfies REQ-4: replays bit-identically"]

#: The same suite titled by criteria row, as a spec writes it: the title cites
#: the row (`REQ-030`), the body cites the requirement (`REQ-3`).
ROW_TAGGED = """\
import { it, expect } from "vitest";
it("satisfies REQ-030: shows the total", () => {
  // The web ledger shows the total (REQ-3)
  expect(1).toBe(1);
});
it("satisfies REQ-040: replays bit-identically", () => {
  // Replay is bit-identical (REQ-4)
  expect(1).toBe(1);
});
"""


def _mixed_target(root: Path) -> Path:
    """A Python suite at the root and a Vitest suite in web/."""
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_engine.py").write_text(
        "def test_engine():\n    assert True\n", encoding="utf-8"
    )
    web = root / "web"
    (web / "tests").mkdir(parents=True)
    (web / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"},
                    "devDependencies": {"vitest": "^2.1.0"}}),
        encoding="utf-8",
    )
    (web / "vitest.config.ts").write_text("export default {}\n", encoding="utf-8")
    return root


def _spec(template: str) -> str:
    return template.format(python=PYTHON, vitest=VITEST)


def _load(root: Path, spec: str) -> dict:
    path = root / "spec-9.md"
    path.write_text(spec, encoding="utf-8")
    result = load_lld({"issue_number": 9, "repo_root": str(root), "lld_path": str(path)})
    assert result.get("error_message", "") == "", result.get("error_message")
    return result


class TestT1TheContractIsBothSuites:
    """T1 (R1, R2, R4): Python functions and running Vitest calls, once each."""

    def test_the_contract_holds_both_suites(self, tmp_path):
        """Fails on main, whose contract is the 2 Python functions alone."""
        result = _load(_mixed_target(tmp_path), _spec(MIXED))

        assert [s["name"] for s in result["test_scenarios"]] == [
            "test_req_1_sums_entries",
            "test_req_2_refuses_negative",
            *TYPESCRIPT_TITLES,
        ]

    def test_the_pytest_scaffold_still_gets_only_the_python_functions(self, tmp_path):
        result = _load(_mixed_target(tmp_path), _spec(MIXED))

        assert [f["name"] for f in result["spec_test_suite"]["functions"]] == [
            "test_req_1_sums_entries",
            "test_req_2_refuses_negative",
        ]


class TestT2EachTypeScriptScenarioCitesItsRequirement:
    """T2 (R3): the REQ tag comes from the call's source, `describe` included."""

    def test_each_typescript_scenario_carries_its_tag(self, tmp_path):
        result = _load(_mixed_target(tmp_path), _spec(MIXED))

        refs = {s["name"]: s["requirement_ref"] for s in result["test_scenarios"]}
        assert refs == {
            "test_req_1_sums_entries": "REQ-1",
            "test_req_2_refuses_negative": "REQ-2",
            "shows the total": "REQ-3",
            "satisfies REQ-4: replays bit-identically": "REQ-4",
        }


class TestT2bARowTitledTestJoinsOnItsRequirement:
    """T2 (R3): a test titled by its criteria row joins on the requirement it
    cites, so N1's coverage join sees every requirement covered."""

    def test_each_row_titled_scenario_carries_the_requirement(self, tmp_path):
        """Fails on main, which has no TypeScript scenario at all."""
        result = _load(_mixed_target(tmp_path), MIXED.format(python=PYTHON, vitest=ROW_TAGGED))

        refs = {s["name"]: s["requirement_ref"] for s in result["test_scenarios"]}
        assert refs["satisfies REQ-030: shows the total"] == "REQ-3"
        assert refs["satisfies REQ-040: replays bit-identically"] == "REQ-4"
        coverage = check_requirement_coverage(result["requirements"], result["test_scenarios"])
        assert coverage["passed"], coverage


class TestT3N1CountsTheWholeSuite:
    """T3 (R1): the ratio gate sees 4 scenarios for 4 requirements."""

    def test_the_mechanical_gates_pass(self, tmp_path):
        """Fails on main: "Only 2 scenario(s) for 4 requirement(s)"."""
        result = _load(_mixed_target(tmp_path), _spec(MIXED))
        assert len(result["requirements"]) == 4

        assert _run_mechanical_gates(result) == []


class TestT4NoPythonFunctionsKeepsTheTablePath:
    """T4 (R6): without Python functions, Section 10's tables are the contract."""

    def test_a_typescript_only_section_10_uses_the_tables(self, tmp_path):
        spec = _spec(TYPESCRIPT_ONLY)
        result = _load(_mixed_target(tmp_path), spec)

        tables = parse_test_scenarios(extract_test_plan_section(spec))
        assert [s["name"] for s in result["test_scenarios"]] == [s["name"] for s in tables]
        assert not set(TYPESCRIPT_TITLES) & {s["name"] for s in result["test_scenarios"]}


class TestT5N0SaysBothCounts:
    """T5 (R5): the contract line names the Python and the TypeScript count."""

    def test_the_line_names_both(self, tmp_path, capsys):
        _load(_mixed_target(tmp_path), _spec(MIXED))

        out = capsys.readouterr().out
        assert (
            "Found 2 executable test functions and 2 TypeScript test calls in the "
            "spec's Section 10" in out
        )
