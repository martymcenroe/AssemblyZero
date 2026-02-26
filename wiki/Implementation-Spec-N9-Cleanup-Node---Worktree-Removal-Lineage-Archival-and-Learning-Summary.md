# Implementation Spec: N9 Cleanup Node - Worktree Removal, Lineage Archival, and Learning Summary

> Generated from [Issue #180](../issues/180)

---

## Overview

Add an N9_cleanup node to the TDD testing workflow that removes worktrees after PR merge, archives lineage from active/ to done/, and generates a deterministic learning summary for future learning agent consumption.

**Objective:** Automate post-implementation cleanup (worktree removal, lineage archival, learning summary generation) as a workflow node.

**Success Criteria:** N9 node added to graph; worktree removed only when PR merged; lineage archived conditionally; learning summary generated; all errors handled gracefully without failing the workflow.

---

## Key Features

- Add cleanup node
- Archive lineage

---

## Related

- [Issue #180](../issues/180)
- [LLD](../docs/lld/active/LLD-180.md)
