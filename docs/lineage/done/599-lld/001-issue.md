---
repo: martymcenroe/AssemblyZero
issue: 599
url: https://github.com/martymcenroe/AssemblyZero/issues/599
fetched: 2026-03-06T13:52:20.325427Z
---

# Issue #599: feat: Inventory-as-Code Node

## Objective
Automate the "Inventory Rule" by adding a mechanical node that updates \`0003-file-inventory.md\` at the end of every workflow.

## Requirements
1. **Scanning:** Automatically detect new \`.md\` files in \`docs/\`.
2. **Parsing:** Categorize files based on the taxonomy in \`0003\`.
3. **Update:** Programmatically insert/update entries in the inventory file.

## Acceptance Criteria
- [ ] No more manual inventory updates required.
- [ ] Consistent status mapping across the repo.

## Related
- ADR 0206 (Sync Architecture)