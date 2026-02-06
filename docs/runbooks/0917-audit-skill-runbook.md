# 0917 - Audit Skill Runbook

**Purpose:** How to use the `/audit` skill to run the 08xx audit suite.

---

## Quick Reference

| Command | What It Does |
|---------|--------------|
| `/audit --help` | Show help and available options |
| `/audit` | Run all standard audits (excludes ultimate tier) |
| `/audit 0809` | Run single audit by number |
| `/audit 0801 0809 0816` | Run multiple specific audits |
| `/audit --ultimate` | Run all audits INCLUDING expensive ones |
| `/audit --deep` | Run with web search for external research |
| `/audit --deep 0801` | Run specific audit with web search |

---

## When to Use

| Scenario | Command | Cost |
|----------|---------|------|
| Weekly hygiene check | `/audit 0816 0834 0838` | Low (Haiku) |
| Monthly governance | `/audit 0809 0817` | Medium (Sonnet) |
| Quarterly deep audit | `/audit --ultimate --deep` | High (Opus) |
| Pre-release security | `/audit 0801 0802` | High (Opus) |
| After incident | `/audit 0811` | High (Opus) |

---

## Workflow

### 1. Start a Session

```
/onboard --quick
```

Load project context before running audits.

### 2. Run the Audit

Choose based on your needs:

**Quick weekly check:**
```
/audit 0816 0834 0838
```

**Full standard suite:**
```
/audit
```

**Everything including expensive audits:**
```
/audit --ultimate
```

### 3. Review Results

Results are saved to: `docs/audit-results/YYYY-MM-DD.md`

The output includes:
- **PASS** - No issues found
- **FAIL** - Issues found, GitHub issues created
- **WARN** - Potential issues, review recommended
- **SKIP** - Audit skipped (missing prerequisites)

### 4. Address Findings

For each FAIL:
1. Review the created GitHub issue
2. Decide: fix now or add to backlog
3. If fixing now, create a worktree

For each WARN:
1. Review the finding
2. Decide if it's a real problem
3. Either fix or document as acceptable risk

### 5. End Session

```
/cleanup
```

---

## Audit Tiers

### Continuous (run automatically)
- 0803 Code Quality (CI)
- 0836 Gitignore Consistency
- 0837 README Compliance

### Weekly (hygiene)
- 0816 Permission Permissiveness
- 0834 Worktree Hygiene
- 0838 Broken References

### Monthly (governance)
- 0809 Agentic AI Governance
- 0817 AssemblyZero Self-Audit
- 0832 Cost Optimization
- 0847 Implementation Completeness

### Quarterly (deep)
- 0805 License Compliance
- 0806 Bias & Fairness
- 0808 AI Safety
- 0812 AI Supply Chain
- 0814 Horizon Scanning

### Ultimate (expensive, explicit only)
- 0801 Security (OWASP)
- 0802 Privacy (GDPR)
- 0810 AI Management System (ISO 42001)
- 0833 Gitignore Encryption Review

---

## Cost Optimization

| Strategy | Savings |
|----------|---------|
| Run specific audits, not full suite | 50-80% |
| Skip `--deep` unless needed | 30-50% |
| Never run `--ultimate` routinely | 60-70% |
| Use weekly/monthly schedule | Predictable budget |

**Recommended weekly routine:**
```
/audit 0816 0834 0838
```
~$0.50-1.00 (Haiku-level audits)

**Recommended monthly routine:**
```
/audit 0809 0817 0832
```
~$2-5 (Sonnet-level audits)

---

## Troubleshooting

### "Audit not found"
Check the audit number exists in `docs/audits/08xx-*.md`

### "Missing prerequisites"
Some audits require:
- Git repository initialized
- GitHub CLI authenticated (`gh auth status`)
- Poetry environment active

### "Audit takes too long"
- Use `--timeout 300` for complex audits
- Or run individual audits instead of full suite

### "Results file not created"
Check write permissions on `docs/audit-results/`

---

## See Also

- [0800 - Audit Index](../audits/0800-audit-index.md) - All audits listed
- [Issue #343](https://github.com/martymcenroe/AssemblyZero/issues/343) - Standalone CLI runner (planned)
- `.claude/commands/audit.md` - Skill implementation

---

## History

| Date | Change |
|------|--------|
| 2026-02-05 | Created. Documents /audit skill usage. |
