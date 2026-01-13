# 0109 - Runbook Template

**Category:** Template
**For:** Operational Procedures (09xx series)

---

## Usage

Copy this template when creating a new runbook. Replace all `[bracketed]` placeholders.

---

# [NUMBER] - [Title]

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** [YYYY-MM-DD]

---

## Purpose

[1-2 sentences describing what this procedure accomplishes and when to use it]

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| [Requirement 1] | `[verification command]` |
| [Requirement 2] | `[verification command]` |

---

## Procedure

### Step 1: [First Step Title]

[Description of what this step does]

```bash
[command if applicable]
```

### Step 2: [Second Step Title]

[Description]

```bash
[command if applicable]
```

### Step N: [Final Step Title]

[Description]

---

## Verification Checklist

| Check | Command | Expected |
|-------|---------|----------|
| [What to verify] | `[command]` | [Expected output] |

---

## Troubleshooting

### "[Error message or symptom]"

[Cause and solution]

### "[Another common issue]"

[Cause and solution]

---

## Related Documents

- [Link to related doc 1]
- [Link to related doc 2]

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | [YYYY-MM-DD] | Initial version |

---

# Template Notes (Delete This Section)

## Numbering Convention

Runbooks use the 09xx range:
- 0900: Runbook index
- 0901-0949: Setup/initialization procedures
- 0950-0989: Maintenance procedures
- 0990-0999: Emergency/recovery procedures

## Writing Guidelines

1. **Be explicit** - Include exact commands, paths, and expected outputs
2. **Assume nothing** - List all prerequisites
3. **Verify everything** - Include a verification checklist
4. **Anticipate failures** - Add troubleshooting section
5. **Link context** - Reference related documents

## Page Breaks

If the runbook will be printed, add page breaks between major sections:
```html
<div style="page-break-after: always;"></div>
```
