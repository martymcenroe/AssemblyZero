# LLD: Encrypt Gemini API Keys at Rest

**Issue:** #25
**Author:** Claude
**Date:** 2026-01-17
**Status:** Gemini Approved (2026-01-17)

## 1. Overview

This LLD describes the implementation of secure credential storage for Gemini API keys, replacing the current plaintext storage with OS keychain integration and environment variable fallback.

## 2. Current State

### 2.1 Storage Location
```
~/.assemblyzero/gemini-credentials.json
```

### 2.2 Current Format
```json
{
  "credentials": [
    {
      "name": "primary",
      "type": "api_key",
      "key": "AIzaSy...",  // Plaintext - INSECURE
      "enabled": true
    },
    {
      "name": "backup",
      "type": "api_key",
      "key": "AIzaSy...",
      "enabled": true
    }
  ]
}
```

### 2.3 Current Code Path
- `gemini-retry.py` reads credentials from JSON file
- Credentials rotated on quota exhaustion
- No encryption, relies on file permissions (chmod 600)

## 3. Proposed Architecture

### 3.1 Credential Storage Hierarchy

```
Priority 1: Environment Variable (GEMINI_API_KEY)
    ↓ (if not set)
Priority 2: OS Keychain (via keyring library)
    ↓ (if unavailable/empty)
Priority 3: Legacy plaintext file (with deprecation warning)
```

### 3.2 Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    gemini-retry.py                       │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              CredentialManager (new)                     │
│  ┌─────────────┬─────────────┬─────────────────────┐   │
│  │ EnvBackend  │KeychainBack │ LegacyFileBackend   │   │
│  │ (Priority 1)│ (Priority 2)│ (Priority 3, deprecated)│
│  └─────────────┴─────────────┴─────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Keychain Service Names

| Platform | Service | Username Format |
|----------|---------|-----------------|
| Windows | `AssemblyZero-Gemini` | `credential-{name}` |
| macOS | `AssemblyZero-Gemini` | `credential-{name}` |
| Linux | `AssemblyZero-Gemini` | `credential-{name}` |

## 4. Detailed Design

### 4.1 New Module: `assemblyzero_credentials.py`

```python
"""
assemblyzero_credentials.py - Secure credential management for AssemblyZero

Provides a unified interface for storing and retrieving API credentials
with support for OS keychain, environment variables, and legacy file storage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
import os
import json
import keyring
import keyring.errors
from pathlib import Path


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

    SERVICE_NAME = "AssemblyZero-Gemini"
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
            import sys
            print(f"[WARNING] Keychain error: {e}", file=sys.stderr)
            return False
        except Exception:
            return False


class LegacyFileBackend(CredentialBackend):
    """Legacy plaintext file backend (deprecated)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path.home() / ".assemblyzero" / "gemini-credentials.json"

    def get_credentials(self) -> List[Credential]:
        if not self.path.exists():
            return []

        try:
            with open(self.path, 'r') as f:
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

    def get_credentials(self) -> List[Credential]:
        """Get credentials from highest-priority available backend."""
        for backend in self.backends:
            credentials = backend.get_credentials()
            if credentials:
                # Warn if using legacy backend
                if isinstance(backend, LegacyFileBackend):
                    import sys
                    print(
                        "[WARNING] Using deprecated plaintext credentials. "
                        "Run 'assemblyzero migrate-credentials' to secure them.",
                        file=sys.stderr
                    )
                return credentials
        return []

    def migrate_to_keychain(self) -> tuple[int, int]:
        """
        Migrate legacy credentials to keychain.
        Returns (migrated_count, failed_count).
        """
        legacy = LegacyFileBackend()
        keychain = KeychainBackend()

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
```

### 4.2 Changes to `gemini-retry.py`

```python
# Replace direct file reading with CredentialManager

from assemblyzero_credentials import CredentialManager

def get_credentials():
    """Get credentials using the credential manager."""
    manager = CredentialManager()
    return manager.get_credentials()
```

### 4.3 Migration Command

New CLI command: `assemblyzero migrate-credentials`

