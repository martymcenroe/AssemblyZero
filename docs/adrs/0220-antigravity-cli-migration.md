# ADR 0220: Antigravity (`agy`) CLI migration for the governance Gemini client

- **Status:** Accepted — implemented (#1595)
- **Date:** 2026-06-13
- **Related:** #1335 (spike), #1595 (this migration), #1596 (legacy reviewer bug), #1334/#1563 (scaffolder GEMINI.md), #1590 (GEMINI.md ACK removal)

## Context

The Gemini CLI retires **2026-06-18** for AI Pro/Ultra and free tiers. Antigravity
CLI (`agy`) is the subscription replacement. **Governance runs on the subscription
(OAuth) quota only — the paid Gemini API is not used (it is ~100x the cost).** So when
the Gemini CLI dies, the OAuth transport in `GeminiClient` breaks and there is no
API-key fallback; the `agy` migration is the sole path and the deadline is hard.

A prior session already removed the GEMINI.md handshake/ACK section fleet-wide (#1590)
because `agy` trips on it on auto-load.

## Findings

**1. The live review path reaches the CLI.** The requirements, spec, and testing
workflows review via `get_provider(config_reviewer)`, default spec `gemini:3.1-pro-preview`
→ `GeminiProvider` → `GeminiClient`. For subscription/OAuth credentials, `GeminiClient`
shells out to the CLI (`_invoke_via_cli`).

**2. `agy`'s interface differs from `gemini`'s** (`agy` v1.0.8): binary `agy`
(`~/AppData/Local/agy/bin/agy.exe`, not always on PATH); prompt via `-p <prompt>`;
`--model <id>`; no `--output-format`; `--sandbox` for restricted mode. `-p -` reads the
prompt from stdin.

**3. `agy` renders its response only to a TTY — SOLVED.** Called with a piped stdout it
exits 0 with empty output (the model call still happens — the log shows successful
keyring auth and `streamGenerateContent` to `daily-cloudcode-pa.googleapis.com` — but
nothing reaches the pipe). The fix: run `agy` under a **pseudo-console via `pywinpty`**
(already a fleet dependency), capture the stream, and strip ANSI/VT codes. Verified
end-to-end: a long JSON governance verdict round-trips intact and parses.

**4. Subscription-only — there is no API-key fallback.** `GeminiClient` also has a
`genai.Client` (API-key) transport, but it is not used in governance because the paid
API is ~100x the subscription cost. The CLI migration is therefore mandatory, not
optional.

**5. A legacy path is incoherent (#1596).** `config.REVIEWER_MODEL = "claude-opus-4-6"`,
yet `nodes/lld_reviewer.py:88` calls `GeminiClient(model=REVIEWER_MODEL)`, which raises
on a non-`gemini-` model. These `nodes/` modules look superseded by `get_provider`;
tracked separately.

## Decision

Migrate `GeminiClient._invoke_via_cli` (#1595) to drive `agy` via a `pywinpty`
pseudo-console:

- `_find_agy_cli` locates `agy` (PATH, then the default Windows install path).
- `_invoke_via_cli` spawns `agy -p <full_prompt> --model <id>` under a pseudo-console
  (wide terminal so long JSON does not wrap), reads to EOF, and `_strip_ansi`-cleans the
  result. A 5-minute timeout terminates a hung call.
- `agy` runs in a **clean temp working directory**, so no repo `GEMINI.md` / `AGENTS.md`
  / `.gemini` bleeds into the governance review. This retires the old GEMINI.md-rename
  workaround and the `.bak` debris it produced.
- The prompt rides in argv; Windows caps a command line at ~32767 chars, so a prompt
  over 30000 is rejected explicitly (stdin-based invocation for oversized prompts is a
  follow-up).

## Consequences

- Governance survives the 2026-06-18 CLI retirement on the subscription quota, no code
  changes to callers.
- New hard dependency on `pywinpty` for the OAuth transport (Windows). The api-key
  transport is unchanged and untouched.
- Oversized prompts (>30 KB argv) fail loudly pending a stdin-based path.
- Legacy `nodes/lld_reviewer.py` / `designer.py` cleanup remains open (#1596).

## Fleet artifacts

Touched: `gemini_client.py` (#1595, done), GEMINI.md fleet templates (#1590, done).
Open: `nodes/lld_reviewer.py` + `nodes/designer.py` (#1596). `tools/gemini_model_check.py`
and the retired `gemini-rotation-instructions.md` (#1221) are unaffected — they concern
model IDs, not the binary.
