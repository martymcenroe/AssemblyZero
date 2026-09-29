# ADR 0235: Skills as Custom Slash Commands

**Date**: 2026-09-29

## Context

Agents frequently operate under the assumption that creating a custom chat UI "slash command" (like `/screenshot` or `/handoff`) requires modifying and recompiling the client binaries (`agy` or Claude Code), leading them to incorrectly argue with the operator that slash commands cannot be injected dynamically.

This blind spot causes severe friction. The operator asks for custom slash commands and expects agents to build them simply by writing a configuration file, but agents stubbornly refuse, believing the UI menu is statically compiled and out of reach.

## Decision

We document and clarify the structural reality of the Antigravity customization system: **The `agy` CLI automatically and dynamically registers ANY discovered Skill as a native slash command by mapping directly to the `name` field in the skill's YAML frontmatter.**

For example, a skill defined with:

```yaml
---
name: screenshot
description: >-
  Use this skill to fetch a screenshot...
---
```

Is instantly exposed in the `agy` UI as the `/screenshot` command. When the user types `/screenshot` and hits enter, the CLI natively intercepts the stroke, matches the skill by its exact `name` property, and triggers the workflow.

## Consequences

1. **Agent Awareness**: Agents must understand that if the user asks them to "build the `/foo` slash command," the user is literally just asking them to create a standard Skill with `name: foo` in its YAML frontmatter.
2. **Error Prevention**: Naming mismatches cause immediate execution failures. If an agent creates a skill named `latest-screenshot` but the user expects `/screenshot`, the CLI will throw an `unknown command` error to the operator because it intercepts the exact string `/screenshot` and fails to match it against its dynamically generated UI list. The text never reaches the LLM.
3. **Strict Compliance**: Agents must NEVER argue that slash commands require modifying the chat application source code. They must simply build a Skill with the requested name.
