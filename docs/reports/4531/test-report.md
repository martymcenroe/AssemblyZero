# Test report: #4531

## Unit

- `tests/unit/test_agy_agent_customizations.py`, 19 tests: the definition sets `inheritCustomizations: false`, `inheritMcp: false`, `tools: []` and `commandExecutionPolicy: off`; it names exactly the hooks file given and carries no rules or skills of its own; a hooks file or home that is not absolute is refused; a path with a space survives the YAML; the written file is the definition; a native agy reads the hooks under this process's home and a WSL agy under WSL's `HOME`; an unreadable WSL `HOME` starts no agy; `_wsl_home` reads `printenv HOME` and raises on a failed, empty or non-Linux answer or on no WSL; the conversation id reaches the caller.
- `tests/unit/test_agy_agent_probe.py`, 12 tests: one turn with no tool passes; a tool call, a tool step, a second turn or a missing transcript fails; a reply carrying the user name fails; hook messages are counted; the transcript is read by conversation id; the empty and 2,141-character prompts have the transport's shape; an unknown check is refused before any call.
- `tests/unit/test_agy_sandbox_args.py`: two tests updated for the definition built per call.

## Real calls

All on 2026-11-02, agy 1.4.0, `gemini-3.8-flash-high`, through the transport's own path with `tools/agy_agent_probe.py`. Eleven calls in all.

| Time (Central) | Definition | Check | Input tokens | Guard hook ran |
|---|---|---|---|---|
| 9:57 AM | `main` | empty | 16,079 | yes |
| 9:58 AM | `inheritCustomizations: false` alone | empty, sized, whoami | 2,052, 2,658, 2,103 | no |
| 10:01 AM | `rules: []`, `skills: []` | empty | 16,093 | not checked |
| 10:02 AM | `rules:` naming one file | empty | 16,157 | not checked |
| 10:02 AM | switch plus absolute hooks path | empty | 2,133 | yes |
| 10:03 AM | switch plus `~/` hooks path | empty | 2,057 | no |
| 10:07 AM | final | empty, sized, whoami | 2,126, 2,732, 2,173 | yes |

The final run passed all three checks: the 2,141-character prompt under 5,000 input tokens (T2), and the `whoami` request refused in one model turn with no tool call and no tool step (T3). "Guard hook ran" is the guard's `started` marker for the conversation, written by its PreInvocation hook.

## Full suite

`tests/unit/`: 13,905 passed, 66 skipped, 7 xfailed. The integration, e2e and adversarial tiers with `ASSEMBLYZERO_MOCK_MODE=1`: 84 passed, 7 skipped.
