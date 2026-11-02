# 0957 - agy never elevates: the pipeline's own tool-less agent

**Issue:** #3612, under #3603. **Runs:** nobody, routinely. The verification below is for a reader who wants to see it hold.

The pipeline calls agy for text: a draft in, a review out. It never asks agy to run a command, it never requests administrator rights, and nothing about a call depends on the machine's agy settings. The one thing it takes from the machine is the hooks file, so the shell guard still holds (#4531). One mechanism makes that true.

## What the pipeline does on every call

agy loads a custom agent from `<cwd>/.agents/agents/<name>/agent.md` and selects it with `--agent <name>`. The transport (`assemblyzero/core/gemini_client.py`) runs every call in a fresh temporary directory, writes the definition below into it, and passes `--agent assemblyzero-text` on both transports. `tools: []` leaves the model no tool to call and `commandExecutionPolicy: off` turns shell execution off, so there is nothing to sandbox, nothing to elevate, and nothing for agy or Windows to ask. A warning from agy that it could not load the agent is a failed call. `--sandbox` is never passed: on Windows it made agy build an AppContainer for each command attempt and relaunch itself as administrator to do so (#3603).

    ---
    name: assemblyzero-text
    description: AssemblyZero pipeline seat. Answers from the prompt text alone. No tools, no shell, no files, no network.
    mainAgent: true
    subagent: false
    hidden: true
    inheritMcp: false
    inheritCustomizations: false
    hooks:
      - "/home/<user>/.gemini/config/hooks.json"
    tools: []
    commandExecutionPolicy: "off"
    ---

The value is quoted because a YAML 1.1 parser reads a bare `off` as the boolean false; quoted, every parser reads the string agy documents.

`inheritCustomizations: false` (#4531) keeps the machine's agy rules, skills, plugins and subagents out of the agent. Without it agy gave every call the operator's whole agy rule set as `<user_rules>`, about 13,000 tokens ahead of the prompt. The switch also drops the machine's hooks, which are the shell guard's hold on agy, so the definition names the hooks file again. The transport fills in the home of the user agy runs as: this process's home for a Linux agy, WSL's `HOME` for a WSL agy. The path must be absolute: agy drops an entry it cannot resolve, `~/` included, and says nothing.

## The verification record

2026-09-25, about 12:15 PM Central, from a directory carrying that definition, with no sandbox flag and the machine's `toolPermission` at `always-proceed`. The prompt asked the model to run `whoami` and to write `probe.txt`. Result: `status SUCCESS`, one turn, 7.1 seconds, stderr empty, no file written, and the answer "I cannot run commands, read or write files, or reach the network because I have no tools available to perform these actions." The call's `input_tokens` were 2,766 against 15,983 for the same model in text mode without the agent, which is the tool schemas leaving the prompt.

2026-11-02, 9:57 AM to 10:07 AM Central, agy 1.4.0 (#4531). Before `inheritCustomizations: false`, an empty prompt through the transport was billed 16,079 input tokens; agy's own record of the call held one tool, `manage_task`, and a 60,659-character system prompt, 51,319 characters of it `<user_rules>`. After it: empty 2,126 input tokens, the 2,141-character prompt of `tools/agy_exit_probe.py` 2,732, a 6,275-character system prompt with no `<user_rules>` or `<skills>`, and the `whoami` request refused in one turn with no tool call. The guard's PreInvocation hook ran on every call.

## To repeat it

In bash, from the AssemblyZero root:

    poetry run python tools/agy_agent_probe.py

It makes three calls through the transport's own path: an empty prompt, the 2,141-character prompt, and the `whoami` request. It fails when the 2,141-character prompt is billed 5,000 input tokens or more, or when agy's transcript of the `whoami` call shows more than one turn or any tool call. If it fails, stop, and record its output on #3603.
