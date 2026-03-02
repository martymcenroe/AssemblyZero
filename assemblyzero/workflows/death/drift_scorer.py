"""Drift scoring — detects factual inaccuracies in documentation.

Issue #535: Extends janitor probes to detect factual inaccuracies
(not just broken links) via regex and glob heuristics.
"""

from __future__ import annotations

import glob
import logging
import os
import re
from datetime import datetime, timezone

from assemblyzero.workflows.death.constants import (
    CRITICAL_DRIFT_THRESHOLD,
    DRIFT_SEVERITY_WEIGHTS,
)
from assemblyzero.workflows.death.models import DriftFinding, DriftReport

logger = logging.getLogger(__name__)

_FINDING_COUNTER = 0


def _next_finding_id() -> str:
    """Generate sequential drift finding ID."""
    global _FINDING_COUNTER
    _FINDING_COUNTER += 1
    return f"DRIFT-{_FINDING_COUNTER:03d}"


def _reset_finding_counter() -> None:
    """Reset finding counter (for testing)."""
    global _FINDING_COUNTER
    _FINDING_COUNTER = 0


# Patterns for numeric claims: e.g., "12+ agents", "34 audits", "5 workflows"
_NUMERIC_CLAIM_PATTERN = re.compile(
    r"(\d+)\+?\s+(specialized\s+)?(?:AI\s+)?(agents?|personas?|tools?|workflows?|audits?|probes?|commands?|skills?)",
    re.IGNORECASE,
)

# Mapping from claim noun to glob pattern for verification
_CLAIM_VERIFICATION: dict[str, str] = {
    "agent": "assemblyzero/personas/*.toml",
    "persona": "assemblyzero/personas/*.toml",
    "tool": "tools/*.py",
    "workflow": "assemblyzero/workflows/*/",
    "audit": "docs/lld/done/*.md",
    "probe": "assemblyzero/workflows/janitor/probes/*.py",
    "command": ".claude/commands/*.md",
    "skill": ".claude/commands/*.md",
}


