# Gemini Credential Rotation Instructions

**For agents stuck on Gemini quota exhaustion errors.**

## The Problem

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
python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --model gemini-3-pro-preview --prompt "your prompt"

# For long prompts via stdin:
python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --model gemini-3-pro-preview < /path/to/prompt.txt

# Check credential status:
python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --status
```

### What It Does

1. Loads credentials from `~/.agentos/gemini-credentials.json`
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
2. Add more API keys to `~/.agentos/gemini-credentials.json`

## Model Requirements (MANDATORY)

**ONLY use these models for reviews:**
- `gemini-3-pro-preview` (primary)
- `gemini-3-pro` (acceptable)

**NEVER substitute Flash or Lite models.** A review with the wrong model is INVALID.

## Quick Copy-Paste Commands

Check status:
```bash
python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --status
```

Simple test:
```bash
python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --model gemini-3-pro-preview --prompt "Say hello"
```

Review with rotation:
```bash
python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --model gemini-3-pro-preview < /path/to/review-prompt.txt
```