```python
def migrate_credentials_command(auto_yes: bool = False):
    """Migrate plaintext credentials to OS keychain.

    Args:
        auto_yes: If True, skip prompts (for scripted usage). Default False.
    """
    import sys

    manager = CredentialManager()

    # Check if migration needed
    legacy = LegacyFileBackend()
    if not legacy.is_available():
        print("No legacy credentials found.")
        return

    # Check for non-interactive session
    is_interactive = sys.stdin.isatty()
    if not is_interactive and not auto_yes:
        print("Non-interactive session detected. Use --yes flag to auto-migrate.")
        return

    # Confirm with user (skip if auto_yes or non-interactive with flag)
    creds = legacy.get_credentials()
    print(f"Found {len(creds)} credentials to migrate.")

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
```

## 5. Security Considerations

### 5.1 Threat Model

| Threat | Mitigation |
|--------|------------|
| Malicious process reads file | Keychain requires user/process authentication |
| Accidental git commit | Credentials no longer in filesystem |
| Memory dump | Keys still in memory during use (unchanged) |
| Keychain compromise | Same risk as any keychain-stored credential |

### 5.2 Permissions

- Keychain backend: Uses OS-level access controls
- Env var backend: Process environment only
- Legacy backend: chmod 600 (current mitigation)

## 6. Testing Strategy

### 6.1 Unit Tests

```python
def test_env_backend_returns_credential_when_set():
    os.environ["GEMINI_API_KEY"] = "test-key"
    backend = EnvBackend()
    creds = backend.get_credentials()
    assert len(creds) == 1
    assert creds[0].key == "test-key"

def test_keychain_backend_store_and_retrieve():
    backend = KeychainBackend()
    if not backend.is_available():
        pytest.skip("Keychain not available")

    cred = Credential(name="test", key="test-key")
    assert backend.store_credential(cred)

    creds = backend.get_credentials()
    assert any(c.name == "test" for c in creds)

    # Cleanup
    backend.delete_credential("test")

def test_credential_manager_priority():
    # Env var takes priority over keychain
    os.environ["GEMINI_API_KEY"] = "env-key"
    manager = CredentialManager()
    creds = manager.get_credentials()
    assert creds[0].name == "env"
```

### 6.2 Integration Tests

- Test on Windows with Credential Manager
- Test on macOS with Keychain
- Test on Linux with Secret Service
- Test CI environment (no keychain, env var only)

## 7. Rollout Plan

### Phase 1: Add New Code (Non-Breaking)
1. Add `keyring` dependency
2. Add `assemblyzero_credentials.py` module
3. Add migration command
4. Keep existing file-based code working

### Phase 2: Switch Default
1. Update `gemini-retry.py` to use CredentialManager
2. Show deprecation warning for plaintext credentials
3. Document migration in changelog

### Phase 3: Deprecate Legacy (Future)
1. Remove plaintext storage support
2. Require keychain or env var

## 8. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| keyring | ^24.0.0 | Cross-platform keychain access |

## 9. Files to Create/Modify

| File | Action |
|------|--------|
| `tools/assemblyzero_credentials.py` | Create |
| `tools/gemini-retry.py` | Modify |
| `pyproject.toml` | Add keyring dependency |
| `tests/test_credentials.py` | Create |

## 10. Acceptance Criteria Verification

| Criteria | How Verified |
|----------|--------------|
| Keys stored in OS Keychain by default | Unit test + manual verification |
| GEMINI_API_KEY overrides stored creds | Unit test |
| Graceful fallback if Keychain unavailable | CI test (no keychain) |
| Migration of existing credentials | Integration test |
| keyring library added | pyproject.toml check |

## 11. Gemini Review Feedback

**Review Date:** 2026-01-17
**Decision:** APPROVE

### Concerns Raised

1. **Headless Linux environments** - CI/servers often lack Secret Service, causing `keyring` to fail
2. **Non-interactive migration** - Migration prompt could hang in CI pipelines

### How Addressed

| Concern | Resolution |
|---------|------------|
| Headless environments | `KeychainBackend.is_available()` now catches `keyring.errors.NoKeyringError` specifically and returns `False` gracefully |
| Non-interactive sessions | Migration command checks `sys.stdin.isatty()` and requires `--yes` flag for scripted usage |

---

*Gemini-reviewed: 2026-01-17 - APPROVE with suggestions incorporated*
