"""A speedrun test's verdict must not depend on the machine running it.

Closes #2248. `speedrun_roll.main()` runs the real #1920 box-health preflight:
it reads live memory through psutil and refuses above 90%, then spends a whole
pytest subprocess on the canary. Tests that call `main()` therefore measured the
host, not the code.

Measured 2026-08-12 on c83f9aff with no source changes: `pytest tests/unit -k
speedrun` passed alone, twice; two copies run concurrently failed 16 and 17
tests. The failing set differed every time, because the second pytest process
was itself the load that pushed the box over the ceiling.

The gate is correct and stays correct for real rolls. What was missing is the
tests' isolation, so `tests/unit/conftest.py` stubs the gate for every test that
imports the launcher. These are the guards on that arrangement -- without them
the fixture could stop engaging and nothing would say so until the next loaded
afternoon.
"""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

UNIT_DIR = Path(__file__).resolve().parent

# The reads that make a verdict a statement about the host.
HOST_READS = ("virtual_memory", "process_iter", "cpu_percent", "psutil")

# This file names every needle above -- in HOST_READS itself and in the
# injection tests, which build a fake psutil on purpose. It is the audit, so it
# is the one file exempt from it.
SELF = Path(__file__).name


def _audited_files() -> list[Path]:
    return sorted(p for p in UNIT_DIR.glob("test_speedrun*.py") if p.name != SELF)


class TestTheFixtureActuallyEngages:
    """A stub that quietly stopped applying would look exactly like a pass."""

    def test_the_launcher_gate_is_not_the_real_one(self):
        assert sr.check_box_health.__module__ != "assemblyzero.speedrun.box_health", (
            "speedrun_roll.check_box_health is the real preflight during a unit "
            "test, so this test's verdict depends on how much memory the "
            "machine happens to be using -- the #2248 defect exactly."
        )

    def test_the_stub_reports_a_healthy_box(self, tmp_path):
        health = sr.check_box_health(tmp_path, tmp_path)
        assert health.ok
        assert health.message == ""

    def test_the_real_gate_is_still_reachable_where_it_is_tested(self):
        """The fixture must rebind only the launcher's name. test_box_health.py
        imports the gate directly and has to get the real one."""
        from assemblyzero.speedrun import box_health

        assert box_health.check_box_health.__module__ == (
            "assemblyzero.speedrun.box_health"
        ), "the fixture leaked past speedrun_roll and blinded box_health's own tests"


class TestNoSpeedrunTestReadsTheHost:
    """The audit, mechanically. A new test file that reaches for psutil fails
    here rather than on the next loaded afternoon."""

    @pytest.mark.parametrize("path", _audited_files(), ids=lambda p: p.name)
    def test_no_direct_host_measurement(self, path):
        source = path.read_text(encoding="utf-8")
        found = [needle for needle in HOST_READS if needle in source]

        assert not found, (
            f"{path.name} names {found}, so it measures the machine running it. "
            "Drive box_health with injected metrics instead -- check_box_health "
            "takes canary= and resources=, and snapshot_resources takes reader=."
        )

    def test_the_audit_covers_every_speedrun_file(self):
        """Pins that the glob finds the files it claims to; a typo'd pattern
        would make the parametrised test above vacuously green."""
        names = {p.name for p in _audited_files()}
        assert len(names) >= 7, f"expected the speedrun test files, found {names}"
        assert "test_speedrun_roll_attempts.py" in names, (
            "the file whose failure opened #2248 is not being audited"
        )
        assert SELF not in names, "the audit must not audit itself"


class TestTheGateItselfIsStillInjectable:
    """#2248 asks that a future caller be able to do this without a global patch."""

    def test_resources_reader_can_be_supplied(self):
        from assemblyzero.speedrun.box_health import snapshot_resources

        class _FakePsutil:
            @staticmethod
            def virtual_memory():
                return type("_M", (), {"percent": 42.0})()

            @staticmethod
            def process_iter(_fields):
                return [type("_P", (), {"info": {"name": "conhost.exe"}})()]

        values, unreadable = snapshot_resources(reader=lambda: _FakePsutil())

        assert unreadable == []
        assert values["memory in use"] == 42.0
        assert values["console windows"] == 1.0

    def test_absent_psutil_needs_no_builtins_patch(self):
        from assemblyzero.speedrun.box_health import snapshot_resources

        def _no_psutil():
            raise ImportError("no psutil")

        values, unreadable = snapshot_resources(reader=_no_psutil)

        assert values == {}
        assert "memory in use" in unreadable
