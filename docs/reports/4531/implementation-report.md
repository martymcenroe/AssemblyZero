# Implementation report: #4531

#4531 asked what the 16,000 input tokens every agy call paid before its prompt were. The cause, with agy's log lines and its own record of the calls, is on the issue.

## The cause

Not the tool schemas: `tools: []` held, and agy's record of a 16,696-token call declared one built-in tool, `manage_task`. The constant was the operator's own agy rule set, `~/.gemini/config/AGENTS.md` and the files under `~/.gemini/config/rules/`, 51,319 characters given to the agent as `<user_rules>`. agy 1.4.0 gives a Markdown agent the user's rules, skills, plugins, subagents and MCP servers unless its definition says `inheritCustomizations: false`. The section follows `<user_information>`, which holds the call's temporary directory and conversation id, so it was never cached.

## What changed

- `assemblyzero/core/gemini_client.py`: the agent definition says `inheritCustomizations: false`. Measured, that also drops the machine's agy hooks, which are the shell guard's hold on agy, so the definition names the hooks file again. The definition is now built per call by `agent_definition(hooks_file)`; the transport passes `_agy_hooks_file()`, which is this process's home for a Linux agy and WSL's `HOME` (`_wsl_home`, cached, raising when unreadable) for a WSL one. A hooks path that is not absolute is refused: agy drops an entry it cannot resolve, `~/` included, without a word. `_agy_once` records agy's `conversation_id` in the call's ledger dict. The comment no longer gives 2,766 as today's figure.
- `tools/agy_agent_probe.py` is new: three bounded calls through `GeminiClient._agy_once` (empty prompt, the 2,141-character prompt of `tools/agy_exit_probe.py`, a `whoami` request), judged against agy's own transcript of each call; exit 1 on any failed call or check. Each call is written to the model-call ledger.
- `tests/conftest.py`: the no-agy fixture stands in for WSL's `HOME`, so no tier starts wsl.exe.
- ADR 0233 gets a third amendment; runbook 0957 shows the new definition and uses the probe to repeat the verification.

## Tried and not used

- `rules: []` and `skills: []`: ignored by agy (16,093 input tokens for an empty prompt).
- A `rules:` entry naming one small file: added to the rule tree, not in place of it (16,157).
- `inheritCustomizations: false` alone: 2,052 input tokens, but the guard's PreInvocation hook stopped running, and the guard's PreToolUse hook is what denies `manage_task`.
- A hooks entry written `~/.gemini/config/hooks.json`: the hooks did not run, and agy said nothing.

## Filed

#4538: the transport fails any call whose answer mentions `--agent`, reporting the agent unloaded.
