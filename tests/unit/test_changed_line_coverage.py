"""The green phase judges the lines the run changed, never whole files (#4436).

Measured on 2026-10-31 in a fresh worktree of a target with pytest at its root
and Vitest in `web/`: a 562-statement Python module read 25% under its
dedicated tests and 65% under the target's whole suite, and every file the
whole Vitest suite loads read 54.28%. A run that changes either module, and
covers every line it wrote, could never reach 95, so it was sent back to the
cap and N4c was asked to test code the run never touched.

The pytest tests here run real pytest and real pytest-cov against a real git
repository under tmp_path; `poetry run` is the one thing they replace, because
the throwaway target has no virtualenv. The Vitest tests use real git and a
stand-in for `npx` that writes the two reports a coverage run writes, in the
shape of a real `coverage-final.json` (`test_changed_lines.py` reads one).

T1 to T7 are the issue's tests. T1, T2, T3 and T5 use only what `main` has, so
they fail there for the reason the issue gives.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.graph import route_after_green
from assemblyzero.workflows.testing.nodes import verify_phases
from assemblyzero.workflows.testing.nodes.verify_phases import verify_green_phase
from assemblyzero.workflows.testing.runners import base_runner, jest_runner

PYTEST = {"framework": "pytest", "coverage_type": "line", "working_directory": None}
VITEST_WEB = {"framework": "vitest", "coverage_type": "line", "working_directory": "web"}

#: A module far larger than anything a run's tests reach.
LARGE_MODULE = "".join(
    f"def untouched_{n}(value):\n    return value + {n}\n\n\n" for n in range(300)
)

#: Ten executable lines, all of them reached by TEST_THE_TEN.
ADDED_TEN = """\
def added(value):
    a = value + 1
    b = a + 1
    c = b + 1
    d = c + 1
    e = d + 1
    f = e + 1
    g = f + 1
    h = g + 1
    return h
"""

TEST_THE_TEN = """\
from pkg.engine import added


def test_added():
    assert added(0) == 8
"""

#: Ten executable lines, of which the `if` body's two are never reached.
ADDED_TWO_MISSED = """\
def added(value):
    a = value + 1
    b = a + 1
    c = b + 1
    d = c + 1
    e = d + 1
    if e < 0:
        g = 0
        return g
    return e
"""

TEST_EIGHT_OF_TEN = """\
from pkg.engine import added


def test_added():
    assert added(0) == 5
"""


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(root), check=True, capture_output=True, text=True,
    ).stdout


def _lay_down(root: Path) -> None:
    (root / ".gitignore").write_text(
        ".coverage\n.assemblyzero/\nnode_modules/\ncoverage/\n__pycache__/\n", encoding="utf-8",
    )
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "engine.py").write_text(LARGE_MODULE, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "test_engine.py").write_text(
        "def test_placeholder():\n    assert True\n", encoding="utf-8",
    )


def _web(root: Path) -> None:
    web = root / "web"
    (web / "src").mkdir(parents=True)
    (web / "tests").mkdir()
    (web / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}}), encoding="utf-8",
    )
    (web / "node_modules" / ".bin").mkdir(parents=True)
    (web / "node_modules" / ".bin" / "vitest").write_text("", encoding="utf-8")
    (web / "node_modules" / "@vitest" / "coverage-v8").mkdir(parents=True)
    (web / "src" / "engine.ts").write_text(
        "".join(f"export const untouched{n} = {n};\n" for n in range(200)), encoding="utf-8",
    )
    (web / "tests" / "engine.test.ts").write_text("// a test\n", encoding="utf-8")


def _init(root: Path) -> None:
    """The base commit on `main`, and the run's branch off it."""
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "base")
    _git(root, "switch", "-c", "issue-7")


