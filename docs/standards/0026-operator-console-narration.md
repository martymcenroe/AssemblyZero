# 0026 — Operator-launched programs narrate to the console they were launched from

**Status:** Active
**Issue:** #2137 (first conforming implementation: #2138, `tools/speedrun_roll.py`)

When the operator runs a command, that command's progress prints live in the
console it was typed into, from launch to final status. Learning what a program
is doing must never require a second console, a `cd`, a `tail`, or a status
command recalled from memory. The console the operator launched from IS the
display.

This principle has been enforced piecemeal for months without ever being
written down, which is how runbook 0952 shipped violating it: issue #128 forced
narration onto the silent requirements workflow, `workflow-lessons-learned-1.md`
names "Silent long-running operations" an anti-pattern ("Progress indicators
every 5 seconds max"), and standard 0019 echoes validation failures to the
console specifically so operators "see what failed without grepping log files".
Each was the same ruling. This document is that ruling, stated once.

## The clauses

### 1. The launched-from console is the display

Progress prints there, live, unbuffered (`PYTHONUNBUFFERED=1` or
`flush=True` — Python buffers stdout off-TTY), until a final line states the
outcome. A program that is silent while working is defective even when it
works: the operator has twice misdiagnosed healthy long stages as hangs
because nothing said otherwise.

### 2. Backgrounding never removes the obligation

Detaching work for survivability (Task Scheduler, service parents, `--detach`)
is a property of the WORK, not of the VIEW. The launching command still streams
the narration by default until the work finishes. Opting OUT of watching is the
flag (`--no-follow`); watching is **never opt-in**. A tool that detaches and
returns silently has moved the display problem onto the operator, which is the
exact thing this standard prohibits.

### 3. Logs are the record; the console is the view

Everything shown on the console must also be durable in a log file (a viewer
can die; the record must not), and everything in the log that the operator
would act on must reach the console. One narration file per run, appended, is
the reference shape (`detached-launcher.log`).

### 4. Silence is a defect

A long quiet stage emits a periodic liveness note — at most every 5 minutes of
narration silence, naming the freshest heartbeat and its timestamp — so
"working on something slow" and "dead" are distinguishable without touching
anything. This does not license chatter: the note is one line, and it appears
only when the narration is quiet.

### 5. Detaching the view is safe, and says so

Ctrl+C on a follower **stops the view, never the work**, and prints two
verbatim commands before exiting: how to re-attach, and how to actually stop
the work. A viewer must be structurally incapable of harming what it watches —
read-only file access and status queries only.

### 6. One command

If a runbook needs a menu of consoles, directories, and from-memory commands
to answer "what is it doing?", the defect is in the program, not the runbook.
Manual log-reading commands may exist in runbooks as **recovery** paths
(follower unavailable, remote shell), never as the primary interface.

## Enforcement

- `tests/unit/test_speedrun_roll_follow.py` pins the reference
  implementation: follow-by-default wiring, the viewer's inability to touch
  the work, and this document's load-bearing clauses at string level.
- New operator-facing tools conform at review. "It writes a log the operator
  can tail" does not satisfy this standard.
- Runbooks present the one-command flow first; hand log-reading demotes to a
  recovery section.

## Origin

2026-08-09. The operator refused runbook 0952's original § Watch — a detached
launch followed by four manual surfaces (tail the narration, tail the newest
heartbeat, query the scheduler, read the triplets) — as unusable, and was
right: every prior incarnation of this ruling (#128, 0019, the lessons-learned
anti-pattern) said the same thing about a different tool. The rule was being
re-derived per program because no standard carried it.

## Reference

- #128 — the requirements workflow made to narrate (the earliest incarnation).
- Standard 0019 § console echo — validation failures reach the console.
- Runbook 0952 — the operator-solo speedrun flow this standard reshaped.
- `tools/speedrun_roll.py` `follow_roll` — the reference viewer.
