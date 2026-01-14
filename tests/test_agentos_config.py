"""
Unit tests for agentos_config.py

Tests cover:
- Default value loading when no config file
- Custom config loading
- Invalid JSON handling
- Schema validation
- Path traversal sanitization
- Auto format selection
- Reload functionality
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))


class TestAgentOSConfig:
    """Test suite for AgentOSConfig."""

    def test_loads_defaults_when_no_file(self, tmp_path):
        """Config uses defaults when file doesn't exist."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            # Need to reload the module to pick up the patched path
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            assert config.agentos_root() == agentos_config.DEFAULTS['agentos_root']['windows']

    def test_loads_custom_values(self, tmp_path):
        """Config loads custom values from file."""
        config_file = tmp_path / 'config.json'
        custom_config = {
            "version": "1.0",
            "paths": {
                "agentos_root": {
                    "windows": r"D:\Custom\AgentOS",
                    "unix": "/d/Custom/AgentOS"
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
        import agentos_config
        # Patch the module-level constant directly
        original_path = agentos_config.CONFIG_PATH
        agentos_config.CONFIG_PATH = config_file
        try:
            config = agentos_config.AgentOSConfig()
            assert config.agentos_root() == r"D:\Custom\AgentOS"
            assert config.projects_root() == r"D:\Custom"
            assert config.user_claude_dir() == r"D:\Custom\.claude"
        finally:
            agentos_config.CONFIG_PATH = original_path

    def test_handles_invalid_json(self, tmp_path):
        """Config falls back to defaults on invalid JSON."""
        config_file = tmp_path / 'config.json'
        config_file.write_text("{ invalid json }")

        with patch('agentos_config.CONFIG_PATH', config_file):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            # Should use defaults, not crash
            assert config.agentos_root() == agentos_config.DEFAULTS['agentos_root']['windows']

    def test_auto_format_selection_windows(self, tmp_path):
        """The 'auto' format selects Windows on Windows OS."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            with patch('platform.system', return_value='Windows'):
                # Reset cached OS detection
                agentos_config.AgentOSConfig._detected_os = None
                config = agentos_config.AgentOSConfig()
                result = config.agentos_root(fmt='auto')
                assert '\\' in result  # Windows path has backslashes

    def test_auto_format_selection_unix(self, tmp_path):
        """The 'auto' format selects Unix on Linux/Mac."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            with patch('platform.system', return_value='Linux'):
                # Reset cached OS detection
                agentos_config.AgentOSConfig._detected_os = None
                config = agentos_config.AgentOSConfig()
                result = config.agentos_root(fmt='auto')
                assert result.startswith('/')  # Unix path

    def test_missing_key_falls_back_to_defaults(self, tmp_path):
        """Missing keys cause fallback to full defaults (schema validation)."""
        config_file = tmp_path / 'config.json'
        partial_config = {
            "version": "1.0",
            "paths": {
                "agentos_root": {
                    "windows": r"D:\Custom\AgentOS",
                    "unix": "/d/Custom/AgentOS"
                }
                # Missing projects_root and user_claude_dir
            }
        }
        config_file.write_text(json.dumps(partial_config))

        with patch('agentos_config.CONFIG_PATH', config_file):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            # Schema validation should fail due to missing keys
            # So all values should be defaults
            assert config.projects_root() == agentos_config.DEFAULTS['projects_root']['windows']

    def test_path_traversal_sanitized(self, tmp_path):
        """Path traversal attacks are neutralized."""
        config_file = tmp_path / 'config.json'
        malicious_config = {
            "version": "1.0",
            "paths": {
                "agentos_root": {
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

        with patch('agentos_config.CONFIG_PATH', config_file):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            # Path should have ../ removed
            result = config.agentos_root()
            assert '..' not in result

            result_unix = config.agentos_root_unix()
            assert '..' not in result_unix

    def test_unix_format_explicit(self, tmp_path):
        """Explicitly requesting unix format works."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            result = config.agentos_root(fmt='unix')
            assert result.startswith('/')

    def test_windows_format_explicit(self, tmp_path):
        """Explicitly requesting windows format works."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            result = config.agentos_root(fmt='windows')
            assert '\\' in result or ':' in result  # Windows path

    def test_reload_picks_up_changes(self, tmp_path):
        """reload() re-reads config from disk."""
        config_file = tmp_path / 'config.json'
        initial_config = {
            "version": "1.0",
            "paths": {
                "agentos_root": {"windows": r"C:\Initial", "unix": "/c/Initial"},
                "projects_root": {"windows": r"C:\Initial", "unix": "/c/Initial"},
                "user_claude_dir": {"windows": r"C:\Initial", "unix": "/c/Initial"}
            }
        }
        config_file.write_text(json.dumps(initial_config))

        import agentos_config
        # Patch the module-level constant directly
        original_path = agentos_config.CONFIG_PATH
        agentos_config.CONFIG_PATH = config_file
        try:
            config = agentos_config.AgentOSConfig()
            assert config.agentos_root() == r"C:\Initial"

            # Update file
            initial_config['paths']['agentos_root']['windows'] = r"C:\Updated"
            config_file.write_text(json.dumps(initial_config))

            # Reload
            config.reload()
            assert config.agentos_root() == r"C:\Updated"
        finally:
            agentos_config.CONFIG_PATH = original_path

    def test_missing_version_uses_defaults(self, tmp_path):
        """Config without version key uses defaults."""
        config_file = tmp_path / 'config.json'
        no_version_config = {
            "paths": {
                "agentos_root": {"windows": r"D:\NoVersion", "unix": "/d/NoVersion"},
                "projects_root": {"windows": r"D:\NoVersion", "unix": "/d/NoVersion"},
                "user_claude_dir": {"windows": r"D:\NoVersion", "unix": "/d/NoVersion"}
            }
        }
        config_file.write_text(json.dumps(no_version_config))

        with patch('agentos_config.CONFIG_PATH', config_file):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            # Should fall back to defaults due to missing version
            assert config.agentos_root() == agentos_config.DEFAULTS['agentos_root']['windows']

    def test_empty_file_uses_defaults(self, tmp_path):
        """Empty config file uses defaults."""
        config_file = tmp_path / 'config.json'
        config_file.write_text("{}")

        with patch('agentos_config.CONFIG_PATH', config_file):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()
            # Should fall back to defaults
            assert config.agentos_root() == agentos_config.DEFAULTS['agentos_root']['windows']

    def test_convenience_methods(self, tmp_path):
        """Convenience _unix() methods work correctly."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config = agentos_config.AgentOSConfig()

            # All _unix methods should return unix-style paths
            assert config.agentos_root_unix().startswith('/')
            assert config.projects_root_unix().startswith('/')
            assert config.user_claude_dir_unix().startswith('/')


class TestValidateSchema:
    """Tests for the _validate_schema method."""

    def test_valid_schema(self, tmp_path):
        """Valid schema passes validation."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config_instance = agentos_config.AgentOSConfig()
            valid_config = {
                "version": "1.0",
                "paths": {
                    "agentos_root": {"windows": "C:\\Test", "unix": "/c/Test"},
                    "projects_root": {"windows": "C:\\Test", "unix": "/c/Test"},
                    "user_claude_dir": {"windows": "C:\\Test", "unix": "/c/Test"}
                }
            }
            errors = config_instance._validate_schema(valid_config)
            assert errors == []

    def test_missing_paths_key(self, tmp_path):
        """Missing 'paths' key is caught."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config_instance = agentos_config.AgentOSConfig()
            invalid_config = {"version": "1.0"}
            errors = config_instance._validate_schema(invalid_config)
            assert "Missing 'paths' key" in errors


class TestSanitizePath:
    """Tests for the _sanitize_path method."""

    def test_removes_forward_slash_traversal(self, tmp_path):
        """Removes ../ patterns."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config_instance = agentos_config.AgentOSConfig()
            result = config_instance._sanitize_path("/foo/../bar/../baz")
            assert ".." not in result

    def test_removes_backslash_traversal(self, tmp_path):
        """Removes ..\\ patterns."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config_instance = agentos_config.AgentOSConfig()
            result = config_instance._sanitize_path(r"C:\foo\..\bar\..\baz")
            assert ".." not in result

    def test_clean_path_unchanged(self, tmp_path):
        """Clean paths are not modified."""
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config_instance = agentos_config.AgentOSConfig()
            clean_path = "/c/Users/mcwiz/Projects"
            result = config_instance._sanitize_path(clean_path)
            assert result == clean_path

    def test_bypass_attempt_blocked(self, tmp_path):
        """
        Bypass attempts like '....//'' are blocked.

        Security fix: Single-pass regex can be bypassed because
        '....//'' -> '../' after one pass. Loop-until-stable prevents this.
        """
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config_instance = agentos_config.AgentOSConfig()

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
        with patch('agentos_config.CONFIG_PATH', tmp_path / 'nonexistent.json'):
            import importlib
            import agentos_config
            importlib.reload(agentos_config)

            config_instance = agentos_config.AgentOSConfig()
            # Deeply nested traversal
            result = config_instance._sanitize_path("a/../b/../c/../d/../e")
            assert ".." not in result
