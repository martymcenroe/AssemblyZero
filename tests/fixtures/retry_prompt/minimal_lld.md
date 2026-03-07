# 998 - Minimal LLD for Testing

## 1. Context

This is a minimal LLD fixture with only one file spec section.
It is used to test unambiguous section extraction.

## Section for assemblyzero/utils/tiny_helper.py

### Function Signatures

```python
def tiny_format(value: str) -> str:
    """Format a value using the tiny convention."""
    ...
```

### Implementation Notes

The tiny helper is a minimal utility with no external dependencies.
It follows the standard pattern of returning formatted strings.
Error handling: raises ValueError on empty input.