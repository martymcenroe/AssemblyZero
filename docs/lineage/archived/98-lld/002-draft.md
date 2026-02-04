# 10098 - Feature: Brief Structure and Placement Standard

<!-- Template Metadata
Last Updated: 2025-01-09
Updated By: Initial LLD creation
Update Reason: New feature LLD for issue #98
-->

## 1. Context & Goal
* **Issue:** #98
* **Objective:** Establish a project-wide standard for brief placement, naming, structure, and lifecycle management
* **Status:** Draft
* **Related Issues:** None

### Open Questions
*Questions that need clarification before or during implementation. Remove when resolved.*

- [x] Should `ideas/` be at project root or inside `docs/`? **Resolved: Project root per issue specification**
- [x] Archive pattern needed now or defer? **Resolved: Defer - delete for now**

## 2. Proposed Changes

*This section is the **source of truth** for implementation. Describe exactly what will be built.*

### 2.1 Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/standards/0009-canonical-project-structure.md` | Modify | Add `ideas/` directory to root structure with rationale |
| `tools/new-repo-setup.py` | Modify | Add `ideas/active/` and `ideas/backlog/` to OTHER_STRUCTURE |
| `docs/templates/0110-brief-template.md` | Add | Create new brief template file |
| `docs/0003-file-inventory.md` | Modify | Add template to inventory |
| `ideas/active/.gitkeep` | Add | Placeholder to preserve empty directory |
| `ideas/backlog/.gitkeep` | Add | Placeholder to preserve empty directory |

### 2.2 Dependencies

*New packages, APIs, or services required.*

```toml
# No new dependencies required
```

### 2.3 Data Structures

```python
# Brief Template Frontmatter Structure (YAML)
frontmatter = {
    "status": str,      # Draft | Active | Blocked | Done | Rejected
    "effort": str,      # S | M | L | XL (optional)
    "value": str,       # Low | Medium | High (optional)
    "blocked_by": str,  # Issue number or description (optional)
}
```

### 2.4 Function Signatures

```python
# No new functions - this is a documentation/configuration change
# new-repo-setup.py modification is directory list addition only
```

### 2.5 Logic Flow (Pseudocode)

```
Brief Lifecycle:
1. Create new brief
   - Place in ideas/backlog/
   - Use kebab-case naming (no numbers)
   - Fill in Problem and Proposal sections
   - Set Status to Draft

2. Promote to active work
   - Move from ideas/backlog/ to ideas/active/
   - Update Status to Active

3. Complete brief
   IF brief becomes GitHub issue THEN
     - Create issue from brief content
     - Delete brief file
   ELSE IF brief implemented directly THEN
     - Update Status to Done
     - Delete brief file
   ELSE IF brief rejected THEN
     - Update Status to Rejected
     - Delete or add rejection note
```

### 2.6 Technical Approach

* **Module:** Documentation and tooling configuration
* **Pattern:** Convention-over-configuration for file organization
* **Key Decisions:** 
  - `ideas/` at root level keeps working documents separate from formal `docs/`
  - Unnumbered files avoid collision with GitHub issue numbers
  - Two-directory structure (active/backlog) provides minimal but useful state tracking

### 2.7 Architecture Decisions

| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|--------|-----------|
| Directory location | `docs/ideas/`, `ideas/`, `.ideas/` | `ideas/` | Visible, separate from formal docs, not hidden |
| Naming scheme | Numbered (`001-`), Dated (`2025-01-`), Plain | Plain kebab-case | Avoids issue number collision, simplest approach |
| State tracking | Single directory, Two directories, Database | Two directories | Simple file-based state without overhead |
| Archive strategy | Archive directory, Git history, Delete | Delete (defer archive) | Simplest starting point, Git provides history |

**Architectural Constraints:**
- Must integrate with existing `new-repo-setup.py` tooling
- Cannot conflict with existing `docs/` structure
- Must work across all projects using this standard

## 3. Requirements

*What must be true when this is done. These become acceptance criteria.*

1. `ideas/` directory structure documented in canonical structure standard
2. `new-repo-setup.py` creates `ideas/active/` and `ideas/backlog/` directories
3. Brief template exists at `docs/templates/0110-brief-template.md`
4. Template includes all required frontmatter fields (Status, Effort, Value)
5. Template includes Problem and Proposal sections
6. Lifecycle rules documented with clear state transitions
7. "What Goes Where" reference included distinguishing briefs from issues

## 4. Alternatives Considered

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| `ideas/` at root | Clear separation, easy to find | Adds to root directory count | **Selected** |
| `docs/ideas/` | Keeps docs together | Mixes formal/informal documents | Rejected |
| Single `ideas/` directory | Simpler structure | No state visibility without reading files | Rejected |
| Numbered briefs (`001-`) | Consistent with standards | Collides with GitHub issue numbers | Rejected |
| Status in filename | State visible in file list | Rename on state change, ugly names | Rejected |

