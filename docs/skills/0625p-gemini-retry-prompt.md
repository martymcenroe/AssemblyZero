# gemini-retry - Prompt Reference

**Tool:** `tools/gemini-retry.py`
**Issue:** [#11](https://github.com/martymcenroe/AgentOS/issues/11)

## When to Use

Use `gemini-retry.py` when you need to run Gemini 3 Pro reviews and want automatic handling of:
- Quota exhaustion (rotates credentials)
- Capacity issues (exponential backoff)
- Model validation (prevents silent downgrades)

## Examples

### Basic Review Request

> "Run a Gemini review on this LLD"

Agent will use:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/gemini-retry.py --model gemini-3-pro-preview --prompt "Review this LLD for security issues: [content]"
```

### Long Prompt (File-Based)

> "Review this implementation report with Gemini"

Agent will:
1. Write prompt to scratchpad file
2. Run with `--prompt-file` flag

### Debug Mode

> "Run Gemini retry with debug output"

Agent will set environment variable:
```bash
GEMINI_RETRY_DEBUG=1 poetry run ... gemini-retry.py ...
```

## Integration with AgentOS

This tool is called by the `/audit` skill for Gemini reviews. It integrates with:
- `gemini-rotate.py` for credential management
- `~/.agentos/gemini-credentials.json` for credential storage
