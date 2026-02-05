---
repo: martymcenroe/AgentOS
issue: 306
url: https://github.com/martymcenroe/AgentOS/issues/306
fetched: 2026-02-05T03:24:19.190874Z
---

# Issue #306: feat: Mechanical validation - verify LLD title issue number matches workflow issue

## Summary

Add a mechanical validation check to catch issue number mismatches in LLD titles.

## Problem

In LLD-099, the drafter generated a title with the wrong issue number:
```markdown
# 199 - Feature: Schema-Driven Project Structure
```

Should have been:
```markdown
# 99 - Feature: Schema-Driven Project Structure
```

This typo passed through Gemini review (Gemini doesn't know the "real" issue number) and was only caught by human inspection.

## Proposed Solution

Add to `validate_mechanical.py`:

```python
def validate_title_issue_number(content: str, issue_number: int) -> list[ValidationError]:
    """Verify the LLD title contains the correct issue number."""
    errors = []
    
    # Extract title (first # line)
    title_match = re.search(r'^#\s*(\d+)\s*[-–—]', content, re.MULTILINE)
    if title_match:
        title_number = int(title_match.group(1))
        if title_number != issue_number:
            errors.append(ValidationError(
                severity="BLOCK",
                message=f"Title issue number ({title_number}) doesn't match workflow issue ({issue_number})"
            ))
    else:
        errors.append(ValidationError(
            severity="WARNING",
            message="Could not extract issue number from title"
        ))
    
    return errors
```

## Why Mechanical?

- The workflow knows the real issue number (from `--issue` flag)
- The drafter can hallucinate/typo the number
- Gemini can't verify this (doesn't have issue number context)
- Simple regex check, no LLM needed

## Files to Modify

| File | Change |
|------|--------|
| `agentos/workflows/requirements/nodes/validate_mechanical.py` | Add `validate_title_issue_number()` |
| `tests/unit/test_validate_mechanical.py` | Add tests for number mismatch |

## Acceptance Criteria

- [ ] Validation BLOCKS if title number != workflow issue number
- [ ] Validation WARNS if title format unrecognized
- [ ] Test covers: correct number, wrong number, missing number

## Labels

`enhancement`, `workflow`, `mechanical-validation`