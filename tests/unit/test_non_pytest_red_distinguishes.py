"""The non-pytest red phase tells the three cases apart (#2805).

The pytest red phase learned to distinguish three situations when tests pass
before any code exists (#2337, #2542, #2670):

* a red-entry marker, or files this run's own earlier attempt wrote, explain
  them -- resume at the green phase;
* the plan says every file is `Modify` and the base ships them -- the passes
  are base-satisfied regression guards, continue to implementation;
* nothing explains them -- the implementation predates the stage, which is
  deterministic on an unchanged worktree, so halt and say so.

`_verify_red_non_pytest` had none of it. #2796 gave it the token and filed
the port, on the reasoning that the two deciding helpers select planned files
with `endswith(".py")` and this path's are `.ts`/`.tsx`/`.js`/`.jsx`, so both
select nothing and can never return True.

**What was missing was a fact, not effort.** Which extensions a framework's
IMPLEMENTATION uses existed nowhere: `framework_detector` carried
`test_file_extension`, the extension of the TEST file, which says nothing
about whether the implementation is `.ts`, `.tsx` or `.js`.
`SOURCE_EXTENSIONS` is that fact, enumerated per `TestFramework` member and
held closed by `test_every_framework_declares_its_source_extensions` — add a
framework without saying what its implementation looks like and the suite
fails rather than that path quietly becoming undecidable again.

**No recorded run exercises this path** — boostgauge is a pytest project —
so every assertion here is a mock roll with a scripted runner, and the
pytest path's behaviour is asserted UNCHANGED, because it is the one with
all the evidence behind it.
"""

from __future__ import annotations

from unittest.mock import patch

from assemblyzero.workflows.testing.framework_detector import (
    SOURCE_EXTENSIONS,
    TestFramework,
    source_extensions,
)
from assemblyzero.workflows.testing.nodes.validate_tests_mechanical import (
    DETERMINISTIC_FAILURE,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _base_ships_the_implementation,
    _implementation_already_exists,
    _verify_red_non_pytest,
)

PLAN_TS = [{"path": "src/widget.ts", "change_type": "Modify"}]


class _Runner:
    def __init__(self, passed: int, failed: int = 0, errors: int = 0) -> None:
        self._r = {
            "raw_output": f"{passed} passed, {failed} failed",
            "passed": passed, "failed": failed, "errors": errors,
            "exit_code": 0 if passed and not failed else 1,
        }

    def run_tests(self, test_paths):
        return dict(self._r)


def _state(tmp_path, **over) -> dict:
    base = {
        "test_files": [str(tmp_path / "widget.spec.ts")],
        "repo_root": str(tmp_path),
        "audit_dir": "",
        "file_counter": 0,
        "issue_number": 4242,
        "files_to_modify": [dict(f) for f in PLAN_TS],
    }
    base.update(over)
    return base


def _roll(tmp_path, runner, state=None, framework=TestFramework.PLAYWRIGHT):
    with patch(
        "assemblyzero.workflows.testing.nodes.verify_phases.get_runner",
        return_value=runner,
    ), patch(
        "assemblyzero.workflows.testing.nodes.verify_phases"
        ".log_workflow_execution",
        lambda **kw: None,
    ):
        return _verify_red_non_pytest(state or _state(tmp_path), {}, framework)


class TestTheTableIsClosed:
    def test_every_framework_declares_its_source_extensions(self):
        """The guard on the fact itself. A new framework with no entry makes
        this path undecidable again, silently, which is how it got here."""
        missing = [f.value for f in TestFramework if f not in SOURCE_EXTENSIONS]
        assert not missing, missing

    def test_pytest_is_py_and_the_js_frameworks_are_not(self):
        assert source_extensions(TestFramework.PYTEST) == (".py",)
        for fw in (TestFramework.PLAYWRIGHT, TestFramework.JEST,
                   TestFramework.VITEST):
            assert ".ts" in source_extensions(fw)
            assert ".py" not in source_extensions(fw)

    def test_an_unknown_framework_falls_back_to_the_old_behaviour(self):
        assert source_extensions(None) == (".py",)


class TestTheHelpersNoLongerSelectNothing:
    """The defect #2796 measured: on a .ts plan both returned False by
    construction, whatever the worktree held."""

    def test_prior_writes_are_invisible_under_the_py_filter(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "widget.ts").write_text("x", encoding="utf-8")
        state = _state(tmp_path, retry_mode=True)
        assert _implementation_already_exists(state) is False
        assert _implementation_already_exists(
            state, source_extensions(TestFramework.PLAYWRIGHT)
        ) is True

    def test_a_modify_base_is_invisible_under_the_py_filter(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "widget.ts").write_text("x", encoding="utf-8")
        state = _state(tmp_path)
        assert _base_ships_the_implementation(state) is False
        assert _base_ships_the_implementation(
            state, source_extensions(TestFramework.PLAYWRIGHT)
        ) is True

    def test_the_pytest_default_is_unchanged(self, tmp_path):
        """The path with the evidence behind it must not move."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "widget.py").write_text("x", encoding="utf-8")
        state = _state(
            tmp_path, retry_mode=True,
            files_to_modify=[{"path": "src/widget.py", "change_type": "Modify"}],
        )
        assert _implementation_already_exists(state) is True
        assert _base_ships_the_implementation(state) is True


class TestTheThreeReadings:
    def test_this_runs_own_writes_resume_the_loop(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "widget.ts").write_text("x", encoding="utf-8")
        result = _roll(
            tmp_path, _Runner(passed=3, failed=1),
            _state(tmp_path, retry_mode=True),
        )
        assert result["error_message"] == ""
        assert result["next_node"] == "N5_verify_green"

    def test_a_modify_base_continues_to_implementation(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "widget.ts").write_text("x", encoding="utf-8")
        result = _roll(tmp_path, _Runner(passed=3, failed=2))
        assert result["error_message"] == ""
        assert result["next_node"] == "N4_implement_code"

    def test_nothing_explaining_them_still_halts_and_says_so(self, tmp_path):
        """Unexplained passes remain fatal, and the message no longer hedges:
        this path now really does perform the check it describes."""
        result = _roll(
            tmp_path, _Runner(passed=3, failed=1),
            _state(tmp_path, files_to_modify=[
                {"path": "src/widget.ts", "change_type": "Add"},
            ]),
        )
        assert result["error_message"].startswith(DETERMINISTIC_FAILURE)
        assert "neither a red-entry marker" in result["error_message"]
        assert result["next_node"] == "END"

    def test_a_properly_red_run_is_untouched(self, tmp_path):
        result = _roll(tmp_path, _Runner(passed=0, failed=4))
        assert result.get("error_message", "") == ""


class TestTheHaltStillBelongsToItsRow:
    def test_the_registered_site_still_halts_with_the_token(self, tmp_path):
        """#2796 filed this site under `impl.red.preexisting_implementation`.
        The port must not move it or drop the token, or the row's `emits` and
        the ratchet both go stale."""
        from assemblyzero.core.gate_registry import registry_by_key

        row = registry_by_key()["impl.red.preexisting_implementation"]
        assert any("_verify_red_non_pytest" in s for s in row.sites), row.sites
        result = _roll(
            tmp_path, _Runner(passed=1, failed=1),
            _state(tmp_path, files_to_modify=[
                {"path": "src/widget.ts", "change_type": "Add"},
            ]),
        )
        assert DETERMINISTIC_FAILURE in result["error_message"]
