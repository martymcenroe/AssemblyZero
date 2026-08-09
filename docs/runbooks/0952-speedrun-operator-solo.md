# 0952 — Operator-solo speedrun: launch, watch cheaply, stop, inspect

- **Date:** 2026-08-02
- **Issue:** #2087
- **Status:** Active. This is the default way to run the campaign. `docs/babysit-protocol.md` is the exception, for live-intervention debugging.

The campaign's original goal was that the operator runs one command, records the
output, and no agent watches anything. The instrumentation for that now exists —
events/heartbeat/stdout triplets, launcher narration, preflight and storm
classifications, failure telemetry, the timing dashboard, the run archiver — but
the operator-facing procedure did not. This is it.

**Watching costs tokens. Reading artifacts afterwards is nearly free.** An agent
tailing a log for ninety minutes spends a fortune to learn what the log already
records. Launch, walk away, and hand an agent § Inspect when it is done.

Every command below was executed once while writing this file. The one exception
is named in § Launch, with its reason.

---

## § Launch

**Operator.** From the AssemblyZero checkout:

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/speedrun_roll.py \
    --repo /c/Users/mcwiz/Projects/boostgauge \
    --issue 1 --issue 4 --issue 7 \
    --attempts 3 \
    --detach
```

Flags, verified against `poetry run python tools/speedrun_roll.py --help` rather
than transcribed:

| Flag | Meaning |
|---|---|
| `--repo` | target repo root (required) |
| `--issue` | issue to roll — **repeatable**, rolled in order |
| `--attempts` | redraw a failed issue up to N times before stopping. Base/gate problems never retry. |
| `--detach` | run via Windows Task Scheduler so the roll outlives this session — then **stay attached, streaming the roll's output into this console** until it finishes (#2138) |
| `--no-follow` | with `--detach`: hand off and return immediately instead of streaming (for scripted callers) |
| `--follow` | re-attach to a roll already running and stream its output here. Takes no `--issue` |
| `--log-dir` | where the triplets land. Default `<repo>/data/speedrun/runs` |
| `--assemblyzero-root` | checkout that owns `orchestrate.py`. Default: the tool's own repo |
| `--detach-stop` | stop a detached roll and everything it spawned |

**Use `--detach`.** A roll started from a session is a descendant of that
session's shell, and a harness kill of the shell takes the whole tree with it.
A scheduled task is parented by the Task Scheduler service instead, so nothing
done to the launching session can reach it.

**Detaching the work does not detach the view** (standard 0026). The command
you typed keeps your console: it streams the roll's narration live until the
final line, then exits with the roll's result. There is nothing else to open
and nothing to type. Ctrl+C stops watching only — the roll keeps running.

> **The launch command is the one command in this runbook not executed during
> authoring.** Running it would start a real pipeline roll, and the shakedown of
> the new gates is deliberately the operator's own session. Its flags are
> verified against `--help` above, which is what the issue's acceptance asks for.

### What can refuse to launch, and what you do about it

All three gates run **before anything is spent** — no branch is created, no
tokens are used. All three exit **91**.

| Refusal | What it means | What you do |
|---|---|---|
| The AssemblyZero tree is not trustworthy | this checkout is behind or dirty, so the roll would execute pipeline code that `main` does not describe | bring it level with `origin/main`, or point `--assemblyzero-root` at a tree that is |
| This machine is not healthy enough | a quick self-check ran far slower than normal, or memory is above 90% | wait for the machine to recover, or find what is loading it. Do not override it — a roll on a sick box wastes hours *and* makes every failure look like a target-repo problem |
| The repository has unanswered questions | one or more issues are open asking you to rule on ambiguous issue text | read each, decide which reading is right, edit the issue so only one survives, close the question |

**The first-ever run on a machine records the health baseline and proceeds.** A
missing baseline never blocks. Nominal is a rolling median over five runs, so it
tracks the machine rather than one lucky run.

---

## § Watch

**You are already watching.** The launch command streams the roll's narration
into the console you launched from (#2138, standard 0026). Healthy output looks
like this — a `BASE` line, then a `LAUNCH` line per roll:

```
2026-08-01 16:34:55 BASE 'hardening-run-16' clean for #2 after self-heal
2026-08-01 16:34:55 LAUNCH base=hardening-run-16 -> run-issue2-163450.log
```

**A quiet stretch is normal, and the follower says so.** Model stages run long
between narration lines. After five minutes of silence the follower prints one
liveness note naming the freshest heartbeat (a roll beats every 15 seconds), so
"slow stage" and "dead" are distinguishable without touching anything.

**Ctrl+C stops WATCHING only, never the roll.** It prints the re-attach and
stop commands as it exits. **Closed the console entirely?** Nothing was lost —
the roll is parented by the scheduler. Re-attach from AssemblyZero:

```bash
poetry run python tools/speedrun_roll.py --repo /c/Users/mcwiz/Projects/boostgauge --follow
```

### Recovery — reading the record by hand

The narration and heartbeats are durable files whether or not anything is
watching. If no follower is available (remote shell, agent doing § Inspect):

```bash
tail -f /c/Users/mcwiz/Projects/boostgauge/data/speedrun/runs/detached-launcher.log
tail -3 /c/Users/mcwiz/Projects/boostgauge/data/speedrun/runs/run-issue1-051632-heartbeat.log
```

**Liveness lives in the heartbeat, not the launcher log.** The last beat is the
time of death under an uncatchable kill; a quiet launcher log during a long
stage is normal, a stopped heartbeat is not:

```
2026-08-01 05:23:03 alive
2026-08-01 05:23:18 alive
2026-08-01 05:23:33 alive
```

**A backoff is not a hang.** When the model provider stops answering, the
launcher waits rather than burning a fresh attempt on the same wall, and says so:

```
STORM BACKOFF 15m before attempt 2/3
```

Waits are 15, then 30, then 60 minutes, capped at 60. A storm on the final
attempt exits immediately rather than waiting for nothing.

**The one rule from the watchdog doctrine:** a stage running past three times its
nominal is a fault, not patience. Waiting longer has never once helped.

---

## § Done, or dead?

Three independent signals. Use more than one.

```bash
# 1. Did the launcher finish? Look for a terminal line per issue.
tail -20 /c/Users/mcwiz/Projects/boostgauge/data/speedrun/runs/detached-launcher.log

