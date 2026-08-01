"""The completeness gate must be handed the LLD, not the spec (#2024).

Every run of boostgauge #2 and #41 logged:

    Section 3 (Requirements) not found in ...spec-0002-implementation-readiness.md
    Layer 2: Prepared 0 requirements, 2 code snippets
    Completeness gate verdict: WARN

The gate compared the implementation against nothing and returned a verdict
anyway. The two documents both have a section 3 and they are not the same
section:

    LLD-041.md   ## 3. Requirements                        <- extractable
    spec-0041... ## 3. Current State (for Modify/Delete files)

`completeness_gate` read `state["lld_path"]`, a legacy key that in this
workflow holds the SPEC -- `load_lld.py` sets it from `find_spec_path()` and
even prints "Spec path:" for it. #656 already resolves the real LLD for its own
use; it was simply never put in state for anyone else to reach.
"""

from pathlib import Path

import pytest

from assemblyzero.workflows.testing.completeness.report_generator import (
    extract_lld_requirements,
)

LLD = """# LLD

## 2. Proposed Changes
stuff

## 3. Requirements

1. The telltale holds a peak for the duration of its window.
2. The peak drops to the highest remaining in-window sample once it ages out.

## 4. Alternatives
"""

SPEC = """# Implementation Spec

## 2. Files to Implement
stuff

## 3. Current State (for Modify/Delete files)
none

## 4. Data Structures
"""


@pytest.fixture
def docs(tmp_path):
    lld = tmp_path / "LLD-002.md"
    lld.write_text(LLD, encoding="utf-8")
    spec = tmp_path / "spec-0002-implementation-readiness.md"
    spec.write_text(SPEC, encoding="utf-8")
    return lld, spec


class TestTheTwoDocumentsDiffer:
    def test_the_lld_yields_requirements(self, docs):
        lld, _ = docs
        assert len(extract_lld_requirements(lld)) == 2

    def test_the_spec_yields_none(self, docs):
        """Not a bug in the extractor -- the spec genuinely has no requirements
        section. Handing it one is the bug."""
        _, spec = docs
        assert extract_lld_requirements(spec) == []


class TestTheGatePrefersTheLld:
    def _state(self, **kw):
        base = {
            "repo_root": "",
            "issue_number": 2,
            "implementation_files": [],
            "test_files": [],
            "audit_dir": "",
        }
        base.update(kw)
        return base

    def test_it_reads_original_lld_path_when_present(self, docs):
        lld, spec = docs
        state = self._state(lld_path=str(spec), original_lld_path=str(lld))
        chosen = state.get("original_lld_path", "") or state.get("lld_path", "")

        assert Path(chosen) == lld
        assert len(extract_lld_requirements(Path(chosen))) == 2

    def test_it_falls_back_to_lld_path_when_no_lld_resolved(self, docs):
        """Pre-#656 shape, and repos where no separate LLD exists."""
        _, spec = docs
        state = self._state(lld_path=str(spec), original_lld_path="")
        chosen = state.get("original_lld_path", "") or state.get("lld_path", "")

        assert Path(chosen) == spec


class TestAnEmptyExtractionIsVisible:
    def test_it_says_the_review_compared_against_nothing(self, docs, capsys):
        from assemblyzero.workflows.testing.completeness.report_generator import (
            prepare_review_materials,
        )

        _, spec = docs
        prepare_review_materials(issue_number=2, lld_path=spec, implementation_files=[])
        out = capsys.readouterr().out

        assert "NO REQUIREMENTS" in out
        assert "against nothing" in out

    def test_a_good_lld_says_nothing_alarming(self, docs, capsys):
        from assemblyzero.workflows.testing.completeness.report_generator import (
            prepare_review_materials,
        )

        lld, _ = docs
        prepare_review_materials(issue_number=2, lld_path=lld, implementation_files=[])

        assert "NO REQUIREMENTS" not in capsys.readouterr().out


class TestTheKeyIsDeclared:
    def test_original_lld_path_is_a_declared_state_field(self):
        """#2018: LangGraph discards undeclared keys at the node boundary, so
        an undeclared key here would never reach the gate at all."""
        from assemblyzero.workflows.testing.state import TestingWorkflowState

        assert "original_lld_path" in TestingWorkflowState.__annotations__
