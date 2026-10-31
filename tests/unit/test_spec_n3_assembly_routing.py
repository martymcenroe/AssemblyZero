"""N3 halts on the errors the spec package's second half raises (#3585).

The first half made every check that cannot run raise
``CompletenessCannotCheck``, which N3 turns into a halt. The second half made
the base tree raise ``BaseTreeError`` when git cannot answer, and the criteria
join raise ``CriteriaTableError`` on a row it cannot read. Both reach N3 from
inside its checks, so N3 halts on them the same way, naming the type and the
cause. Any other exception is a fault in the code and still escapes.
"""

from __future__ import annotations

import importlib

import pytest

from assemblyzero.workflows.implementation_spec.base_tree import BaseTreeError
from assemblyzero.workflows.implementation_spec.criteria_coverage import (
    CriteriaTableError,
)

# The nodes package re-exports the node function under the module's name, so
# the module is imported by its full path.
vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)

DRAFT = "# Implementation Spec\n\n## Overview\n\n" + ("filler " * 30)


def _state(tmp_path):
    return {
        "spec_draft": DRAFT,
        "files_to_modify": [],
        "pattern_references": [],
        "repo_root": str(tmp_path),
        "lld_content": "",
        "review_iteration": 1,
    }


def _raising(exc):
    def run_checks(state, spec_draft):
        raise exc
    return run_checks


@pytest.mark.parametrize(
    "exc",
    [
        BaseTreeError("git show origin/main:pyproject.toml exited 128: bad object"),
        CriteriaTableError("criteria row 3 has no REQ tag the join can read"),
    ],
    ids=["base_tree", "criteria_table"],
)
def test_n3_halts_on_the_second_halfs_errors(tmp_path, monkeypatch, capsys, exc):
    monkeypatch.setattr(vc, "_run_checks", _raising(exc))
    result = vc.validate_completeness(_state(tmp_path))
    message = result["completeness_cannot_check"]
    assert type(exc).__name__ in message
    assert str(exc) in message
    assert result["error_message"] == message
    assert result["validation_passed"] is False
    assert message in capsys.readouterr().err


def test_any_other_exception_still_escapes_as_a_fault(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "_run_checks", _raising(KeyError("spec_draft")))
    with pytest.raises(KeyError):
        vc.validate_completeness(_state(tmp_path))
