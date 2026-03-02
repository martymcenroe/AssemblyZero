

```python
"""Reconciliation engine — walks codebase, compares docs, produces report or fixes.

Issue #535: Produces ReconciliationActions from DriftFindings,
generates ADRs, archives stale docs, updates README.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone

from assemblyzero.workflows.death.constants import ADR_OUTPUT_PATH
from assemblyzero.workflows.death.models import (
    DriftFinding,
    DriftReport,
    ReconciliationAction,
    ReconciliationReport,
)

logger = logging.getLogger(__name__)

# Mapping from drift category to reconciliation action type
_CATEGORY_TO_ACTION: dict[str, str] = {
    "count_mismatch": "update_count",
    "feature_contradiction": "update_description",
    "missing_component": "add_section",
    "stale_reference": "remove_section",
    "architecture_drift": "create_adr",
}


def walk_the_field(
    codebase_root: str,
    drift_report: DriftReport,
) -> list[ReconciliationAction]:
    """Phase 1: Walk codebase, compare docs against reality, produce actions."""
    actions: list[ReconciliationAction] = []

    for finding in drift_report["findings"]:
        action_type = _CATEGORY_TO_ACTION.get(finding["category"], "update_description")

        action: ReconciliationAction = {
            "target_file": finding["doc_file"],
            "action_type": action_type,
            "description": f"Fix {finding['category']}: {finding['doc_claim']} -> {finding['code_reality']}",
            "old_content": finding["doc_claim"],
            "new_content": finding["code_reality"],
            "drift_finding_id": finding["id"],
        }
        actions.append(action)

    return actions


def harvest(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 2: Write ADRs and diagrams.

    dry_run=True returns actions without writing files.
    dry_run=False writes files to disk.
    """
    if dry_run:
        logger.info("Harvest phase: dry_run=True, no files written.")
        return actions

    for action in actions:
        if action["action_type"] == "create_adr" and action["new_content"]:
            target = os.path.join(codebase_root, action["target_file"])
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(action["new_content"])
                logger.info("Wrote ADR to %s", target)
            except OSError as exc:
                logger.error("Failed to write %s: %s", target, exc)

    return actions


def archive_old_age(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 3: Move old artifacts to legacy/done."""
    if dry_run:
        logger.info("Archive phase: dry_run=True, no files moved.")
        return actions

    for action in actions:
        if action["action_type"] == "archive":
            source = os.path.join(codebase_root, action["target_file"])
            legacy_dir = os.path.join(codebase_root, "docs", "legacy")
            os.makedirs(legacy_dir, exist_ok=True)
            dest = os.path.join(legacy_dir, os.path.basename(action["target_file"]))
            try:
                if os.path.exists(source):
                    shutil.move(source, dest)
                    logger.info("Archived %s -> %s", source, dest)
            except OSError as exc:
                logger.error("Failed to archive %s: %s", source, exc)

    return actions


def chronicle(
    actions: list[ReconciliationAction],
    codebase_root: str,
    dry_run: bool = True,
) -> list[ReconciliationAction]:
    """Phase 4: Update README and wiki to describe current reality."""
    if dry_run:
        logger.info("Chronicle phase: dry_run=True, no files updated.")
        return actions

    for action in actions:
        if action["action_type"] in ("update_count", "update_description"):
            target = os.path.join(codebase_root, action["target_file"])
            if os.path.exists(target) and action["old_content"] and action["new_content"]:
                try:
                    with open(target, "r", encoding="utf-8") as f:
                        content = f.read()
                    updated = content.replace(action["old_content"], action["new_content"])
                    if updated != content:
                        with open(target, "w", encoding="utf-8") as f:
                            f.write(updated)
                        logger.info("Updated %s", target)
                except OSError as exc:
                    logger.error("Failed to update %s: %s", target, exc)

    return actions


def generate_adr(
    finding: DriftFinding,
    actions: list[ReconciliationAction],
    adr_template_path: str,
    output_dir: str,
    dry_run: bool = True,
) -> str | None:
    """Generate ADR from architecture drift finding.

    Returns:
        dry_run=True: ADR content string, or None if non-qualifying.
        dry_run=False: File path of written ADR, or None if non-qualifying.
    """
    if finding["category"] != "architecture_drift":
        return None

    # Build ADR content
    related_actions = [a for a in actions if a["drift_finding_id"] == finding["id"]]
    actions_text = "\n".join(
        f"- {a['description']}" for a in related_actions
    ) or "- No specific file changes identified"

    content = f"""# ADR 0015: Age Transition Protocol

## Status

Accepted

## Context

Documentation claimed '{finding["doc_claim"]}' but {finding["code_reality"]}.

Evidence: {finding["evidence"]}

Severity: {finding["severity"]} (confidence: {finding["confidence"]})

## Decision

Update documentation to reflect current codebase reality. The age transition protocol (Hourglass Protocol, Issue #535) detected this architectural drift and triggered reconciliation.

Related actions:
{actions_text}

## Alternatives Considered

1. **Ignore the drift** — Documentation would continue to diverge from reality.
2. **Revert the code** — The code change was intentional and provides value.
3. **Update documentation** — Selected. Align docs with the system as it exists.

## Consequences

- Documentation accurately reflects codebase architecture
- Future readers will not be misled by stale architectural descriptions
- The Hourglass Protocol age counter advances, resetting drift accumulation
"""

    if dry_run:
        return content

    # Write to disk
    output_path = os.path.join(output_dir, "0015-age-transition-protocol.md")
    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("ADR written to %s", output_path)
    return output_path


def build_reconciliation_report(
    trigger: str,
    trigger_details: str,
    drift_report: DriftReport,
    actions: list[ReconciliationAction],
    mode: str,
    age_number: int,
) -> ReconciliationReport:
    """Assemble the full reconciliation report."""
    total_findings = len(drift_report["findings"])
    critical = drift_report["critical_count"]
    major = drift_report["major_count"]
    minor = drift_report["minor_count"]

    parts = []
    if critical:
        parts.append(f"{critical} critical")
    if major:
        parts.append(f"{major} major")
    if minor:
        parts.append(f"{minor} minor")
    severity_summary = ", ".join(parts) if parts else "none"

    summary = (
        f"DEATH found {total_findings} drift finding(s) ({severity_summary}). "
        f"{len(actions)} reconciliation action(s) {'proposed' if mode == 'report' else 'applied'}."
    )

    return {
        "age_number": age_number,
        "trigger": trigger,
        "trigger_details": trigger_details,
        "drift_report": drift_report,
        "actions": actions,
        "mode": mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
    }
```
