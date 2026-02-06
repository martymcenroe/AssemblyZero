# gemini-retry - CLI Reference

**Tool:** `tools/gemini-retry.py`
**Issue:** [#11](https://github.com/martymcenroe/AssemblyZero/issues/11)

## Quick Start

```bash
# Basic usage with prompt
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-retry.py --prompt "Review this code" --model gemini-3-pro-preview

# With prompt file (for long prompts)
poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/gemini-retry.py --prompt-file /path/to/prompt.txt --model gemini-3-pro-preview
```

## Parameters

| Flag | Required | Description |
|------|----------|-------------|
| `--prompt`, `-p` | Yes* | Prompt text |
| `--prompt-file`, `-f` | Yes* | Path to file containing prompt |
| `--model` | No | Model to use (default: gemini-3-pro-preview) |

*One of `--prompt` or `--prompt-file` is required.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_RETRY_MAX` | 20 | Maximum retry attempts |
| `GEMINI_RETRY_BASE_DELAY` | 30 | Initial backoff delay (seconds) |
| `GEMINI_RETRY_MAX_DELAY` | 600 | Maximum backoff delay (seconds) |
| `GEMINI_RETRY_LOG_DIR` | logs/ | Directory for retry logs |
| `GEMINI_RETRY_DEBUG` | 0 | Set to 1 for verbose output |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (response on stdout) |
| 1 | Permanent failure (all credentials exhausted) |
| 2 | Invalid arguments |

## Key Behavior

1. **Credential Rotation**: On QUOTA_EXHAUSTED, rotates to next credential
2. **Exponential Backoff**: On CAPACITY_EXHAUSTED, waits with backoff
3. **Model Validation**: Rejects silent downgrades to Flash models
4. **Logging**: All attempts logged to `logs/gemini-retry-*.jsonl`
