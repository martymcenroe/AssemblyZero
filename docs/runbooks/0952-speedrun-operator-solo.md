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
    --detach
```

Flags, verified against `poetry run python tools/speedrun_roll.py --help` rather
than transcribed. `tests/unit/test_runbook_0952_flags.py` re-checks that claim
against the launcher's own argparse and parses every example on this page, so
the verification is re-run rather than asserted (#2295):

| Flag | Meaning |
|---|---|
| `--repo` | target repo root (required) |
| `--issue` | issue to roll — **repeatable**, rolled in order |
| `--attempts` | retired by operator ruling #2206 — only `1` is accepted, and a higher value refuses at preflight before anything is spent. A failure halts so its cause can be found; the relaunch resumes from the failed stage (#2193) rather than re-paying for the stages that passed. |
| `--detach` | run via Windows Task Scheduler so the roll outlives this session — then **stay attached, streaming the roll's output into this console** until it finishes (#2138) |
| `--no-follow` | with `--detach`: hand off and return immediately instead of streaming (for scripted callers) |
| `--follow` | re-attach to a roll already running and stream its output here. Takes no `--issue` |
| `--log-dir` | where the triplets land. Default `<repo>/data/speedrun/runs` |
| `--assemblyzero-root` | checkout that owns `orchestrate.py`. Default: the tool's own repo |
| `--detach-stop` | stop a detached roll and everything it spawned |
| `--override-prereqs` | launch even though the previous run's unresolved questions are still open (#2167) — runs anyway once; the next launch re-checks |
| `--redraw-completed` | redraw an issue this arc has **already rolled to success** (#2191). Without it, an interactive launch demands a typed `REDRAW <N>` and a non-interactive one refuses — so an issue number typed out of habit cannot silently redo work already merged into the arc. Scoped to the current arc: a new base branch starts with an empty slate |
| `--fresh` | redraw every stage from scratch (#2193). Without it, a launch that finds a prior non-conflict failure with the LLD already passed resumes from the failed stage — the passed stages are reused, not paid for again. A conflict-blocked issue always redraws fresh: the ruling edited the issue text, and the preserved draft embeds the pre-ruling wording |
| `--narration` | starting view level: `terse`, `verbose`, `tutorial`, or `quiz` (#2159/#2160/#2161 — tutorial annotates each node and gate; quiz pauses the DISPLAY at transitions for multiple choice generated from the graph, roll unaffected). Press `v` in the console to toggle live; the log on disk is always complete |

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

All of these gates run **before anything is spent** — no branch is created, no
tokens are used. All exit **91**.

| Refusal | What it means | What you do |
|---|---|---|
| The AssemblyZero tree is not trustworthy | this checkout is behind or dirty, so the roll would execute pipeline code that `main` does not describe | bring it level with `origin/main`, or point `--assemblyzero-root` at a tree that is |
| This machine is not healthy enough | a quick self-check ran far slower than normal, or memory is above 90% | wait for the machine to recover, or find what is loading it. Do not override it — a roll on a sick box wastes hours *and* makes every failure look like a target-repo problem |
| The repository has unanswered questions | one or more issues are open asking you to rule on ambiguous issue text | work § Rule below — decide, edit, **pre-check**, then close the question |
| The arc's binding docs conflict with the default branch | design docs or ADRs were ruled on both branches and the two edits collide (#2205) | merge them by hand, then roll. Nothing was changed — the launcher refuses rather than resolving a ruling on your behalf |

**Binding docs sync themselves (#2205).** The roll reads design docs and ADRs
from the attempt branch, not from `main` — issue text arrives live from
GitHub, docs do not. Before anything is drawn, the launcher carries any
binding-doc commits from the default branch onto the arc and says so:

```
SYNC 2 binding-doc commit(s) on 'main' not yet on 'hardening-run-17' -- carrying them onto the arc before the roll reads them
SYNC verified: 'hardening-run-17' now carries the binding docs from 'main'
```

An arc already current is silent and costs nothing. This exists because an
arc once carried a two-day-old aesthetic doc while five rulings sat on
`main`: the spec stage failed twice on an objection the operator had already
answered, and the answer was invisible to the pipeline.

**The first-ever run on a machine records the health baseline and proceeds.** A
missing baseline never blocks. Nominal is a rolling median over five runs, so it
tracks the machine rather than one lucky run.

---

## § Rule — answering a must-resolve question

A roll that finds two acceptance criteria specifying different outcomes for the
same situation halts, files a `must-resolve` issue naming both sentences, and
blocks every later launch until you answer. Only you can answer it: the gate
reports that two readings are defensible, and choosing between them is a
decision about the product.

**The order is: decide, edit, pre-check, close, roll.**

**1. Decide, and edit the issue so only one reading survives.** Read the two
sentences the question quotes. Amend the issue text — both sentences, not only
the one the gate named. A qualifier added to one sentence and not its
neighbours is what produces the next contradiction.

**2. Pre-check before you close anything.**

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/check_requirements.py \
    --repo /c/Users/mcwiz/Projects/boostgauge --issue 7
```

