```python
"""Hourglass state machine — orchestrates DEATH's reconciliation protocol.

Issue #535: LangGraph StateGraph implementing the age transition workflow.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.death.age_meter import (
    check_meter_threshold,
    compute_age_meter,
    fetch_closed_issues_since,
    load_age_meter_state,
    save_age_meter_state,
)
from assemblyzero.workflows.death.constants import (
    AGE_METER_STATE_PATH,
    CRITICAL_DRIFT_THRESHOLD,
    DEFAULT_THRESHOLD,
    HISTORY_PATH,
)
from assemblyzero.workflows.death.drift_scorer import (
    build_drift_report,
    check_critical_drift,
)
from assemblyzero.workflows.death.models import (
    AgeMeterState,
    HourglassState,
    ReconciliationReport,
)
from assemblyzero.workflows.death.reconciler import (
    archive_old_age,
    build_reconciliation_report,
    chronicle,
    harvest,
    walk_the_field,
)

logger = logging.getLogger(__name__)


def _node_init(state: HourglassState) -> dict[str, Any]:
    """Init node: load age meter state, log trigger."""
    trigger = state["trigger"]
    if trigger == "meter":
        logger.info("THE SAND HAS RUN OUT.")
    elif trigger == "summon":
        logger.info("DEATH HAS BEEN SUMMONED.")
    elif trigger == "critical_drift":
        logger.info("THE DOCUMENTS LIE. DEATH ARRIVES UNBIDDEN.")

    age_meter = load_age_meter_state()
    if age_meter is None:
        age_meter = {
            "current_score": 0,
            "threshold": DEFAULT_THRESHOLD,
            "last_death_visit": None,
            "last_computed": datetime.now(timezone.utc).isoformat(),
            "weighted_issues": [],
            "age_number": 1,
        }

    return {"step": "walk_field", "age_meter": age_meter}


def _node_walk_field(state: HourglassState) -> dict[str, Any]:
    """Walk field node: run drift scanners."""
    errors = list(state.get("errors", []))
    try:
        codebase_root = state["codebase_root"]
        drift_report = build_drift_report(codebase_root)
    except Exception as exc:
        logger.error("Walk field failed: %s", exc)
        errors.append(f"walk_field: {exc}")
        drift_report = {
            "findings": [],
            "total_score": 0.0,
            "critical_count": 0,
            "major_count": 0,
            "minor_count": 0,
            "scanned_docs": [],
            "scanned_code_paths": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {"step": "harvest", "drift_report": drift_report, "errors": errors}


def _node_harvest(state: HourglassState) -> dict[str, Any]:
    """Harvest node: produce reconciliation actions."""
    errors = list(state.get("errors", []))
    drift_report = state.get("drift_report")
    mode = state["mode"]
    dry_run = mode == "report"

    if drift_report is None:
        errors.append("harvest: no drift report available")
        return {"step": "archive", "errors": errors}

    try:
        codebase_root = state["codebase_root"]
        actions = walk_the_field(codebase_root, drift_report)
        actions = harvest(actions, codebase_root, dry_run=dry_run)

        age_meter = state["age_meter"]
        report = build_reconciliation_report(
            trigger=state["trigger"],
            trigger_details=f"DEATH triggered by {state['trigger']}",
            drift_report=drift_report,
            actions=actions,
            mode=mode,
            age_number=age_meter["age_number"],
        )
    except Exception as exc:
        logger.error("Harvest failed: %s", exc)
        errors.append(f"harvest: {exc}")
        report = None

    return {"step": "archive", "reconciliation_report": report, "errors": errors}


def _route_after_harvest(state: HourglassState) -> str:
    """Route: 'archive' if report mode or confirmed, 'complete' if reaper declined."""
    if state["mode"] == "report":
        return "archive"
    if state.get("confirmed", False):
        return "archive"
    return "complete"


def _node_archive(state: HourglassState) -> dict[str, Any]:
    """Archive node: move old artifacts."""
    errors = list(state.get("errors", []))
    mode = state["mode"]
    dry_run = mode == "report"
    report = state.get("reconciliation_report")

    if report and report.get("actions"):
        try:
            codebase_root = state["codebase_root"]
            archive_old_age(report["actions"], codebase_root, dry_run=dry_run)
        except Exception as exc:
            logger.error("Archive failed: %s", exc)
            errors.append(f"archive: {exc}")

    return {"step": "chronicle", "errors": errors}


def _node_chronicle(state: HourglassState) -> dict[str, Any]:
    """Chronicle node: update README and wiki."""
    errors = list(state.get("errors", []))
    mode = state["mode"]
    dry_run = mode == "report"
    report = state.get("reconciliation_report")

    if report and report.get("actions"):
        try:
            codebase_root = state["codebase_root"]
            chronicle(report["actions"], codebase_root, dry_run=dry_run)
        except Exception as exc:
            logger.error("Chronicle failed: %s", exc)
            errors.append(f"chronicle: {exc}")

    return {"step": "rest", "errors": errors}


def _node_rest(state: HourglassState) -> dict[str, Any]:
    """Rest node: reset meter, increment age, record history."""
    age_meter = {**state["age_meter"]}
    old_age = age_meter["age_number"]

    # Reset meter
    age_meter["current_score"] = 0
    age_meter["age_number"] = old_age + 1
    age_meter["last_death_visit"] = datetime.now(timezone.utc).isoformat()
    age_meter["weighted_issues"] = []

    # Save updated meter
    try:
        save_age_meter_state(age_meter)
    except Exception as exc:
        logger.error("Failed to save age meter state: %s", exc)

    # Append to history
    try:
        history_path = HISTORY_PATH
        history: list[dict[str, Any]] = []
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)

        report = state.get("reconciliation_report")
        entry = {
            "age_number": old_age,
            "trigger": state["trigger"],
            "trigger_details": f"DEATH triggered by {state['trigger']}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "findings_count": len(report["drift_report"]["findings"]) if report else 0,
            "actions_count": len(report["actions"]) if report else 0,
            "mode": state["mode"],
        }
        history.append(entry)

        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as exc:
        logger.error("Failed to update history: %s", exc)

    logger.info("THE NEW AGE BEGINS. Age %d.", age_meter["age_number"])

    return {"step": "complete", "age_meter": age_meter}


def _node_complete(state: HourglassState) -> dict[str, Any]:
    """Complete node: DEATH departs."""
    return {"step": "complete"}


def create_hourglass_graph() -> StateGraph:
    """Create the LangGraph state machine for the Hourglass Protocol."""
    graph = StateGraph(HourglassState)

    graph.add_node("init", _node_init)
    graph.add_node("walk_field", _node_walk_field)
    graph.add_node("harvest", _node_harvest)
    graph.add_node("archive", _node_archive)
    graph.add_node("chronicle", _node_chronicle)
    graph.add_node("rest", _node_rest)
    graph.add_node("complete", _node_complete)

    graph.set_entry_point("init")
    graph.add_edge("init", "walk_field")
    graph.add_edge("walk_field", "harvest")
    graph.add_conditional_edges("harvest", _route_after_harvest, {"archive": "archive", "complete": "complete"})
    graph.add_edge("archive", "chronicle")
    graph.add_edge("chronicle", "rest")
    graph.add_edge("rest", "complete")
    graph.add_edge("complete", END)

    return graph


def should_death_arrive(
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> tuple[bool, str, str]:
    """Check all three triggers. Returns (should_trigger, trigger_type, details)."""
    # Check critical drift first (highest priority)
    drift_score = 0.0
    try:
        drift_report = build_drift_report(codebase_root)
        drift_score = drift_report["total_score"]
        if check_critical_drift(drift_report):
            return (
                True,
                "critical_drift",
                f"Drift score {drift_report['total_score']} exceeds critical threshold {CRITICAL_DRIFT_THRESHOLD}.",
            )
    except Exception as exc:
        logger.warning("Drift check failed: %s", exc)

    # Check meter threshold
    try:
        state = load_age_meter_state()
        if state is None:
            state = {
                "current_score": 0,
                "threshold": DEFAULT_THRESHOLD,
                "last_death_visit": None,
                "last_computed": datetime.now(timezone.utc).isoformat(),
                "weighted_issues": [],
                "age_number": 1,
            }

        issues = fetch_closed_issues_since(
            repo=repo,
            since=state.get("last_death_visit"),
            github_token=github_token,
        )
        state = compute_age_meter(issues, state)
        save_age_meter_state(state)

        if check_meter_threshold(state):
            return (
                True,
                "meter",
                f"Age meter reached {state['current_score']}/{state['threshold']}. THE SAND HAS RUN OUT.",
            )

        return (
            False,
            "",
            f"No triggers active. Meter: {state['current_score']}/{state['threshold']}. Drift: {drift_score}/{CRITICAL_DRIFT_THRESHOLD}",
        )
    except Exception as exc:
        logger.warning("Meter check failed: %s", exc)
        return (False, "", f"Trigger check failed: {exc}")


def run_death(
    mode: Literal["report", "reaper"],
    trigger: Literal["meter", "summon", "critical_drift"],
    codebase_root: str,
    repo: str,
    github_token: str | None = None,
) -> ReconciliationReport:
    """Execute the full DEATH reconciliation protocol."""
    age_meter = load_age_meter_state()
    if age_meter is None:
        age_meter = {
            "current_score": 0,
            "threshold": DEFAULT_THRESHOLD,
            "last_death_visit": None,
            "last_computed": datetime.now(timezone.utc).isoformat(),
            "weighted_issues": [],
            "age_number": 1,
        }

    initial_state: HourglassState = {
        "trigger": trigger,
        "mode": mode,
        "codebase_root": codebase_root,
        "age_meter": age_meter,
        "drift_report": None,
        "reconciliation_report": None,
        "step": "init",
        "errors": [],
        "confirmed": mode == "report",  # Report mode auto-confirms
    }

    graph = create_hourglass_graph()
    compiled = graph.compile()
    result = compiled.invoke(initial_state)

    report = result.get("reconciliation_report")
    if report is None:
        # Build minimal report on failure
        report = build_reconciliation_report(
            trigger=trigger,
            trigger_details=f"DEATH triggered by {trigger} but failed",
            drift_report={
                "findings": [],
                "total_score": 0.0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "scanned_docs": [],
                "scanned_code_paths": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            actions=[],
            mode=mode,
            age_number=age_meter["age_number"],
        )

    return report
```
