# Implementation Report: the rest of the API-key path removed (#3583, ADR 0237)

#3672 and #3673 had already removed `google-genai`, `langchain-google-genai`, `tools/assemblyzero_credentials.py` and its tests, and every live import of the four SDK modules. This removes what ADR 0237 lists as remaining.

## Code

- **`assemblyzero/core/errors.py`: `classify_gemini_error` is retired.** In its place is `classify_agy_error`, which says what it classifies: agy's failure text, wrapped by the caller in an exception.
  - The function had stopped touching the SDK, but its docstring and section header still described `google.genai` and `google.api_core`.
  - It also matched the key-only token `API_KEY_INVALID`, which agy never reports; that token is gone.
  - Its three callers are updated: `assemblyzero/core/gemini_client.py`, `assemblyzero/core/llm_provider.py` and `assemblyzero/workflows/testing/adversarial_gemini.py`.
- **`assemblyzero/core/gemini_client.py`: dead code removed.**
  - The method `_classify_error` called itself "deprecated, kept for backward compatibility". Only its own tests called it, and those tests asserted that `API_KEY_INVALID` is an auth error.
  - It took with it the three pattern constants it alone read: `QUOTA_EXHAUSTED_PATTERNS`, `CAPACITY_PATTERNS` and `AUTH_ERROR_PATTERNS`. The last of these named `API_KEY_INVALID` and "API key not valid".
- **`pyproject.toml` and `poetry.lock`:** `google-auth` is removed with `poetry remove`. No module in `assemblyzero/`, `tools/` or `tests/` imported it.

## Comments

- `assemblyzero/workflows/implementation_spec/nodes/validate_completeness.py`: the third-party example `google.genai` becomes `requests.adapters`.
- `assemblyzero/workflows/testing/adversarial_gemini.py`: the module docstring and the `_invoke_provider` docstring keep #2926's history but no longer name the SDK module or the key variable as if they were in play.
- `tools/land_2283_ci_tiers.py`: the PR text it carries described an adversarial test that skips when neither key is set; it is corrected.

## The environment (requirement 6)

- **Ubuntu: clean.**
  - Neither variable is set in this session's login-initialised shell.
  - No user or system startup file names either one: `~/.bashrc`, `~/.profile`, `~/.bash_profile`, `~/.zshrc`, `/etc/environment` and `/etc/profile.d/`.
- **Projects tree: clean.**
  - A script read the 18 `.env`, `.env.*` and `.dev.vars` files in-process, printing names only; none defines either variable.
  - No script under Projects runs `setx` or `SetEnvironmentVariable` on either.
- **Windows: the operator's.** The User and Machine scopes and the PowerShell profiles are his to check. The exact commands are posted on #3583, because the Machine scope needs elevation and the profiles may sit under OneDrive.

## Runbooks (requirement 3)

No runbook, standard, ADR other than 0237, README or CLAUDE.md tells the operator to set a key. The remaining mentions are in `docs/lld/done/`, `docs/audit/done/` and a draft spec: historical records, and `done/` directories are not edited.

## Requirement 1, the full-read ledger

Superseded by the #3585 work order. Its step 5 (#3581) builds that ledger for every tracked file in `assemblyzero/` and `tools/`, and this step does the API-key part named in the order.
