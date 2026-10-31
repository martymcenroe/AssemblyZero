"""run_frameworks turns an unknown framework into an ownership failure (#4311).

The runner registry raises `UnknownFrameworkError` for a framework it does not
know (#3585); it used to answer None, and a lone unknown framework ran as
pytest. `run_frameworks` wraps it in `TestFileOwnershipError`, the failure N2
to N5 already halt on, so the run stops naming the framework.
"""

from __future__ import annotations

import pytest

from assemblyzero.workflows.testing.framework_ownership import (
    TestFileOwnershipError,
    run_frameworks,
)


@pytest.mark.parametrize(
    "state",
    [
        {"framework_config": {"framework": "nosuchrunner"}},
        {"framework_configs": [{"framework": "nosuchrunner"}]},
        {"framework_configs": [{"framework": "pytest"}, {"framework": "nosuchrunner"}]},
    ],
    ids=["single_legacy", "single", "one_of_two"],
)
def test_an_unknown_framework_is_an_ownership_failure_naming_it(state):
    with pytest.raises(TestFileOwnershipError, match="nosuchrunner"):
        run_frameworks(state)


def test_a_config_that_names_no_framework_is_still_pytest():
    runs = run_frameworks({"framework_configs": [{"working_directory": "."}]})
    assert [run.framework.value for run in runs] == ["pytest"]
