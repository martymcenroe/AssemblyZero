# Implementation Report: Remove Gemini Rotation Remnants

## Summary
The local credential rotation logic that attempted to rotate API keys and track state inside `GeminiClient` was completely removed, as it was obsoleted when Gemini calls were re-routed through the `agy` CLI which handles governance centrally.

## Changes Made
- **assemblyzero/core/gemini_client.py**: Completely stripped `Credential`, `RotationState`, and `CredentialPoolExhaustedException`. Removed `get_credential_status()` and `log_gemini_event()`. Rewrote `invoke()` to eliminate the recursive multi-credential attempts and local rate-limit tracking, relying instead on straightforward CLI invocation. 
- **assemblyzero/core/capacity.py**: Rewrote `_gemini_capacity()` to just return `True`, because we no longer have local credential availability visibility (the transport layer handles it).
- **assemblyzero/core/preflight.py**: Removed `check_gemini_available` and `check_gemini_reachable` which checked the removed credential files. 
- **pyproject.toml**: Removed dead dependencies `langchain-google-genai` and `google-genai`.
- **tools/**: Removed obsolete `gemini-retry.py` and `assemblyzero_credentials.py`.
- **tests/**: Removed `test_gemini_client_capacity.py`, `test_no_retired_rotation_advice.py`, `test_credentials.py`. Cleaned up `test_gemini_client.py` and `conftest.py`.
