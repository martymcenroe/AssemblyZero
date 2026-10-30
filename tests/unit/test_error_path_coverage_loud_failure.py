"""error_path_coverage under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md. A check that did not run is
never ``ok``: its caller set ``passed=report.ok`` and recorded it as passed.
"""
from __future__ import annotations

from assemblyzero.workflows.implementation_spec import error_path_coverage as epc

TESTS_ONLY = "```python\ndef test_one():\n    assert True\n```\n"
COVERED = (
    "```python\ndef load(path):\n    raise ValueError('bad')\n```\n\n"
    "```python\ndef test_bad():\n    with pytest.raises(ValueError):\n        load('x')\n```\n"
)


def test_102_a_spec_with_no_implementation_fence_is_not_ok():
    report = epc.error_path_coverage(TESTS_ONLY)
    assert report.ran is False
    assert report.ok is False
    assert "cannot be checked" in epc.format_report(report)


def test_a_spec_whose_error_paths_are_tested_is_ok():
    report = epc.error_path_coverage(COVERED)
    assert report.ran is True and report.ok is True


def test_an_untested_raise_is_not_ok():
    report = epc.error_path_coverage(COVERED.replace("pytest.raises(ValueError)", "nothing()"))
    assert report.ran is True and report.ok is False
    assert report.untested == ["ValueError"]