@pytest.fixture
def target(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    _lay_down(root)
    _init(root)
    return root


@pytest.fixture
def mixed_target(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    root.mkdir()
    _lay_down(root)
    _web(root)
    _init(root)
    return root


@pytest.fixture
def real_pytest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """`poetry run pytest` as this interpreter's pytest, on the target."""
    real = verify_phases.run_command

    def run(command, **kwargs):
        if list(command[:3]) == ["poetry", "run", "pytest"]:
            command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *command[3:]]
        return real(command, **kwargs)

    monkeypatch.setattr(verify_phases, "run_command", run)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "target"))


def _state(root: Path, **overrides) -> dict:
    state = {
        "issue_number": 7,
        "repo_root": str(root),
        "base_branch": "main",
        "test_files": [str(root / "tests" / "test_engine.py")],
        "implementation_files": [str(root / "pkg" / "engine.py")],
        "coverage_target": 95,
        "audit_dir": "",
        "file_counter": 0,
        "iteration_count": 0,
        "max_iterations": 5,
        "skip_e2e": True,
        "previous_coverage": -1.0,
        "previous_passed": -1,
        "framework_config": PYTEST,
        "framework_configs": [PYTEST],
    }
    state.update(overrides)
    return state


def _append(path: Path, text: str) -> int:
    """Append `text` to `path`; the number of its first new line."""
    before = path.read_text(encoding="utf-8")
    path.write_text(before + text, encoding="utf-8")
    return before.count("\n") + 1


@pytest.fixture
def logged(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    """Each workflow log event N5 writes, as (event, details)."""
    events: list[tuple[str, dict]] = []

    def record(**kwargs):
        events.append((kwargs["event"], kwargs.get("details") or {}))

    monkeypatch.setattr(verify_phases, "log_workflow_execution", record)
    return events


class _Vitest:
    """Stands in for `npx`. A coverage run writes the summary and the
    per-line report a real one writes, from `hits` (line -> count) for one
    file; the summary's percentage is the whole-file figure the issue
    measured, so it is far under any target."""

    def __init__(self, root: Path, source: str, hits: dict[int, int], *,
                 summary: bool = True, lines: bool = True, passed: int = 3,
                 failed: int = 0) -> None:
        self.root, self.source, self.hits = root, source, hits
        self.summary, self.lines, self.passed, self.failed = summary, lines, passed, failed
        self.calls: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.calls.append(list(command))
        cwd = Path(kwargs["cwd"])
        if "--coverage.enabled=true" in command:
            (cwd / "coverage").mkdir(exist_ok=True)
            if self.summary:
                (cwd / "coverage" / "coverage-summary.json").write_text(json.dumps({
                    "total": {"lines": {"total": 210, "covered": 114, "skipped": 0, "pct": 54.28}},
                }), encoding="utf-8")
            if self.lines:
                ordered = sorted(self.hits)
                (cwd / "coverage" / "coverage-final.json").write_text(json.dumps({
                    str(self.root / self.source): {
                        "path": str(self.root / self.source),
                        "statementMap": {
                            str(index): {
                                "start": {"line": line, "column": 0},
                                "end": {"line": line, "column": 9},
                            } for index, line in enumerate(ordered)
                        },
                        "s": {str(index): self.hits[line] for index, line in enumerate(ordered)},
                        "fnMap": {}, "f": {}, "branchMap": {}, "b": {},
                    },
                }), encoding="utf-8")
        report = {"numPassedTests": self.passed, "numFailedTests": self.failed,
                  "numPendingTests": 0, "numTotalTests": self.passed + self.failed}
        return subprocess.CompletedProcess(
            args=command, returncode=1 if self.failed else 0,
            stdout=json.dumps(report), stderr="",
        )


def _vitest_state(root: Path, **overrides) -> dict:
    return _state(
        root,
        test_files=[str(root / "web" / "tests" / "engine.test.ts")],
        implementation_files=[str(root / "web" / "src" / "engine.ts")],
        framework_config=VITEST_WEB,
        framework_configs=[VITEST_WEB],
        **overrides,
    )


def _green_with(npx: _Vitest, state: dict) -> dict:
    with patch.object(base_runner, "run_command", side_effect=npx), \
         patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        return verify_green_phase(state)


# ---------------------------------------------------------------------------
# T1 and T2 (R1, R4): pytest
# ---------------------------------------------------------------------------


def test_t1_ten_covered_lines_in_a_large_module_pass_at_95(target, real_pytest):
    """Fails on `main`: the gate reads the whole module, far under 95."""
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    (target / "tests" / "test_engine.py").write_text(TEST_THE_TEN, encoding="utf-8")

    result = verify_green_phase(_state(target))

    assert result["error_message"] == ""
    assert result["next_node"] == "N7_finalize"
    assert result["coverage_achieved"] == 100.0
    assert verify_phases.parse_pytest_output(result["green_phase_output"])["coverage"] < 60, (
        "the whole-file figure is still far under the target it no longer has to meet"
    )


def test_t2_two_of_the_ten_uncovered_are_refused_and_named(target, real_pytest):
    """Fails on `main`: the shortfall names no changed line."""
    first = _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TWO_MISSED) + 2
    (target / "tests" / "test_engine.py").write_text(TEST_EIGHT_OF_TEN, encoding="utf-8")

    result = verify_green_phase(_state(target))

    missed = [first + 7, first + 8]
    assert result["next_node"] == "N4c_augment_tests"
    assert result["coverage_achieved"] == 80.0
    assert result["uncovered_changed_lines"] == {"pkg/engine.py": missed}
    assert f"pkg/engine.py: {missed[0]}-{missed[1]}" in result["test_failure_summary"]


