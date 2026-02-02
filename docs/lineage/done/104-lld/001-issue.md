# Issue #104: feat: Verdict Analyzer - Template Improvement from Gemini Verdicts

# Plan: Verdict Analyzer - Template Improvement from Gemini Verdicts

## Overview

A generic Python CLI that analyzes Gemini governance verdicts across repos, extracts patterns from blocking issues, and improves templates. First use case: LLD template (0102).

**Immediate goal:** Get the LLD template improved NOW so you can blast through 5 LLD creations tonight.

---

## Core Features

| Feature | Description |
|---------|-------------|
| `--scan` | Discover and parse verdicts from all repos, store in SQLite |
| `--recommend` | Generate recommendations for a template based on patterns |
| `--auto` | Apply recommendations directly to the template |
| `--stats` | Show pattern frequencies and blocking categories |
| `--export` | Export for future RAG integration |

---

## SQLite Schema (RAG-ready)

```sql
-- Track examined verdicts (avoids re-processing)
CREATE TABLE verdicts (
    id INTEGER PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    repo TEXT NOT NULL,
    issue_id TEXT,
    verdict_type TEXT CHECK (verdict_type IN ('lld', 'issue')),
    decision TEXT CHECK (decision IN ('APPROVED', 'BLOCK', 'REVISE')),
    raw_content TEXT NOT NULL,
    content_hash TEXT NOT NULL,  -- SHA256 for change detection
    first_seen_at TEXT NOT NULL,
    last_analyzed_at TEXT NOT NULL
);

-- Extracted blocking issues with template section mapping
CREATE TABLE blocking_issues (
    id INTEGER PRIMARY KEY,
    verdict_id INTEGER REFERENCES verdicts(id),
    tier INTEGER CHECK (tier IN (1, 2, 3)),
    category TEXT NOT NULL,  -- Security, Safety, Cost, Legal, Quality, Architecture
    description TEXT NOT NULL,
    template_section TEXT,   -- Matched section from 0102
    UNIQUE(verdict_id, category, description)
);

-- Aggregated patterns for recommendations
CREATE TABLE pattern_stats (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    description_pattern TEXT NOT NULL,  -- Normalized
    occurrence_count INTEGER NOT NULL,
    template_section TEXT,
    UNIQUE(category, description_pattern)
);
```

**DB Location:** `~/.agentos/verdicts.db` (git-ignored, RAG-exportable)

---

## Files to Create

| File | Purpose |
|------|---------|
| `tools/verdict-analyzer.py` | Main CLI entry point |
| `tools/verdict_analyzer/__init__.py` | Package init |
| `tools/verdict_analyzer/parser.py` | Parse verdict markdown (LLD + Issue formats) |
| `tools/verdict_analyzer/database.py` | SQLite operations |
| `tools/verdict_analyzer/patterns.py` | Pattern extraction & normalization |
| `tools/verdict_analyzer/template_updater.py` | Safe template modification |
| `tests/test_verdict_analyzer.py` | Unit tests |

---

## CLI Interface

```bash
# Scan all verdicts (first run)
poetry run python tools/verdict-analyzer.py --scan --all-repos

# Generate recommendations (dry-run by default)
poetry run python tools/verdict-analyzer.py \
    --recommend \
    --template docs/templates/0102-feature-lld-template.md \
    --min-occurrences 2

# Apply recommendations automatically
poetry run python tools/verdict-analyzer.py \
    --recommend \
    --template docs/templates/0102-feature-lld-template.md \
    --auto

# Show statistics
poetry run python tools/verdict-analyzer.py --stats
```

---

## Pattern Extraction Logic

### Verdict Locations
- `docs/lineage/active/**/NNN-verdict.md`
- `docs/lineage/done/**/NNN-verdict.md`
- `docs/audit/done/**/NNN-verdict.md`

### Category to Template Section Mapping

```python
CATEGORY_TO_SECTION = {
    # Tier 1 (BLOCKING)
    'Security': '7. Security Considerations',
    'Safety': '9. Risks & Mitigations',
    'Cost': '8. Performance Considerations',
    'Legal': '5. Data & Fixtures',
    # Tier 2 (HIGH PRIORITY)
    'Quality': '3. Requirements',
    'Architecture': '2. Proposed Changes',
}
```

### Common Blocking Patterns (from 275 verdicts analyzed)

| Pattern | Frequency | Template Section |
|---------|-----------|------------------|
| Data residency not specified | HIGH | 5. Data & Fixtures |
| Input sanitization missing | HIGH | 7. Security |
| Capacity limits not defined | MEDIUM | 8. Performance |
| Vague acceptance criteria | HIGH | 3. Requirements |
| External API without disclosure | MEDIUM | 5. Data & Fixtures |
| Authentication gaps (CI/headless) | MEDIUM | 7. Security |

---

## Template Update Strategy

1. **Parse template sections** - Extract current content by `## N.` headers
2. **Match patterns to sections** - Use category mapping
3. **Generate recommendations:**
   - High-frequency issues â†’ Add checklist item to table
   - Repeated gaps â†’ Add guidance tip after header
   - Specific recommendations â†’ Add example
4. **Safe write:**
   - Create `.bak` backup
   - Write to `.tmp` first
   - Atomic rename

### Injection Format

```markdown
## 7. Security Considerations

> **Common blockers:** Input sanitization, data residency, API key exposure,
> authentication for CI/headless environments.

| Concern | Mitigation | Status |
|---------|------------|--------|
| Input sanitization | Validate all user-provided paths | TODO |
| ...existing rows... |
```

---

## Future Hooks (document, don't implement)

| Feature | Issue | Description |
|---------|-------|-------------|
| Janitor integration | #94 | Invoke after lineage archival |
| Compaction | Future | Remove DB entries for deleted files (like sync-permissions) |
| Issue template (0101) | #77 | Second use case after LLD |
| LangGraph node | Future | Mechanical constraint: iterate until template score > threshold |

---

## Verification

```bash
# 1. Run scan on AgentOS
poetry run python tools/verdict-analyzer.py --scan

# 2. Check stats
poetry run python tools/verdict-analyzer.py --stats
# Expected: ~275 verdicts, pattern frequencies by category

# 3. Dry-run recommendations
poetry run python tools/verdict-analyzer.py \
    --recommend \
    --template docs/templates/0102-feature-lld-template.md
# Expected: Preview of template changes

# 4. Apply with --auto
poetry run python tools/verdict-analyzer.py \
    --recommend \
    --template docs/templates/0102-feature-lld-template.md \
    --auto
# Expected: Template updated, backup created

# 5. Verify template
git diff docs/templates/0102-feature-lld-template.md
# Expected: New guidance/checklists in relevant sections
```

---

## Critical Files

| File | Why |
|------|-----|
| `tools/agentos-permissions.py` | CLI pattern, dry-run mode, atomic writes |
| `docs/templates/0102-feature-lld-template.md` | Target template (11 sections) |
| `.claude/project-registry.json` | Multi-repo discovery |
| `docs/lineage/active/83-lld/003-verdict.md` | Example LLD verdict format |
| `docs/lineage/active/100-lld/003-verdict.md` | Example issue verdict format |
