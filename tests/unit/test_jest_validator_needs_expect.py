"""A Jest or Vitest test file must assert: `JestRunner.validate_test_file`
checks for `expect(` as its docstring always said (#3067).

The docstring listed two checks and the code made one, so a file whose tests
call the code and assert nothing validated, ran green, and produced coverage
of behaviour nobody checked. `PlaywrightRunner.validate_test_file` implements
both of its bullets; this one now does too.

The TypeScript scaffold's own placeholders were the same hole from the other
side (ledger 0908, `scaffold_tests.py:457` and `:489`): `expect(true).toBe(true)`
and `await expect(page).toBeTruthy()` pass with no implementation at all, so a
fresh TypeScript scaffold could never fail its red phase. Each placeholder now
fails until a real test replaces it, as the Python scaffold's `assert False`
does.

`shutil.which` answers for `npx`; nothing is run.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.nodes.scaffold_tests import (
    generate_ts_test_file_content,
)
from assemblyzero.workflows.testing.runner_registry import (
    get_framework_config,
    get_runner,
)
from assemblyzero.workflows.testing.runners import jest_runner, playwright_runner

ASSERTS_NOTHING = """import { describe, it } from '@jest/globals';

describe('the collector', () => {
  it('reads the handle count', () => {
    getHandleCount();
  });
});
"""

ASSERTS = """import { describe, it, expect } from 'vitest';

describe('the collector', () => {
  it('reads the handle count', () => {
    expect(getHandleCount()).toBe(3);
  });
});
"""

#: `expect` imported and never called.
IMPORTS_EXPECT_ONLY = """import { describe, it, expect } from 'vitest';

describe('the collector', () => {
  it('reads the handle count', () => {
    getHandleCount();
  });
});
"""

SCENARIOS = [
    {"name": "test_replay", "description": "Replays a user's session\nto the end",
     "requirement_ref": "REQ-1", "test_type": "unit", "mock_needed": False,
     "assertions": []},
]


@pytest.fixture(params=[TestFramework.JEST, TestFramework.VITEST])
def runner(request, tmp_path):
    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        return get_runner(request.param, str(tmp_path))


def test_a_test_that_asserts_nothing_is_refused(runner):
    errors = runner.validate_test_file("tests/collector.test.ts", ASSERTS_NOTHING)
    assert errors == ["No expect() assertions found in tests/collector.test.ts"]


def test_expect_imported_but_never_called_is_refused(runner):
    errors = runner.validate_test_file("tests/collector.test.ts", IMPORTS_EXPECT_ONLY)
    assert any("No expect() assertions" in e for e in errors)


def test_a_test_that_asserts_is_accepted(runner):
    assert runner.validate_test_file("tests/collector.test.ts", ASSERTS) == []


@pytest.mark.parametrize("framework", [TestFramework.JEST, TestFramework.VITEST])
def test_the_unit_scaffold_placeholder_fails_until_replaced(framework):
    """Ledger `scaffold_tests.py:489`: the placeholder was expect(true).toBe(true)."""
    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        content = generate_ts_test_file_content(
            SCENARIOS, get_framework_config(framework), issue_number=7
        )
    assert "expect(true).toBe(true)" not in content
    assert "expect(false).toBe(true)" in content, "a placeholder that cannot pass"
    assert "TDD RED" in content


def test_the_playwright_scaffold_placeholder_fails_until_replaced():
    """Ledger `scaffold_tests.py:457`: the placeholder was expect(page).toBeTruthy()."""
    content = generate_ts_test_file_content(
        SCENARIOS, get_framework_config(TestFramework.PLAYWRIGHT), issue_number=7
    )
    assert "toBeTruthy()" not in content
    assert "expect(false).toBe(true)" in content
    assert "TDD RED" in content


@pytest.mark.parametrize("framework", list(TestFramework)[1:])
def test_a_scenario_name_with_a_quote_or_newline_is_a_valid_string(framework):
    """`it('Replays a user's session` closed the string at the apostrophe,
    and a newline in the description ended the literal."""
    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"), \
         patch.object(playwright_runner.shutil, "which", return_value="/usr/bin/npx"):
        content = generate_ts_test_file_content(
            SCENARIOS, get_framework_config(framework), issue_number=7
        )
    assert "\"Replays a user's session\\nto the end\"" in content


@pytest.mark.parametrize("framework", [TestFramework.JEST, TestFramework.VITEST])
def test_the_scaffold_passes_its_own_framework_validator(framework, tmp_path):
    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        content = generate_ts_test_file_content(
            SCENARIOS, get_framework_config(framework), issue_number=7
        )
        runner = get_runner(framework, str(tmp_path))
    assert runner.validate_test_file("tests/issue_7.test.ts", content) == []
