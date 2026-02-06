# Lessons Learned: Verdict Analyzer & Self-Improvement Loop

**Date:** 2026-02-01
**Context:** E2E testing of Verdict Analyzer (Issue #104) and template improvement workflow
**Duration:** ~2 hours

---

## Executive Summary

Built and tested a closed-loop system where governance feedback automatically improves templates. Key insight: **Issues get blocked 15x more often than LLDs** - the bottleneck is at issue definition, not detailed design.

---

## Key Lessons

### 1. Separate Data Before Drawing Conclusions

**What happened:** Initially analyzed 164 verdicts as a single pool. All were classified as "lld" type, leading to recommendations being applied to both templates equally.

**The problem:** The parser detected verdict type by looking for `## User Story` in the content, but verdict files don't contain the original document structure - they contain review feedback.

**The fix:** Updated parser to detect by header (`# Issue Review:` vs `# Governance Verdict:`) and path fallback (`-lld` vs `-issue`).

**Result after separation:**
| Type | Verdicts | Blocking Issues | Rate |
|------|----------|-----------------|------|
| Issue | 46 | 67 | 1.5/verdict |
| LLD | 118 | 13 | 0.1/verdict |

**Lesson:** Always segment data by type before analyzing patterns. Aggregated analysis hides important distinctions.

---

### 2. Progressive Elaboration Requires Different Templates

**What happened:** Almost applied the same heavy sections (Architecture Decisions, Cost Analysis, Legal Compliance) to both issue and LLD templates.

**The problem:** Issues define WHAT and WHY. LLDs define HOW. Issues should be lightweight.

**The fix:**
- LLD template: Full sections with tables and detailed prompts
- Issue template: Simple Risk Checklist with checkboxes

```markdown
## Risk Checklist
- [ ] **Architecture:** Does this change system structure?
- [ ] **Cost:** Does this add API calls, storage, or compute?
- [ ] **Legal/PII:** Does this handle personal data?
- [ ] **Safety:** Can this cause data loss or instability?
```

**Lesson:** The same pattern (e.g., "address architecture concerns") needs different implementations at different stages of elaboration.

---

### 3. The Bottleneck is Earlier Than Expected

**What we assumed:** LLDs were getting blocked because they lacked detail.

**What data showed:** Issues get blocked 15x more often. The problem is unclear requirements, not insufficient design.

**Top issue blockers:**
1. Architecture context missing (20)
2. Quality/requirements unclear (19)
3. Legal implications unstated (8)
4. Security not addressed (8)

**Lesson:** When optimizing a pipeline, measure where blockages actually occur. Don't assume.

---

### 4. Incremental Database Updates Enable Fast Iteration

**Implementation:** Scanner uses content hashes to skip unchanged files.

**Benefit:** After initial scan (164 files), subsequent scans process only new/changed verdicts in seconds.

**Pattern:**
```python
if db.needs_update(filepath, content_hash):
    record = parse_verdict(filepath)
    db.upsert_verdict(record)
```

**Lesson:** For any analysis tool that will be run repeatedly, build in incremental processing from the start.

---

### 5. Template Metadata Enables Audit Trail

**What we added:**
```markdown
<!-- Template Metadata
Last Updated: 2026-02-01
Updated By: Verdict Analyzer (tools/verdict-analyzer.py)
Update Reason: Added sections based on 80 blocking issues from 164 verdicts
Categories addressed: architecture (23), safety (9), legal (8), cost (6)
-->
```

**Benefit:** Future agents/humans can see:
- When template was last updated
- What tool made the change
- What data drove the decision

**Lesson:** Automated changes should be self-documenting.

---

## Bugs Fixed During E2E Testing

| Bug | Symptom | Fix |
|-----|---------|-----|
| `find_registry()` missing arg | `TypeError` on scan | Pass `Path.cwd()` |
| `parse_verdict()` wrong signature | `TypeError` on parse | Use 1 arg not 2 |
| `get_pattern_stats()` doesn't exist | `AttributeError` | Use `get_stats()` |
| Verdict type always "lld" | Wrong recommendations | Detect by header/path |
| `discover_verdicts()` wrong paths | 0 verdicts found | Add `docs/lineage/active` |
| `validate_verdict_path()` too broad | Non-verdicts included | Check "verdict" in filename |

**Lesson:** E2E testing catches interface mismatches that unit tests miss. Run the actual workflow.

---

## The Self-Improvement Loop

```
Governance Reviews → Verdicts → Pattern Analysis → Template Updates → Better Documents → Fewer Blocks
```

This is the first implementation of AssemblyZero learning from its own failures. The "Janitor" agent will eventually run this automatically.

---

## Files Changed

| File | Change |
|------|--------|
| `tools/verdict-analyzer.py` | CLI fixes |
| `tools/verdict_analyzer/parser.py` | Multi-format parsing, type detection |
| `tools/verdict_analyzer/scanner.py` | Path fixes |
| `docs/templates/0102-feature-lld-template.md` | Added 4 sections |
| `docs/templates/0101-issue-template.md` | Added Risk Checklist |
| `wiki/How-the-AssemblyZero-Learns.md` | New page |
| `docs/runbooks/0910-verdict-analyzer-*.md` | Updated examples |

---

## Quotes

> "Give a man a fish and you feed him for a day. Teach a man to fish and you feed him for a lifetime."

> "The fish learned to fish."

> "We created the djinn."
