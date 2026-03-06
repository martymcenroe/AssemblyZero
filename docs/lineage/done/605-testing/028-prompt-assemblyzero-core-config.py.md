# Implementation Request: assemblyzero/core/config.py

## Task

Write the complete contents of `assemblyzero/core/config.py`.

Change type: Modify
Description: Default update

## LLD Specification

# Implementation Spec: 0605 - Systemic Model Refresh

<!-- Metadata -->
| Field | Value |
|-------|-------|
| Issue | #605 |
| LLD | `docs/lld/active/LLD-605.md` |
| Generated | 2026-03-06 |
| Status | APPROVED |

## 1. Overview
Align models with Gemini 3.1.

## 2. Files to Implement
| Order | File | Change Type | Description |
|-------|------|-------------|-------------|
| 1 | `assemblyzero/core/config.py` | Modify | Default update |
| 2 | `assemblyzero/core/llm_provider.py` | Modify | Mapping update |
| 3 | `tools/gemini-rotate.py` | Modify | String update |
| 4 | `tools/gemini-model-check.sh` | Add | Check script |
| 5 | `tests/test_assemblyzero_config.py` | Modify | Test update |
| 6 | `tests/test_gemini_client.py` | Modify | Test update |

## 3. Requirements
1. Use Gemini 3.1.
2. Update Claude 4.6.

## 10. Test Mapping
| Test ID | Scenario | Expected |
|---------|----------|----------|
| T010 | Model ID verification (REQ-1) | Success |
| T020 | Claude mapping verification (REQ-2) | Success |

## 10. Implementation Notes
None.


## Required File Paths (from LLD - do not deviate)

The following paths are specified in the LLD. Write ONLY to these paths:


Any files written to other paths will be rejected.

## Repository Structure

The actual directory layout of this repository:

```
tests/
  accessibility/
  adversarial/
  benchmark/
  compliance/
  contract/
  e2e/
  fixtures/
    death/
    issue_workflow/
    janitor/
      mock_repo/
    lld_tracking/
    metrics/
    mock_lineage/
    mock_repo/
      src/
    rag/
    scout/
    scraper/
    spelunking/
    verdict_analyzer/
  harness/
  integration/
  security/
  tools/
  unit/
    test_death/
    test_gate/
    test_janitor/
    test_rag/
    test_spelunking/
  visual/
  __init__.py
  conftest.py
  test_assemblyzero_config.py
  test_audit.py
  test_audit_sharding.py
  test_credentials.py
  test_designer.py
  test_gemini_client.py
  test_gemini_credentials_v2.py
  test_integration_workflow.py
  ... and 13 more files
assemblyzero/
  core/
    validation/
  graphs/
  hooks/
  metrics/
  nodes/
  rag/
  spelunking/
  telemetry/
  utils/
  workflows/
    death/
    implementation_spec/
      nodes/
    issue/
      nodes/
    janitor/
      probes/
    lld/
    orchestrator/
    parallel/
    requirements/
      nodes/
      parsers/
    scout/
    testing/
      completeness/
      knowledge/
      nodes/
      runners/
      templates/
  __init__.py
  tracing.py
dashboard/
  src/
    client/
      components/
      pages/
  package.json
  tsconfig.client.json
  tsconfig.json
  tsconfig.worker.json
  wrangler.toml
data/
  hourglass/
  unleashed/
```

Use these real paths — do NOT invent paths that don't exist.

## Existing File Contents

The file currently contains:

