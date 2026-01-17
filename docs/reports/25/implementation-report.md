# Implementation Report: Encrypt Gemini API Keys at Rest

**Issue:** [#25](https://github.com/martymcenroe/AgentOS/issues/25)
**Date:** 2026-01-17
**Branch:** `25-encrypt-gemini-keys`

## Summary

Implemented secure credential storage for Gemini API keys using OS keychain integration with environment variable and legacy file fallbacks.

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `tools/agentos_credentials.py` | Created | New credential manager module with keychain, env, and legacy backends |
| `tools/gemini-rotate.py` | Modified | Updated to use CredentialManager for API keys |
| `tests/test_credentials.py` | Created | 22 unit tests for credential management |
| `pyproject.toml` | Modified | Added `keyring ^25.7.0` dependency |
| `poetry.lock` | Modified | Updated with keyring and its dependencies |

## Design Decisions

### 1. Three-Backend Priority System

Implemented credential retrieval with priority hierarchy:
1. **Environment Variable** (`GEMINI_API_KEY`) - Highest priority for CI/CD
2. **OS Keychain** - Default secure storage for local users
3. **Legacy File** - Backward compatibility (read-only, deprecated)

**Rationale:** Supports all use cases - CI pipelines (env vars), local development (keychain), and existing users (legacy file with migration path).

### 2. Graceful Degradation

All backend failures are caught and logged without crashing:
- `keyring.errors.NoKeyringError` returns empty credentials (common in CI)
- `keyring.errors.KeyringError` logs warning and continues
- Legacy file not found returns empty credentials

**Rationale:** Gemini review feedback emphasized headless/CI environment support.

### 3. Non-Interactive Session Handling

Migration command detects `sys.stdin.isatty()` and requires `--yes` flag for scripted usage.

**Rationale:** Prevents hanging in CI pipelines (Gemini review feedback).

### 4. Service Name Convention

Keychain entries use:
- Service: `AgentOS-Gemini`
- Username: `credential-{name}` for keys, `_credential_index` for index

**Rationale:** Namespaced to avoid conflicts with other applications.

## Known Limitations

1. **OAuth credentials not migrated** - OAuth is handled by gemini CLI directly (`~/.gemini/oauth_creds.json`). This implementation only handles API keys.

2. **Keychain index stored in keychain** - The list of credential names is stored as JSON in the keychain itself. This is a simple approach but means the index can't be inspected without keychain access.

3. **No automatic migration** - Users must run `python -m tools.agentos_credentials migrate` manually. We chose not to auto-migrate to avoid unexpected prompts.

## Backward Compatibility

- **Existing users:** Legacy file continues to work with deprecation warning
- **New users:** Can use keychain or env vars
- **CI pipelines:** `GEMINI_API_KEY` env var works without changes

## Security Improvements

| Before | After |
|--------|-------|
| Plaintext JSON file | OS keychain (encrypted) |
| Any process can read | OS-level access control |
| Visible in filesystem | Not in filesystem |

---

*Implementation follows Gemini-approved LLD (docs/reports/25/lld-encrypt-gemini-keys.md)*