# 2. Is anything still beating? A fresh timestamp means alive.
ls -t /c/Users/mcwiz/Projects/boostgauge/data/speedrun/runs/*-heartbeat.log | head -1 | xargs tail -2

# 3. What does Windows think? Ready == not running.
MSYS_NO_PATHCONV=1 schtasks /Query /TN AZ-SpeedrunRoll
```

```
TaskName                                 Next Run Time          Status
======================================== ====================== ===============
AZ-SpeedrunRoll                          N/A                    Ready
```

`Running` means it is still going. `Ready` means it is not.

> **`MSYS_NO_PATHCONV=1` is load-bearing here.** Without it Git Bash rewrites
> `/Query` into `C:/Program Files/Git/Query` and schtasks rejects it. This bit
> the author of this runbook while writing this very line.

---

## § Stop

**Operator.**

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/speedrun_roll.py \
    --repo /c/Users/mcwiz/Projects/boostgauge --detach-stop
```

With nothing running it says so and exits 0:

```
No recorded pid at C:\Users\mcwiz\Projects\boostgauge\data\speedrun\runs\detached-roll.pid.
```

**What it does:** kills the detached launcher and every process it spawned.

**What it does not do:** it does not revert the target repo, delete a worktree,
close a PR, or roll back a branch. Whatever the roll had already written is still
there. That is deliberate — a stop should not also destroy the evidence of why
you stopped it. Clean-up happens on the next launcher start, which sweeps every
pipeline worktree: clean ones are removed, dirty ones have their content
committed to a `graveyard/*` branch first, and directories git no longer tracks
are relocated rather than deleted.

---

## § Inspect — the post-run evaluation

**Agent.** Executed by *reading artifacts*, not by having watched. Work top to
bottom; each step names its own file or tool.

**1. The roll-by-roll record.** Read the launcher narration end to end. It is the
only file that shows the sequence of attempts, self-heals, redraws and backoffs.

```bash
cat /c/Users/mcwiz/Projects/<repo>/data/speedrun/runs/detached-launcher.log
```

**2. Per-roll outcome.** Each roll has a triplet — `<tag>-events.log` (START /
BASE / LAUNCH / EXIT), `<tag>.log` (orchestrator stdout, including the stage
table), `<tag>-heartbeat.log`. The events log's `EXIT rc=` is authoritative for
success; the stage table in the stdout log says which stage failed and whether a
retry was `RESUMED` or `REGENERATED`.

```bash
ls /c/Users/mcwiz/Projects/<repo>/data/speedrun/runs/*-events.log | tail -5
```

**3. Validation-failure telemetry.** One record per drafter validation failure,
fingerprinted.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/prompt_failure_report.py --repo /c/Users/mcwiz/Projects/<repo>
```

An empty file is a real answer, not a broken tool:

```
No telemetry file at C:\Users\mcwiz\Projects\boostgauge\data\speedrun\telemetry\prompt-failures.jsonl
```

If it has content, rank it by cost and follow
`docs/standards/0025-prompt-revision-from-telemetry.md`:

```bash
poetry run python tools/prompt_revision_rank.py --repo /c/Users/mcwiz/Projects/<repo>
```

**4. Regenerate the timing dashboard.** Where the wall-clock went.

```bash
poetry run python tools/campaign_timing_dashboard.py --repo /c/Users/mcwiz/Projects/<repo>
```

Writes `data/speedrun/analysis/runs.csv` and `campaign-timing.png` under the
target repo. Read the CSV; the PNG is for the operator.

**5. Questions the run raised.** If any rolls halted on ambiguous issue text,
they filed issues. These block the next launch until ruled on.

```bash
gh issue list --repo martymcenroe/<repo> --label must-resolve --state open
```

Empty output means none are open.

**6. Archive the run.** Last, because it is the only step that is unrecoverable
if skipped — arcs are never merged to main, so a run's product lives only on
branches and in logs.

```bash
poetry run python tools/speedrun_archive.py \
    --repo /c/Users/mcwiz/Projects/<repo> --run <integration-branch> --dry-run
poetry run python tools/speedrun_archive.py \
    --repo /c/Users/mcwiz/Projects/<repo> --run <integration-branch>
```

**Verify `"complete": true` in the archive's `index.json`.** The command exits
nonzero and names the missing component when it is not. A partial archive never
authorizes deleting anything.

### The paste block

Give this to any agent, verbatim. Evaluation should be one paste, not a
conversation.

```
Evaluate speedrun run <RUN-NAME> in <REPO-PATH> per AssemblyZero
docs/runbooks/0952-speedrun-operator-solo.md § Inspect.

Read artifacts only — do not launch, re-run, or resume anything, and do not
delete any branch or worktree. Work steps 1 through 6 in order and report:

  1. rolls attempted, and the outcome of each
  2. which stage failed on each failed roll, and whether its retry RESUMED or
     REGENERATED
  3. any provider-storm backoffs, with their durations
  4. the top validation-failure fingerprints by cost, or "telemetry empty"
  5. run time vs diagnose+fix time for the run's dates
  6. any must-resolve issues now open
  7. the archive path and whether index.json says complete: true

Finish with the single highest-value change to make before the next run, and
the evidence for it.
```

---

## Related

- `docs/babysit-protocol.md` — the agent-watching model this replaces. Use it
  only when you intend to intervene mid-run.
- `docs/standards/0025-prompt-revision-from-telemetry.md` — what to do with the
  telemetry once step 3 has ranked it.
