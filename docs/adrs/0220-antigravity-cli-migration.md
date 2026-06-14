# ADR 0220: Antigravity (`agy`) CLI migration for the governance Gemini client

- **Status:** Proposed — primary path actionable now; CLI port blocked (see #1595)
- **Date:** 2026-06-13
- **Related:** #1335 (this spike), #1595 (CLI port, blocked), #1596 (legacy reviewer bug), #1334/#1563 (scaffolder GEMINI.md), #1590 (GEMINI.md ACK removal)

## Context

The Gemini CLI retires **2026-06-18** for AI Pro/Ultra and free tiers. Antigravity
CLI (`agy`) is the subscription replacement. A prior session already removed the
GEMINI.md handshake/ACK section fleet-wide (#1590) because `agy` trips on it on
auto-load. This ADR covers the remaining governance-code question: does AssemblyZero's
LLD/spec/test-plan review pipeline depend on the retiring `gemini` binary, and what is
the migration?

## Findings

**1. The live review path does reach the `gemini` CLI.** The requirements, spec, and
testing workflows review via `get_provider(config_reviewer)` with default spec
`gemini:3.1-pro-preview` (`workflows/requirements/nodes/review.py:136`,
`workflows/testing/nodes/review_test_plan.py:491`,
`workflows/implementation_spec/nodes/review_spec.py`). That resolves to
`GeminiProvider` → `GeminiClient(model="gemini-3.1-pro-preview")`. `GeminiClient` has
two transports: an **OAuth** path that shells out to the `gemini` binary
(`_invoke_via_cli`) and an **api_key** path that calls the `google.genai` SDK directly
(`genai.Client`). Only the OAuth/CLI path breaks on 2026-06-18.

**2. `agy`'s interface differs from `gemini`'s** (observed, `agy` v1.0.8):

| Concern | `gemini` (current) | `agy` (target) |
|---|---|---|
| binary lookup | `shutil.which("gemini")` + npm `.cmd` | `agy` (`~/AppData/Local/agy/bin/agy.exe`; on PATH after `agy install`) |
| prompt input | `--prompt -` (stdin) | `--print "<prompt>"` (**argument**, not stdin) |
| model flag | `--model <id>` | `--model <id>` |
| output format | `--output-format text` | (none) |
| read-only mode | `--approval-mode plan` `--skip-trust` | `--sandbox` |

**3. `agy` print mode produces no output as a headless subprocess.** `agy --print "..."`
returns exit 0 with **empty stdout and stderr** when invoked from a non-TTY subprocess
(tested twice from a clean temp dir, with and without `--sandbox`/`--model`).
`GeminiClient` treats `returncode == 0 and not stdout` as failure, so a naive port would
make every governance review fail. **This blocks the CLI port** (#1595) until `agy`
emits output under `subprocess.run(capture_output=True)` — probably an auth/TTY issue
the operator must resolve (`agy login` is a credential prompt the agent must not trigger).

**4. The api_key path is the deadline-safe answer.** `GeminiClient`'s `genai.Client`
transport does not touch the CLI and is unaffected by the CLI retirement. If
`~/.assemblyzero/gemini-credentials.json` includes a Gemini **API key**, governance keeps
working past 2026-06-18 with **zero code change**. The `agy` CLI port is only needed to
keep using **subscription (OAuth)** quota instead of paid API keys.

**5. A legacy path is incoherent (#1596).** `config.REVIEWER_MODEL = "claude-opus-4-6"`,
yet `nodes/lld_reviewer.py:88` calls `GeminiClient(model=REVIEWER_MODEL)`, which raises
on any non-`gemini-` model. These `nodes/` modules appear superseded by the
`get_provider` abstraction; tracked separately.

## Decision

1. **Deadline mitigation (do first, no code):** ensure a Gemini API-key credential is
   configured so the `genai.Client` transport carries governance through the CLI
   retirement. Verify by running a review with OAuth credentials disabled.
2. **`agy` CLI port (#1595):** apply the interface translation in the table above — but
   only after the operator confirms `agy --print` returns output when called as a
   subprocess. Blocked until then. Needed only to preserve subscription quota.
3. **Legacy cleanup (#1596):** determine whether `review_lld_node` / the designer node
   are still wired into any graph; delete if dead, fix the model wiring if live.

## Consequences

- Governance is **not** at hard risk on 2026-06-18 provided an API key exists (decision 1).
- The subscription-quota cost saving from OAuth is paused until #1595 unblocks.
- `agy`'s headless behavior is the single open question gating the CLI port; it cannot be
  resolved agent-side (no credential-prompt access).

## Fleet artifacts reviewed (per #1335 question 7)

Touched/identified: `gemini_client.py` (#1595), `nodes/lld_reviewer.py` + `nodes/designer.py`
(#1596), GEMINI.md fleet templates (#1590, done). `tools/gemini_model_check.py` and
`docs/prompts/gemini-rotation-instructions.md` (already retired in #1221) are unaffected by
the CLI retirement — they concern model IDs and the API path, not the binary.