**Rationale:** The selected options prioritize simplicity, clear separation of concerns, and avoiding conflicts with the existing GitHub issue numbering system.

## 5. Data & Fixtures

*Per [0108-lld-pre-implementation-review.md](0108-lld-pre-implementation-review.md) - complete this section BEFORE implementation.*

### 5.1 Data Sources

| Attribute | Value |
|-----------|-------|
| Source | N/A - Template-based documentation |
| Format | Markdown with YAML frontmatter |
| Size | Small text files (< 10KB typical) |
| Refresh | Manual creation by developers |
| Copyright/License | Project license applies |

### 5.2 Data Pipeline

```
Developer idea ──manual──► ideas/backlog/*.md ──promotion──► ideas/active/*.md ──completion──► GitHub Issue or Delete
```

### 5.3 Test Fixtures

| Fixture | Source | Notes |
|---------|--------|-------|
| Sample brief | Generated | Example brief for testing template |
| Empty project | Generated | Fresh directory for testing new-repo-setup.py |

### 5.4 Deployment Pipeline

No deployment pipeline - documentation and configuration changes only.

**If data source is external:** N/A

## 6. Diagram

### 6.1 Mermaid Quality Gate

Before finalizing any diagram, verify in [Mermaid Live Editor](https://mermaid.live) or GitHub preview:

- [x] **Simplicity:** Similar components collapsed (per 0006 §8.1)
- [x] **No touching:** All elements have visual separation (per 0006 §8.2)
- [x] **No hidden lines:** All arrows fully visible (per 0006 §8.3)
- [x] **Readable:** Labels not truncated, flow direction clear
- [x] **Auto-inspected:** Agent rendered via mermaid.ink and viewed (per 0006 §8.5)

**Agent Auto-Inspection (MANDATORY):**

**Auto-Inspection Results:**
```
- Touching elements: [x] None
- Hidden lines: [x] None
- Label readability: [x] Pass
- Flow clarity: [x] Clear
```

*Reference: [0006-mermaid-diagrams.md](0006-mermaid-diagrams.md)*

### 6.2 Brief Lifecycle Diagram

```mermaid
stateDiagram-v2
    [*] --> Draft: Create brief
    
    Draft --> Active: Promote to active work
    Draft --> Rejected: Decline idea
    
    Active --> Done: Implement directly
    Active --> Promoted: Create GitHub Issue
    Active --> Blocked: Dependency identified
    
    Blocked --> Active: Blocker resolved
    Blocked --> Rejected: Cannot proceed
    
    Done --> [*]: Delete file
    Promoted --> [*]: Delete file
    Rejected --> [*]: Delete file
    
    note right of Draft: ideas/backlog/
    note right of Active: ideas/active/
```

### 6.3 Directory Structure Diagram

```mermaid
graph TD
    Root[Project Root]
    
    Root --> Ideas[ideas/]
    Root --> Docs[docs/]
    Root --> Src[src/]
    
    Ideas --> Active[active/]
    Ideas --> Backlog[backlog/]
    
    Active --> A1[feature-x.md]
    Active --> A2[refactor-y.md]
    
    Backlog --> B1[cool-idea.md]
    Backlog --> B2[tech-debt-z.md]
    
    Docs --> Standards[standards/]
    Docs --> Templates[templates/]
    
    Templates --> T1[0110-brief-template.md]
```

## 7. Security & Safety Considerations

### 7.1 Security

| Concern | Mitigation | Status |
|---------|------------|--------|
| Sensitive info in briefs | Documentation guidance to avoid secrets | Addressed |
| Access control | Relies on repository permissions | N/A - existing control |

### 7.2 Safety

| Concern | Mitigation | Status |
|---------|------------|--------|
| Brief loss on deletion | Git history preserves deleted files | Addressed |
| Accidental deletion of active work | Clear directory separation | Addressed |
| Orphaned briefs | Periodic review recommended in docs | Addressed |

**Fail Mode:** Fail Open - Briefs are informal; loss is recoverable from Git history

**Recovery Strategy:** Retrieve deleted briefs from Git history if needed

## 8. Performance & Cost Considerations

### 8.1 Performance

| Metric | Budget | Approach |
|--------|--------|----------|
| File system operations | Negligible | Standard file I/O |
| Repository size | < 1KB per brief | Text files only |
| Build time impact | None | No build integration |

**Bottlenecks:** None - static documentation files

### 8.2 Cost Analysis

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| Storage | Free (Git) | ~10KB/month | $0 |
| Developer time | N/A | Minimal overhead | N/A |

**Cost Controls:**
- N/A - No direct costs

**Worst-Case Scenario:** Repository accumulates many briefs; easily resolved by cleanup

## 9. Legal & Compliance

| Concern | Applies? | Mitigation |
|---------|----------|------------|
| PII/Personal Data | No | Briefs are technical documents |
| Third-Party Licenses | No | No external dependencies |
| Terms of Service | No | No external services |
| Data Retention | N/A | Git history handles retention |
| Export Controls | No | Documentation only |

**Data Classification:** Internal

**Compliance Checklist:**
- [x] No PII stored without consent - N/A
- [x] All third-party licenses compatible - N/A
- [x] External API usage compliant - N/A
- [x] Data retention policy documented - Git history

## 10. Verification & Testing

*Ref: [0005-testing-strategy-and-protocols.md](0005-testing-strategy-and-protocols.md)*

**Testing Philosophy:** Automated verification where possible; manual review for documentation quality.

### 10.1 Test Scenarios

| ID | Scenario | Type | Input | Expected Output | Pass Criteria |
|----|----------|------|-------|-----------------|---------------|
| 010 | new-repo-setup creates ideas dirs | Auto | Fresh directory | `ideas/active/` and `ideas/backlog/` exist | Directories created |
| 020 | Template renders correctly | Auto | Template file | Valid markdown with YAML frontmatter | No syntax errors |
| 030 | .gitkeep files present | Auto | Created directories | `.gitkeep` in each empty dir | Files exist |
| 040 | Standard doc updated | Manual | 0009 standard | Contains ideas/ section | Section present with rationale |
| 050 | Inventory updated | Manual | 0003 inventory | Contains 0110 template | Entry present |

### 10.2 Test Commands

```bash
# Test new-repo-setup.py creates directories
mkdir /tmp/test-repo && cd /tmp/test-repo
python tools/new-repo-setup.py
test -d ideas/active && test -d ideas/backlog && echo "PASS" || echo "FAIL"

# Validate template markdown
python -c "import yaml; yaml.safe_load(open('docs/templates/0110-brief-template.md').read().split('---')[1])"
```

### 10.3 Manual Tests (Only If Unavoidable)

| ID | Scenario | Why Not Automated | Steps |
|----|----------|-------------------|-------|
| 040 | Standard doc quality | Requires human judgment on clarity | 1. Read 0009 standard 2. Verify ideas/ section is clear and complete |
| 050 | Inventory correctness | Requires context verification | 1. Check 0003 inventory 2. Verify 0110 entry matches template |

## 11. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Developers don't adopt convention | Med | Med | Clear documentation, tooling support |
| Brief/issue confusion | Low | Low | "What Goes Where" reference table |
| Orphaned briefs accumulate | Low | Med | Periodic cleanup recommendation |
| Template becomes stale | Low | Low | Version in template, review process |

## 12. Definition of Done

### Code
- [ ] `new-repo-setup.py` modified to create `ideas/active/` and `ideas/backlog/`
- [ ] `.gitkeep` files added to preserve empty directories

### Tests
- [ ] new-repo-setup.py tested on fresh directory
- [ ] Template validates as correct markdown/YAML

### Documentation
- [ ] `docs/standards/0009-canonical-project-structure.md` updated with `ideas/` section
- [ ] `docs/templates/0110-brief-template.md` created
- [ ] `docs/0003-file-inventory.md` updated with new template
- [ ] Implementation Report (`docs/reports/98/implementation-report.md`) completed
- [ ] Test Report (`docs/reports/98/test-report.md`) completed

### Review
- [ ] Code review completed
- [ ] User approval before closing issue

---

## Appendix A: Brief Template Content

The template at `docs/templates/0110-brief-template.md` will contain:

```markdown
---
status: Draft
effort: 
value: 
blocked_by: 
---

# Idea: {Title}

## Problem

{What problem does this solve? Why does it matter?}

## Proposal

{What is the proposed solution? Be specific enough to evaluate.}

## Implementation (Optional)

{Technical approach, if known. Can be filled in later.}

## Next Steps (Optional)

- [ ] {Step 1}
- [ ] {Step 2}
```

## Appendix B: What Goes Where Reference

| Document Type | Location | Naming | When to Use |
|---------------|----------|--------|-------------|
| Speculative idea | `ideas/backlog/` | `kebab-case.md` | Early-stage thinking, might not happen |
| Active work item | `ideas/active/` | `kebab-case.md` | Committed work, not yet formal issue |
| Formal tracked work | GitHub Issues | Issue number | Needs tracking, collaboration, prioritization |
| Design specification | `docs/llds/` | `1XXXX-*.md` | Approved work requiring detailed design |
| Project standard | `docs/standards/` | `0XXX-*.md` | Permanent project conventions |

## Appendix C: Review Log

*Track all review feedback with timestamps and implementation status.*

### Review Summary

| Review | Date | Verdict | Key Issue |
|--------|------|---------|-----------|
| - | - | - | Pending initial review |

**Final Status:** PENDING