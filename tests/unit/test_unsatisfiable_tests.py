"""#2347: a test no implementation can satisfy must not be frozen as contract.

Measured twice, independently:

  run-issue7-192332  FAILED test_default_config_path_non_windows -
                     pathlib.UnsupportedOperation: cannot instantiate
                     'PosixPath' on your system   (34 passed, 1 failed)
  run-issue7-231606  FAILED tests/test_issue_7.py::test_config_path_non_windows
                     - pathlib.UnsupportedOperation   (31 passed, 1 failed,
                     100% coverage)

Both tests patch `os.name` to "posix" and call code reaching `Path.home()`.
Patching `os.name` does not change which Path flavour pathlib builds, so the
test cannot pass on Windows under any implementation.

The freeze protocol (#2064/#2066) reads a repeated failing set as "the tests
are the contract; rewrite only the implementation". Correct when the tests are
right. Here it is inverted, and the strike counter is a timer on an
unwinnable loop rather than an exit from it.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.nodes.augment_tests import (
    build_augment_prompt,
)
from assemblyzero.workflows.testing.nodes.verify_phases import (
    _unsatisfiable_test_failures,
)

# The real summary line from run-issue7-231606.
REAL_OUTPUT = (
    "=========================== short test summary info ===========\n"
    "FAILED tests/test_issue_7.py::test_config_path_non_windows - "
    "pathlib.UnsupportedOperation: cannot instantiate 'PosixPath' on your system\n"
    "1 failed, 31 passed in 0.22s\n"
)


def test_the_real_failure_is_recognised_as_unsatisfiable() -> None:
    assert _unsatisfiable_test_failures(REAL_OUTPUT) == {
        "tests/test_issue_7.py::test_config_path_non_windows",
    }


@pytest.mark.parametrize("reason", [
    "pathlib.UnsupportedOperation: cannot instantiate 'PosixPath'",
    "ModuleNotFoundError: No module named 'winreg'",
    "ImportError: cannot import name 'x' from 'y'",
    "NotImplementedError",
])
def test_environment_errors_are_unsatisfiable(reason: str) -> None:
    output = f"FAILED tests/t.py::test_a - {reason}\n"
    assert _unsatisfiable_test_failures(output) == {"tests/t.py::test_a"}


@pytest.mark.parametrize("reason", [
    "AssertionError: assert 3 == 4",
    "AssertionError",
    "assert {'a': 1} == {'a': 2}",
    "TypeError: unsupported operand type(s)",
    "ValueError: invalid literal",
])
def test_real_failures_are_left_to_the_freeze_protocol(reason: str) -> None:
    """The protocol is load-bearing when the tests are right.

    Mistaking an assertion failure for an unsatisfiable one would disable it,
    which is a worse failure than the one this closes.
    """
    output = f"FAILED tests/t.py::test_a - {reason}\n"
    assert _unsatisfiable_test_failures(output) == set()


@pytest.mark.parametrize("output", [
    "",
    "31 passed in 0.2s",
    "FAILED tests/t.py::test_a",              # no reason recorded
    "FAILED not-a-test-id - ImportError",     # not a test id
    "some prose mentioning ImportError\n",
])
def test_unreadable_input_contributes_nothing(output: str) -> None:
    assert _unsatisfiable_test_failures(output) == set()


def test_a_mixed_run_separates_the_two_kinds() -> None:
    output = (
        "FAILED tests/t.py::test_platform - pathlib.UnsupportedOperation\n"
        "FAILED tests/t.py::test_logic - AssertionError: assert 1 == 2\n"
    )
    assert _unsatisfiable_test_failures(output) == {"tests/t.py::test_platform"}


def test_n4c_is_told_not_to_write_them() -> None:
    """Reduce recurrence at the source, not only at the gate."""
    prompt = build_augment_prompt(
        "tests/test_x.py", "def test_a():\n    assert 1\n",
        {"src/pkg/config.py": "27: return Path.home()"},
        coverage_achieved=78.0, coverage_target=95,
    )

    assert "must be able to PASS on the machine running it" in prompt
    assert "os.name" in prompt
    assert "skipif" in prompt
