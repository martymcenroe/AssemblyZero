# Implementation Spec: Feature: Inventory-as-Code Node

> Generated from [Issue #599](../issues/599)

---

## Overview

Automate the "Inventory Rule" by adding a mechanical node that scans `docs/`, categorizes `.md` files, and updates `0003-file-inventory.md` at the end of every workflow.

**Objective:** Automatically maintain an accurate, categorized markdown table of all documentation files without overwriting human-modified statuses.

**Success Criteria:** Detects all nested `.md` files in `docs/`, correctly maps subdirectories to categories, preserves manual status changes, and safely updates the markdown file between bounding comments. Must fail open (not crash the workflow) if file errors occur.

---

## Related

- [Issue #599](../issues/599)
- [LLD](../docs/lld/active/LLD-599.md)
