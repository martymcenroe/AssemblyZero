# 0236 - Gemini is reached only through agy; no API key, no API-key SDK, no fallback

**Status:** Accepted
**Date:** 2026-09-29

## Context and Problem Statement

ADR 0220 established `agy` as the Gemini transport. #1605 retired the API-key rotation on 2026-06-23. However, no decision record explicitly banned API keys, and the codebase still contains machinery to read and fallback to a `GEMINI_API_KEY` (e.g., in `tools/assemblyzero_credentials.py` and `google-genai` dependencies). This led to incidents like #2926 where nodes silently fell back to an unauthenticated or stale-key client and skipped execution.

## Decision

**AssemblyZero reaches Gemini only through `agy`. There is no Gemini API key, no API-key SDK path, and no fallback to one.**

- `agy` is the only Gemini transport.
- No code reads a Gemini or Google API key.
- SDKs that accept an API key (`google-genai`, `langchain-google-genai`) are banned as dependencies.
- If `agy` is unavailable, the run stops loudly (see ADR 0235: Loud Failure). It never falls back to an API-key client.

## Consequences

The following artifacts and code paths must be completely removed:

- `langchain-google-genai` and `google-genai` dependencies in `pyproject.toml`.
- `tools/assemblyzero_credentials.py` and its tests (`tests/unit/test_credentials.py`).
- The SDK exception classifier in `assemblyzero/core/errors.py` (handling `google.genai` and `google.api_core`).
- API key handling in `tests/e2e/conftest.py`.
- Stale comments and docstrings describing the retired path (e.g., in `adversarial_gemini.py` and `validate_completeness.py`).
- The `GEMINI_API_KEY` and `GOOGLE_API_KEY` environment variables on both the operator's Windows and Ubuntu machines.
