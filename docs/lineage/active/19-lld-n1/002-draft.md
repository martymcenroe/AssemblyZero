# 119 - Chore: Review and Rearrange Audit Classes/Tiers

<!-- Template Metadata
Last Updated: 2025-01-XX
Updated By: Issue #19 creation
Update Reason: Initial LLD for audit reorganization
-->

## 1. Context & Goal
* **Issue:** #19
* **Objective:** Review all 33 audits for category fit, define --ultimate tier criteria, and update the audit index with coherent organization
* **Status:** Draft
* **Related Issues:** #18 (--ultimate tier concept)

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [ ] Should the --ultimate tier be a separate category or a tag that spans existing categories?
- [ ] Are there audits that should be deprecated rather than rearranged?
- [ ] What's the threshold for "expensive" that qualifies for --ultimate tier (time, API calls, manual effort)?

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/0800-audit-index.md` | Modify | Reorganize audit categories, add tier definitions |
| `docs/0801-frequency-matrix.md` | Modify | Update frequency recommendations per new tiers |
| `docs/08xx-*.md` (various) | Modify | Update category headers in individual audit docs |

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# No new dependencies - documentation-only change
```

### 2.3 Data Structures

```markdown
# Conceptual structure - audit categorization schema

## Categories (existing)
- Documentation Health (08xx)
- Core Development (08xx)  
- AI Governance (08xx)
- Meta (08xx)

## Tiers (new dimension)
- Standard: Default tier, run per frequency matrix
- Ultimate: Expensive/rare audits, explicit --ultimate flag required
```

### 2.4 Function Signatures

```bash
# CLI usage patterns (no code changes, just documentation)
./audit.sh --category documentation  # Run category
./audit.sh --ultimate               # Run expensive audits
./audit.sh --all                    # Standard audits only
./audit.sh --all --ultimate         # Include ultimate tier
```

### 2.5 Logic Flow (Pseudocode)

```
1. Inventory all 33 audits with current categories
2. FOR EACH audit:
   - Evaluate primary focus (docs, code, AI, meta)
   - Check for category misalignment
   - Assess cost (time, API calls, manual steps)
   - Flag if --ultimate candidate
3. Group proposed changes
4. Draft new index structure
5. Update frequency matrix
6. Update individual audit headers
```

### 2.6 Technical Approach

* **Module:** `docs/08xx-*`
* **Pattern:** Documentation reorganization
* **Key Decisions:** Tiers are orthogonal to categories (an audit can be in "Core Development" AND be "--ultimate" tier)

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Tier structure | Separate category vs. Tag/flag | Tag/flag | Allows audits to stay in logical categories while marking expense |
| Category count | Keep 4 vs. Add 5th vs. Reduce to 3 | Keep 4 | Existing categories are sound, just need cleanup |
| Ultimate criteria | Time-based vs. Cost-based vs. Both | Both | "Expensive" means slow OR costly OR both |

**Architectural Constraints:**
- Must not break existing audit runner scripts
- Must maintain backward compatibility with current `--category` flags

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. All 33 audits reviewed and assigned to appropriate category
2. --ultimate tier criteria documented with clear threshold definitions
3. Candidate audits identified and marked for --ultimate tier
4. 0800-audit-index.md updated with new organization
5. Frequency matrix updated if any timing changes needed
6. Each rearranged audit's individual doc header updated

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Keep current organization | No work, no risk | Continued confusion, technical debt | **Rejected** |
| Full redesign with new categories | Fresh start | Scope creep, not needed per issue | **Rejected** |
| Light reorganization + tier system | Addresses pain points, minimal disruption | Requires tier definition work | **Selected** |

**Rationale:** Issue explicitly states "housekeeping task, not a redesign" - light touch is appropriate

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | Existing `docs/08xx-*.md` files |
| Format | Markdown |
| Size | 33 audit documents |
| Refresh | Manual (one-time reorganization) |
| Copyright/License | N/A (internal docs) |

### 5.2 Data Pipeline

