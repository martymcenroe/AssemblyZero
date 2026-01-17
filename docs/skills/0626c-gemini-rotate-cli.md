# gemini-rotate - CLI Reference

**Tool:** `tools/gemini-rotate.py`

## Quick Start

```bash
# Check credential status
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --status

# Direct usage (like gemini CLI)
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --prompt "Review this" --model gemini-3-pro-preview

# With stdin
cat prompt.txt | poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-rotate.py --model gemini-3-pro-preview
```

## Parameters

| Flag | Required | Description |
|------|----------|-------------|
| `--prompt` | No | Prompt text |
| `--model` | No | Model to use (default: gemini-3-pro-preview) |
| `--status` | No | Show credential status |

## Credential Storage

Credentials are stored in: `~/.agentos/gemini-credentials.json`

```json
{
  "credentials": [
    {
      "name": "primary-oauth",
      "type": "oauth",
      "enabled": true,
      "account_name": "user@gmail.com"
    },
    {
      "name": "backup-api-key",
      "type": "api_key",
      "key": "AIza...",
      "enabled": true
    }
  ]
}
```

## Rotation State

Tracks exhausted credentials in: `~/.agentos/gemini-rotation-state.json`

State is automatically managed:
- Credentials marked exhausted on quota errors
- Reset times tracked from API response
- Automatic reactivation after reset

## Key Behavior

1. **Quota Detection**: Recognizes `TerminalQuotaError`, `QUOTA_EXHAUSTED`
2. **Capacity Detection**: Recognizes `MODEL_CAPACITY_EXHAUSTED`, `RESOURCE_EXHAUSTED`
3. **Credential Cycling**: Rotates through all enabled credentials
4. **State Persistence**: Remembers which credentials are exhausted