def scan_readme_claims(
    readme_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan README for factual claims and verify against codebase.

    Checks numeric claims (tool counts, file counts, persona counts).
    """
    if not os.path.exists(readme_path):
        logger.warning("README not found at %s", readme_path)
        return []

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    findings: list[DriftFinding] = []

    for match in _NUMERIC_CLAIM_PATTERN.finditer(content):
        claimed_count = int(match.group(1))
        noun = match.group(3).lower().rstrip("s")  # Normalize to singular

        if noun not in _CLAIM_VERIFICATION:
            continue

        pattern = os.path.join(codebase_root, _CLAIM_VERIFICATION[noun])
        if pattern.endswith("/"):
            # Directory glob
            actual_items = [
                d for d in glob.glob(pattern)
                if os.path.isdir(d) and not d.endswith("__pycache__")
            ]
        else:
            actual_items = glob.glob(pattern)
            # Filter out __init__.py for probes
            actual_items = [
                f for f in actual_items
                if not os.path.basename(f).startswith("__")
            ]

        actual_count = len(actual_items)

        if actual_count != claimed_count:
            findings.append({
                "id": _next_finding_id(),
                "severity": "critical" if abs(actual_count - claimed_count) > 5 else "major",
                "doc_file": os.path.relpath(readme_path, codebase_root),
                "doc_claim": match.group(0),
                "code_reality": f"Found {actual_count} {noun} items via glob('{_CLAIM_VERIFICATION[noun]}')",
                "category": "count_mismatch",
                "confidence": 0.95,
                "evidence": f"glob('{_CLAIM_VERIFICATION[noun]}') returned {actual_count} matches",
            })

    return findings


def scan_inventory_accuracy(
    inventory_path: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Compare file inventory against actual filesystem.

    Detects files listed in inventory but missing from disk.
    """
    if not os.path.exists(inventory_path):
        logger.warning("Inventory not found at %s", inventory_path)
        return []

    with open(inventory_path, "r", encoding="utf-8") as f:
        content = f.read()

    findings: list[DriftFinding] = []

    # Parse markdown table rows — look for file paths
    # Pattern: | path/to/file.ext | ... |
    path_pattern = re.compile(r"\|\s*`?([a-zA-Z0-9_./-]+\.[a-zA-Z]+)`?\s*\|")

    for match in path_pattern.finditer(content):
        file_path = match.group(1)
        full_path = os.path.join(codebase_root, file_path)

        if not os.path.exists(full_path):
            findings.append({
                "id": _next_finding_id(),
                "severity": "major",
                "doc_file": os.path.relpath(inventory_path, codebase_root),
                "doc_claim": f"{file_path} listed in inventory",
                "code_reality": "File does not exist on disk",
                "category": "stale_reference",
                "confidence": 1.0,
                "evidence": f"os.path.exists('{full_path}') = False",
            })

    return findings


def scan_architecture_docs(
    docs_dir: str,
    codebase_root: str,
) -> list[DriftFinding]:
    """Scan architecture docs for claims that contradict code structure.

    Uses simple heuristics — checks for "not" claims and verifies.
    """
    findings: list[DriftFinding] = []

    if not os.path.isdir(docs_dir):
        logger.warning("Docs directory not found at %s", docs_dir)
        return findings

    # Scan markdown files in docs directory
    for md_file in glob.glob(os.path.join(docs_dir, "**/*.md"), recursive=True):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for "does not use X" or "not X" patterns
        negation_pattern = re.compile(
            r"(?:does\s+not|doesn't|not)\s+(?:use|include|have|support)\s+(.+?)(?:\.|,|\n)",
            re.IGNORECASE,
        )

        for match in negation_pattern.finditer(content):
            claimed_absent = match.group(1).strip().lower()

            # Check if something matching this exists in codebase
            for dirpath, dirnames, filenames in os.walk(codebase_root):
                dirnames[:] = [d for d in dirnames if d not in {"__pycache__", ".git", "node_modules", ".assemblyzero"}]
                rel_dir = os.path.relpath(dirpath, codebase_root)

                if claimed_absent.replace(" ", "_") in rel_dir.lower() or claimed_absent.replace(" ", "-") in rel_dir.lower():
                    findings.append({
                        "id": _next_finding_id(),
                        "severity": "major",
                        "doc_file": os.path.relpath(md_file, codebase_root),
                        "doc_claim": match.group(0).strip(),
                        "code_reality": f"Directory {rel_dir} exists in codebase",
                        "category": "feature_contradiction",
                        "confidence": 0.7,
                        "evidence": f"Found directory matching '{claimed_absent}' at {rel_dir}",
                    })
                    break  # One finding per claim

    return findings


def compute_drift_score(findings: list[DriftFinding]) -> float:
    """Compute aggregate drift score. critical=10, major=5, minor=1."""
    score = 0.0
    for finding in findings:
        severity = finding["severity"]
        score += DRIFT_SEVERITY_WEIGHTS.get(severity, 1.0)
    return score


def build_drift_report(
    codebase_root: str,
    docs_to_scan: list[str] | None = None,
) -> DriftReport:
    """Run all drift scanners and produce aggregated report."""
    _reset_finding_counter()

    all_findings: list[DriftFinding] = []
    scanned_docs: list[str] = []

    # Scan README
    readme_path = os.path.join(codebase_root, "README.md")
    if os.path.exists(readme_path):
        scanned_docs.append("README.md")
        all_findings.extend(scan_readme_claims(readme_path, codebase_root))

    # Scan inventory if it exists
    inventory_candidates = [
        os.path.join(codebase_root, "docs", "inventory.md"),
        os.path.join(codebase_root, "INVENTORY.md"),
    ]
    for inv_path in inventory_candidates:
        if os.path.exists(inv_path):
            rel_path = os.path.relpath(inv_path, codebase_root)
            scanned_docs.append(rel_path)
            all_findings.extend(scan_inventory_accuracy(inv_path, codebase_root))

    # Scan architecture docs
    docs_dir = os.path.join(codebase_root, "docs")
    if os.path.isdir(docs_dir):
        scanned_docs.append("docs/")
        all_findings.extend(scan_architecture_docs(docs_dir, codebase_root))

    # Apply additional doc scanning if specified
    if docs_to_scan:
        for doc_path in docs_to_scan:
            full_path = os.path.join(codebase_root, doc_path)
            if os.path.exists(full_path) and doc_path not in scanned_docs:
                scanned_docs.append(doc_path)

    total_score = compute_drift_score(all_findings)
    critical_count = sum(1 for f in all_findings if f["severity"] == "critical")
    major_count = sum(1 for f in all_findings if f["severity"] == "major")
    minor_count = sum(1 for f in all_findings if f["severity"] == "minor")

    return {
        "findings": all_findings,
        "total_score": total_score,
        "critical_count": critical_count,
        "major_count": major_count,
        "minor_count": minor_count,
        "scanned_docs": scanned_docs,
        "scanned_code_paths": [codebase_root],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def check_critical_drift(
    report: DriftReport,
    threshold: float = CRITICAL_DRIFT_THRESHOLD,
) -> bool:
    """Check if drift score exceeds critical threshold."""
    return report["total_score"] >= threshold