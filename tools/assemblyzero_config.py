#!/usr/bin/env python3
"""
AssemblyZero configuration loader.

Provides centralized path configuration for AssemblyZero tools and scripts.
Paths are loaded from ~/.assemblyzero/config.json with fallback to defaults.

Usage:
    from assemblyzero_config import config

    # Get paths (default: Windows format)
    root = config.assemblyzero_root()
    root_unix = config.assemblyzero_root_unix()

    # Or use format parameter
    root = config.assemblyzero_root(fmt='unix')
    root = config.assemblyzero_root(fmt='auto')  # Detect from OS

Security Features:
    - Path traversal sanitization (removes ../ patterns)
    - Schema validation on load
    - Generic error messages (no info leakage)

See: docs/reports/15/lld-path-parameterization.md
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
# These match the current hardcoded values for backward compatibility
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
    """
    Configuration manager for AssemblyZero paths.

    Loads paths from ~/.assemblyzero/config.json with fallback to defaults.
    Thread-safe for reading (singleton pattern).
    """

    # Cache OS detection result
    _detected_os: Optional[str] = None

    def __init__(self):
        """Initialize config by loading from file or using defaults."""
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

        Security fix: Use loop-until-stable approach to prevent bypass.
        Single-pass regex can be bypassed (e.g., '....//'' -> '../').

        Args:
            path: The path string from config

        Returns:
            Sanitized path string, or default path if suspicious
        """
        original = path
        sanitized = path

        # Loop until no more traversal patterns found (prevents bypass)
        # Example bypass without loop: '....//'' -> '../' after one pass
        max_iterations = 10  # Safety limit
        for _ in range(max_iterations):
            prev = sanitized

            # Remove ../ and ..\ patterns (standard traversal)
            sanitized = re.sub(r'\.\.[\\/]', '', sanitized)

            # Remove standalone .. at end
            sanitized = re.sub(r'\.\.$', '', sanitized)

            # Remove .. at start of path (e.g., '..secret' from '..../secret')
            sanitized = re.sub(r'^\.\.', '', sanitized)

            # Remove .. after path separator (e.g., '/..foo' patterns)
            sanitized = re.sub(r'([\\/])\.\.(?=[^\\/.]|$)', r'\1', sanitized)

            if sanitized == prev:
                break  # No more patterns found

        # Additional check: normalize path using pathlib for Windows paths
        # This catches cases like 'C:\foo\..\bar' -> 'C:\bar'
        if sanitized and not sanitized.startswith('/'):
            # Looks like Windows path - use pathlib normalization
            try:
                normalized = str(Path(sanitized).resolve())
                # Only use normalized if it doesn't escape (sanity check)
                if '..' not in normalized:
                    sanitized = normalized
            except (ValueError, OSError):
                pass  # Keep the regex-sanitized version

        # Final safety check: if '..' still present anywhere, path is suspicious
        if '..' in sanitized:
            logger.warning(
                f"Path still contains '..' after sanitization, using empty string"
            )
            sanitized = ""

        # Log if we modified the path (potential attack indicator)
        if sanitized != original:
            logger.warning(
                "Path sanitization modified config path (potential traversal attempt)"
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
        """
        Get AssemblyZero root directory path.

        Args:
            fmt: Path format ('windows', 'unix', or 'auto')

        Returns:
            AssemblyZero root path string
        """
        return self._get_path('assemblyzero_root', fmt)

    def assemblyzero_root_unix(self) -> str:
        """Get AssemblyZero root directory path in Unix format."""
        return self._get_path('assemblyzero_root', 'unix')

    def projects_root(self, fmt: PathFormat = 'windows') -> str:
        """
        Get projects root directory path.

        Args:
            fmt: Path format ('windows', 'unix', or 'auto')

        Returns:
            Projects root path string
        """
        return self._get_path('projects_root', fmt)

    def projects_root_unix(self) -> str:
        """Get projects root directory path in Unix format."""
        return self._get_path('projects_root', 'unix')

    def user_claude_dir(self, fmt: PathFormat = 'windows') -> str:
        """
        Get user Claude directory path (~/.claude).

        Args:
            fmt: Path format ('windows', 'unix', or 'auto')

        Returns:
            User Claude directory path string
        """
        return self._get_path('user_claude_dir', fmt)

    def user_claude_dir_unix(self) -> str:
        """Get user Claude directory path in Unix format."""
        return self._get_path('user_claude_dir', 'unix')

    def reload(self) -> None:
        """
        Reload configuration from disk.

        Useful if the config file has been modified and you want to
        pick up changes without restarting the process.
        """
        self._config = self._load_config()


# Singleton instance - import this for normal usage
config = AssemblyZeroConfig()


# CLI for testing
if __name__ == "__main__":
    import sys

    print("AssemblyZero Configuration")
    print("=" * 50)
    print(f"Config file: {CONFIG_PATH}")
    print(f"Config exists: {CONFIG_PATH.exists()}")
    print()
    print("Current Paths (Windows format):")
    print(f"  assemblyzero_root:    {config.assemblyzero_root()}")
    print(f"  projects_root:   {config.projects_root()}")
    print(f"  user_claude_dir: {config.user_claude_dir()}")
    print()
    print("Current Paths (Unix format):")
    print(f"  assemblyzero_root:    {config.assemblyzero_root_unix()}")
    print(f"  projects_root:   {config.projects_root_unix()}")
    print(f"  user_claude_dir: {config.user_claude_dir_unix()}")
