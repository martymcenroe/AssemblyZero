"""A planned sibling's import resolves before the sibling is written (#2883).

boostgauge #4, `run-issue4-003342` (2026-09-06 00:33). The path guard had
just been fixed (#2879) and the implementer began on the plan's first file:

    [1/5] src/boostgauge/collector.py (Add)...
        Calling Claude... (15s)
        [RETRY 2/2] attempt 1 failed (Validation failed: Unresolvable imports:
        boostgauge.collectors.windows (line 100...) -- retrying
        Calling Claude... (30s)
        Calling Claude... error (45s)
    FATAL: Failed to implement src/boostgauge/collector.py: Validation failed
    after 2 attempts: Unresolvable imports: boostgauge.collectors.windows (line 95)

The generated collector.py was right: LLD-004 has the abstract collector
dispatch to the platform module, and `src/boostgauge/collectors/windows.py` is
the plan's SECOND file. `validate_imports` (#842) resolves internal imports
against the disk, the plan is written [1/5], [2/5], ... in order, and nobody
told the validator what the plan would write. A deterministic refusal, paid
for six times across three orchestrator attempts.

Three layers are tested, because a fix in the validator alone changes nothing
if the plan never reaches it: the validator's rule, `validate_code_response`
carrying the plan, and `implement_code` handing it to every generation.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.nodes.implementation import orchestrator
from assemblyzero.workflows.testing.nodes.implementation.import_validator import (
    validate_imports,
)
from assemblyzero.workflows.testing.nodes.implementation.parsers import (
    validate_code_response,
)

RUN_27_PLAN = [
    {"path": "src/boostgauge/collector.py", "change_type": "Add"},
    {"path": "src/boostgauge/collectors/windows.py", "change_type": "Add"},
    {"path": "tests/unit/test_collector.py", "change_type": "Add"},
    {"path": "tests/integration/test_windows_sweep_crosscheck.py", "change_type": "Add"},
    {"path": "tests/benchmark/test_sweep_cost.py", "change_type": "Add"},
]
PLANNED = [spec["path"] for spec in RUN_27_PLAN]

# The shape run 27 generated: the platform dispatch imports the planned
# sibling inside a function, exactly as the design asks.
COLLECTOR = (
    '"""Abstract collector and platform dispatch."""\n'
    "from __future__ import annotations\n"
    "\n"
    "import platform\n"
    "\n"
    "\n"
    "def make_collector():\n"
    '    if platform.system() == "Windows":\n'
    "        from boostgauge.collectors.windows import WindowsCollector\n"
    "        return WindowsCollector()\n"
    '    raise RuntimeError("unsupported platform")\n'
)
COLLECTOR_IMPORT_LINE = 9

UNPLANNED = COLLECTOR.replace("collectors.windows", "collectors.linux")


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


# =============================================================================
# The validator's rule
# =============================================================================


class TestTheValidator:
    def test_run_27s_import_of_the_planned_sibling_is_valid(self, seed_base):
        valid, bad = validate_imports(
            COLLECTOR, "src/boostgauge/collector.py", seed_base,
            planned_paths=PLANNED,
        )

        assert (valid, bad) == (True, [])

    def test_without_the_plan_the_disk_rule_is_unchanged(self, seed_base):
        """The refusal run 27 hit, reproduced: no plan, no sibling on disk."""
        valid, bad = validate_imports(
            COLLECTOR, "src/boostgauge/collector.py", seed_base,
        )

        assert valid is False
        assert bad == [f"boostgauge.collectors.windows (line {COLLECTOR_IMPORT_LINE})"]

    def test_an_unplanned_absent_module_is_still_refused_with_its_line(self, seed_base):
        """#842's case: neither on disk nor in the plan is a hallucination."""
        valid, bad = validate_imports(
            UNPLANNED, "src/boostgauge/collector.py", seed_base,
            planned_paths=PLANNED,
        )

        assert valid is False
        assert bad == [f"boostgauge.collectors.linux (line {COLLECTOR_IMPORT_LINE})"]

    def test_the_package_form_resolves_when_a_planned_file_sits_under_it(self, seed_base):
        """`from boostgauge.collectors import windows` names the directory;
        the planned windows.py makes it a namespace package."""
        code = "from boostgauge.collectors import windows\n\n\ndef go():\n    return windows\n"

        valid, bad = validate_imports(
            code, "src/boostgauge/collector.py", seed_base, planned_paths=PLANNED,
        )

        assert (valid, bad) == (True, [])

    def test_the_package_rule_does_not_leak_to_a_sibling_module(self, seed_base):
        """A planned windows.py under collectors/ must not vouch for
        collectors/linux.py: the directory rule binds the full module path,
        never its parent."""
        code = "from boostgauge.collectors.linux import LinuxCollector\n\n\ndef go():\n    return LinuxCollector\n"

        valid, bad = validate_imports(
            code, "src/boostgauge/collector.py", seed_base, planned_paths=PLANNED,
        )

        assert valid is False
        assert bad == ["boostgauge.collectors.linux (line 1)"]

    def test_a_planned_path_with_backslashes_still_matches(self, seed_base):
        """The plan is read from an LLD on Windows; separators vary."""
        valid, bad = validate_imports(
            COLLECTOR, "src/boostgauge/collector.py", seed_base,
            planned_paths=["src\\boostgauge\\collectors\\windows.py"],
        )

        assert (valid, bad) == (True, [])

    def test_a_flat_layout_plan_resolves_too(self, tmp_path):
        code = "from chiron.provenance import Citation\n\n\ndef go():\n    return Citation\n"

        valid, bad = validate_imports(
            code, "chiron/cli.py", tmp_path, planned_paths=["chiron/provenance.py"],
        )

        assert (valid, bad) == (True, [])