def test_r4_n4c_is_asked_for_those_two_lines_and_no_others(target, real_pytest):
    """Every other uncovered line of the 300-function module is out of scope."""
    from assemblyzero.workflows.testing.nodes import augment_tests

    first = _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TWO_MISSED) + 2
    (target / "tests" / "test_engine.py").write_text(TEST_EIGHT_OF_TEN, encoding="utf-8")
    result = verify_green_phase(_state(target))
    audit = target / "audit"
    audit.mkdir()
    prompts: list[str] = []

    def fake_call(prompt, **kwargs):
        prompts.append(prompt)
        return "no code here", ""

    with patch.object(augment_tests, "call_claude_for_file", side_effect=fake_call):
        augment_tests.augment_tests_for_coverage(
            {**_state(target), **result, "audit_dir": str(audit)}
        )

    assert prompts, "the node reached its model call"
    marked = [line for line in prompts[0].splitlines() if line.startswith(">>")]
    assert [line.split()[1] for line in marked] == [f"{first + 7}:", f"{first + 8}:"]
    assert "untouched_0" not in prompts[0]
    assert "Test ONLY the lines marked as uncovered" in prompts[0]


# ---------------------------------------------------------------------------
# T3 (R1, R4): Vitest
# ---------------------------------------------------------------------------


def test_t3_ten_covered_lines_on_a_vitest_module_pass_at_95(mixed_target):
    """Fails on `main`: `total.lines.pct` is every file the tests load."""
    first = _append(
        mixed_target / "web" / "src" / "engine.ts",
        "".join(f"export const added{n} = {n};\n" for n in range(10)),
    )
    hits = {line: 0 for line in range(1, first)} | {first + n: 2 for n in range(10)}
    npx = _Vitest(mixed_target, "web/src/engine.ts", hits)

    result = _green_with(npx, _vitest_state(mixed_target))

    assert result["error_message"] == ""
    assert result["next_node"] == "N7_finalize"
    assert result["coverage_achieved"] == 100.0


