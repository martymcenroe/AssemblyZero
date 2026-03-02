

```python
"""Tests for reconciliation engine.

Issue #535: T150, T160, T360–T390.
"""

from __future__ import annotations

import os
import tempfile

from assemblyzero.workflows.death.models import DriftFinding, DriftReport
from assemblyzero.workflows.death.reconciler import (
    generate_adr,
    harvest,
    walk_the_field,
)


def test_action_generation_from_count_mismatch():
    """T150: count_mismatch finding -> update_count action.

    Input: DriftFinding(category="count_mismatch")
    Expected: ReconciliationAction(action_type="update_count")
    """
    drift_report: DriftReport = {
        "findings": [
            {
                "id": "DRIFT-001",
                "severity": "critical",
                "doc_file": "README.md",
                "doc_claim": "12+ agents",
                "code_reality": "36 agents",
                "category": "count_mismatch",
                "confidence": 0.95,
                "evidence": "glob found 36",
            }
        ],
        "total_score": 10.0,
        "critical_count": 1,
        "major_count": 0,
        "minor_count": 0,
        "scanned_docs": ["README.md"],
        "scanned_code_paths": ["/project"],
        "timestamp": "2026-02-17T12:45:00Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        actions = walk_the_field(tmpdir, drift_report)
        assert len(actions) == 1
        assert actions[0]["action_type"] == "update_count"
        assert actions[0]["drift_finding_id"] == "DRIFT-001"


def test_report_mode_no_writes():
    """T160: dry_run=True produces no file writes.

    Input: actions list, dry_run=True
    Expected: No filesystem side effects
    """
    actions = [
        {
            "target_file": "README.md",
            "action_type": "update_count",
            "description": "Update count",
            "old_content": "12+",
            "new_content": "36",
            "drift_finding_id": "DRIFT-001",
        }
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        result = harvest(actions, tmpdir, dry_run=True)
        assert result == actions
        # Verify no files were created in tmpdir beyond what existed
        assert len(os.listdir(tmpdir)) == 0


def test_generate_adr_architecture_drift():
    """T360: Architecture drift finding generates ADR content.

    Input: DriftFinding(category="architecture_drift"), dry_run=True
    Expected: ADR content string with Context, Decision, Rationale sections
    """
    finding: DriftFinding = {
        "id": "DRIFT-010",
        "severity": "major",
        "doc_file": "docs/architecture.md",
        "doc_claim": "System does not use vector embeddings",
        "code_reality": "RAG pipeline exists at assemblyzero/rag/",
        "category": "architecture_drift",
        "confidence": 0.9,
        "evidence": "Directory assemblyzero/rag/ contains 8 Python files",
    }
    actions = [
        {
            "target_file": "docs/architecture.md",
            "action_type": "update_description",
            "description": "Update architecture description",
            "old_content": "System does not use vector embeddings",
            "new_content": "System includes RAG pipeline",
            "drift_finding_id": "DRIFT-010",
        }
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        content = generate_adr(
            finding=finding,
            actions=actions,
            adr_template_path=tmpdir,
            output_dir=tmpdir,
            dry_run=True,
        )
        assert content is not None
        assert "## Status" in content
        assert "## Context" in content
        assert "## Decision" in content
        assert "vector embeddings" in content


def test_generate_adr_non_qualifying():
    """T370: count_mismatch finding returns None.

    Input: DriftFinding(category="count_mismatch")
    Expected: None
    """
    finding: DriftFinding = {
        "id": "DRIFT-001",
        "severity": "critical",
        "doc_file": "README.md",
        "doc_claim": "12+ agents",
        "code_reality": "36 agents",
        "category": "count_mismatch",
        "confidence": 0.95,
        "evidence": "glob found 36",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_adr(
            finding=finding,
            actions=[],
            adr_template_path=tmpdir,
            output_dir=tmpdir,
            dry_run=True,
        )
        assert result is None


def test_generate_adr_reaper_writes_file():
    """T380: dry_run=False creates file at output path.

    Input: architecture_drift finding, dry_run=False
    Expected: File created at output_dir/0015-age-transition-protocol.md
    """
    finding: DriftFinding = {
        "id": "DRIFT-010",
        "severity": "major",
        "doc_file": "docs/architecture.md",
        "doc_claim": "No vector embeddings",
        "code_reality": "RAG pipeline exists",
        "category": "architecture_drift",
        "confidence": 0.9,
        "evidence": "Directory exists",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        result = generate_adr(
            finding=finding,
            actions=[],
            adr_template_path=tmpdir,
            output_dir=tmpdir,
            dry_run=False,
        )
        assert result is not None
        assert result.endswith("0015-age-transition-protocol.md")
        assert os.path.exists(result)
        with open(result) as f:
            content = f.read()
        assert "## Context" in content


def test_generate_adr_report_no_write():
    """T390: dry_run=True returns content but creates no file.

    Input: architecture_drift finding, dry_run=True
    Expected: Content string returned, no file created
    """
    finding: DriftFinding = {
        "id": "DRIFT-010",
        "severity": "major",
        "doc_file": "docs/architecture.md",
        "doc_claim": "No vector embeddings",
        "code_reality": "RAG pipeline exists",
        "category": "architecture_drift",
        "confidence": 0.9,
        "evidence": "Directory exists",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        content = generate_adr(
            finding=finding,
            actions=[],
            adr_template_path=tmpdir,
            output_dir=tmpdir,
            dry_run=True,
        )
        assert isinstance(content, str)
        assert "## Context" in content
        # Verify no ADR file was created
        adr_path = os.path.join(tmpdir, "0015-age-transition-protocol.md")
        assert not os.path.exists(adr_path)
```
