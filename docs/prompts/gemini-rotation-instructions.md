# Gemini Credential Rotation Instructions

**For agents stuck on Gemini quota exhaustion errors.**

---

## ⛔ HARD GATE: Model Verification Required (READ FIRST)

**EVERY Gemini review MUST include model verification in your response to the user.**

### After EVERY Gemini call, you MUST state:

```
**Gemini Review Model:** [gemini-3-pro-preview | gemini-3-pro | OTHER]
```

### VALID models (proceed with workflow):
- `gemini-3-pro-preview` ✅
- `gemini-3-pro` ✅

### INVALID models (DEAD STOP - DO NOT PROCEED):
- `gemini-2.0-flash` ❌ INVALID
- `gemini-2.5-flash` ❌ INVALID
- `gemini-*-lite` ❌ INVALID
- Any model not containing `3-pro` ❌ INVALID

### If you used an INVALID model:

1. **STOP IMMEDIATELY** - Do not proceed with workflow
2. **TELL THE USER:**
   > "⚠️ Gemini review was performed with [model name], which is INVALID for reviews. This review does not count. Gemini 3 Pro is required. Cannot proceed until Pro model is available."
3. **DO NOT create issues, merge PRs, or take any action based on the invalid review**
4. **Use rotation tool to retry with Pro model:**
   ```bash
   python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --model gemini-3-pro-preview --prompt "..."
   ```

### Why This Matters

Flash/Lite models lack the reasoning depth for quality reviews. A Flash review that says "APPROVE" may miss critical issues that Pro would catch. **A review by the wrong model is worse than no review** because it creates false confidence.

**The orchestrator (user) cares deeply about review quality. Do not cheat.**

---

---

## ⚠️ Windows Encoding Issue (COMMON FAILURE)

**If your Gemini call fails with encoding errors, garbled output, or truncated responses - READ THIS.**

### The Problem

Windows console cannot handle Unicode box-drawing characters in prompts:
- `│` `─` `┌` `┐` `└` `┘` `├` `┤` `┬` `┴` `┼` `◀` `▶`

These characters cause `UnicodeEncodeError` or garbled output on Windows.

### Symptoms

- Error mentions `encoding`, `charmap`, or `codec`
- Output shows `?????` or garbled characters
- Python crashes with `UnicodeEncodeError`
- Prompt gets truncated at the first special character

### The Fix

**Option 1: Remove Unicode characters from prompts**
Use ASCII alternatives:
- `|` instead of `│`
- `-` instead of `─`
- `+` instead of `└` `┌` `┐` `┘`
- `<` `>` instead of `◀` `▶`

**Option 2: Use stdin with UTF-8 file**
Write your prompt to a file (UTF-8 encoded), then pipe it:
```bash
python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --model gemini-3-pro-preview < /path/to/prompt.txt
```

**Option 3: Use the Write tool first**
```
1. Use Write tool to save prompt to scratchpad (UTF-8)
2. Then use Bash to pipe the file to gemini-rotate.py
```

### Prevention

**When creating prompts for Gemini, NEVER use box-drawing characters.**
Stick to basic ASCII: `| - + * # = _ [ ] ( ) < >`

---

## Quota Exhaustion Problem

When you see errors like:
- `TerminalQuotaError`
- `You have exhausted your capacity on this model`
- `QUOTA_EXHAUSTED`

**Exponential backoff will NOT help.** These are account-level quota limits that reset in ~24 hours. Retrying wastes time.

## The Solution

Use `gemini-rotate.py` instead of calling `gemini` directly. It rotates through multiple credentials automatically.

### Usage

```bash
# Instead of:
gemini --model gemini-3-pro-preview -p "your prompt"

# Use:
python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --model gemini-3-pro-preview --prompt "your prompt"

# For long prompts via stdin:
python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --model gemini-3-pro-preview < /path/to/prompt.txt

# Check credential status:
python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --status
```

### What It Does

1. Loads credentials from `~/.assemblyzero/gemini-credentials.json`
2. Skips credentials marked as quota-exhausted
3. Tries each available credential until one succeeds
4. Tracks exhaustion per credential with reset times
5. Reports when ALL credentials are exhausted

### If ALL Credentials Are Exhausted

When you see: `All credentials exhausted`

**STOP. Do not retry. Report to user:**
> "Gemini 3 Pro quota exhausted across all configured credentials. Cannot proceed with review until quota resets or new credentials are added."

The user can:
1. Wait for quota reset (~24h)
2. Add more API keys to `~/.assemblyzero/gemini-credentials.json`

## Model Requirements (MANDATORY)

**ONLY use these models for reviews:**
- `gemini-3-pro-preview` (primary)
- `gemini-3-pro` (acceptable)

**NEVER substitute Flash or Lite models.** A review with the wrong model is INVALID.

## Quick Copy-Paste Commands

Check status:
```bash
python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --status
```

Simple test:
```bash
python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --model gemini-3-pro-preview --prompt "Say hello"
```

Review with rotation:
```bash
python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --model gemini-3-pro-preview < /path/to/review-prompt.txt
```
