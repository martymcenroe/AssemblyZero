---
repo: martymcenroe/AssemblyZero
issue: 605
url: https://github.com/martymcenroe/AssemblyZero/issues/605
fetched: 2026-03-06T06:06:44.747711Z
---

# Issue #605: feat: Systemic Model Version Refresh (Gemini 3.1 & Claude 4.6+)

## Objective
Refresh all hardcoded model identifiers across the codebase to ensure we are using the latest stable versions.

## Requirements
1. **Gemini Update:** Transition from \`gemini-3-pro-preview\` to \`gemini-3.1-pro-preview\` or \`gemini-3.1-pro\` as canonical across all tools and config.
2. **Claude Update:** Verify and update \`MODEL_MAP\` in \`llm_provider.py\` for Opus/Sonnet 4.6+ variants.
3. **Config Sync:** Update \`assemblyzero/core/config.py\` and tool defaults (\`gemini-rotate.py\`, etc.).
4. **Test Audit:** Update unit tests that assert against old model strings.

## Related
- Issue #600 (Current implementation)