```
08xx-*.md files ──manual review──► Categorization spreadsheet ──edit──► Updated 08xx-*.md files
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| N/A | N/A | Documentation-only change, no test fixtures needed |

### 5.4 Deployment Pipeline

Manual merge to main branch. No deployment steps.

**If data source is external:** N/A - all internal documentation

## 6. Diagram

### 6.1 Mermaid Quality Gate

Before finalizing any diagram, verify in [Mermaid Live Editor](https://mermaid.live) or GitHub preview:

- [x] **Simplicity:** Similar components collapsed (per 0006 §8.1)
- [x] **No touching:** All elements have visual separation (per 0006 §8.2)
- [x] **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- [x] **Readable:** Labels not truncated, flow direction clear
- [ ] **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)

**Auto-Inspection Results:**
```
- Touching elements: [ ] None / [ ] Found: ___
- Hidden lines: [ ] None / [ ] Found: ___
- Label readability: [ ] Pass / [ ] Issue: ___
- Flow clarity: [ ] Clear / [ ] Issue: ___
```

*Reference: [0006-mermaid-diagrams.md](0006-mermaid-diagrams.md)*

### 6.2 Diagram

```mermaid
graph TB
    subgraph Categories
        DH[Documentation Health]
        CD[Core Development]
        AG[AI Governance]
        ME[Meta]
    end
    
    subgraph Tiers
        ST[Standard Tier<br/>Default, per frequency]
        UT[Ultimate Tier<br/>--ultimate flag required]
    end
    
    DH --> ST
    DH --> UT
    CD --> ST
    CD --> UT
    AG --> ST
    AG --> UT
    ME --> ST
    ME --> UT
    
    style UT fill:#ff9999
    style ST fill:#99ff99
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| N/A | Documentation-only change | N/A |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Breaking existing audit scripts | Test `--category` flags still work | TODO |
| Loss of audit history | Git history preserves all changes | Addressed |

**Fail Mode:** N/A - documentation change

**Recovery Strategy:** Git revert if issues discovered

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| N/A | N/A | Documentation-only change |

**Bottlenecks:** None

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| Human time | ~2 hours | One-time | N/A |

**Cost Controls:**
- [x] Scope limited to reorganization, not redesign

**Worst-Case Scenario:** N/A

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Internal documentation |
| Third-Party Licenses | No | No external content |
| Terms of Service | No | N/A |
| Data Retention | No | N/A |
| Export Controls | No | N/A |

**Data Classification:** Internal

**Compliance Checklist:**
- [x] No PII stored without consent
- [x] All third-party licenses compatible with project license
- [x] External API usage compliant with provider ToS
- [x] Data retention policy documented

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Documentation changes verified through manual review and link checking.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | All audits accounted for | Manual | Count audits in index | 33 audits listed | All 33 present |
| 020 | Category links valid | Auto | Run link checker | No broken links | 0 broken links |
| 030 | Tier criteria documented | Manual | Review index | Clear --ultimate definition | Human verified |
| 040 | Frequency matrix consistent | Manual | Cross-check index vs matrix | Categories match | All align |

*Note: Use 3-digit IDs with gaps of 10 (010, 020, 030...) to allow insertions.*

### 10.2 Test Commands

```bash
# Check for broken links in docs
find docs -name "08*.md" -exec grep -l "0800\|08[0-9][0-9]" {} \;

# Verify audit count
ls docs/08[0-9][0-9]-*.md | wc -l
```

### 10.3 Manual Tests (Only If Unavoidable)

| ID | Scenario | Why Not Automated | Steps |
|----|----------|-------------------|-------|
| 010 | Audit accounting | Requires semantic understanding of audit scope | Review each audit, confirm category assignment |
| 030 | Tier criteria quality | Subjective quality judgment | Read --ultimate definition, verify it's actionable |
| 040 | Matrix consistency | Cross-document semantic alignment | Compare category names between index and matrix |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Scope creep into redesign | Med | Med | Strict adherence to "housekeeping" framing |
| Breaking audit runner | High | Low | Test existing --category flags post-change |
| Incomplete review | Low | Low | Systematic checklist for all 33 audits |

## 12. Definition of Done

### Code
- [ ] N/A - Documentation only

### Tests
- [ ] All 33 audits accounted for in index
- [ ] No broken internal links

### Documentation
- [ ] 0800-audit-index.md reorganized
- [ ] --ultimate tier criteria defined
- [ ] Frequency matrix updated
- [ ] Individual audit headers updated (if moved)

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

---

## Appendix A: Current Audit Inventory

*Working document for review process*

### Documentation Health (Current)
| Audit | Description | Potential Issues | Ultimate? |
|-------|-------------|------------------|-----------|
| TBD | TBD | TBD | TBD |

### Core Development (Current)
| Audit | Description | Potential Issues | Ultimate? |
|-------|-------------|------------------|-----------|
| TBD | TBD | TBD | TBD |

### AI Governance (Current)
| Audit | Description | Potential Issues | Ultimate? |
|-------|-------------|------------------|-----------|
| TBD | TBD | TBD | TBD |

### Meta (Current)
| Audit | Description | Potential Issues | Ultimate? |
|-------|-------------|------------------|-----------|
| TBD | TBD | TBD | TBD |

*Note: This inventory will be populated during implementation*

---

## Appendix B: --Ultimate Tier Criteria (Draft)

An audit qualifies for --ultimate tier if it meets ANY of:

1. **Time:** Takes >10 minutes to complete
2. **Cost:** Makes >100 API calls OR costs >$1 per run
3. **Frequency:** Should run less than monthly
4. **Manual:** Requires significant manual verification steps
5. **Invasive:** Makes changes that are hard to reverse

---

## Appendix: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | Awaiting review |

**Final Status:** PENDING