def test_t3_two_of_ten_uncovered_on_a_vitest_module_are_refused_and_named(mixed_target):
    """Fails on `main`: 54.28% routes to N4c, and nothing names a line."""
    from assemblyzero.workflows.testing.nodes.augment_tests import (
        augment_tests_for_coverage,
    )

    first = _append(
        mixed_target / "web" / "src" / "engine.ts",
        "".join(f"export const added{n} = {n};\n" for n in range(10)),
    )
    hits = {line: 0 for line in range(1, first)} | {first + n: 2 for n in range(8)}
    hits |= {first + 8: 0, first + 9: 0}
    state = _vitest_state(mixed_target)

    result = _green_with(_Vitest(mixed_target, "web/src/engine.ts", hits), state)

    assert result["next_node"] == "N4c_augment_tests"
    assert result["coverage_achieved"] == 80.0
    assert result["coverage_gap_framework"] == "vitest"
    assert result["uncovered_changed_lines"] == {"web/src/engine.ts": [first + 8, first + 9]}
    halted = augment_tests_for_coverage({**state, **result})
    assert f"web/src/engine.ts: {first + 8}-{first + 9}" in halted["error_message"]


def test_the_reports_leave_nothing_for_a_checkpoint_to_commit(mixed_target):
    """The target that measured #4436 does not ignore `web/coverage/`, so a
    report left there is staged by a checkpoint's `git add -A` and lands in
    the run's PR."""
    first = _append(mixed_target / "web" / "src" / "engine.ts", "export const a = 1;\n")
    (mixed_target / ".gitignore").write_text("node_modules/\n__pycache__/\n", encoding="utf-8")

    _green_with(
        _Vitest(mixed_target, "web/src/engine.ts", {first: 1}), _vitest_state(mixed_target),
    )

    assert "coverage" not in _git(mixed_target, "status", "--porcelain", "-uall")


def test_reports_a_failing_run_wrote_leave_too(mixed_target):
    """Jest writes its reports whether or not tests fail, and nothing reads
    them then."""
    npx = _Vitest(mixed_target, "web/src/engine.ts", {1: 0}, failed=1)

    result = _green_with(npx, _vitest_state(mixed_target))

    assert result["next_node"] == "N4_implement_code"
    assert not (mixed_target / "web" / "coverage" / "coverage-final.json").exists()
    assert not (mixed_target / "web" / "coverage" / "coverage-summary.json").exists()


def test_t3_vitest_is_told_to_report_the_changed_file_even_if_no_test_loads_it(mixed_target):
    source = mixed_target / "web" / "src" / "lonely.ts"
    source.write_text("export const lonely = 1;\n", encoding="utf-8")
    npx = _Vitest(mixed_target, "web/src/lonely.ts", {1: 0})

    result = _green_with(npx, _vitest_state(mixed_target))

    assert "--coverage.include=src/lonely.ts" in npx.calls[0], "relative to the project"
    assert result["uncovered_changed_lines"] == {"web/src/lonely.ts": [1]}, "a measured zero"


# ---------------------------------------------------------------------------
# T4 (R1): a new file counts whole
# ---------------------------------------------------------------------------


def test_t4_a_new_file_is_judged_whole(target, real_pytest):
    (target / "pkg" / "fresh.py").write_text(
        "def one():\n    return 1\n\n\ndef two():\n    return 2\n", encoding="utf-8",
    )
    (target / "tests" / "test_engine.py").write_text(
        "from pkg.fresh import one\n\n\ndef test_one():\n    assert one() == 1\n",
        encoding="utf-8",
    )
    result = verify_green_phase(_state(
        target, implementation_files=[str(target / "pkg" / "fresh.py")],
    ))

    assert result["next_node"] == "N4c_augment_tests"
    assert result["coverage_achieved"] == 75.0, "3 of its 4 executable lines"
    assert result["uncovered_changed_lines"] == {"pkg/fresh.py": [6]}


def test_t4_a_new_file_no_test_imports_is_a_measured_zero_not_a_failure(target, real_pytest):
    (target / "pkg" / "fresh.py").write_text(
        "def one():\n    return 1\n", encoding="utf-8",
    )
    result = verify_green_phase(_state(
        target, implementation_files=[str(target / "pkg" / "fresh.py")],
    ))

    assert result["error_message"] == ""
    assert result["next_node"] == "N4c_augment_tests"
    assert result["coverage_achieved"] == 0.0
    assert result["uncovered_changed_lines"] == {"pkg/fresh.py": [1, 2]}