# =============================================================================
# validate_code_response carries the plan
# =============================================================================


class TestValidateCodeResponse:
    def test_the_plan_reaches_the_validator(self, seed_base):
        valid, error = validate_code_response(
            COLLECTOR, "src/boostgauge/collector.py",
            repo_root=str(seed_base), planned_paths=PLANNED,
        )

        assert (valid, error) == (True, "")

    def test_without_the_plan_the_message_is_run_27s(self, seed_base):
        valid, error = validate_code_response(
            COLLECTOR, "src/boostgauge/collector.py", repo_root=str(seed_base),
        )

        assert valid is False
        assert error == (
            f"Unresolvable imports: boostgauge.collectors.windows "
            f"(line {COLLECTOR_IMPORT_LINE})"
        )


# =============================================================================
# The generator and the stage hand it through
# =============================================================================


def _claude_returns(code: str):
    calls: list[str] = []

    def fake(prompt, file_path="", model="", system_prompt=""):
        calls.append(file_path)
        return f"```python\n{code}```", ""

    return fake, calls


class TestGenerateFileWithRetry:
    def test_the_planned_import_is_accepted_on_the_first_attempt(self, seed_base):
        fake, calls = _claude_returns(COLLECTOR)

        with patch.object(orchestrator, "call_claude_for_file", fake):
            code, success = orchestrator.generate_file_with_retry(
                "src/boostgauge/collector.py", "write it",
                repo_root=seed_base, planned_paths=PLANNED,
            )

        assert success is True
        assert "from boostgauge.collectors.windows import WindowsCollector" in code
        assert len(calls) == 1, "one generation, no retry on a planned import"

    def test_without_the_plan_the_retries_are_exhausted_as_on_run_27(self, seed_base):
        fake, calls = _claude_returns(COLLECTOR)

        with patch.object(orchestrator, "call_claude_for_file", fake), \
             pytest.raises(orchestrator.ImplementationError) as halted:
            orchestrator.generate_file_with_retry(
                "src/boostgauge/collector.py", "write it",
                repo_root=seed_base, max_retries=2,
            )

        assert "Unresolvable imports: boostgauge.collectors.windows" in str(halted.value)
        assert len(calls) == 2, "the deterministic refusal was paid for twice"


class TestImplementCode:
    def test_every_generation_receives_the_whole_plan(self, seed_base):
        received: list[list[str] | None] = []

        def fake_generate(filepath, **kwargs):
            received.append(kwargs.get("planned_paths"))
            return "# generated\n", True

        def no_batch(prompt, file_path="", model="", system_prompt=""):
            return "", "batch path is not under test"

        state = {
            "repo_root": str(seed_base),
            "lld_content": "## 2.1 Files\n",
            "files_to_modify": [dict(spec) for spec in RUN_27_PLAN],
            "test_files": ["tests/unit/test_collector.py"],
            "iteration_count": 0,
            "audit_dir": str(seed_base / "audit"),
        }
        with patch.object(orchestrator, "generate_file_with_retry", fake_generate), \
             patch.object(orchestrator, "call_claude_for_file", no_batch), \
             patch.object(orchestrator, "record_iteration_cost", return_value=0), \
             patch.object(orchestrator, "get_cumulative_cost", return_value=0.0):
            try:
                orchestrator.implement_code(state)
            except Exception:
                pass

        assert received, "the stage must reach generation"
        assert all(plan == PLANNED for plan in received), received
