# 0845 - Terminology Consistency Audit

**Status:** STUB - Implementation pending
**Category:** Documentation Health
**Frequency:** On rename, quarterly
**Auto-Fix:** Yes (search-replace with confirmation)

---

## Purpose

Enforce consistent terminology across the codebase. When we rename "sentinel" to "unleashed", every reference must update. Stale terms cause confusion and break searches.

---

## Checks

### 1. Deprecated Term Detection

Maintain a deprecation registry:

| Old Term | New Term | Deprecated Date | Grace Period |
|----------|----------|-----------------|--------------|
| sentinel | unleashed | 2026-01-20 | 7 days |
| config | settings | 2026-01-15 | expired |
| slash command | skill | 2026-01-10 | expired |

**Suggested implementation:**
```bash
# For each deprecated term
grep -r "sentinel" --include="*.md" --include="*.py" docs/ tools/
# Flag any matches after grace period
```

### 2. Inconsistent Naming Patterns

Detect mixed conventions:
- `kebab-case` vs `snake_case` vs `camelCase` in same context
- `Audit` vs `audit` vs `AUDIT` for same concept
- `AgentOS` vs `agentos` vs `agent-os`

### 3. Acronym Consistency

| Acronym | Expanded | Used Consistently? |
|---------|----------|-------------------|
| LLD | Low-Level Design | Check all uses |
| ADR | Architecture Decision Record | Check all uses |
| PTY | Pseudo-Terminal | Check all uses |

First use in a document should expand, subsequent can abbreviate.

### 4. Cross-File Naming Conflicts

Same concept, different names in different files:
- `docs/index.md` calls it "Command Reference"
- `CLAUDE.md` calls it "Skill Reference"
- `.claude/commands/` implies "commands"

### 5. Code-Doc Terminology Mismatch

Code uses `UserManager`, docs say `UserService`. Either:
- Docs are stale
- Code was renamed and docs forgot
- Intentional abstraction (should be noted)

---

## Deprecation Registry

Location: `docs/terminology-registry.json` (proposed)

```json
{
  "deprecated": [
    {
      "old": "sentinel",
      "new": "unleashed",
      "date": "2026-01-20",
      "reason": "Migrated to separate repo",
      "exceptions": ["historical reports", "audit results"]
    }
  ],
  "canonical": {
    "the CLI tool": "Claude Code",
    "the agent config system": "AgentOS",
    "user-level commands": "skills"
  }
}
```

---

## Auto-Fix Capability

1. **Search-replace** deprecated terms (with confirmation)
2. **Cannot auto-fix** ambiguous cases (human decides)
3. **Generate report** of all violations for batch review

---

## Suggestions for Future Implementation

1. **Glossary Generation**: Auto-generate glossary from first-use definitions.

2. **Spell-Check Integration**: Catch typos that create phantom terms.

3. **Context-Aware Replacement**: "config" in Python code vs "config" in docs may need different handling.

4. **Migration Scripts**: When renaming, generate `sed` script for batch replacement.

5. **Historical Exception Tagging**: Mark historical docs as exempt from current terminology rules.

6. **Term Frequency Analysis**: Which terms are used most? Are there near-duplicates suggesting consolidation?

---

## Audit Record

| Date | Auditor | Findings | Issues Created |
|------|---------|----------|----------------|
| - | - | STUB - Not yet implemented | - |

---

## Related

- [0838 - Broken References](0838-audit-broken-references.md)
- [0844 - File Inventory](0844-audit-file-inventory.md)
