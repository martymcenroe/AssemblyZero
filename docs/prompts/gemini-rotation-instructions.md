# Gemini CLI Notes — Rotation, Encoding, and Model Selection

**For agents using Gemini for reviews / quota-rotation situations / Windows prompt encoding issues.**

> **Why this file exists:** `/onboard` skill loads it into every session whose repo has `.unleashed.json` `assemblyZero: true`. Keep it concise — it pays per-session context cost.

---

## 1. Expected model

Reviews should run on the current Gemini Pro family model — at time of writing that's `gemini-3-pro-preview`, but Google's preview-model naming is in flux. The rotation tool (`tools/gemini-rotate.py`) accepts whatever `--model` string you pass and surfaces the response model name in its output; treat that as authoritative for "what actually ran."

**Quality reminder:** Pro-family models are meaningfully stronger for code review than Flash/Lite variants. If the orchestrator is asking for a real review, use Pro. If a Flash result comes back from the API anyway (model-fallback by Google), surface that to the operator and let them decide whether to retry — don't silently treat it as a Pro review.

What used to be in this section: a hard-stop gate that refused to proceed on any non-`3-pro` model name. Removed because Google's model naming is moving, and a hard match against literal strings produces false-positive blocks during the transition windows.

---

## 2. Windows console encoding (common failure)

If a Gemini call fails with encoding errors, garbled output, or truncated responses — this is almost always Windows console encoding handling Unicode poorly.

### The problem

Windows console (`cp1252` / `cp437` by default) cannot represent Unicode box-drawing characters in prompts:

```
│ ─ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼ ◀ ▶
```

Symptoms:
- `UnicodeEncodeError` mentioning `charmap` or `codec`
- Output shows `?????` or garbled characters
- Python crashes immediately, or prompt gets truncated at the first non-ASCII character

### Three remediations

**Substitute ASCII** — `|` for `│`, `-` for `─`, `+` for `└` `┌` `┐` `┘`, `<` `>` for `◀` `▶`. Simplest; works everywhere.

**Pipe a UTF-8 file** — write the prompt to disk with UTF-8 encoding, pipe via stdin:

```bash
poetry run python tools/gemini-rotate.py --model gemini-3-pro-preview < /path/to/prompt.txt
```

**Use Write tool first** — Write the prompt to a scratchpad (UTF-8 by default), then Bash to pipe the file. Same as above but explicit.

### Prevention

When generating prompts programmatically for any CLI tool on Windows, stay in basic ASCII: `| - + * # = _ [ ] ( ) < >`. The encoding issue isn't Gemini-specific; it bites any CLI invocation where Python writes Unicode to stdin/argv on a Windows console.

---

## 3. Quota rotation (`tools/gemini-rotate.py`)

Use when:

- `TerminalQuotaError`
- `You have exhausted your capacity on this model`
- `QUOTA_EXHAUSTED`

These are account-level quota limits, typically ~24h reset. Exponential backoff does not help.

### Usage

```bash
# Instead of bare `gemini --model ... -p "prompt"`:
poetry run python tools/gemini-rotate.py --model gemini-3-pro-preview --prompt "prompt text"

# Long prompts via stdin (preferred on Windows):
poetry run python tools/gemini-rotate.py --model gemini-3-pro-preview < /path/to/prompt.txt

# Credential status:
poetry run python tools/gemini-rotate.py --status
```

### What it does

1. Loads credentials from `~/.assemblyzero/gemini-credentials.json`
2. Skips credentials marked quota-exhausted
3. Tries each available credential until one succeeds
4. Tracks exhaustion per credential with reset times
5. Reports when all credentials are exhausted

### If all credentials exhausted

When the tool prints `All credentials exhausted`:

```
STOP. Do not retry. Report to user:
"Gemini Pro quota exhausted across all configured credentials.
Cannot proceed with review until quota resets or new credentials are added."
```

User actions: wait for quota reset (~24h), or add credentials to `~/.assemblyzero/gemini-credentials.json`.

---

## Change history

| Date | Change | Why |
|---|---|---|
| 2026-05-23 | Removed §1 hard-gate that DEAD-STOPped on non-`3-pro` model names. Softened to advisory. Reformatted to reduce per-onboard context cost. | Hard match against literal model names produces false-positive blocks during Google's preview-model rename transitions; user signal "gemini cli is changing and it's all a mess." Issue: #1221. |
| 2026-02-28 | Initial version with hard gate. | — |
