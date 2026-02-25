# Implementation Spec: Cross-Project Metrics Aggregation for AssemblyZero Usage Tracking

> Generated from [Issue #333](../issues/333)

---

## Overview

Build a cross-project metrics aggregation system that collects issue velocity, workflow usage, and Gemini review outcomes across all repositories using AssemblyZero governance workflows, outputting unified metrics dashboards as JSON files.

**Objective:** Produce a single CLI-driven pipeline that reads a config of tracked repos, queries GitHub API for each, aggregates per-repo and cross-project metrics, and writes dated JSON output with a human-readable summary.

**Success Criteria:** All 34 test scenarios (T010–T340) pass with ≥95% coverage; `python tools/collect_cross_project_metrics.py --config ./tracked_repos.json` produces valid JSON output and stdout summary; partial repo failures degrade gracefully.

---

## Related

- [Issue #333](../issues/333)
- [LLD](../docs/lld/active/LLD-333.md)
