# Agent Prohibited Actions

Rules defining what AI agents must never do, regardless of user instructions.

## 1. Core Prohibitions

### 1.1 Git History Destruction

**NEVER execute these commands:**

| Command | Risk Level | Alternative |
|---------|------------|-------------|
| `git reset --hard` | CRITICAL | `git revert <commit>` |
| `git push --force` | CRITICAL | `git push --force-with-lease` (with approval) |
| `git clean -fd` | HIGH | `git clean -n` (dry run first) |
| `git branch -D` (on shared) | HIGH | `git branch -d` (safe delete) |

### 1.2 Secret Exposure

**NEVER:**
- Output environment variables to logs/files
- Commit files containing secrets
- Execute `env`, `printenv`, or equivalent
- Store credentials in code

### 1.3 Arbitrary Code Execution

**NEVER:**
- Use `eval()` with untrusted input
- Execute code from external URLs
- Run commands with user-provided arguments without validation

### 1.4 Bypassing Lock Files

**NEVER:**
- Use `pip install` directly (use `poetry add`)
- Modify `requirements.txt` manually
- Skip dependency pinning

## 2. Issue Closure Rules

### 2.1 No Premature Closure

AI agents must NEVER close issues until:
1. Human testing is complete
2. User explicitly confirms success
3. All acceptance criteria are met

**Workflow:**
```
AI: Commits with (ref #ID)
AI: "Ready for testing in commit XXXXXX"
Human: Tests the implementation
Human: "Confirmed working"
AI: May now close issue
```

### 2.2 Documentation-Only Exception

For pure documentation changes (no code), immediate closure is acceptable.

## 3. Communication Rules

### 3.1 No False Completion

**NEVER claim:**
- "Done" when work is partial
- "Tested" when only implemented
- "Working" without verification

### 3.2 No Suppressed Errors

**ALWAYS report:**
- Unexpected errors
- Failing tests
- Dependency conflicts
- Security warnings

## 4. Safe Alternatives

| Instead of... | Use... |
|---------------|--------|
| `git reset --hard` | `git revert` or `git stash` |
| `pip install pkg` | `poetry add pkg` |
| `rm -rf directory` | `git clean -n` then confirm |
| Direct issue close | Wait for human confirmation |
| Ignoring test failures | Report and investigate |

## 5. Enforcement

### 5.1 Pre-execution Checks

Before executing any command:
1. Check against prohibited list
2. Verify command is scoped appropriately
3. Consider side effects

### 5.2 Permission Boundaries

Agents should operate within:
- Project directory only
- Documented permission patterns
- Approved tool configurations

## 6. Rationale

### Why These Rules?

1. **Irrecoverability:** Some actions cannot be undone
2. **Collaboration:** Shared repos require coordination
3. **Trust:** Users trust agents not to cause harm
4. **Audit Trail:** Actions should be traceable

### The Meta-Rule

When in doubt, ask. It's always better to:
- Request clarification
- Propose a plan for approval
- Use the safer alternative

---

*Source: AssemblyZero/docs/standards/agent-prohibited-actions.md*
*Projects may extend with additional project-specific prohibitions.*
