# 0027 — Idempotent rolls: preserve the evidence, then restore the universe

**Status:** Active
**Issue:** #2143 (implementation gaps: #2144 file janitor, #2145 exit reconcile, #2146 precondition posture)

**A roll is idempotent: rerunnable, always.** This is the operator's definition,
ruled 2026-08-09, and it is about state, not math: after any roll — success,
failure, or death — the operator can type the same launch command again and it
runs, because nothing from the previous roll is in the way and nothing from the
previous roll was lost. The machinery cleans up after itself; it never hands
its mess to the operator.

Two ordered obligations and a bound.

## 1. Preserve, then restore

Every exit a roll controls — success, failure, gate refusal, storm exit,
deliberate stop — does two things, in this order:

1. **Save every emission.** Logs, drafted LLDs, branch content, telemetry,
   the stage tables — all of it, preserved on refs and files that persist
   (graveyard branches, archives, `data/speedrun/`), tracked, forever. A
   failed run's clues are the product of the failure; they are why the
   failure was worth paying for.
2. **Restore the borrowed state.** The target repo and AssemblyZero end
   exactly as the roll found them: default branch checked out, no untracked
   files the pipeline made, no stray sibling folders in `~/Projects`, no
   stashes, no extra worktrees, no leftover branches beyond the deliberate
   graveyard. "Restore verified" may only be claimed when the verification
   actually covers all of that — a restore that checks only tracked
   modifications and worktree counts while pipeline-emitted untracked files
   sit in `docs/` is reporting a wish (that gap is #2145).

## 2. Janitor on entry

SIGKILL, power loss, an errant Ctrl+C, a reboot: some deaths leave no author
alive to clean up. The obligation transfers to the NEXT launch, which begins
by cleaning up after any incapacitated predecessor — preserve its evidence,
then reset to pristine, then proceed with its own preflight.

Refuse-and-tell-the-human is not a janitor. A launch that finds a
predecessor's leavings and stops with "commit, stash, or resolve them first"
has handed the machinery's own mess to the operator — the exact failure mode
this standard exists to end (run-16's LLD droppings blocked two launches,
eight days later, and a human had to clear them; that gap is #2144/#2146).

The worktree sweep (#2077) is the reference janitor: preserve dirty content
to a graveyard branch, remove clean registered worktrees plainly, relocate
what git no longer knows, never use force, never delete unpreserved content,
never abort the roll over a janitor problem. Extend that posture to every
class of leavings, not only worktrees.

## 3. The bound: cleanliness never destroys evidence

Preservation always precedes removal — structurally, not as a convention:
nothing is removed that is not first reachable from a ref or stored in the
run's record. `data/speedrun/**` (runs, telemetry, analysis) is the saved
evidence itself and is exempt from cleaning by design.

## The one legitimate refusal

The machinery refuses to touch content it cannot prove it authored. Pipeline
emissions live at known paths (the emission allowlist, shared across #2144,
#2145, #2146); everything else is presumed to be the operator's work, and a
launch blocked on operator-owned dirt refuses BY NAME, classifying each
blocking path so the console (standard 0026) says exactly what is in the way
and whose it is. That refusal is the safeguard working.

## What exists today, and what is missing

| Mechanism | Covers | Gap |
|---|---|---|
| `restore_repo` (#2005), launcher `finally` | checkout branch, this roll's worktrees, tracked modifications | untracked pipeline emissions invisible to its verification — #2145 |
| Worktree sweep (#2077), launcher start | all pipeline worktrees, both locations | files are not worktrees — #2144 |
| Graveyard branches / run archiver (#2076) | preservation targets | nothing routes file leavings into them automatically — #2144/#2145 |
| `speedrun_new_attempt` preconditions | last-line defense of a settled tree | refuse-first posture hands machinery-owned dirt to the operator — #2146 |

## Origin

2026-08-09. Two consecutive launches were blocked by leavings the machinery
had created and never cleaned: ten stranded sibling worktrees (swept by hand
that morning) and two untracked LLD files from run-16 (moved by hand that
afternoon). The operator's ruling, paraphrased: the roll machine must be
potty-trained — a failed roll saves its evidence and resets the universe, a
starting roll cleans up after any predecessor that could not, and the
operator is never the janitor of the machine's own waste.

## Reference

- Standard 0026 — the console narrates what the janitor did.
- `assemblyzero/speedrun/worktrees.py` — the reference preserve-then-clear
  implementation this standard generalizes.
- #2005, #2076, #2077 — the existing partial mechanisms.
- #2144, #2145, #2146 — the implementation issues that close the gaps.
