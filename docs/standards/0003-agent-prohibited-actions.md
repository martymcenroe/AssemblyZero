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

### 2.1 Complete Delivery Required

There is no such thing as partial issue completion in this environment. AI agents are required to do all the work to fulfill an issue.
1. All code changes and tests must be completed.
2. The agent must use `Closes #N` in all commits related to the task.
3. The naked `(#N)` and `(ref #N)` formats are permanently banned.

**Workflow:**
```
AI: Completes all implementation and tests
AI: Commits with (Closes #ID)
AI: Creates PR and follows the PR Merge Protocol
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

### 5.3 Token Restrictions

Agents MUST use Fine-Grained PATs, not classic tokens. The following flags are prohibited because the restricted token will reject them:

| Command | Why Prohibited |
|---------|----------------|
| `gh pr merge --admin` | Bypasses branch protection |
| `gh api -X DELETE .../protection` | Removes branch rules |
| `gh api .../actions/secrets` | Accesses repo secrets |

See `docs/runbooks/0925-agent-token-setup.md` for token creation and rotation.

## 6. Quota Exhaustion: Fail Fast

When Claude Max quota is exhausted or Anthropic API returns billing errors (402, 429 with billing context), agents MUST:

1. **Stop immediately** — do not retry, do not fall back to other models
2. **Report the error** — include the `[NON-RETRYABLE]` prefix so the user knows
3. **Suggest `--resume`** — the workflow can continue after the cooldown window

Errors matching `is_non_retryable_error()` patterns (`"usage limit"`, `"usage has been exhausted"`, `"wait until"`) are classified as billing errors and bypass all retry logic.

See [Cost Management](../wiki/Cost-Management.md) for the full quota detection flow.

## 7. Rationale

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