def test_the_report_leaves_no_file_behind_to_dirty_the_worktree(target, real_pytest):
    """The landing refuses a worktree with an untracked file in it, and a
    target need not ignore `.assemblyzero/`."""
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    (target / "tests" / "test_engine.py").write_text(TEST_THE_TEN, encoding="utf-8")

    verify_green_phase(_state(target))

    assert not (target / verify_phases.GREEN_COVERAGE_REPORT).exists()


def _audit_dir(root: Path) -> Path:
    """Where N0 puts it: inside the worktree, and not ignored."""
    audit = root / "docs" / "lineage" / "active" / "7-testing"
    audit.mkdir(parents=True)
    return audit


def test_the_runs_own_snapshots_are_never_judged_on_the_next_iteration(target, real_pytest):
    """The hill-climb copies the run's source into the audit directory, and
    N2 saves its scaffold there as `.py`. On every iteration after the first
    those read as new Python files, at zero, unless they are told apart."""
    first = _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TWO_MISSED) + 2
    (target / "tests" / "test_engine.py").write_text(TEST_EIGHT_OF_TEN, encoding="utf-8")
    audit = _audit_dir(target)
    (audit / "042-test-scaffold.py").write_text("def scaffold():\n    return 1\n", encoding="utf-8")
    state = _state(target, audit_dir=str(audit), issue_number=7)

    one = verify_green_phase(state)
    assert list((audit / "best-iteration").glob("*.py")), "the snapshot this test is about exists"

    two = verify_green_phase({**state, **one})

    expected = {"pkg/engine.py": [first + 7, first + 8]}
    assert one["uncovered_changed_lines"] == expected
    assert two["uncovered_changed_lines"] == expected, "the second pass judges the same lines"
    assert two["coverage_achieved"] == 80.0


def test_a_checkpoint_that_commits_the_snapshots_does_not_put_them_in_the_diff(target, real_pytest):
    """The same with the copies tracked: a checkpoint's `git add -A` takes the
    audit directory, so they reach `git diff`, not only the untracked list."""
    first = _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TWO_MISSED) + 2
    (target / "tests" / "test_engine.py").write_text(TEST_EIGHT_OF_TEN, encoding="utf-8")
    audit = _audit_dir(target)
    state = _state(target, audit_dir=str(audit))
    one = verify_green_phase(state)
    _git(target, "add", "-A")
    _git(target, "commit", "-m", "[CP:post-green] issue #7: workflow checkpoint")

    two = verify_green_phase({**state, **one})

    assert two["uncovered_changed_lines"] == {"pkg/engine.py": [first + 7, first + 8]}


def test_a_committed_change_is_judged_too(target, real_pytest):
    """N4 commits a checkpoint before N5 runs, so a run's lines are mostly in
    its history, not its working tree."""
    first = _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TWO_MISSED) + 2
    (target / "tests" / "test_engine.py").write_text(TEST_EIGHT_OF_TEN, encoding="utf-8")
    _git(target, "add", "-A")
    _git(target, "commit", "-m", "[CP:post-impl] issue #7: workflow checkpoint")

    result = verify_green_phase(_state(target))

    assert result["uncovered_changed_lines"] == {"pkg/engine.py": [first + 7, first + 8]}


# ---------------------------------------------------------------------------
# T5 (R2): a framework with nothing to judge
# ---------------------------------------------------------------------------


