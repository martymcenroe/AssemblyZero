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
from pathlib import Path, PureWindowsPath
from typing import Literal, Optional

# Configure logging
logger = logging.getLogger(__name__)

PathFormat = Literal['windows', 'unix', 'auto']

# Expected config schema keys (for validation)
# Every path key is optional in the file (#4763): a key it leaves out takes its
# default. A fleet key it does carry needs both formats, as before.
PATH_KEYS = {'assemblyzero_root', 'projects_root', 'user_claude_dir'}
# Where new_repo.py creates a repository (#4763). Either format may be absent;
# with the key absent, new_repo_root() is projects_root().
NEW_REPO_ROOT_KEY = 'new_repo_root'
# Where the fleet's Projects roots setting is (#4773): a pointer, set only on the
# operator's machine, so no tracked file names where that setting lives. Either
# format may be absent; with the key absent, projects_roots_file() is None and
# assemblyzero.core.projects_root uses the checkout's parent as the one root.
PROJECTS_ROOTS_FILE_KEY = 'projects_roots_file'
REQUIRED_FORMAT_KEYS = {'windows', 'unix'}

def _spellings(path: Path) -> dict:
    """A real path in both formats this module serves (#3536).

    On a Windows drive: `C:\\...` and Git Bash's `/c/...`. Under WSL, a drive seen
    through `/mnt/c/...` gets its `C:\\...` twin; an ext4 path has no Windows
    spelling, so both formats are the POSIX path. The format a caller gets on its
    own OS ('auto') is therefore always a path that exists there.
    """
    posix = path.as_posix()
    if len(posix) > 2 and posix[1] == ":":
        return {"windows": posix.replace("/", "\\"), "unix": "/" + posix[0].lower() + posix[2:]}
    if posix.startswith("/mnt/") and len(posix) >= 6 and posix[5].isalpha() and posix[6:7] in ("", "/"):
        rest = posix[6:] or "/"
        return {"windows": posix[5].upper() + ":" + rest.replace("/", "\\"), "unix": posix}
    return {"windows": posix, "unix": posix}


# Default paths (SINGLE SOURCE OF TRUTH), derived from where this checkout sits
# rather than spelled (#3536). The spelled defaults were the Windows user
# directory in its Windows and Git Bash forms; under WSL the 'unix' one pointed at a directory that does
# not exist, so every tool using this module resolved the tree wrongly there. On
# the Windows machine the derived values equal the old ones.
# ~/.assemblyzero/config.json still overrides every one of them.
_REPO = Path(__file__).resolve().parents[1]
DEFAULTS = {
    "assemblyzero_root": _spellings(_REPO),
    "projects_root": _spellings(_REPO.parent),
    "user_claude_dir": _spellings(Path.home() / ".claude"),
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
        if not isinstance(config, dict):
            return ["Top level must be a JSON object"]

        errors = []

        if "version" not in config:
            errors.append("Missing 'version' key")

        if "paths" not in config:
            errors.append("Missing 'paths' key")
            return errors  # Can't validate further without paths

        paths = config["paths"]
        if not isinstance(paths, dict):
            errors.append("'paths' must be a dictionary")
            return errors

        for key in sorted(PATH_KEYS | {NEW_REPO_ROOT_KEY, PROJECTS_ROOTS_FILE_KEY}):
            if key not in paths:
                continue  # an absent key takes its default (#4763)
            value = paths[key]
            if not isinstance(value, dict):
                errors.append(f"Path '{key}' must be a dictionary")
                continue
            if key in PATH_KEYS:
                for fmt in sorted(REQUIRED_FORMAT_KEYS):
                    if fmt not in value:
                        errors.append(f"Path '{key}' missing '{fmt}' format")
            carried = [fmt for fmt in sorted(REQUIRED_FORMAT_KEYS) if fmt in value]
            if not carried:
                errors.append(f"Path '{key}' carries neither 'windows' nor 'unix'")
            for fmt in carried:
                if not isinstance(value[fmt], str):
                    errors.append(f"Path '{key}' format '{fmt}' must be a string")

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
            if PureWindowsPath(sanitized).drive and self._get_os_format() != 'windows':
                # Off Windows, a 'C:\...' path names a place on the Windows side,
                # so it is normalized as a Windows path. resolve() would read it
                # as a relative file name and join it to this side's current
                # directory (#4180).
                sanitized = str(PureWindowsPath(sanitized))
            else:
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
                "Path still contains '..' after sanitization, using empty string"
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
        # Why a config file that exists was not used, or None (#4763). Tools
        # fall back to defaults as before; new_repo.py refuses instead.
        self.load_error: str | None = None
        path = CONFIG_PATH
        if not path.exists():
            logger.debug(f"Config file not found at {path}, using defaults")
            return {"version": "1.0", "paths": DEFAULTS}

        try:
            with open(path, encoding='utf-8') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            # Security: Generic error message, no exception details
            logger.warning("Config file contains invalid JSON, using defaults")
            self.load_error = f"{path} is not valid JSON (line {e.lineno}, column {e.colno})"
            return {"version": "1.0", "paths": DEFAULTS}
        except UnicodeDecodeError:
            logger.warning("Config file is not UTF-8, using defaults")
            self.load_error = f"{path} is not UTF-8 text"
            return {"version": "1.0", "paths": DEFAULTS}
        except IOError as e:
            # Security: Generic error message, no exception details
            logger.warning("Could not read config file, using defaults")
            self.load_error = f"{path} could not be read ({e.strerror or type(e).__name__})"
            return {"version": "1.0", "paths": DEFAULTS}

        # Validate schema
        errors = self._validate_schema(config)
        if errors:
            logger.warning(
                f"Config validation failed ({len(errors)} errors), using defaults"
            )
            for error in errors:
                logger.debug(f"  Validation error: {error}")
            self.load_error = f"{path} failed validation: " + "; ".join(errors)
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

    def new_repo_root(self, fmt: PathFormat = 'windows') -> str:
        """Where new_repo.py creates a new repository (#4763).

        Its own key, so a new repository can start on another disk while every
        tool that reads projects_root still sees the whole fleet. With the key
        absent, exactly what projects_root(fmt) returns.
        """
        if NEW_REPO_ROOT_KEY not in self._config.get("paths", {}):
            return self.projects_root(fmt=fmt)
        return self._get_path(NEW_REPO_ROOT_KEY, fmt)

    def projects_roots_file(self, fmt: PathFormat = 'windows') -> str | None:
        """Where the fleet's Projects roots setting is, or None (#4773).

        None when the key is absent, and when it carries no value for this
        format: unlike the other paths, it never falls back to the other OS's
        spelling, which would name a file this side cannot open.
        assemblyzero.core.projects_root reads the same key itself.
        """
        if fmt == 'auto':
            fmt = self._get_os_format()
        entry = self._config.get("paths", {}).get(PROJECTS_ROOTS_FILE_KEY)
        if not isinstance(entry, dict) or fmt not in entry:
            return None
        return self._sanitize_path(entry[fmt])

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
