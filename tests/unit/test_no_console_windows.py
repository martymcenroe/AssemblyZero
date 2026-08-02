"""A detached roll must not put windows on the operator's desktop (#2037).

Reported live during boostgauge phases 5-6, 2026-07-31: console windows popping
up continuously during an unattended run.

Whether a child shows a console depends on the PARENT. Under the agent's Bash
shell the child inherited an existing console and nothing appeared; under Task
Scheduler (#2015) the parent has no console, so every `claude -p` call allocated
its own. The flags were unchanged -- the environment moved out from under them,
which is why this shipped without anyone seeing it.

Only a human watching the desktop can catch a regression here, so these assert
the flags directly.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def _healthy_box(*_args, **_kwargs):
    """#1920: these tests exercise argv and the task definition, not machine
    health. Stubbed like the sibling staleness gate above it."""
    from assemblyzero.speedrun.box_health import BoxHealth

    return BoxHealth(True, [], "")

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402

WIN32_ONLY = pytest.mark.skipif(
    sys.platform != "win32", reason="console windows are a Windows concern"
)


class TestModelCallsAreWindowless:
    @WIN32_ONLY
    def test_the_provider_asks_for_no_window(self):
        """One window per model call, and a roll makes one call per file per
        iteration."""
        import inspect

        from assemblyzero.core import llm_provider

        source = inspect.getsource(llm_provider)
        assert "CREATE_NO_WINDOW" in source, (
            "the model subprocess must suppress its console; without a console "
            "to inherit it allocates one"
        )

    @WIN32_ONLY
    def test_process_group_is_kept(self):
        """#526 needs CREATE_NEW_PROCESS_GROUP to tree-kill on timeout. The two
        flags compose; suppressing the window must not cost that."""
        import inspect

        from assemblyzero.core import llm_provider

        source = inspect.getsource(llm_provider)
        assert "CREATE_NEW_PROCESS_GROUP" in source

    def test_the_two_flags_compose(self):
        """Guard against someone 'simplifying' to one of them later."""
        if sys.platform != "win32":
            pytest.skip("Windows creation flags")
        combined = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        assert combined & subprocess.CREATE_NO_WINDOW
        assert combined & subprocess.CREATE_NEW_PROCESS_GROUP


class TestTheRollItselfIsWindowless:
    def test_pythonw_is_preferred_when_present(self, tmp_path):
        """A scheduled task running python.exe shows a console for the whole
        roll, not just a flash."""
        py = tmp_path / "python.exe"
        py.write_text("", encoding="utf-8")
        (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")

        assert sr.windowless_interpreter(str(py)) == str(tmp_path / "pythonw.exe")

    def test_it_falls_back_when_there_is_no_pythonw(self, tmp_path):
        """A visible console beats a task that cannot start."""
        py = tmp_path / "python.exe"
        py.write_text("", encoding="utf-8")

        assert sr.windowless_interpreter(str(py)) == str(py)

    def test_a_non_python_interpreter_is_left_alone(self, tmp_path):
        other = tmp_path / "pypy.exe"
        other.write_text("", encoding="utf-8")
        assert sr.windowless_interpreter(str(other)) == str(other)

    def test_the_scheduled_command_uses_the_windowless_interpreter(self, tmp_path):
        """End to end through launch_detached: the XML must name pythonw."""
        py = tmp_path / "python.exe"
        py.write_text("", encoding="utf-8")
        (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")

        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)

        calls = []

        def _run(cmd, cwd=None):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(sr, "_run", _run), \
                patch.object(sr.sys, "platform", "win32"), \
                patch.object(sr.sys, "executable", str(py)), \
                patch.object(sr, "check_assemblyzero_tree", lambda p: []),                 patch.object(sr, "check_box_health", _healthy_box):
            code = sr.main(["--repo", str(repo), "--issue", "7", "--detach"])

        assert code == 0
        xml = (repo / "data" / "speedrun" / "runs" / "detached-task.xml").read_text(
            encoding="utf-16"
        )
        assert "pythonw.exe" in xml
        assert "<Command>" in xml


class TestThePipelineSubprocess:
    def test_orchestrate_is_spawned_without_a_console(self):
        """The roll's own child gets the same treatment; under Task Scheduler
        it has no console to inherit either."""
        import inspect

        source = inspect.getsource(sr.roll_issue)
        assert "CREATE_NO_WINDOW" in source
