"""LangGraph StateGraph definition for the Janitor workflow.

Issue #94: Lu-Tze: The Janitor

Graph nodes:
  n0_sweeper  - Run probes, collect findings
  n1_fixer    - Apply auto-fixes for fixable findings
  n2_reporter - Report unfixable findings via selected backend

Conditional edges:
  n0_sweeper -> END          if no findings
  n0_sweeper -> n1_fixer     if fixable findings exist and auto_fix=True
  n0_sweeper -> n2_reporter  if only unfixable findings
  n1_fixer   -> n2_reporter  if unfixable findings remain
  n1_fixer   -> END          if all findings fixed
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from langgraph.graph import END, StateGraph

from assemblyzero.workflows.janitor import fixers as _fixers
from assemblyzero.workflows.janitor.probes import get_probes, run_probe_safe
from assemblyzero.workflows.janitor.reporter import (
    build_report_body,
    get_reporter,
)
from assemblyzero.workflows.janitor.state import (
    Finding,
    FixAction,
    JanitorState,
)


def n0_sweeper(state: JanitorState) -> dict:
    """Execute all probes in scope and collect findings."""
    probes = get_probes(state["scope"])
    probe_results = []

    for probe_name, probe_fn in probes:
        result = run_probe_safe(probe_name, probe_fn, state["repo_root"])
        probe_results.append(result)

    # Flatten all findings
    all_findings: list[Finding] = []
    for pr in probe_results:
        all_findings.extend(pr.findings)

    return {
        "probe_results": probe_results,
        "all_findings": all_findings,
    }


def n1_fixer(state: JanitorState) -> dict:
    """Apply auto-fixes for all fixable findings."""
    repo_root = state["repo_root"]
    dry_run = state["dry_run"]
    create_pr = state.get("create_pr", False)

    fixable = [f for f in state["all_findings"] if f.fixable]
    unfixable = [f for f in state["all_findings"] if not f.fixable]

    fix_actions: list[FixAction] = []

    # Group fixable findings by category
    by_category: dict[str, list[Finding]] = defaultdict(list)
    for f in fixable:
        by_category[f.category].append(f)

    for category, findings in by_category.items():
        if category == "broken_link":
            actions = _fixers.fix_broken_links(findings, repo_root, dry_run)
            fix_actions.extend(actions)
        elif category == "stale_worktree":
            actions = _fixers.fix_stale_worktrees(findings, repo_root, dry_run)
            fix_actions.extend(actions)

    # Create commits for file-modifying fixes (not worktree prunes)
    if not dry_run and not create_pr:
        # Group committed files by category
        for category, findings in by_category.items():
            if category == "broken_link":
                files = list(
                    {f.file_path for f in findings if f.file_path}
                )
                if files:
                    msg = _fixers.generate_commit_message(
                        category, len(findings), files
                    )
                    _fixers.create_fix_commit(repo_root, category, files, msg)

    if not dry_run and create_pr:
        branch_name = f"janitor/fixes-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}"
        msg = "chore: janitor auto-fixes (ref #94)"
        pr_url = _fixers.create_fix_pr(repo_root, branch_name, msg)
        if pr_url:
            # Add PR URL info (will be picked up by reporter if needed)
            pass

    return {
        "fix_actions": fix_actions,
        "unfixable_findings": unfixable,
    }


def n2_reporter(state: JanitorState) -> dict:
    """Report unfixable findings via the configured reporter backend."""
    reporter = get_reporter(state["reporter_type"], state["repo_root"])

    # When routing skips fixer (sweep → reporter), unfixable_findings
    # won't be populated.  Fall back to extracting from all_findings.
    unfixable = state.get("unfixable_findings") or []
    if not unfixable:
        unfixable = [f for f in state.get("all_findings", []) if not f.fixable]

    body = build_report_body(
        unfixable,
        state.get("fix_actions") or [],
        state.get("probe_results") or [],
    )

    # Determine max severity
    max_severity = "info"
    for f in unfixable:
        if f.severity == "critical":
            max_severity = "critical"
            break
        if f.severity == "warning":
            max_severity = "warning"

    existing = reporter.find_existing_report()
    if existing:
        report_url = reporter.update_report(existing, body, max_severity)  # type: ignore[arg-type]
    else:
        report_url = reporter.create_report("Janitor Report", body, max_severity)  # type: ignore[arg-type]

    return {
        "report_url": report_url,
        "exit_code": 1,  # Unfixable issues remain
    }


def route_after_sweep(state: JanitorState) -> str:
    """Conditional routing after n0_sweeper completes."""
    all_findings = state.get("all_findings", [])
    if not all_findings:
        return "__end__"

    has_fixable = any(f.fixable for f in all_findings)
    auto_fix = state.get("auto_fix", False)

    if has_fixable and auto_fix:
        return "n1_fixer"

    return "n2_reporter"


def route_after_fix(state: JanitorState) -> str:
    """Conditional routing after n1_fixer completes."""
    unfixable = state.get("unfixable_findings", [])
    if unfixable:
        return "n2_reporter"
    return "__end__"


def build_janitor_graph() -> StateGraph:
    """Build and compile the LangGraph state graph for the janitor workflow."""
    graph = StateGraph(JanitorState)

    # Add nodes
    graph.add_node("n0_sweeper", n0_sweeper)
    graph.add_node("n1_fixer", n1_fixer)
    graph.add_node("n2_reporter", n2_reporter)

    # Set entry point
    graph.set_entry_point("n0_sweeper")

    # Add conditional edge after sweeper
    graph.add_conditional_edges(
        "n0_sweeper",
        route_after_sweep,
        {
            "n1_fixer": "n1_fixer",
            "n2_reporter": "n2_reporter",
            "__end__": END,
        },
    )

    # Add conditional edge after fixer
    graph.add_conditional_edges(
        "n1_fixer",
        route_after_fix,
        {
            "n2_reporter": "n2_reporter",
            "__end__": END,
        },
    )

    # Reporter always goes to END
    graph.add_edge("n2_reporter", END)

    return graph.compile()