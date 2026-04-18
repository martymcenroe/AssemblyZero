# 0929 - AI CLI Tools Reference

**Category:** Runbook / Reference
**Version:** 1.1
**Last Updated:** 2026-04-18

> **Renumbered from 0927 → 0929** to resolve a filename collision with `0927-new-repo-human-checklist.md`. (Closes #924)

---

## Purpose

Quick reference for the three AI CLI coding tools: Claude Code, Gemini CLI, and Codex CLI (OpenAI). Covers models, reasoning levels, configuration, and when to use each.

**Note:** This landscape changes weekly. Verify model names and pricing before making decisions.

---

## Tool Summary

| | Claude Code | Gemini CLI | Codex CLI |
|---|------------|------------|-----------|
| **Vendor** | Anthropic | Google | OpenAI |
| **Top model** | Opus 4.6 | Gemini 3.1 Pro | GPT-5.4 |
| **SWE-bench** | 80.8% | 80.6% | ~80% |
| **Context** | 1M tokens | 1M tokens | Varies |
| **Free tier** | No ($20/mo min) | Yes (1000 req/day) | With ChatGPT sub |
| **MCP support** | Yes | Yes | Yes |
| **Open source** | Yes | Yes | Yes |
| **Platform** | macOS/Linux/Windows | macOS/Linux/Windows | macOS/Linux (Win experimental) |

---

## 1. Claude Code (Anthropic)

### Models

| Model | Use Case |
|-------|----------|
| **Opus 4.6** | Complex reasoning, architecture, patent review |
| **Sonnet 4.6** | Daily driver, standard development |
| **Haiku 4.5** | Scaffolding, boilerplate, simple automation |

### Reasoning Levels (`/effort`)

The old keyword system ("think", "think harder", "megathink", "ultrathink") is **deprecated** but still functional. Use `/effort` instead.

| Level | Thinking Budget | When to Use |
|-------|----------------|-------------|
| `low` | Minimal | Quick answers, simple lookups |
| `medium` | Moderate | Routine coding, file edits |
| `high` | Deep (default) | Complex reasoning, architecture |
| `max` | Unconstrained | Hardest problems, full chain of thought |

**Three ways to set it:**

```bash
# 1. Per-session (in the CLI)
/effort max

# 2. Persistent (settings file)
# Add to ~/.claude/settings.json:
#   "effortLevel": "high"

# 3. Environment variable
CLAUDE_CODE_EFFORT_LEVEL=max claude
```

### Pricing

| Plan | Cost | Notes |
|------|------|-------|
| Pro | $20/mo | Basic access |
| Max 5x | $100/mo | 5x usage |
| Max 20x | $200/mo | 20x usage |
| API (Sonnet) | $3/$15 per 1M tokens | In/out |
| API (Opus) | $5/$25 per 1M tokens | In/out |

### Key Features (2026)

- **Agent Teams** (experimental): Multiple Claude Code instances coordinating
- **Skills & Agents**: Custom skills with frontmatter, hot reload
- **Plugins**: 9,000+ in marketplace
- **`/teleport`**: Transfer CLI session to claude.ai/code
- **HTTP hooks**: POST JSON to URLs
- **MCP servers**: Full Model Context Protocol

---

## 2. Gemini CLI (Google)

### Models

| Model | Use Case |
|-------|----------|
| **Gemini 3.1 Pro** | Flagship reasoning (preview) |
| **Gemini 3 Flash** | Pro-grade at Flash speed |
| **Auto mode** (default) | Routes to best model per task |

### Reasoning Levels

| Setting | Effect |
|---------|--------|
| `thinkingLevel: low` | Minimal reasoning |
| `thinkingLevel: medium` | Balanced |
| `thinkingLevel: high` | Deep Think activated |
| `thinkingBudget: N` | Raw token budget (0–24576) |

Configure in Gemini CLI config file or per-request.

### Pricing

| Tier | Cost | Notes |
|------|------|-------|
| **Free** | $0 | 1000 req/day, 60/min — no credit card |
| API (2.5 Pro) | $1.25/$10 per 1M tokens | In/out |
| API (Flash) | $0.30/$2.50 per 1M tokens | In/out |

### Key Features (2026)

- **Free tier**: The killer feature — 1000 requests/day
- **1M token context**: Largest context window
- **Plan Mode**: Multi-step task planning
- **MCP servers**: Same protocol as Claude Code and Codex
- **Open source**: Full source on GitHub

---

## 3. Codex CLI (OpenAI)

### Models

| Model | Use Case |
|-------|----------|
| **GPT-5.4** | Flagship, recommended for most tasks |
| **GPT-5.3-Codex ("Spark")** | Fast tasks, Pro subscribers |
| **GPT-5.2-Codex** | Mid-tier, supports xhigh reasoning |
| **codex-mini-latest** | Budget ($1.50/$6 per 1M tokens) |

### Reasoning Levels

Supported on GPT-5.2-Codex and GPT-5.3-Codex:

| Level | When to Use |
|-------|-------------|
| `low` | Quick, simple tasks |
| `medium` | Daily driver |
| `high` | Complex reasoning |
| `xhigh` | Maximum thinking time |

Configure via `config.toml` or `/model` command mid-session.

### Pricing

Bundled with ChatGPT subscriptions:

| Plan | Cost | Messages/5hr |
|------|------|-------------|
| Plus | $20/mo | 30–150 |
| Pro | $200/mo | 300–1500 |

### Key Features (2026)

- **Full-screen terminal UI**: Watch plans, approve/reject inline
- **Sandbox security**: Native OS-level sandboxing
- **Cached web search**: Enabled by default
- **MCP servers**: Same protocol as others
- **`/model` command**: Switch models mid-session
- **Platform**: macOS/Linux; Windows is experimental

---

## When to Use Which

| Task | Recommended Tool | Why |
|------|-----------------|-----|
| **Daily development** | Claude Code (Sonnet) | Speed + ecosystem |
| **Deep reasoning / patent review** | Claude Code (Opus `/effort max`) | Best autonomous reasoning |
| **Budget-conscious research** | Gemini CLI (free tier) | 1000 req/day at $0 |
| **Large context analysis** | Gemini CLI | 1M token context |
| **Security-sensitive execution** | Codex CLI | Native sandboxing |
| **Quick prototyping** | Gemini CLI (free) or Codex (Plus sub) | Low cost, fast iteration |

---

## Installing All Three

```bash
# Claude Code (npm)
npm install -g @anthropic-ai/claude-code

# Gemini CLI (npm)
npm install -g @anthropic-ai/gemini-cli
# or: npm install -g @anthropic-ai/gemini-cli  -- check actual package name

# Codex CLI
# See: https://developers.openai.com/codex/cli/
```

**Note:** Verify current install commands — package names change. The above are approximate.

---

## Related Documents

- [0925 - Agent Token Setup](0925-agent-token-setup.md) — PAT configuration for Claude Code and Gemini CLI
- [0905 - Gemini Credentials](0905-gemini-credentials.md) — Gemini-specific auth
- [0900 - Runbook Index](0900-runbook-index.md)

---

## History

| Date | Change |
|------|--------|
| 2026-03-09 | Initial reference created. Models: Opus 4.6, Gemini 3.1 Pro, GPT-5.4. |