```python
"""Configuration constants for AssemblyZero LLD review.

This module defines constants that control LLD review behavior,
including model hierarchy and credential paths.
"""

import os
from pathlib import Path

# =============================================================================
# Model Hierarchy (NEVER downgrade for reviews)
# =============================================================================

# Primary review model - highest reasoning tier available
REVIEWER_MODEL = os.environ.get("REVIEWER_MODEL", "gemini-3.1-pro-preview")

# Acceptable fallback models (Pro-tier only)
REVIEWER_MODEL_FALLBACKS = ["gemini-3.1-pro"]

# Forbidden models - fail closed rather than use these
FORBIDDEN_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash",
    "gemini-2.5-lite",
    "gemini-lite",
    "gemini-3-pro-preview",
    "gemini-3-pro",
]

# =============================================================================
# Claude Model (REQ-2: Claude 4.6)
# =============================================================================

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-4.6-sonnet")

# =============================================================================
# Credential Paths
# =============================================================================

CREDENTIALS_FILE = Path.home() / ".assemblyzero" / "gemini-credentials.json"
ROTATION_STATE_FILE = Path.home() / ".assemblyzero" / "gemini-rotation-state.json"
GEMINI_API_LOG_FILE = Path.home() / ".assemblyzero" / "gemini-api.jsonl"

# =============================================================================
# Retry Configuration
# =============================================================================

MAX_RETRIES_PER_CREDENTIAL = 3
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 60.0

# =============================================================================
# Logging Paths (Issue #57: Session-Sharded Logging)
# =============================================================================

# Permanent audit trail (consolidated from shards)
DEFAULT_AUDIT_LOG_PATH = Path("logs/review_history.jsonl")

# Active session shards directory (gitignored, ephemeral)
LOGS_ACTIVE_DIR = Path("logs/active")

# =============================================================================
# Prompt Paths
# =============================================================================

LLD_REVIEW_PROMPT_PATH = Path("docs/skills/0702c-LLD-Review-Prompt.md")
LLD_GENERATOR_PROMPT_PATH = Path("docs/skills/0705-lld-generator.md")

# =============================================================================
# Output Paths
# =============================================================================

LLD_DRAFTS_DIR = Path("docs/llds/drafts")
```

Modify this file according to the LLD specification.

## Tests That Must Pass

