# 0957 - agy never elevates, and the setting the pipeline requires

**Issue:** #3605, under #3603. **Runs:** the operator, once, on each machine that runs the pipeline.

The pipeline calls agy for text: a draft in, a review out. It never asks agy to run a command, and it never requests administrator rights. Two things make that true, and this runbook is the one step the operator does for the second.

## What the pipeline does on its own

`GeminiClient` passes no flag between the agy binary and the model. `--sandbox` was withdrawn on 2026-09-25: on Windows it makes agy build an AppContainer for each shell command the model attempts, and agy obtains the administrator token for that by relaunching itself elevated, which is a UAC dialog naming `agy.exe`. Before every call the client reads `~/.gemini/antigravity-cli/settings.json` and refuses to run, naming the file and the value it found, unless `toolPermission` is absent or `request-review`.

## The one step: set agy to review, not proceed

agy's `toolPermission` setting decides what happens when the model proposes a tool call. The documented values are `request-review` (the default), `proceed-in-sandbox`, `strict` and `always-proceed`. In print mode there is no prompt to answer, so under `request-review` a shell command is soft-denied: nothing runs, agy exits 0, and a notice goes to stderr. Under `always-proceed` the command runs unattended. Under `proceed-in-sandbox` agy asks for administrator rights.

Open `C:\Users\mcwiz\.gemini\antigravity-cli\settings.json` in an editor and set the line to:

    "toolPermission": "request-review",

Save the file. The change reaches the next agy process; nothing needs restarting. This is also the setting agy's interactive sessions will use, so a command the model proposes in an interactive session asks before it runs.

## Verify, with the operator watching

Run one print-mode call whose prompt asks the model to run a harmless command, and watch for a dialog. In bash, from the AssemblyZero checkout:

    poetry run python tools/gemini-retry.py --prompt "Run the shell command whoami and report its output verbatim."

Expected: no UAC dialog, the answer says the command could not be run, exit 0, and a notice on stderr. Then read the step back from agy's conversation store under `C:\Users\mcwiz\.gemini\antigravity-cli\conversations\` to confirm no command executed. Record the result on #3603.

If the pipeline refuses with `AgyToolExecutionEnabledError`, the message names the file and the value it found. Set the value above and rerun. Never answer a UAC dialog for agy with Yes: one grant builds the container permanently, and every later sandboxed command runs inside it.
