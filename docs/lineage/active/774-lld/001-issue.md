---
repo: martymcenroe/AssemblyZero
issue: 774
url: https://github.com/martymcenroe/AssemblyZero/issues/774
fetched: 2026-03-18T22:41:54.033306Z
---

# Issue #774: feat: full LLM call instrumentation — input parameters + output metadata per invocation (#774)

## Problem

Every LLM call across all workflows must log both what we *sent* and what came *back*, per invocation. Currently some workflows may capture partial metadata but there's no uniform instrumentation. Can't answer "is `--effort max` worth it?" or "does Opus review better than Sonnet?" without data.

## Input Parameters (selectable)

- Provider + model (`claude:opus`, `gemini:3.1-pro-preview`)
- Effort level (`--effort low|medium|high|max`)
- Budget cap (`--max-budget-usd`)
- Fallback model
- JSON schema (if structured output)
- Context window size
- Temperature (if applicable)

## Output Metadata (read from API response)

- Input tokens consumed
- Output tokens consumed
- Thinking tokens (if applicable)
- Cache read/write tokens
- Stop reason
- Model actually used (may differ from requested if fallback triggered)
- Latency (wall clock)
- Cost estimate

Some things read may not be selectable — e.g., the API returns context window usage but you can't set it. Log it anyway.

## Purpose

Treat reviewer quality (#770) and parameter tuning (#772) as experiments. Without per-call data, all tuning decisions are guesswork.

## Scope

All workflows — LLD, impl spec, TDD implementation. Not just one.

## Refs

- #770 (Claude-reviewing-Claude tuning)
- #772 (extended provider parameters)
- #773 (--no-api default + claude:opus reviewer)
- #646 (prior cost tracking — closed, narrower scope)