```python
# From C:\Users\mcwiz\Projects\AssemblyZero-605\tests\test_assemblyzero_config.py
"""
Unit tests for assemblyzero_config.py

Tests cover:
- Default value loading when no config file
- Custom config loading
- Invalid JSON handling
- Schema validation
- Path traversal sanitization
- Auto format selection
- Reload functionality

Issue #605: Model ID verification tests (T010, T020)
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))


class TestAssemblyZeroConfig:
    """Test suite for AssemblyZeroConfig."""

    def test_loads_defaults_when_no_file(self, tmp_path):
        """Config uses defaults when file doesn't exist."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            # Need to reload the module to pick up the patched path
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            assert config.assemblyzero_root() == assemblyzero_config.DEFAULTS['assemblyzero_root']['windows']

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

        import importlib
        import assemblyzero_config
        # Patch the module-level constant directly
        original_path = assemblyzero_config.CONFIG_PATH
        assemblyzero_config.CONFIG_PATH = config_file
        try:
            config = assemblyzero_config.AssemblyZeroConfig()
            assert config.assemblyzero_root() == r"D:\Custom\AssemblyZero"
            assert config.projects_root() == r"D:\Custom"
            assert config.user_claude_dir() == r"D:\Custom\.claude"
        finally:
            assemblyzero_config.CONFIG_PATH = original_path

    def test_handles_invalid_json(self, tmp_path):
        """Config falls back to defaults on invalid JSON."""
        config_file = tmp_path / 'config.json'
        config_file.write_text("{ invalid json }")

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            # Should use defaults, not crash
            assert config.assemblyzero_root() == assemblyzero_config.DEFAULTS['assemblyzero_root']['windows']

    def test_auto_format_selection_windows(self, tmp_path):
        """The 'auto' format selects Windows on Windows OS."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            with patch('platform.system', return_value='Windows'):
                # Reset cached OS detection
                assemblyzero_config.AssemblyZeroConfig._detected_os = None
                config = assemblyzero_config.AssemblyZeroConfig()
                result = config.assemblyzero_root(fmt='auto')
                assert '\\' in result  # Windows path has backslashes

    def test_auto_format_selection_unix(self, tmp_path):
        """The 'auto' format selects Unix on Linux/Mac."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            with patch('platform.system', return_value='Linux'):
                # Reset cached OS detection
                assemblyzero_config.AssemblyZeroConfig._detected_os = None
                config = assemblyzero_config.AssemblyZeroConfig()
                result = config.assemblyzero_root(fmt='auto')
                assert result.startswith('/')  # Unix path

    def test_missing_key_falls_back_to_defaults(self, tmp_path):
        """Missing keys cause fallback to full defaults (schema validation)."""
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
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            # Schema validation should fail due to missing keys
            # So all values should be defaults
            assert config.projects_root() == assemblyzero_config.DEFAULTS['projects_root']['windows']

    def test_path_traversal_sanitized(self, tmp_path):
        """Path traversal attacks are neutralized."""
        config_file = tmp_path / 'config.json'
        malicious_config = {
            "version": "1.0",
            "paths": {
                "assemblyzero_root": {
                    "windows": r"C:\Users\..\..\..\Windows\System32",
                    "unix": "/c/Users/../../../etc/passwd"
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
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            # Path should have ../ removed
            result = config.assemblyzero_root()
            assert '..' not in result

            result_unix = config.assemblyzero_root_unix()
            assert '..' not in result_unix

    def test_unix_format_explicit(self, tmp_path):
        """Explicitly requesting unix format works."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            result = config.assemblyzero_root(fmt='unix')
            assert result.startswith('/')

    def test_windows_format_explicit(self, tmp_path):
        """Explicitly requesting windows format works."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            result = config.assemblyzero_root(fmt='windows')
            assert '\\' in result or ':' in result  # Windows path

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

        import assemblyzero_config
        # Patch the module-level constant directly
        original_path = assemblyzero_config.CONFIG_PATH
        assemblyzero_config.CONFIG_PATH = config_file
        try:
            config = assemblyzero_config.AssemblyZeroConfig()
            assert config.assemblyzero_root() == r"C:\Initial"

            # Update file
            initial_config['paths']['assemblyzero_root']['windows'] = r"C:\Updated"
            config_file.write_text(json.dumps(initial_config))

            # Reload
            config.reload()
            assert config.assemblyzero_root() == r"C:\Updated"
        finally:
            assemblyzero_config.CONFIG_PATH = original_path

    def test_missing_version_uses_defaults(self, tmp_path):
        """Config without version key uses defaults."""
        config_file = tmp_path / 'config.json'
        no_version_config = {
            "paths": {
                "assemblyzero_root": {"windows": r"D:\NoVersion", "unix": "/d/NoVersion"},
                "projects_root": {"windows": r"D:\NoVersion", "unix": "/d/NoVersion"},
                "user_claude_dir": {"windows": r"D:\NoVersion", "unix": "/d/NoVersion"}
            }
        }
        config_file.write_text(json.dumps(no_version_config))

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            # Should fall back to defaults due to missing version
            assert config.assemblyzero_root() == assemblyzero_config.DEFAULTS['assemblyzero_root']['windows']

    def test_empty_file_uses_defaults(self, tmp_path):
        """Empty config file uses defaults."""
        config_file = tmp_path / 'config.json'
        config_file.write_text("{}")

        with patch('assemblyzero_config.CONFIG_PATH', config_file):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()
            # Should fall back to defaults
            assert config.assemblyzero_root() == assemblyzero_config.DEFAULTS['assemblyzero_root']['windows']

    def test_convenience_methods(self, tmp_path):
        """Convenience _unix() methods work correctly."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config = assemblyzero_config.AssemblyZeroConfig()

            # All _unix methods should return unix-style paths
            assert config.assemblyzero_root_unix().startswith('/')
            assert config.projects_root_unix().startswith('/')
            assert config.user_claude_dir_unix().startswith('/')


class TestValidateSchema:
    """Tests for the _validate_schema method."""

    def test_valid_schema(self, tmp_path):
        """Valid schema passes validation."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config_instance = assemblyzero_config.AssemblyZeroConfig()
            valid_config = {
                "version": "1.0",
                "paths": {
                    "assemblyzero_root": {"windows": "C:\\Test", "unix": "/c/Test"},
                    "projects_root": {"windows": "C:\\Test", "unix": "/c/Test"},
                    "user_claude_dir": {"windows": "C:\\Test", "unix": "/c/Test"}
                }
            }
            errors = config_instance._validate_schema(valid_config)
            assert errors == []

    def test_missing_paths_key(self, tmp_path):
        """Missing 'paths' key is caught."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config_instance = assemblyzero_config.AssemblyZeroConfig()
            invalid_config = {"version": "1.0"}
            errors = config_instance._validate_schema(invalid_config)
            assert "Missing 'paths' key" in errors


class TestSanitizePath:
    """Tests for the _sanitize_path method."""

    def test_removes_forward_slash_traversal(self, tmp_path):
        """Removes ../ patterns."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config_instance = assemblyzero_config.AssemblyZeroConfig()
            result = config_instance._sanitize_path("/foo/../bar/../baz")
            assert ".." not in result

    def test_removes_backslash_traversal(self, tmp_path):
        """Removes ..\\ patterns."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config_instance = assemblyzero_config.AssemblyZeroConfig()
            result = config_instance._sanitize_path(r"C:\foo\..\bar\..\baz")
            assert ".." not in result

    def test_clean_path_unchanged(self, tmp_path):
        """Clean paths are not modified."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config_instance = assemblyzero_config.AssemblyZeroConfig()
            clean_path = "/c/Users/mcwiz/Projects"
            result = config_instance._sanitize_path(clean_path)
            assert result == clean_path

    def test_bypass_attempt_blocked(self, tmp_path):
        """
        Bypass attempts like '....//'' are blocked.

        Security fix: Single-pass regex can be bypassed because
        '....//'' -> '../' after one pass. Loop-until-stable prevents this.
        """
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config_instance = assemblyzero_config.AssemblyZeroConfig()

            # Test various bypass attempts
            bypass_attempts = [
                "....//etc/passwd",        # ....// -> ../ after single pass
                "..../secret",             # ..../ -> ../ after single pass
                "foo/....//bar",           # Embedded bypass
                "......///etc",            # Triple-dot bypass
                r"C:\foo\....\\..\bar",    # Windows bypass attempt
            ]

            for attempt in bypass_attempts:
                result = config_instance._sanitize_path(attempt)
                assert ".." not in result, f"Bypass succeeded for: {attempt} -> {result}"

    def test_multiple_traversal_layers(self, tmp_path):
        """Multiple layers of traversal are all removed."""
        with patch('assemblyzero_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import assemblyzero_config
            importlib.reload(assemblyzero_config)

            config_instance = assemblyzero_config.AssemblyZeroConfig()
            # Deeply nested traversal
            result = config_instance._sanitize_path("a/../b/../c/../d/../e")
            assert ".." not in result


class TestModelIdVerification:
    """Issue #605: Verify model IDs are correctly set after systemic refresh.

    T010: Gemini model ID verification (REQ-1)
    T020: Claude model ID verification (REQ-2)
    """

    def test_t010_gemini_model_id_is_3_1(self):
        """T010: REVIEWER_MODEL defaults to gemini-3.1-pro-preview (REQ-1).

        Verifies the default Gemini model in config.py has been updated
        to Gemini 3.1 as part of the systemic model refresh.
        """
        from assemblyzero.core.config import (
            FORBIDDEN_MODELS,
            REVIEWER_MODEL_FALLBACKS,
        )

        # Check default (when env var not set) by inspecting the source directly
        # We can't easily unset env vars that may override, so verify the
        # module-level constants that don't depend on env vars.
        assert "gemini-3.1-pro" in REVIEWER_MODEL_FALLBACKS, (
            "REVIEWER_MODEL_FALLBACKS must include gemini-3.1-pro"
        )

        # Ensure old Gemini 2.x and 3.0 models are forbidden
        for forbidden in ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-3-pro-preview", "gemini-3-pro"]:
            assert forbidden in FORBIDDEN_MODELS, (
                f"{forbidden} must be in FORBIDDEN_MODELS"
            )

        # Verify the default REVIEWER_MODEL contains gemini-3.1
        # (may be overridden by env var, but the source default must be correct)
        from assemblyzero.core import config as config_module
        import inspect
        source = inspect.getsource(config_module)
        assert 'gemini-3.1-pro-preview' in source, (
            "config.py source must reference gemini-3.1-pro-preview as default"
        )

    def test_t020_claude_model_id_is_4_6(self):
        """T020: CLAUDE_MODEL defaults to claude-4.6-sonnet (REQ-2).

        Verifies the default Claude model in config.py has been updated
        to Claude 4.6 as part of the systemic model refresh.
        """
        # Verify the source default contains claude-4.6
        from assemblyzero.core import config as config_module
        import inspect
        source = inspect.getsource(config_module)
        assert 'claude-4.6-sonnet' in source, (
            "config.py source must reference claude-4.6-sonnet as default"
        )

        # Also verify via llm_provider that the mapping is consistent
        from assemblyzero.core import llm_provider as llm_module
        provider_source = inspect.getsource(llm_module)
        assert 'claude-4.6' in provider_source, (
            "llm_provider.py must reference claude-4.6 model"
        )
        assert 'gemini-3.1' in provider_source, (
            "llm_provider.py must reference gemini-3.1 model"
        )

# From C:\Users\mcwiz\Projects\AssemblyZero-605\tests\test_gemini_client.py
"""Tests for the Gemini client with rotation logic.

Test Scenarios from LLD:
- 090: 429 triggers rotation
- 100: 529 triggers backoff
- 110: All credentials exhausted
- 120: Model verification
- 130: Forbidden model rejected

Issue #605: Systemic Model Refresh — Gemini 3.1, Claude 4.6
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assemblyzero.core.gemini_client import (
    Credential,
    GeminiCallResult,
    GeminiClient,
    GeminiErrorType,
    RotationState,
)


@pytest.fixture
def temp_credentials_file():
    """Create a temporary credentials file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        creds_file = Path(tmpdir) / "credentials.json"
        creds_file.write_text(
            json.dumps(
                {
                    "credentials": [
                        {"name": "key-1", "key": "test-key-1", "enabled": True, "type": "api_key"},
                        {"name": "key-2", "key": "test-key-2", "enabled": True, "type": "api_key"},
                        {"name": "key-3", "key": "test-key-3", "enabled": True, "type": "api_key"},
                    ]
                }
            )
        )
        yield creds_file


@pytest.fixture
def temp_state_file():
    """Create a temporary state file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "state.json"


class TestGeminiClientModelValidation:
    """Tests for model validation in GeminiClient."""

    def test_130_forbidden_model_rejected_flash(self):
        """Test that Flash model is rejected at initialization."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gemini-2.0-flash")

        assert "forbidden" in str(exc_info.value).lower()

    def test_130_forbidden_model_rejected_lite(self):
        """Test that Lite model is rejected at initialization."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gemini-2.5-lite")

        assert "forbidden" in str(exc_info.value).lower()

    def test_130_forbidden_model_rejected_old_3_pro(self):
        """Test that old gemini-3-pro-preview is rejected after 3.1 refresh."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gemini-3-pro-preview")

        assert "forbidden" in str(exc_info.value).lower()

    def test_130_forbidden_model_rejected_old_3_pro_ga(self):
        """Test that old gemini-3-pro is rejected after 3.1 refresh."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gemini-3-pro")

        assert "forbidden" in str(exc_info.value).lower()

    def test_valid_pro_model_accepted(self, temp_credentials_file, temp_state_file):
        """Test that Gemini 3.1 Pro model is accepted."""
        # Should not raise
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )
        assert client.model == "gemini-3.1-pro-preview"

    def test_non_gemini_model_rejected(self):
        """Test that non-Gemini models are rejected."""
        with pytest.raises(ValueError) as exc_info:
            GeminiClient(model="gpt-4")

        assert "not a valid Gemini model" in str(exc_info.value)

    def test_120_model_id_is_gemini_3_1(self, temp_credentials_file, temp_state_file):
        """T010: Verify Gemini 3.1 model ID is accepted (REQ-1)."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )
        assert "3.1" in client.model
        assert client.model == "gemini-3.1-pro-preview"


class TestCredentialLoading:
    """Tests for credential loading."""

    def test_loads_credentials_from_file(self, temp_credentials_file, temp_state_file):
        """Test that credentials are loaded from file."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        creds = client._load_credentials()
        assert len(creds) == 3
        assert creds[0].name == "key-1"
        assert creds[0].key == "test-key-1"

    def test_missing_credentials_file_raises(self, temp_state_file):
        """Test that missing credentials file raises FileNotFoundError."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=Path("/nonexistent/creds.json"),
            state_file=temp_state_file,
        )

        with pytest.raises(FileNotFoundError):
            client._load_credentials()


class TestErrorClassification:
    """Tests for error classification."""

    def test_quota_exhausted_detection(self, temp_credentials_file, temp_state_file):
        """Test that 429/quota errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        assert (
            client._classify_error("TerminalQuotaError: exhausted")
            == GeminiErrorType.QUOTA_EXHAUSTED
        )
        assert (
            client._classify_error("You have exhausted your capacity")
            == GeminiErrorType.QUOTA_EXHAUSTED
        )
        assert (
            client._classify_error("429 Too Many Requests")
            == GeminiErrorType.QUOTA_EXHAUSTED
        )

    def test_capacity_exhausted_detection(self, temp_credentials_file, temp_state_file):
        """Test that 529/capacity errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        assert (
            client._classify_error("MODEL_CAPACITY_EXHAUSTED")
            == GeminiErrorType.CAPACITY_EXHAUSTED
        )
        assert (
            client._classify_error("503 Service Unavailable")
            == GeminiErrorType.CAPACITY_EXHAUSTED
        )
        assert (
            client._classify_error("The model is overloaded")
            == GeminiErrorType.CAPACITY_EXHAUSTED
        )

    def test_auth_error_detection(self, temp_credentials_file, temp_state_file):
        """Test that auth errors are classified correctly."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        assert (
            client._classify_error("API_KEY_INVALID") == GeminiErrorType.AUTH_ERROR
        )
        assert (
            client._classify_error("401 Unauthorized") == GeminiErrorType.AUTH_ERROR
        )
        assert (
            client._classify_error("PERMISSION_DENIED") == GeminiErrorType.AUTH_ERROR
        )


class TestRotationLogic:
    """Tests for credential rotation logic."""

    def test_090_429_triggers_rotation(self, temp_credentials_file, temp_state_file):
        """Test that 429 error causes rotation to next credential."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        call_sequence = []

        def mock_client_init(api_key):
            """Capture API key and return mock client."""
            call_sequence.append(api_key)
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception(
                "TerminalQuotaError: exhausted"
            )
            return mock_client

        with patch("assemblyzero.core.gemini_client.genai.Client") as mock_client_class:
            mock_client_class.side_effect = mock_client_init

            result = client.invoke("system", "content")

        # Should have tried all 3 credentials
        assert len(call_sequence) == 3
        assert call_sequence[0] == "test-key-1"
        assert call_sequence[1] == "test-key-2"
        assert call_sequence[2] == "test-key-3"

        # Result should indicate rotation occurred
        assert result.rotation_occurred is True
        assert result.success is False

    def test_100_529_triggers_backoff(self, temp_credentials_file, temp_state_file):
        """Test that 529 error causes backoff retry on same credential."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        attempts = [0]

        def mock_generate(*args, **kwargs):
            attempts[0] += 1
            if attempts[0] < 3:
                raise Exception("MODEL_CAPACITY_EXHAUSTED")
            # Succeed on 3rd attempt
            mock_response = MagicMock()
            mock_response.text = "Success"
            return mock_response

        def mock_client_init(api_key):
            """Return mock client with generate_content that tracks attempts."""
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = mock_generate
            return mock_client

        with patch("assemblyzero.core.gemini_client.genai.Client") as mock_client_class:
            mock_client_class.side_effect = mock_client_init

            with patch("time.sleep"):  # Skip actual delay
                result = client.invoke("system", "content")

        # Should have retried 3 times on same credential
        assert attempts[0] == 3
        assert result.success is True
        assert result.rotation_occurred is False

    def test_110_all_credentials_exhausted(self, temp_credentials_file, temp_state_file):
        """Test behavior when all credentials are exhausted."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        def mock_client_init(api_key):
            """Return mock client that always raises quota error."""
            mock_client = MagicMock()
            mock_client.models.generate_content.side_effect = Exception(
                "TerminalQuotaError: exhausted"
            )
            return mock_client

        with patch("assemblyzero.core.gemini_client.genai.Client") as mock_client_class:
            mock_client_class.side_effect = mock_client_init

            result = client.invoke("system", "content")

        assert result.success is False
        # When all credentials fail due to quota exhaustion, error type is QUOTA_EXHAUSTED
        assert result.error_type == GeminiErrorType.QUOTA_EXHAUSTED
        assert "All credentials failed" in result.error_message


class TestBackoffDelay:
    """Tests for backoff delay calculation."""

    def test_exponential_backoff(self, temp_credentials_file, temp_state_file):
        """Test that backoff delay is exponential."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        # Base is 2.0 seconds, exponential growth
        assert client._backoff_delay(0) == 2.0  # 2 * 2^0 = 2
        assert client._backoff_delay(1) == 4.0  # 2 * 2^1 = 4
        assert client._backoff_delay(2) == 8.0  # 2 * 2^2 = 8

    def test_backoff_max_cap(self, temp_credentials_file, temp_state_file):
        """Test that backoff is capped at maximum."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        # Should be capped at 60 seconds
        assert client._backoff_delay(10) == 60.0


class TestResetTimeParsing:
    """Tests for quota reset time parsing."""

    def test_parses_reset_time(self, temp_credentials_file, temp_state_file):
        """Test parsing of reset time from error message."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        result = client._parse_reset_time("Your quota will reset after 15h11m58s")
        assert result is not None
        assert abs(result - 15.2) < 0.1  # 15 hours + 11 minutes

    def test_returns_none_for_unparseable(self, temp_credentials_file, temp_state_file):
        """Test that unparseable messages return None."""
        client = GeminiClient(
            model="gemini-3.1-pro-preview",
            credentials_file=temp_credentials_file,
            state_file=temp_state_file,
        )

        result = client._parse_reset_time("Some random error message")
        assert result is None


```

## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
FAILED tests/test_assemblyzero_config.py::TestModelIdVerification::test_t020_claude_model_id_is_4_6
1 failed, 40 passed, 8 warnings in 2.21s
```

Read the error messages carefully and fix the root cause in your implementation.

## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the Python code.

```python
# Your Python code here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the Python code in a single fenced code block
