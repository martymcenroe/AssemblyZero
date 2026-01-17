# 0904 - Sentinel

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-01-17

---

## Purpose

Launch Claude CLI with AI-gated permission control. Sentinel intercepts permission prompts and uses Haiku to auto-approve safe commands while alerting on potentially unsafe ones.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Poetry installed | `poetry --version` |
| AgentOS dependencies | `poetry install --directory /c/Users/mcwiz/Projects/AgentOS` |
| ANTHROPIC_API_KEY set | Check `.env` in AgentOS root |
| Bash aliases sourced | `source ~/.bash_profile` |

---

## Procedure

### Step 1: Launch Sentinel (Production)

```bash
sentinel
```

This runs `sentinel.py` - the production version.

### Step 2: Launch Sentinel (Test)

For testing changes to sentinel before deploying to production:

```bash
sentinel-test
```

This runs `sentinel-test.py` - make changes here first.

### Step 3: Usage

Sentinel wraps Claude CLI transparently:
- **SAFE commands** - Auto-approved with green `[SENTINEL] SAFE` message
- **UNSAFE commands** - Bell alert + red `[SENTINEL] UNSAFE` message, requires manual decision

---

## How It Works

1. Spawns Claude CLI in a PTY
2. Monitors output for "Allow this command to run?" prompts
3. Extracts the command from the buffer
4. Sends command to Haiku with forbidden paths context
5. Haiku responds SAFE or UNSAFE
6. SAFE: auto-sends 'y', UNSAFE: alerts user for manual decision

### Forbidden Paths

Loaded from multiple sources:
- Hardcoded defaults: `OneDrive`, `AppData`, `~`, `/c/Users/*/`
- `~/.claude/settings.local.json` → `permissions.deny`
- `.claude/settings.local.json` → `permissions.deny`, `ignorePatterns`

---

## Verification Checklist

| Check | Command | Expected |
|-------|---------|----------|
| Alias exists | `type sentinel` | Shows alias definition |
| Test alias exists | `type sentinel-test` | Shows alias definition |
| Sentinel launches | `sentinel` | Shows `[SENTINEL v1.0.0]` banner |
| Forbidden paths loaded | Watch startup | Shows "X patterns loaded" |

---

## Troubleshooting

### "Failed to spawn Claude"

**Cause:** `claude` CLI not in PATH or winpty issue
**Solution:** Ensure Claude CLI is installed: `claude --version`

### "UNSAFE on everything"

**Cause:** Haiku API call failing (falls back to deny-all)
**Solution:** Check ANTHROPIC_API_KEY in `.env`, verify API connectivity

### No auto-approval happening

**Cause:** Permission prompt regex not matching
**Solution:** Check `PROMPT_REGEX` pattern in sentinel.py matches Claude's current prompt format

---

## Related Documents

- `tools/sentinel.py` - Production code
- `tools/sentinel-test.py` - Test version (modify here first)
- `~/.bash_profile` - Alias definitions

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial version |
