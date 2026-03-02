

```python
"""Tests for drift scoring.

Issue #535: T090–T140.
"""

from __future__ import annotations

import os
import tempfile

from assemblyzero.workflows.death.drift_scorer import (
    _reset_finding_counter,
    check_critical_drift,
    compute_drift_score,
    scan_inventory_accuracy,
    scan_readme_claims,
)
from assemblyzero.workflows.death.models import DriftFinding


def test_numeric_claim_mismatch():
    """T090: Detects numeric claim mismatch in README.

    Input: README says "12+ agents", codebase has 36 persona files
    Expected: DriftFinding with category="count_mismatch"
    """
    _reset_finding_counter()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create README with numeric claim
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Project\n\nAssemblyZero includes 12 agents for various tasks.\n")

        # Create persona directory with different count
        personas_dir = os.path.join(tmpdir, "assemblyzero", "personas")
        os.makedirs(personas_dir)
        for i in range(36):
            with open(os.path.join(personas_dir, f"persona_{i}.toml"), "w") as f:
                f.write(f"name = 'persona_{i}'")

        findings = scan_readme_claims(readme_path, tmpdir)
        assert len(findings) >= 1
        assert findings[0]["category"] == "count_mismatch"


def test_accurate_readme_no_findings():
    """T100: Accurate README produces no findings.

    Input: README says "36 agents", codebase has 36 persona files
    Expected: No findings
    """
    _reset_finding_counter()

    with tempfile.TemporaryDirectory() as tmpdir:
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w") as f:
            f.write("# Project\n\nAssemblyZero includes 36 agents for various tasks.\n")

        personas_dir = os.path.join(tmpdir, "assemblyzero", "personas")
        os.makedirs(personas_dir)
        for i in range(36):
            with open(os.path.join(personas_dir, f"persona_{i}.toml"), "w") as f:
                f.write(f"name = 'persona_{i}'")

        findings = scan_readme_claims(readme_path, tmpdir)
        # Filter to agent/persona related findings
        agent_findings = [f for f in findings if "agent" in f.get("doc_claim", "").lower() or "persona" in f.get("doc_claim", "").lower()]
        assert len(agent_findings) == 0


def test_inventory_missing_file():
    """T110: Detects file in inventory but missing from disk.

    Input: Inventory lists "tools/old_tool.py", file does not exist
    Expected: DriftFinding with category="stale_reference"
    """
    _reset_finding_counter()

    with tempfile.TemporaryDirectory() as tmpdir:
        inv_path = os.path.join(tmpdir, "inventory.md")
        with open(inv_path, "w") as f:
            f.write("| File | Status |\n")
            f.write("|------|--------|\n")
            f.write("| `tools/old_tool.py` | Active |\n")

        findings = scan_inventory_accuracy(inv_path, tmpdir)
        assert len(findings) >= 1
        assert findings[0]["category"] == "stale_reference"


def test_inventory_file_exists():
    """T120: File exists in inventory — no finding.

    Input: Inventory lists "tools/real_tool.py", file exists
    Expected: No findings
    """
    _reset_finding_counter()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create the file
        tools_dir = os.path.join(tmpdir, "tools")
        os.makedirs(tools_dir)
        with open(os.path.join(tools_dir, "real_tool.py"), "w") as f:
            f.write("# real tool")

        inv_path = os.path.join(tmpdir, "inventory.md")
        with open(inv_path, "w") as f:
            f.write("| File | Status |\n")
            f.write("|------|--------|\n")
            f.write("| `tools/real_tool.py` | Active |\n")

        findings = scan_inventory_accuracy(inv_path, tmpdir)
        assert len(findings) == 0


def test_drift_score_computation():
    """T130: Drift score computation: 2 critical + 1 major + 3 minor = 28.

    Input: 2 critical (10 each), 1 major (5), 3 minor (1 each)
    Expected: 28.0
    """
    findings: list[DriftFinding] = []
    base = {"doc_file": "README.md", "doc_claim": "x", "code_reality": "y", "category": "count_mismatch", "confidence": 0.9, "evidence": "z"}

    for i in range(2):
        findings.append({**base, "id": f"DRIFT-C{i}", "severity": "critical"})
    findings.append({**base, "id": "DRIFT-M0", "severity": "major"})
    for i in range(3):
        findings.append({**base, "id": f"DRIFT-m{i}", "severity": "minor"})

    score = compute_drift_score(findings)
    assert score == 28.0  # 2*10 + 1*5 + 3*1


def test_critical_drift_threshold():
    """T140: Critical drift threshold check.

    Input: DriftReport with total_score=30.0
    Expected: True
    """
    report = {
        "findings": [],
        "total_score": 30.0,
        "critical_count": 3,
        "major_count": 0,
        "minor_count": 0,
        "scanned_docs": [],
        "scanned_code_paths": [],
        "timestamp": "2026-02-17T12:45:00Z",
    }
    assert check_critical_drift(report) is True


def test_critical_drift_below_threshold():
    """Critical drift below threshold returns False."""
    report = {
        "findings": [],
        "total_score": 29.9,
        "critical_count": 0,
        "major_count": 0,
        "minor_count": 0,
        "scanned_docs": [],
        "scanned_code_paths": [],
        "timestamp": "2026-02-17T12:45:00Z",
    }
    assert check_critical_drift(report) is False
```