This runs the roll's own gate against your edited text — the same function,
imported, not a second implementation of it. One model call, a few minutes.

| Exit | Meaning | What you do |
|---|---|---|
| 0 | the gate found no contradictions | go to step 3 |
| 1 | it found more, printed verbatim | return to step 1. The pre-check filed them as must-resolve issues, exactly as a roll would |
| 2 | the check could not run | fix that first. Nothing was verified, and unlike a roll this never passes quietly |

> **This command's flags and its exit-2 path were executed while writing this
> section; a full clean run against a live issue was not.** That call spends a
> drafter-class model request and, on a conflict, files must-resolve issues on
> the target repo — side effects that belong to a real ruling rather than to
> authoring a runbook. The gate call itself is covered by
> `tests/unit/test_check_requirements.py`, which drives the live node through
> every one of its outcomes.

**3. Close the must-resolve issues, and roll.** Close them only on a clean
pre-check. Closing them on an unverified edit puts the launcher back in
business against text that still contradicts itself.

**Why the pre-check exists.** boostgauge #7 took five rulings, and each was
verified by paying for the next launch: edit, roll, wait through the
codebase-analysis node, and learn three minutes in that the amendment had
introduced a fresh contradiction. Seven conflicts were discovered that way. On
the sixth iteration the gate was run by hand against the draft first and caught
three defects before anything was spent. This step is that pass, made
repeatable (#2221).

**The pre-check is advisory; the roll's gate is authoritative.** A pre-check
attestation goes stale the same way a draft does — the issue text and the
binding docs both keep moving (#2206). The roll runs the gate again on every
launch, and that run is the one that counts.

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

**A dead provider ends the issue immediately (#2206).** When the model provider
stops answering, the roll says so and stops — with no redraw to protect, there
is nothing to wait for:

```
STORM ended #4 -- the provider stopped answering; nothing was redrawn (#2206). Relaunch when it recovers.
```

The former behaviour — waiting 15, then 30, then 60 minutes before redrawing —
went with the redraw loop. Relaunch once the provider recovers; the stages that
already passed resume rather than re-run.

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

**3b. The healing ledger.** What the machinery fixed about itself (#2164) —
resets, sweeps, janitor acts, storm waits, restore reconciles — one record
per heal, partials first-class. A heal that recurs across three runs is a
defect wearing a bandage, and the report emits a ready-to-file issue stub.
Filing is the operator's call, never automatic.

```bash
poetry run python tools/heal_report.py --repo /c/Users/mcwiz/Projects/<repo>
```

An empty ledger is a real answer, same cold-start rule as the telemetry.

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

Empty output means none are open. Anything listed is answered by working
§ Rule above — decide, edit, pre-check, close — and the pre-check is what keeps
the answer from costing a launch to verify.

**6. Confirm the archive.** A successful roll archives itself and verifies the
result (#2353), so on that path this step is a read, not a run. The launcher
prints the verdict under `ROLL SUCCEEDED`:

```
  Archive: C:\Users\mcwiz\Projects\<repo>\data\speedrun\archives\<run>
    rolls 6 | branches 1 integration + 64 graveyard | files 542
    complete yes
    manifest OK
```

Confirm two lines: `complete yes` and `manifest OK`. Anything else is named in
the same block, and an archive failure never changes the roll's own verdict —
the roll succeeded; a failed archive is its own problem.

Archive by hand when there is no launcher verdict to read: a failed or
interrupted roll, an archive that reported a problem, or a re-archive after
adding branches.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/speedrun_archive.py \
    --repo /c/Users/mcwiz/Projects/<repo> --run <integration-branch> --dry-run
```

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/speedrun_archive.py \
    --repo /c/Users/mcwiz/Projects/<repo> --run <integration-branch>
```

Then assert the archive is sound. `--verify` checks both dimensions in one
exit code: that the archive records itself complete, naming any missing
component, and that every captured file still matches its recorded sha256.

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/speedrun_archive.py \
    --verify /c/Users/mcwiz/Projects/<repo>/data/speedrun/archives/<run>
```

A partial archive never authorizes deleting anything. Archiving is the only
step that is unrecoverable if skipped — arcs are never merged to main, so a
run's product lives only on branches and in logs.

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
  4. the top validation-failure fingerprints by cost, or "telemetry empty",
     plus the healing ledger's recurring-heal issue stubs, or "no recurrences"
  5. run time vs diagnose+fix time for the run's dates
  6. any must-resolve issues now open
  7. the archive path, and the `--verify` exit status for it

Finish with the single highest-value change to make before the next run, and
the evidence for it.
```

---

## Related

- `docs/babysit-protocol.md` — the agent-watching model this replaces. Use it
  only when you intend to intervene mid-run.
- `docs/standards/0025-prompt-revision-from-telemetry.md` — what to do with the
  telemetry once step 3 has ranked it.
