#!/usr/bin/env python3
"""
agentos_credentials.py - Secure credential management for AgentOS

Provides a unified interface for storing and retrieving API credentials
with support for OS keychain, environment variables, and legacy file storage.

Priority hierarchy:
1. Environment Variable (GEMINI_API_KEY) - highest priority
2. OS Keychain (via keyring library)
3. Legacy plaintext file (deprecated, read-only)

Issue: #25
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
import json
import os
import sys
from pathlib import Path

import keyring
import keyring.errors


@dataclass
class Credential:
    """A single API credential."""
    name: str
    key: str
    credential_type: str = "api_key"
    enabled: bool = True


class CredentialBackend(ABC):
    """Abstract base class for credential storage backends."""

    @abstractmethod
    def get_credentials(self) -> List[Credential]:
        """Retrieve all credentials from this backend."""
        pass

    @abstractmethod
    def store_credential(self, credential: Credential) -> bool:
        """Store a credential. Returns True on success."""
        pass

    @abstractmethod
    def delete_credential(self, name: str) -> bool:
        """Delete a credential by name. Returns True on success."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend is available on the current system."""
        pass


class EnvBackend(CredentialBackend):
    """Environment variable backend (highest priority)."""

    ENV_VAR = "GEMINI_API_KEY"

    def get_credentials(self) -> List[Credential]:
        key = os.environ.get(self.ENV_VAR)
        if key:
            return [Credential(name="env", key=key)]
        return []

    def store_credential(self, credential: Credential) -> bool:
        return False  # Can't store to env vars

    def delete_credential(self, name: str) -> bool:
        return False  # Can't delete env vars

    def is_available(self) -> bool:
        return bool(os.environ.get(self.ENV_VAR))


class KeychainBackend(CredentialBackend):
    """OS Keychain backend using keyring library."""

    SERVICE_NAME = "AgentOS-Gemini"
    INDEX_KEY = "_credential_index"

    def get_credentials(self) -> List[Credential]:
        credentials = []
        try:
            # Get list of credential names from index
            index_json = keyring.get_password(self.SERVICE_NAME, self.INDEX_KEY)
            if not index_json:
                return []

            names = json.loads(index_json)
            for name in names:
                key = keyring.get_password(self.SERVICE_NAME, f"credential-{name}")
                if key:
                    credentials.append(Credential(name=name, key=key))
        except keyring.errors.NoKeyringError:
            # No keyring backend available
            pass
        except keyring.errors.KeyringError as e:
            print(f"[WARNING] Keychain error reading credentials: {e}", file=sys.stderr)
        except Exception:
            pass
        return credentials

    def store_credential(self, credential: Credential) -> bool:
        try:
            # Store the key
            keyring.set_password(
                self.SERVICE_NAME,
                f"credential-{credential.name}",
                credential.key
            )

            # Update index
            index_json = keyring.get_password(self.SERVICE_NAME, self.INDEX_KEY)
            names = json.loads(index_json) if index_json else []
            if credential.name not in names:
                names.append(credential.name)
                keyring.set_password(self.SERVICE_NAME, self.INDEX_KEY, json.dumps(names))

            return True
        except keyring.errors.NoKeyringError:
            return False
        except keyring.errors.KeyringError as e:
            print(f"[WARNING] Keychain error storing credential: {e}", file=sys.stderr)
            return False
        except Exception:
            return False

    def delete_credential(self, name: str) -> bool:
        try:
            keyring.delete_password(self.SERVICE_NAME, f"credential-{name}")

            # Update index
            index_json = keyring.get_password(self.SERVICE_NAME, self.INDEX_KEY)
            if index_json:
                names = json.loads(index_json)
                if name in names:
                    names.remove(name)
                    keyring.set_password(self.SERVICE_NAME, self.INDEX_KEY, json.dumps(names))
            return True
        except keyring.errors.NoKeyringError:
            return False
        except keyring.errors.KeyringError as e:
            print(f"[WARNING] Keychain error deleting credential: {e}", file=sys.stderr)
            return False
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if keychain is available. Handles headless/CI environments gracefully."""
        try:
            # Try a test operation
            keyring.get_password(self.SERVICE_NAME, "_test")
            return True
        except keyring.errors.NoKeyringError:
            # No keyring backend available (common in CI/headless Linux)
            return False
        except keyring.errors.KeyringError as e:
            # Other keyring errors (locked, permissions, etc.)
            print(f"[WARNING] Keychain error: {e}", file=sys.stderr)
            return False
        except Exception:
            return False


class LegacyFileBackend(CredentialBackend):
    """Legacy plaintext file backend (deprecated)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path.home() / ".agentos" / "gemini-credentials.json"

    def get_credentials(self) -> List[Credential]:
        if not self.path.exists():
            return []

        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return [
                Credential(
                    name=c.get("name", f"key-{i}"),
                    key=c["key"],
                    credential_type=c.get("type", "api_key"),
                    enabled=c.get("enabled", True)
                )
                for i, c in enumerate(data.get("credentials", []))
                if c.get("enabled", True)
            ]
        except Exception:
            return []

    def store_credential(self, credential: Credential) -> bool:
        return False  # Don't allow new storage to legacy format

    def delete_credential(self, name: str) -> bool:
        return False  # Don't modify legacy file

    def is_available(self) -> bool:
        return self.path.exists()


