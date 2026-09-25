# 0957 - agy never elevates: the pipeline's own tool-less agent

**Issue:** #3612, under #3603. **Runs:** nobody, routinely. The verification below is for a reader who wants to see it hold.

The pipeline calls agy for text: a draft in, a review out. It never asks agy to run a command, it never requests administrator rights, and nothing about a call depends on the machine's agy settings. One mechanism makes that true.

## What the pipeline does on every call

agy loads a custom agent from `<cwd>/.agents/agents/<name>/agent.md` and selects it with `--agent <name>`. The transport (`assemblyzero/core/gemini_client.py`) runs every call in a fresh temporary directory, writes the definition below into it, and passes `--agent assemblyzero-text` on both transports. `tools: []` leaves the model no tool to call and `commandExecutionPolicy: off` turns shell execution off, so there is nothing to sandbox, nothing to elevate, and nothing for agy or Windows to ask. A warning from agy that it could not load the agent is a failed call. `--sandbox` is never passed: on Windows it made agy build an AppContainer for each command attempt and relaunch itself as administrator to do so (#3603).

    ---
    name: assemblyzero-text
    description: AssemblyZero pipeline seat. Answers from the prompt text alone. No tools, no shell, no files, no network.
    mainAgent: true
    subagent: false
    hidden: true
    inheritMcp: false
    tools: []
    commandExecutionPolicy: "off"
    ---

The value is quoted because a YAML 1.1 parser reads a bare `off` as the boolean false; quoted, every parser reads the string agy documents.

## The verification record

2026-09-25, about 12:15 PM Central, from a directory carrying that definition, with no sandbox flag and the machine's `toolPermission` at `always-proceed`. The prompt asked the model to run `whoami` and to write `probe.txt`. Result: `status SUCCESS`, one turn, 7.1 seconds, stderr empty, no file written, and the answer "I cannot run commands, read or write files, or reach the network because I have no tools available to perform these actions." The call's `input_tokens` were 2,766 against 15,983 for the same model in text mode without the agent, which is the tool schemas leaving the prompt.

## To repeat it

In bash, from the AssemblyZero checkout, with the probe files under `data/scratch-2026-09-25-run-report-design/agy-agent-probe/` (the agent under `cwd/.agents/agents/assemblyzero-text/agent.md`, the prompt in `prompt.txt`):

    poetry run python tools/gemini-retry.py --prompt-file data/scratch-2026-09-25-run-report-design/agy-agent-probe/prompt.txt

Expected: the same answer, no dialog, no `probe.txt`. If the answer reports that a command ran or a file was written, the agent was not honored; stop, and record the exact output on #3603.
