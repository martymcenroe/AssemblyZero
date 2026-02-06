# Implementation Report: Issue #15 - Path Parameterization

**Issue:** [#15](https://github.com/martymcenroe/AssemblyZero/issues/15)
**Date:** 2026-01-14
**Status:** Complete

---

## Summary

Implemented `assemblyzero_config.py`, a configuration loader that replaces hardcoded paths throughout AssemblyZero with configurable values. Paths are loaded from `~/.assemblyzero/config.json` with fallback to backward-compatible defaults.

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `tools/assemblyzero_config.py` | Created | Configuration loader (331 lines) |
| `~/.assemblyzero/config.json` | Created | User-level path configuration |

---

## Design Decisions

### 1. Dual Path Format

**Why both Windows and Unix:**
- Bash commands require Unix paths (`/c/Users/...`)
- Read/Write/Edit tools require Windows paths (`C:\Users\...`)
- Each path has both formats in config

**Implementation:** Each path key contains a dictionary with `windows` and `unix` formats:
```json
{
  "assemblyzero_root": {
    "windows": "C:\\Users\\mcwiz\\Projects\\AssemblyZero",
    "unix": "/c/Users/mcwiz/Projects/AssemblyZero"
  }
}
```

### 2. Singleton Pattern (`tools/assemblyzero_config.py:309-310`)

**Why singleton:**
- Config should be loaded once per process
- Multiple imports get same instance
- Thread-safe for reading

**Usage:**
```python
from assemblyzero_config import config
root = config.assemblyzero_root()
```

### 3. Backward Compatibility

**Defaults match existing hardcoded values:**
- If `~/.assemblyzero/config.json` doesn't exist, defaults are used
- Existing setups continue working without any changes
- No migration required for current users

### 4. Path Traversal Security (`tools/assemblyzero_config.py:128-190`)

**Security fix identified in Gemini review:**
- Original single-pass regex could be bypassed (`....//` → `../`)
- Implemented loop-until-stable sanitization
- Additional pathlib normalization for Windows paths
- Final safety check rejects any path still containing `..`

---

## Architecture

```
User
  |
  v
assemblyzero_config.py
  |
  +---> _load_config()
  |         |
  |         +---> Check ~/.assemblyzero/config.json
  |         +---> Validate schema
  |         +---> Fall back to DEFAULTS if invalid
  |         v
  |     Cached config dict
  |
  +---> _get_path(key, fmt)
  |         |
  |         +---> Get path from config
  |         +---> Resolve 'auto' format
  |         +---> _sanitize_path()
  |         v
  |     Safe path string
  |
  +---> Public methods: assemblyzero_root(), projects_root(), user_claude_dir()
```

---

## Key Implementation Details

### Schema Validation (`tools/assemblyzero_config.py:95-126`)

Required structure:
- `version` key for future migrations
- `paths` dictionary with `assemblyzero_root`, `projects_root`, `user_claude_dir`
- Each path must have `windows` and `unix` formats

### Format Selection (`tools/assemblyzero_config.py:227-249`)

Supports three modes:
- `'windows'` - Returns Windows format path
- `'unix'` - Returns Unix format path
- `'auto'` - Detects OS and returns appropriate format

### Error Handling

| Error | Response |
|-------|----------|
| Config file missing | Use defaults (silent) |
| Invalid JSON | Log warning, use defaults |
| Schema validation fails | Log warning, use defaults |
| Path traversal detected | Log warning, sanitize or reject |

---

## Deviations from Original Issue Spec

### Environment Variable Approach

**Original consideration:** Use environment variables for paths

**Implemented:** JSON config file approach instead

**Rationale:** Environment variables can't be read by Claude Code's prompt system. JSON config can be documented and versioned.

---

## Exit Codes (CLI Mode)

When run as `python assemblyzero_config.py`:
- Prints current configuration
- No error codes (informational only)

---

## Related Documentation

- LLD: `docs/reports/15/lld-path-parameterization.md`
- Gemini Reviews: `docs/reports/15/review-1-general.md` through `review-4-code.md`
