"""Tests for extract_test_plan_section — code-fence false-positive fix (#455)."""

from assemblyzero.workflows.testing.nodes.load_lld import extract_test_plan_section


def test_skips_heading_inside_code_fence():
    """A ## 10. heading inside a code block must not match."""
    content = '''\
Some intro text.

```python
example = """
## 10. Verification & Testing

This is inside a code fence and should be ignored.
"""
```

## 10. Verification & Testing

Real test plan content here.

| ID | Test |
|----|------|
| T1 | Check something |

## 11. Next Section
'''
    result = extract_test_plan_section(content)
    assert "Real test plan content here." in result
    assert "inside a code fence" not in result


def test_matches_normal_heading():
    """Standard heading outside code fences works as before."""
    content = """\
## 10. Test Plan

| ID | Scenario |
|----|----------|
| T1 | Basic check |

## 11. Appendix
"""
    result = extract_test_plan_section(content)
    assert "Basic check" in result


def test_section_9_test_mapping():
    """Implementation spec Section 9 format still works."""
    content = """\
## 9. Test Mapping

| Test ID | Tests Function |
|---------|---------------|
| T010 | detect_cascade_risk() |

## 10. Dependencies
"""
    result = extract_test_plan_section(content)
    assert "detect_cascade_risk" in result


def test_no_match_returns_empty():
    """Returns empty string when no test section found."""
    content = "# Just a README\n\nNo test section here.\n"
    result = extract_test_plan_section(content)
    assert result == ""
