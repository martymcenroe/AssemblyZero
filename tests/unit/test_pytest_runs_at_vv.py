"""The runner's pytest carries -vv, so an assertion's compared values reach
the implementer whole (#2924).

boostgauge #4, `run-issue4-145211` (2026-09-06 14:52). The circular import
fixed, the full suite running, one regression left -- the repo's
`test_config.py` comparing `Thresholds()` to the config's defaults:

    E   AssertionError: assert Thresholds(co...0, red=50000)) == Thresholds(co...0, red=20000))
    E     Differing attributes:
    E     ['conpty', 'memory_percent', 'process_count', 'handle_count']

The four expected bands live in `config.py`, outside the plan; the one place
they reach the implementer is that left-hand repr, and pytest truncates it
at verbosity 1. The implementer guessed, the same test failed again, and
the stagnation gate began counting.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.verify_phases import run_pytest


class TestTheRunnersArgv:
    def test_the_targeted_run_is_vv(self, tmp_path: Path):
        seen: list[list[str]] = []

        def fake_run_command(cmd, **kwargs):
            seen.append(list(cmd))
            return SimpleNamespace(returncode=0, stdout="1 passed", stderr="")

        with patch.object(verify_phases, "run_command", side_effect=fake_run_command):
            run_pytest(["tests/unit/test_x.py"], repo_root=tmp_path)

        assert seen[0][:5] == ["poetry", "run", "pytest", "-vv", "--tb=short"]
        assert "-v" not in seen[0]

    def test_the_full_suite_run_is_vv(self, tmp_path: Path):
        seen: list[list[str]] = []

        def fake_run_command(cmd, **kwargs):
            seen.append(list(cmd))
            return SimpleNamespace(returncode=0, stdout="119 passed", stderr="")

        with patch.object(verify_phases, "run_command", side_effect=fake_run_command):
            run_pytest([], repo_root=tmp_path)

        assert seen[0][:5] == ["poetry", "run", "pytest", "-vv", "--tb=short"]


class TestWhatVvBuys:
    """pytest itself: the comparison run 44 needed, at -v and at -vv."""

    CASE = '''\
from dataclasses import dataclass


@dataclass(frozen=True)
class Band:
    yellow: float
    red: float


@dataclass(frozen=True)
class Thresholds:
    conpty: Band = Band(30, 60)
    memory_percent: Band = Band(60, 80)
    process_count: Band = Band(300, 500)
    handle_count: Band = Band(30000, 20000)


def test_thresholds_from_config_matches_the_collector_defaults():
    expected = Thresholds(Band(30, 60), Band(60, 80), Band(300, 500), Band(30000, 50000))
    assert expected == Thresholds()
'''

    def _run(self, tmp_path: Path, verbosity: str) -> str:
        test_file = tmp_path / "test_run_44.py"
        test_file.write_text(self.CASE, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), verbosity, "--tb=short",
             "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=120,
        )
        return result.stdout + result.stderr

    def test_at_v_the_values_are_elided(self, tmp_path: Path):
        output = self._run(tmp_path, "-v")

        assert "Thresholds(co..." in output

    def test_at_vv_run_44s_bands_are_all_there(self, tmp_path: Path):
        output = self._run(tmp_path, "-vv")

        assert "Thresholds(co..." not in output
        assert "handle_count=Band(yellow=30000, red=50000)" in output
        assert "handle_count=Band(yellow=30000, red=20000)" in output