class CredentialManager:
    """
    Unified credential manager with backend priority.

    Priority order:
    1. Environment variables (GEMINI_API_KEY)
    2. OS Keychain (via keyring)
    3. Legacy plaintext file (deprecated, read-only)
    """

    def __init__(self):
        self.backends = [
            EnvBackend(),
            KeychainBackend(),
            LegacyFileBackend(),
        ]
        self._warned_legacy = False

    def get_credentials(self) -> List[Credential]:
        """Get credentials from highest-priority available backend."""
        for backend in self.backends:
            credentials = backend.get_credentials()
            if credentials:
                # Warn if using legacy backend (once per session)
                if isinstance(backend, LegacyFileBackend) and not self._warned_legacy:
                    print(
                        "[WARNING] Using deprecated plaintext credentials. "
                        "Run 'python -m tools.agentos_credentials migrate' to secure them.",
                        file=sys.stderr
                    )
                    self._warned_legacy = True
                return credentials
        return []

    def get_keychain_backend(self) -> KeychainBackend:
        """Get the keychain backend for direct operations."""
        return self.backends[1]  # KeychainBackend is at index 1

    def get_legacy_backend(self) -> LegacyFileBackend:
        """Get the legacy backend for migration."""
        return self.backends[2]  # LegacyFileBackend is at index 2

    def migrate_to_keychain(self) -> tuple[int, int]:
        """
        Migrate legacy credentials to keychain.
        Returns (migrated_count, failed_count).
        """
        legacy = self.get_legacy_backend()
        keychain = self.get_keychain_backend()

        if not keychain.is_available():
            raise RuntimeError("Keychain not available on this system")

        credentials = legacy.get_credentials()
        migrated = 0
        failed = 0

        for cred in credentials:
            if keychain.store_credential(cred):
                migrated += 1
            else:
                failed += 1

        return (migrated, failed)


def migrate_credentials_command(auto_yes: bool = False):
    """Migrate plaintext credentials to OS keychain.

    Args:
        auto_yes: If True, skip prompts (for scripted usage). Default False.
    """
    manager = CredentialManager()
    legacy = manager.get_legacy_backend()

    # Check if migration needed
    if not legacy.is_available():
        print("No legacy credentials found.")
        return

    # Check for non-interactive session
    is_interactive = sys.stdin.isatty()
    if not is_interactive and not auto_yes:
        print("Non-interactive session detected. Use --yes flag to auto-migrate.")
        return

    # Get credentials to migrate
    creds = legacy.get_credentials()
    if not creds:
        print("No credentials found in legacy file.")
        return

    print(f"Found {len(creds)} credentials to migrate.")

    # Confirm with user (skip if auto_yes)
    if not auto_yes:
        response = input("Migrate to OS keychain? [y/N] ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return

    # Perform migration
    try:
        migrated, failed = manager.migrate_to_keychain()
        print(f"Migrated: {migrated}, Failed: {failed}")
    except RuntimeError as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        return

    if failed == 0 and migrated > 0:
        if auto_yes:
            # Don't auto-delete - too dangerous
            print("Plaintext file retained. Delete manually after verification.")
        else:
            response = input("Delete plaintext file? [y/N] ")
            if response.lower() == 'y':
                legacy.path.unlink()
                print("Plaintext credentials removed.")


def main():
    """CLI entry point for credential management."""
    import argparse

    parser = argparse.ArgumentParser(
        description="AgentOS Credential Manager - Secure API key storage"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # migrate command
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate plaintext credentials to OS keychain"
    )
    migrate_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-confirm migration (for scripted usage)"
    )

    # list command
    subparsers.add_parser(
        "list",
        help="List available credentials (names only, not keys)"
    )

    # status command
    subparsers.add_parser(
        "status",
        help="Show credential backend status"
    )

    args = parser.parse_args()

    if args.command == "migrate":
        migrate_credentials_command(auto_yes=args.yes)
    elif args.command == "list":
        manager = CredentialManager()
        creds = manager.get_credentials()
        if creds:
            print(f"Found {len(creds)} credential(s):")
            for c in creds:
                print(f"  - {c.name} ({c.credential_type})")
        else:
            print("No credentials found.")
    elif args.command == "status":
        manager = CredentialManager()
        print("Credential Backend Status:")
        print(f"  Environment (GEMINI_API_KEY): {'Available' if manager.backends[0].is_available() else 'Not set'}")
        print(f"  OS Keychain: {'Available' if manager.backends[1].is_available() else 'Not available'}")
        print(f"  Legacy file: {'Exists' if manager.backends[2].is_available() else 'Not found'}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
