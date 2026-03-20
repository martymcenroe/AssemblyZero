---
repo: martymcenroe/AssemblyZero
issue: 838
url: https://github.com/martymcenroe/AssemblyZero/issues/838
fetched: 2026-03-20T00:45:44.982757Z
---

# Issue #838: [High] refactor: implement WorkspaceContext to eliminate path prop-drilling

Create a unified WorkspaceContext object to manage assemblyzero_root and target_repo instead of passing Path objects through every function.