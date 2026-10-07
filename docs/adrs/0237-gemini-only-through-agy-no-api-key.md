# ADR 0237: Gemini is reached only through agy; no API key, no API-key SDK, no fallback

**Status:** Accepted (the operator, 2026-10-06, in session `55a83d74-76d7-4ae2-8fce-20d30173a8fc`: "I accept ADR 0236 and ADR 0237.")
**Date:** 2026-10-06
**Deciders:** Operator
**Related:** ADR 0220 (agy transport), ADR 0234 (Gemini in agy drafts and validates), ADR 0236 (every failure is loud), #3582, #3583, #3585, #1605, #2926, #3672, #3673

---

## Decision

**AssemblyZero reaches Gemini only through `agy`. There is no Gemini API key, no SDK that takes a key is a dependency, and nothing falls back to one.**

- No code reads `GEMINI_API_KEY` or `GOOGLE_API_KEY`.
- No code imports `google.genai`, `google.generativeai`, `google.api_core` or `langchain_google_genai`.
- No package that exists to call Gemini, or to authenticate to Google, with a key or with Google credentials is a dependency.

ADR 0220 made `agy` the transport, and #1605 retired the API-key rotation on 2026-06-23. This ADR makes the absence permanent, and makes it something a test can fail on.

## When agy is unavailable

The run stops, per ADR 0236. This covers four cases:
- no `agy` on the path;
- `agy` not signed in;
- an `agy` call that fails;
- a model id that `agy` does not serve.

The failure is loud and logged with the seat, the spec and the error, and it alerts the operator. No downstream node runs.

There is no second transport to try and no "skipped". #2926 showed what the fallback did: from 2026-07-31 to 2026-09-06, the N7.5 review fell through to `google.genai.Client()`. That client read a stale `GEMINI_API_KEY` from the machine's environment, received `API_KEY_INVALID`, and skipped on every one of 19 runs, telling no one.

## What is already gone

These were verified at `f29dbb17` on 2026-10-06:
- **The SDK dependencies.** `google-genai` and `langchain-google-genai` are no longer dependencies in `pyproject.toml` (#3672, #3673).
- **The key manager.** `tools/assemblyzero_credentials.py`, which started from `GEMINI_API_KEY`, and its test `tests/unit/test_credentials.py` are deleted.
- **The imports.** No live import of the four modules above remains in `assemblyzero/`, `tools/` or `tests/`.
- **The e2e key handling.** `tests/e2e/conftest.py` no longer names a Gemini or Google key.

## What remains, and must be removed (#3583)

1. **The SDK exception classifier.** `classify_gemini_error` (`assemblyzero/core/errors.py:229-262`) classifies `google.genai` and `google.api_core` exceptions. Three callers route `agy` failures through it:
   - `assemblyzero/core/gemini_client.py:50` (import), `:640` (call), and `:711`, a deprecated method's docstring that names it;
   - `assemblyzero/core/llm_provider.py:1758-1760`;
   - `assemblyzero/workflows/testing/adversarial_gemini.py:27` (import) and `:294` (call).

   It is retired. The callers classify what `agy` actually returns: its exit code and its output.
2. **Comments that describe the SDK path as present.**
   - `assemblyzero/core/errors.py:230` and `:237-241`, which go with the classifier in item 1;
   - `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py:1478`;
   - `assemblyzero/workflows/testing/adversarial_gemini.py:11-12` and `:326`.

   Each is corrected or removed. The test docstring at `tests/unit/test_adversarial_gemini.py:324-325` describes #2926 as history and stays.
3. **A pinned dependency nothing imports.** `google-auth` (`pyproject.toml:28`) has no import anywhere in `assemblyzero/`, `tools/` or `tests/`. It authenticates to Google, and is removed with its lock entry.
4. **Stale text in a landed one-shot script.** `tools/land_2283_ci_tiers.py:95` describes an adversarial test that skips when neither key is set. #3583 corrects or retires that text.
5. **The keys themselves**, on both machines:
   - **Ubuntu:** the user's shell startup files and environment, `/etc/environment` and `/etc/profile.d/`.
   - **Windows:** the User and Machine environment scopes.

   #3583 requirement 6 gives the procedure. A key is tested for by its name, never by printing its value. The `sudo` and Machine-scope removals are the operator's commands.

## The guard

#3583 adds an `ast` test in the unit tier, citing this ADR. It fails on two things anywhere under `assemblyzero/` or `tools/`:
- an import of any of the four modules above;
- a read of `GEMINI_API_KEY` or `GOOGLE_API_KEY`, through `os.environ`, `os.getenv` or `os.environ.get`.

A second assertion fails if `pyproject.toml` names `google-genai`, `langchain-google-genai`, `google-generativeai` or `google-auth`. None comes back.

## Consequences

- **`agy` is the only Gemini transport.** A machine without `agy` signed in cannot run a workflow that names a Gemini spec. The preflight says so before the first node (#3506).
- **Gemini failures are classified from `agy`'s exit and output.** They are no longer read from SDK exception types the code no longer receives.
- **Nothing can bring the key path back unseen.** A change that reintroduces it fails the unit tier.

## Provenance

The operator gave the rule in the supervising session `238abf52-9bc1-4653-b664-4051b8942d47` on 2026-09-25 at about 9:05 AM Central. The #3562 summary had asked him to remove `GEMINI_API_KEY` from his environment, and he answered that the fleet uses no API key. This ADR was drafted on 2026-10-06 under the #3585 work order.
