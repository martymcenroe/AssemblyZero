# Issue #161: Bug: Unicode encoding error in run_requirements_workflow.py on Windows

## Summary
The `run_requirements_workflow.py` tool fails with a `UnicodeDecodeError` when processing GitHub issues that contain Unicode box-drawing characters (or other non-ASCII characters).

## Error
```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 5993: character maps to <undefined>
```

## Root Cause
On Windows, Python defaults to `cp1252` encoding for subprocess output. When `gh issue view` returns content containing Unicode characters (like box-drawing characters), the cp1252 codec cannot decode them.

## Affected Issue
- Repository: `martymcenroe/RCA-PDF-extraction-pipeline`
- Issue #35: "HTML Forensic Report Generator"
- Contains ASCII art wireframes using Unicode box-drawing characters

## Suggested Fix
When calling `subprocess.run()` or `subprocess.Popen()` for `gh` commands, explicitly set `encoding='utf-8'`.

## Impact
- Blocks LLD generation for any issue containing non-ASCII characters
- Affects Windows users (Linux/macOS default to UTF-8)
- Issues written by our own workflow tools can contain these characters

---

*Note: This lineage file created manually because the workflow cannot process its own bug report (bootstrap problem).*