def test_t5_a_python_only_run_is_not_judged_on_vitest_and_the_log_says_so(
    mixed_target, real_pytest, capsys,
):
    """Fails on `main`: Vitest's 54.28% routes the run to N4c."""
    _append(mixed_target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    (mixed_target / "tests" / "test_engine.py").write_text(TEST_THE_TEN, encoding="utf-8")
    npx = _Vitest(mixed_target, "web/src/engine.ts", {1: 0, 2: 0})
    state = _state(
        mixed_target,
        test_files=[
            str(mixed_target / "tests" / "test_engine.py"),
            str(mixed_target / "web" / "tests" / "engine.test.ts"),
        ],
        implementation_files=[str(mixed_target / "pkg" / "engine.py")],
        framework_configs=[PYTEST, VITEST_WEB],
    )

    result = _green_with(npx, state)

    assert result["error_message"] == ""
    assert result["next_node"] == "N7_finalize"
    assert result["coverage_achieved"] == 100.0, "Python's lines, and only Python's"
    assert "vitest (web): no changed executable lines" in capsys.readouterr().out


def test_r2_the_log_records_the_framework_it_did_not_judge(
    mixed_target, real_pytest, logged,
):
    _append(mixed_target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    (mixed_target / "tests" / "test_engine.py").write_text(TEST_THE_TEN, encoding="utf-8")
    npx = _Vitest(mixed_target, "web/src/engine.ts", {1: 0, 2: 0})
    state = _state(
        mixed_target,
        test_files=[
            str(mixed_target / "tests" / "test_engine.py"),
            str(mixed_target / "web" / "tests" / "engine.test.ts"),
        ],
        framework_configs=[PYTEST, VITEST_WEB],
    )

    _green_with(npx, state)

    not_judged = [details for event, details in logged if event == "coverage_not_judged"]
    assert [details["framework"] for details in not_judged] == ["vitest (web)"]
    assert not_judged[0]["whole_file_coverage"] == 54.28, "reported, deciding nothing"


def test_r2_a_run_that_changes_only_test_files_passes_on_any_figure(target, real_pytest):
    (target / "tests" / "test_engine.py").write_text(
        "def test_more():\n    assert 1 + 1 == 2\n", encoding="utf-8",
    )
    result = verify_green_phase(_state(
        target, implementation_files=[str(target / "tests" / "test_engine.py")],
    ))

    assert result["error_message"] == ""
    assert result["next_node"] == "N7_finalize"
    assert result["coverage_judged"] is False


def test_r2_a_run_that_only_deletes_lines_passes(target, real_pytest):
    engine = target / "pkg" / "engine.py"
    lines = engine.read_text(encoding="utf-8").splitlines(keepends=True)
    engine.write_text("".join(lines[:-4]), encoding="utf-8")

    result = verify_green_phase(_state(target))

    assert result["error_message"] == ""
    assert result["next_node"] == "N7_finalize"
    assert result["coverage_judged"] is False


def test_r2_a_changed_comment_is_no_changed_line(target, real_pytest):
    _append(target / "pkg" / "engine.py", "# a note\n\n")

    result = verify_green_phase(_state(target))

    assert result["next_node"] == "N7_finalize"
    assert result["coverage_judged"] is False


def test_r2_a_framework_with_changed_source_and_no_test_file_is_still_judged(mixed_target):
    """`_no_targeted_tests` used to say there was nothing to verify. There is
    when the run changed that framework's source: its whole suite is measured."""
    first = _append(
        mixed_target / "web" / "src" / "engine.ts", "export const added = 1;\n",
    )
    npx = _Vitest(mixed_target, "web/src/engine.ts", {first: 0})
    state = _state(
        mixed_target,
        test_files=[str(mixed_target / "tests" / "test_engine.py")],
        implementation_files=[str(mixed_target / "web" / "src" / "engine.ts")],
        framework_config=PYTEST,
        framework_configs=[VITEST_WEB, PYTEST],
    )

    result = _green_with(npx, state)

    assert result["next_node"] == "N4c_augment_tests"
    assert result["uncovered_changed_lines"] == {"web/src/engine.ts": [first]}
    assert npx.calls[0][-1].startswith("--coverage."), "no test path: the whole suite"


# ---------------------------------------------------------------------------
# R3: whole-file coverage is reported and decides nothing
# ---------------------------------------------------------------------------


def test_r3_a_targets_own_fail_under_cannot_fail_the_run(target, real_pytest):
    """pytest-cov enforces `fail_under` from the target's config on its own,
    with exit 1 and no failed test. The explicit 0 is what overrides it."""
    (target / "pyproject.toml").write_text(
        "[tool.coverage.report]\nfail_under = 99\n", encoding="utf-8",
    )
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    (target / "tests" / "test_engine.py").write_text(TEST_THE_TEN, encoding="utf-8")

    result = verify_green_phase(_state(target))

    assert result["next_node"] == "N7_finalize"
    assert result["pytest_exit_code"] == 0
    assert "Required test coverage" not in result["green_phase_output"]


def test_r3_the_gate_passes_no_whole_module_threshold(target, real_pytest):
    seen: list[str] = []
    real = verify_phases.run_command

    def spy(command, **kwargs):
        seen.extend(command)
        return real(command, **kwargs)

    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    (target / "tests" / "test_engine.py").write_text(TEST_THE_TEN, encoding="utf-8")
    with patch.object(verify_phases, "run_command", side_effect=spy):
        verify_green_phase(_state(target))

    assert "--cov-fail-under=0" in seen
    assert not any(a.startswith("--cov-fail-under=") and a != "--cov-fail-under=0" for a in seen)


def test_r3_whole_file_coverage_is_reported(target, real_pytest, capsys, logged):
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    (target / "tests" / "test_engine.py").write_text(TEST_THE_TEN, encoding="utf-8")

    verify_green_phase(_state(target))

    out = capsys.readouterr().out
    assert "10 of 10 changed executable line(s) covered (100.0%, target 95%)" in out
    assert "is reported and decides nothing" in out
    judged = next(details for event, details in logged if event == "changed_line_coverage")
    assert judged["whole_file_coverage"] < 60
    assert judged["percent"] == 100.0


# ---------------------------------------------------------------------------
# T6 (R5): a measurement that cannot be read halts
# ---------------------------------------------------------------------------


def _says_all_passed(**_kwargs) -> dict:
    return {
        "returncode": 0, "stdout": "15 passed in 0.1s\n", "stderr": "",
        "parsed": {"passed": 15, "failed": 0, "errors": 0, "coverage": 0.0},
    }


def _assert_measurement_halt(result: dict, state: dict) -> None:
    assert result["next_node"] == "end"
    assert "COVERAGE MEASUREMENT FAILED" in result["error_message"]
    assert "not a test gap" in result["error_message"]
    assert route_after_green({**state, **result}) == "HALT"


def test_t6_a_missing_report_halts_and_names_the_path(target):
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    state = _state(target)

    with patch.object(verify_phases, "run_pytest", side_effect=lambda *a, **k: _says_all_passed()):
        result = verify_green_phase(state)

    _assert_measurement_halt(result, state)
    assert "green-coverage.json" in result["error_message"]


@pytest.mark.parametrize("content", [
    "this is not json",
    "[]",
    '{"files": "nothing"}',
    '{"files": {"pkg/engine.py": {"executed_lines": [1]}}}',
], ids=["not-json", "not-an-object", "no-table", "no-missing-lines"])
def test_t6_an_unreadable_report_halts(target, content):
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    state = _state(target)

    def writes_garbage(*_args, coverage_report=None, **_kwargs):
        Path(coverage_report).write_text(content, encoding="utf-8")
        return _says_all_passed()

    with patch.object(verify_phases, "run_pytest", side_effect=writes_garbage):
        result = verify_green_phase(state)

    _assert_measurement_halt(result, state)


def test_t6_a_missing_report_is_never_zero_changed_lines_on_a_test_only_run(target):
    """The strongest reading of R5: with nothing to judge, the answer would
    be a pass. It still needs a measurement behind it."""
    (target / "tests" / "test_engine.py").write_text(
        "def test_more():\n    assert True\n", encoding="utf-8",
    )
    state = _state(target, implementation_files=[])

    with patch.object(verify_phases, "run_pytest", side_effect=lambda *a, **k: _says_all_passed()):
        result = verify_green_phase(state)

    _assert_measurement_halt(result, state)


def test_t6_a_report_with_no_data_quotes_coverages_reason(target):
    state = _state(target)
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)

    def no_data(*_args, **_kwargs):
        return {**_says_all_passed(), "stderr": "CoverageWarning: No data was collected."}

    with patch.object(verify_phases, "run_pytest", side_effect=no_data):
        result = verify_green_phase(state)

    assert "No data was collected" in result["error_message"]


def test_t6_a_stale_report_from_an_earlier_iteration_is_never_read(target):
    stale = target / verify_phases.GREEN_COVERAGE_REPORT
    stale.parent.mkdir()
    stale.write_text(json.dumps({"files": {}}), encoding="utf-8")
    state = _state(target)

    with patch.object(verify_phases, "run_pytest", side_effect=lambda *a, **k: _says_all_passed()):
        result = verify_green_phase(state)

    _assert_measurement_halt(result, state)


def test_t6_a_changed_file_the_report_does_not_name_halts(target):
    _append(target / "pkg" / "engine.py", "\n\n" + ADDED_TEN)
    state = _state(target)

    def names_another_file(*_args, coverage_report=None, **_kwargs):
        Path(coverage_report).write_text(json.dumps({"files": {
            "pkg/other.py": {"executed_lines": [1], "missing_lines": []},
        }}), encoding="utf-8")
        return _says_all_passed()

    with patch.object(verify_phases, "run_pytest", side_effect=names_another_file):
        result = verify_green_phase(state)

    _assert_measurement_halt(result, state)
    assert "pkg/engine.py" in result["error_message"]
    assert "pkg/other.py" in result["error_message"], "says what the report did hold"


@pytest.mark.parametrize("summary, lines", [(False, True), (True, False)],
                         ids=["no-summary", "no-per-line-report"])
def test_t6_vitest_halts_on_either_report_missing(mixed_target, summary, lines):
    first = _append(mixed_target / "web" / "src" / "engine.ts", "export const a = 1;\n")
    npx = _Vitest(mixed_target, "web/src/engine.ts", {first: 1}, summary=summary, lines=lines)
    state = _vitest_state(mixed_target)

    result = _green_with(npx, state)

    _assert_measurement_halt(result, state)
    assert "coverage-" in result["error_message"]


def test_t6_vitest_with_nothing_changed_still_needs_its_report(mixed_target):
    npx = _Vitest(mixed_target, "web/src/engine.ts", {1: 0}, lines=False)
    state = _vitest_state(mixed_target)

    result = _green_with(npx, state)

    _assert_measurement_halt(result, state)


def test_t6_a_failing_run_needs_no_report(target):
    """While tests fail coverage decides nothing, so its absence is no failure."""
    def failing(*_args, **_kwargs):
        return {
            "returncode": 1, "stdout": "1 failed, 2 passed\n", "stderr": "",
            "parsed": {"passed": 2, "failed": 1, "errors": 0, "coverage": 40.0},
        }

    with patch.object(verify_phases, "run_pytest", side_effect=failing):
        result = verify_green_phase(_state(target))

    assert result["error_message"] == ""
    assert result["next_node"] == "N4_implement_code"


def test_t6_a_run_with_no_base_halts_before_the_suite_runs(target):
    state = _state(target, base_branch="")

    with patch.object(verify_phases, "run_pytest") as never:
        result = verify_green_phase(state)

    assert never.call_count == 0
    _assert_measurement_halt(result, state)
    assert "no base branch and no base commit" in result["error_message"]


def test_t6_a_base_that_shares_no_history_halts(target):
    state = _state(target, base_branch="no-such-branch")

    result = verify_green_phase(state)

    _assert_measurement_halt(result, state)
    assert "no-such-branch" in result["error_message"]


# ---------------------------------------------------------------------------
# T7 (R6): #4266's T1 and T2 are in test_coverage_target_source.py
# ---------------------------------------------------------------------------
