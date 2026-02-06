# Verdict Analyzer Recommendations Report

**Generated:** 2026-02-01
**Template Analyzed:** `docs/templates/0102-feature-lld-template.md`
**Database:** `.assemblyzero/verdicts.db`

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Verdicts | 164 |
| Total Blocking Issues | 80 |
| APPROVED | 36 |
| BLOCKED | 128 |

### By Tier
| Tier | Count |
|------|-------|
| Tier 1 (Blocking) | 33 |
| Tier 2 (High Priority) | 47 |

### By Category
| Category | Count |
|----------|-------|
| architecture | 23 |
| quality | 23 |
| security | 10 |
| safety | 9 |
| legal | 8 |
| cost | 6 |
| observability | 1 |

---

## Recommendations for LLD Template

Found **6 recommendations** based on pattern analysis:

### 1. [add_section] Architecture & Design
- **Pattern count:** 23 occurrences
- **Suggestion:** Add Architecture & Design section to address common architecture issues
- **Rationale:** Architecture issues represent the most common category of blocking issues (tied with quality). The LLD template should explicitly prompt authors to address architectural decisions.

### 2. [add_section] Implementation Notes (Quality)
- **Pattern count:** 23 occurrences
- **Suggestion:** Add Implementation Notes section to address common quality issues
- **Rationale:** Quality issues are equally common as architecture issues. A dedicated section for implementation quality considerations would help prevent these.

### 3. [add_section] Security Considerations
- **Pattern count:** 10 occurrences
- **Suggestion:** Add Security Considerations section to address common security issues
- **Rationale:** Security issues appear frequently enough to warrant a dedicated template section.

### 4. [add_section] Safety Considerations
- **Pattern count:** 9 occurrences
- **Suggestion:** Add section to address common safety issues
- **Rationale:** Safety issues (data loss prevention, fail-safe behavior) are recurring concerns.

### 5. [add_section] Legal/Compliance
- **Pattern count:** 8 occurrences
- **Suggestion:** Add section to address common legal issues
- **Rationale:** Legal considerations (PII handling, licensing, compliance) appear regularly.

### 6. [add_section] Cost Analysis
- **Pattern count:** 6 occurrences
- **Suggestion:** Add section to address common cost issues
- **Rationale:** Cost-related issues (API costs, resource usage, quota management) need explicit consideration.

---

## Next Steps

1. Review the current LLD template to see which sections already exist
2. Prioritize which recommendations to implement (architecture + quality have highest counts)
3. Draft section content based on actual blocking issue descriptions
4. Submit template changes through governance workflow

---

## Recommendations for Issue Template

Also analyzed `docs/templates/0101-issue-template.md`:

| # | Type | Section | Pattern Count |
|---|------|---------|---------------|
| 1 | add_section | Architecture & Design | 23 |
| 2 | add_section | Implementation Notes | 23 |
| 3 | add_checklist_item | Security Considerations | 10 |
| 4 | add_section | Implementation Notes | 9 |
| 5 | add_section | Implementation Notes | 8 |
| 6 | add_section | Implementation Notes | 6 |

**Note:** The issue template already has a Security Considerations section, so the tool suggests adding a checklist item rather than a new section.

---

## Raw Category Data

To see the actual blocking issue descriptions for each category, run:
```bash
# View all blocking issues grouped by category
sqlite3 .assemblyzero/verdicts.db "SELECT category, description FROM blocking_issues ORDER BY category, tier"
```
