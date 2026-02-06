# gemini-rotate - Prompt Reference

**Tool:** `tools/gemini-rotate.py`

## When to Use

Use `gemini-rotate.py` when you need to:
- Check which Gemini credentials are available
- Understand why Gemini requests are failing
- Manually trigger a Gemini request with rotation

Note: Most users should use `gemini-retry.py` instead, which calls this tool internally.

## Examples

### Check Credential Status

> "What Gemini credentials are available?"

Agent will run:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-rotate.py --status
```

Output:
```
Credential Status (2 total)
===========================
✓ primary-oauth (oauth) - user@gmail.com
✗ backup-api-key (api_key) - EXHAUSTED until 2026-01-17 00:00
```

### Reset Exhausted State

> "Reset the Gemini credential rotation state"

Agent will delete the state file:
```bash
rm ~/.assemblyzero/gemini-rotation-state.json
```

## Adding New Credentials

1. Edit `~/.assemblyzero/gemini-credentials.json`
2. Add API key or OAuth credential entry
3. Run `--status` to verify

For OAuth credentials, run `gemini auth login` first to set up `~/.gemini/oauth_creds.json`.
