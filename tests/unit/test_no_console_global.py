"""Console suppression is a process-wide default, not a per-call-site habit (#2040).

#2037 added CREATE_NO_WINDOW to the two spawn sites that were known about. The
pipeline has 27 -- git, gh, poetry, pytest, claude -- and a poetry.exe window
appeared on the operator's desktop minutes after that fix merged.

A default that must be remembered at every call site is a defect generator, and
this particular defect is invisible in logs: only a human watching the screen
sees a window appear. That is how it shipped twice.
"""

import subprocess
import sys
from unittest.mock import patch

import pytest

from assemblyzero.core import no_console

WIN32_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="creation flags are a Windows concern"
)


@pytest.fixture
def fresh():
    """Restore the real constructor, since install() mutates a global."""
    original = subprocess.Popen.__init__
    was = no_console._installed
    no_console._installed = False
    yield
    subprocess.Popen.__init__ = original
    no_console._installed = was


class TestTheDefaultApplies:
    @WIN32_ONLY
    def test_a_plain_spawn_gets_no_window(self, fresh):
        seen = {}

        def _capture(self, *args, **kwargs):
            seen.update(kwargs)
            raise RuntimeError("stop before spawning")

        # Install over a recording constructor so the merged flags are visible.
        subprocess.Popen.__init__ = _capture
        no_console.install()
        with pytest.raises(RuntimeError):
            subprocess.Popen(["git", "status"])

        assert seen.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW

    @WIN32_ONLY
    def test_existing_flags_are_preserved(self, fresh):
        """#526 needs CREATE_NEW_PROCESS_GROUP to tree-kill on timeout."""
        seen = {}

        def _capture(self, *args, **kwargs):
            seen.update(kwargs)
            raise RuntimeError("stop")

        subprocess.Popen.__init__ = _capture
        no_console.install()
        with pytest.raises(RuntimeError):
            subprocess.Popen(
                ["git", "status"],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

        flags = seen.get("creationflags", 0)
        assert flags & subprocess.CREATE_NO_WINDOW
        assert flags & subprocess.CREATE_NEW_PROCESS_GROUP


class TestDeliberateConsolesAreLeftAlone:
    @WIN32_ONLY
    def test_an_explicit_new_console_is_not_overridden(self, fresh):
        """Asking for a console is a decision; silently removing it would be a
        different bug from the one being fixed."""
        seen = {}

        def _capture(self, *args, **kwargs):
            seen.update(kwargs)
            raise RuntimeError("stop")

        subprocess.Popen.__init__ = _capture
        no_console.install()
        with pytest.raises(RuntimeError):
            subprocess.Popen(["cmd"], creationflags=subprocess.CREATE_NEW_CONSOLE)

        assert not seen.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW

    @WIN32_ONLY
    def test_a_detached_process_is_not_overridden(self, fresh):
        seen = {}

        def _capture(self, *args, **kwargs):
            seen.update(kwargs)
            raise RuntimeError("stop")

        subprocess.Popen.__init__ = _capture
        no_console.install()
        with pytest.raises(RuntimeError):
            subprocess.Popen(["cmd"], creationflags=0x00000008)

        assert not seen.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW


class TestInstallIsSafe:
    def test_installing_twice_does_not_stack(self, fresh):
        no_console.install()
        first = subprocess.Popen.__init__
        no_console.install()
        assert subprocess.Popen.__init__ is first

    def test_it_reports_whether_it_is_installed(self, fresh):
        assert no_console.is_installed() is False
        no_console.install()
        assert no_console.is_installed() is (sys.platform == "win32")

    def test_off_windows_it_is_a_no_op(self, fresh):
        original = subprocess.Popen.__init__
        with patch.object(no_console.sys, "platform", "linux"):
            no_console.install()
        assert subprocess.Popen.__init__ is original


class TestTheEntryPointsInstallIt:
    def test_orchestrate_installs_before_importing_the_graph(self):
        """Order matters: anything imported first could spawn during import."""
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2] / "tools" / "orchestrate.py"
        ).read_text(encoding="utf-8")

        install_at = source.index("_install_no_console()")
        graph_at = source.index("from assemblyzero.workflows.orchestrator.graph")
        assert install_at < graph_at, (
            "the suppression must be in force before the pipeline is imported"
        )

    def test_speedrun_roll_installs_it(self):
        from pathlib import Path

        source = (
            Path(__file__).resolve().parents[2] / "tools" / "speedrun_roll.py"
        ).read_text(encoding="utf-8")
        assert "_install_no_console()" in source
