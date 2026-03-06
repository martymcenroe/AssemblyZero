---
repo: martymcenroe/AssemblyZero
issue: 598
url: https://github.com/martymcenroe/AssemblyZero/issues/598
fetched: 2026-03-06T00:52:25.730105Z
---

# Issue #598: feat: Permissible Command Middleware

## Objective
Implement a mechanical "firewall" for shell commands to prevent agents from using dangerous or unauthorized flags.

## Requirements
1. **Deny List:** Hard-block substrings: \`--admin\`, \`--force\`, \`-D\`, \`--hard\`.
2. **Implementation:** Create a utility in \`assemblyzero/utils/shell.py\` that all workflow nodes must use.
3. **Action:** Raise \`SecurityException\` if a blocked flag is detected.

## Acceptance Criteria
- [ ] Nodes are incapable of executing \`gh pr merge --admin\` even with owner tokens.
- [ ] Unit tests verify blocking of all prohibited flags.

## Related
- #595 (Restricted Auth)