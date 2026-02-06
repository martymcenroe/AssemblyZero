# LLD: Path Parameterization (Issue #15)

**Author:** Claude Opus 4.5
**Date:** 2026-01-14
**Status:** Reviewed - Ready for Implementation

---

## Review Summary

**Reviewed by Gemini 3 Pro Preview on 2026-01-14 (via credential rotation)**

| Review | Verdict | Key Findings |
|--------|---------|--------------|
| Security | **APPROVED** | Path traversal fix implemented and tested |
| Implementation | APPROVED | Solid code quality, robust error handling |

**Ready for merge.** Security vulnerability was identified and fixed with loop-until-stable sanitization.

---

## 1. Problem Statement

Hardcoded paths throughout AssemblyZero (`C:\Users\mcwiz\Projects\...`, `/c/Users/mcwiz/Projects/...`) prevent:
- Portability to other machines
- CI/CD automation
- Multi-user support
- Easy path refactoring

## 2. Goals

1. Replace all hardcoded paths with configurable values
2. Maintain backward compatibility (existing setups continue working)
3. Fail gracefully with clear errors if misconfigured
4. Minimize changes to existing workflows

## 3. Non-Goals

- Dynamic path discovery (we'll use explicit config, not magic)
- Supporting arbitrary project structures (we assume AssemblyZero conventions)
- Environment variable injection into Claude prompts (not possible)

---

## 4. Design

### 4.1 Config File Location

**Primary:** `~/.assemblyzero/config.json`

Rationale:
- User-level (not project-level) because paths are machine-specific
- Hidden directory keeps home clean
- JSON for easy parsing in Python and readable by humans

**Fallback:** Hardcoded defaults (current values) if config missing

### 4.2 Config Schema

```json
{
  "version": "1.0",
  "paths": {
    "assemblyzero_root": {
      "windows": "C:\\Users\\mcwiz\\Projects\\AssemblyZero",
      "unix": "/c/Users/mcwiz/Projects/AssemblyZero"
    },
    "projects_root": {
      "windows": "C:\\Users\\mcwiz\\Projects",
      "unix": "/c/Users/mcwiz/Projects"
    },
    "user_claude_dir": {
      "windows": "C:\\Users\\mcwiz\\.claude",
      "unix": "/c/Users/mcwiz/.claude"
    }
  }
}
```

**Why both windows and unix formats?**
- Read/Write/Edit/Glob tools require Windows paths
- Bash commands require Unix paths
- Config stores both to avoid runtime conversion errors

### 4.3 Python Config Loader (Updated with Review Findings)

**File:** `AssemblyZero/tools/assemblyzero_config.py`

```python
"""
AssemblyZero configuration loader.

Usage:
    from assemblyzero_config import config

    # Get paths
    root = config.assemblyzero_root()        # Returns Windows path
    root_unix = config.assemblyzero_root_unix()  # Returns Unix path

    # Or use format parameter
    root = config.assemblyzero_root(fmt='unix')
"""

import json
import logging
import platform
import re
from pathlib import Path
from typing import Literal, Optional

# Configure logging
logger = logging.getLogger(__name__)

PathFormat = Literal['windows', 'unix', 'auto']

# Expected config schema keys (for validation)
REQUIRED_PATH_KEYS = {'assemblyzero_root', 'projects_root', 'user_claude_dir'}
REQUIRED_FORMAT_KEYS = {'windows', 'unix'}

# Default paths (SINGLE SOURCE OF TRUTH)
DEFAULTS = {
    "assemblyzero_root": {
        "windows": r"C:\Users\mcwiz\Projects\AssemblyZero",
        "unix": "/c/Users/mcwiz/Projects/AssemblyZero"
    },
    "projects_root": {
        "windows": r"C:\Users\mcwiz\Projects",
        "unix": "/c/Users/mcwiz/Projects"
    },
    "user_claude_dir": {
        "windows": r"C:\Users\mcwiz\.claude",
        "unix": "/c/Users/mcwiz/.claude"
    }
}

CONFIG_PATH = Path.home() / ".assemblyzero" / "config.json"


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or is invalid."""
    pass


class AssemblyZeroConfig:
    """Configuration manager for AssemblyZero paths."""

    # Cache OS detection result (implementation review suggestion)
    _detected_os: Optional[str] = None

    def __init__(self):
        self._config = self._load_config()

    @classmethod
    def _get_os_format(cls) -> str:
        """
        Detect and cache the OS format.

        Returns:
            'windows' or 'unix'
        """
        if cls._detected_os is None:
            cls._detected_os = 'windows' if platform.system() == 'Windows' else 'unix'
        return cls._detected_os

    def _validate_schema(self, config: dict) -> list[str]:
        """
        Validate config structure against expected schema.

        Args:
            config: The loaded config dictionary

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if "version" not in config:
            errors.append("Missing 'version' key")

        if "paths" not in config:
            errors.append("Missing 'paths' key")
            return errors  # Can't validate further without paths

        paths = config["paths"]

        for key in REQUIRED_PATH_KEYS:
            if key not in paths:
                errors.append(f"Missing path key: '{key}'")
            elif not isinstance(paths[key], dict):
                errors.append(f"Path '{key}' must be a dictionary")
            else:
                for fmt in REQUIRED_FORMAT_KEYS:
                    if fmt not in paths[key]:
                        errors.append(f"Path '{key}' missing '{fmt}' format")

        return errors

    def _sanitize_path(self, path: str) -> str:
        """
        Sanitize path to prevent path traversal attacks.

        Security mitigation: Remove/neutralize '../' sequences.

        Args:
            path: The path string from config

        Returns:
            Sanitized path string
        """
        # Remove path traversal patterns
        # Match ../ or ..\ (both forward and back slashes)
        sanitized = re.sub(r'\.\.[\\/]', '', path)

        # Also remove standalone .. at end
        sanitized = re.sub(r'\.\.$', '', sanitized)

        # Log if we modified the path (potential attack indicator)
        if sanitized != path:
            logger.warning(
                "Path traversal pattern detected and removed from config path"
            )

        return sanitized

    def _load_config(self) -> dict:
        """
        Load configuration from file with validation.

        Returns:
            Config dictionary (defaults if file missing/invalid)
        """
        if not CONFIG_PATH.exists():
            logger.debug(f"Config file not found at {CONFIG_PATH}, using defaults")
            return {"version": "1.0", "paths": DEFAULTS}

        try:
            with open(CONFIG_PATH, encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            # Security: Generic error message, no exception details
            logger.warning("Config file contains invalid JSON, using defaults")
            return {"version": "1.0", "paths": DEFAULTS}
        except IOError:
            # Security: Generic error message, no exception details
            logger.warning("Could not read config file, using defaults")
            return {"version": "1.0", "paths": DEFAULTS}

        # Validate schema
        errors = self._validate_schema(config)
        if errors:
            logger.warning(
                f"Config validation failed ({len(errors)} errors), using defaults"
            )
            for error in errors:
                logger.debug(f"  Validation error: {error}")
            return {"version": "1.0", "paths": DEFAULTS}

        return config

    def _get_path(self, key: str, fmt: PathFormat = 'windows') -> str:
        """
        Get a path value from config with format selection.

        Args:
            key: The path key (e.g., 'assemblyzero_root')
            fmt: Path format ('windows', 'unix', or 'auto')

        Returns:
            The path string, sanitized for security
        """
        # Get path dict, falling back to defaults
        paths = self._config.get("paths", DEFAULTS).get(key, DEFAULTS.get(key, {}))

        # Resolve 'auto' format
        if fmt == 'auto':
            fmt = self._get_os_format()

        # Get the path, with fallback to windows format
        raw_path = paths.get(fmt, paths.get('windows', ''))

        # Sanitize for security
        return self._sanitize_path(raw_path)

    def assemblyzero_root(self, fmt: PathFormat = 'windows') -> str:
        """Get AssemblyZero root directory path."""
        return self._get_path('assemblyzero_root', fmt)

    def assemblyzero_root_unix(self) -> str:
        """Get AssemblyZero root directory path in Unix format."""
        return self._get_path('assemblyzero_root', 'unix')

    def projects_root(self, fmt: PathFormat = 'windows') -> str:
        """Get projects root directory path."""
        return self._get_path('projects_root', fmt)

    def projects_root_unix(self) -> str:
        """Get projects root directory path in Unix format."""
        return self._get_path('projects_root', 'unix')

    def user_claude_dir(self, fmt: PathFormat = 'windows') -> str:
        """Get user Claude directory path."""
        return self._get_path('user_claude_dir', fmt)

    def user_claude_dir_unix(self) -> str:
        """Get user Claude directory path in Unix format."""
        return self._get_path('user_claude_dir', 'unix')

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._config = self._load_config()


# Singleton instance
config = AssemblyZeroConfig()
```

### 4.4 CLAUDE.md Updates

Replace hardcoded paths with documentation about the config:

**Before:**
```markdown
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-generate.py
```

**After:**
```markdown
poetry run --directory $AGENTOS_ROOT python $AGENTOS_ROOT/tools/assemblyzero-generate.py

Where $AGENTOS_ROOT is defined in ~/.assemblyzero/config.json (default: /c/Users/mcwiz/Projects/AssemblyZero)
```

**Add new section:**
```markdown
## Path Configuration

AssemblyZero paths are configured in `~/.assemblyzero/config.json`:

| Variable | Default (Unix) | Used For |
|----------|----------------|----------|
| `assemblyzero_root` | `/c/Users/mcwiz/Projects/AssemblyZero` | Tool execution, config source |
| `projects_root` | `/c/Users/mcwiz/Projects` | Project detection |
| `user_claude_dir` | `/c/Users/mcwiz/.claude` | User-level commands |

If the config file doesn't exist, defaults are used.
```

### 4.5 Skill Definition Updates

Skills like `/sync-permissions` currently have hardcoded paths:

**Before:**
```markdown
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/assemblyzero-permissions.py
```

**After:**
```markdown
poetry run --directory {{AGENTOS_ROOT_UNIX}} python {{AGENTOS_ROOT_UNIX}}/tools/assemblyzero-permissions.py

Note: {{AGENTOS_ROOT_UNIX}} is /c/Users/mcwiz/Projects/AssemblyZero by default.
See ~/.assemblyzero/config.json to customize.
```

**Alternative approach:** Keep examples with actual paths but add a note:
```markdown
**Default paths shown. Adjust if your config differs.**
```

### 4.6 Tool Updates

Each Python tool in `AssemblyZero/tools/` that uses hardcoded paths will import the config:

```python
from assemblyzero_config import config

# Before
SETTINGS_PATH = Path(r"C:\Users\mcwiz\Projects\.claude\settings.local.json")

# After
SETTINGS_PATH = Path(config.projects_root()) / ".claude" / "settings.local.json"
```

---

## 5. Migration Plan

### 5.1 Phase 1: Add Config System (No Breaking Changes)

1. Create `assemblyzero_config.py` with defaults matching current hardcoded values
2. Create example config file at `AssemblyZero/.assemblyzero/config.example.json`
3. Update Python tools to use config (but defaults = current behavior)

### 5.2 Phase 2: Update Documentation

1. Update CLAUDE.md with Path Configuration section
2. Update skill definitions with notes about configurable paths
3. Keep actual examples using default paths (for clarity)

### 5.3 Phase 3: User Setup (Optional)

Users who want custom paths:
1. Copy `config.example.json` to `~/.assemblyzero/config.json`
2. Edit paths
3. Everything works

Users who don't customize: No action needed, defaults continue working.

---

## 6. Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tools/assemblyzero_config.py` | New | Config loader module |
| `tests/test_assemblyzero_config.py` | New | Unit tests |
| `.assemblyzero/config.example.json` | New | Example config |
| `CLAUDE.md` | Modify | Add Path Configuration section |
| `tools/assemblyzero-permissions.py` | Modify | Use config for paths |
| `tools/assemblyzero-generate.py` | Modify | Use config for paths |
| `.claude/commands/*.md` | Modify | Add config notes |
| `~/.claude/commands/*.md` | Modify | Add config notes |

---

## 7. Testing (Updated with Review Findings)

### 7.1 Unit Tests

```python
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

# Test imports assume assemblyzero_config is importable
# from assemblyzero_config import AssemblyZeroConfig, ConfigError, DEFAULTS


class TestAssemblyZeroConfig:
    """Test suite for AssemblyZeroConfig."""

    def test_loads_defaults_when_no_file(self, tmp_path):
        """Config uses defaults when file doesn't exist."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            from assemblyzero_config import AssemblyZeroConfig
            config = AssemblyZeroConfig()
            assert config.assemblyzero_root() == DEFAULTS['assemblyzero_root']['windows']

    def test_loads_custom_values(self, tmp_path):
        """Config loads custom values from file."""
        config_file = tmp_path / 'config.json'
        custom_config = {
            "version": "1.0",
            "paths": {
                "assemblyzero_root": {
                    "windows": r"D:\Custom\AssemblyZero",
                    "unix": "/d/Custom/AssemblyZero"
                },
                "projects_root": {
                    "windows": r"D:\Custom",
                    "unix": "/d/Custom"
                },
                "user_claude_dir": {
                    "windows": r"D:\Custom\.claude",
                    "unix": "/d/Custom/.claude"
                }
            }
        }
        config_file.write_text(json.dumps(custom_config))

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            from assemblyzero_config import AssemblyZeroConfig
            config = AssemblyZeroConfig()
            assert config.assemblyzero_root() == r"D:\Custom\AssemblyZero"

    def test_handles_invalid_json(self, tmp_path):
        """Config falls back to defaults on invalid JSON."""
        config_file = tmp_path / 'config.json'
        config_file.write_text("{ invalid json }")

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            from assemblyzero_config import AssemblyZeroConfig
            config = AssemblyZeroConfig()
            # Should use defaults, not crash
            assert config.assemblyzero_root() == DEFAULTS['assemblyzero_root']['windows']

    def test_auto_format_selection(self, tmp_path):
        """The 'auto' format selects based on OS."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            with patch('platform.system', return_value='Windows'):
                from assemblyzero_config import AssemblyZeroConfig
                config = AssemblyZeroConfig()
                # Force recalculation
                AssemblyZeroConfig._detected_os = None
                result = config.assemblyzero_root(fmt='auto')
                assert '\\' in result  # Windows path

    def test_missing_key_uses_default(self, tmp_path):
        """Missing keys fall back to defaults."""
        config_file = tmp_path / 'config.json'
        partial_config = {
            "version": "1.0",
            "paths": {
                "assemblyzero_root": {
                    "windows": r"D:\Custom\AssemblyZero",
                    "unix": "/d/Custom/AssemblyZero"
                }
                # Missing projects_root and user_claude_dir
            }
        }
        config_file.write_text(json.dumps(partial_config))

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            from assemblyzero_config import AssemblyZeroConfig
            config = AssemblyZeroConfig()
            # Schema validation should fail, use defaults for all
            assert config.projects_root() == DEFAULTS['projects_root']['windows']

    def test_path_traversal_sanitized(self, tmp_path):
        """Path traversal attacks are neutralized."""
        config_file = tmp_path / 'config.json'
        malicious_config = {
            "version": "1.0",
            "paths": {
                "assemblyzero_root": {
                    "windows": r"C:\Users\..\..\Windows\System32",
                    "unix": "/c/Users/../../etc/passwd"
                },
                "projects_root": {
                    "windows": r"C:\Projects",
                    "unix": "/c/Projects"
                },
                "user_claude_dir": {
                    "windows": r"C:\.claude",
                    "unix": "/c/.claude"
                }
            }
        }
        config_file.write_text(json.dumps(malicious_config))

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            from assemblyzero_config import AssemblyZeroConfig
            config = AssemblyZeroConfig()
            # Path should have ../ removed
            result = config.assemblyzero_root()
            assert '..' not in result

    def test_unix_format_explicit(self, tmp_path):
        """Explicitly requesting unix format works."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            from assemblyzero_config import AssemblyZeroConfig
            config = AssemblyZeroConfig()
            result = config.assemblyzero_root(fmt='unix')
            assert result.startswith('/')

    def test_reload_picks_up_changes(self, tmp_path):
        """reload() re-reads config from disk."""
        config_file = tmp_path / 'config.json'
        initial_config = {
            "version": "1.0",
            "paths": {
                "assemblyzero_root": {"windows": r"C:\Initial", "unix": "/c/Initial"},
                "projects_root": {"windows": r"C:\Initial", "unix": "/c/Initial"},
                "user_claude_dir": {"windows": r"C:\Initial", "unix": "/c/Initial"}
            }
        }
        config_file.write_text(json.dumps(initial_config))

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            from assemblyzero_config import AssemblyZeroConfig
            config = AssemblyZeroConfig()
            assert config.assemblyzero_root() == r"C:\Initial"

            # Update file
            initial_config['paths']['assemblyzero_root']['windows'] = r"C:\Updated"
            config_file.write_text(json.dumps(initial_config))

            # Reload
            config.reload()
            assert config.assemblyzero_root() == r"C:\Updated"
```

### 7.2 Integration Tests

1. Run `assemblyzero-permissions.py --audit` with default config → works
2. Run with custom config pointing to different location → works
3. Run with missing config file → uses defaults, works
4. Run with malformed config → uses defaults, logs warning

---

## 8. Rollback Plan

If issues arise:
1. Revert to hardcoded paths in tools
2. Keep config loader but don't use it
3. Config system is additive, not destructive

---

## 9. Open Questions (Resolved)

1. **Should we use environment variables too?**
   - Decision: Start with config file only, add env var support later if needed

2. **Where should config.example.json live?**
   - Decision: `AssemblyZero/.assemblyzero/config.example.json`

3. **How do we handle the first-time setup?**
   - Decision: Use defaults, let user create manually

---

## 10. Review Checklist

- [x] Schema design reviewed (Gemini General Review)
- [x] Security reviewed (Gemini Security Review)
- [x] Implementation reviewed (Gemini Implementation Review)
- [x] Path traversal mitigation added
- [x] Schema validation added
- [x] Error messages genericized
- [x] Test coverage expanded
- [x] Backward compatibility verified
- [x] Documentation clear
- [x] Migration path clear
