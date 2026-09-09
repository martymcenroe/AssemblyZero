# Implementation Report — A Standing Order Survives a Task Boundary (#3301)

## Issue Reference

[#3301: Cascade Prevention halts at every task boundary and nothing says a standing operator order survives one](https://github.com/martymcenroe/AssemblyZero/issues/3301)

## What Changed

Six lines of prose in `CLAUDE.md`, immediately after **Cascade Prevention**: a new
`## Standing Orders` section carrying two paragraphs. No code. No behaviour in any
tool changes; the behaviour that changes is an agent's, at load time.

**Cascade Prevention itself is untouched.** That was the whole design constraint.
It exists because agents genuinely did wander into unauthorized work, and deleting
or weakening it would trade one real failure for another. The addition says only
when the word "unprompted" has stopped applying.

## The Diagnosis

The section instructs the agent to stop and ask at every completed task. Nothing
in the file — or in the layers loaded alongside it — says that a standing
operator order to keep going survives such a boundary. So an agent that has been
told to continue reads each finished unit as a fresh unprompted state and stops,
correctly by the text and wrongly by the instruction it was given.

Measured on this file before the change: **4 halt-shaped instructions, 0
continue-shaped ones.** The imbalance is not an accident of drafting. Every halt
rule was earned by an agent doing too much; none was earned by an agent doing too
little, because that failure is invisible — an agent that stops early looks
polite. So the corpus only ever accumulates halts, and a standing order, being
unwritten, loses to text.

## Why This Shape

Three alternatives were considered and rejected.

**Delete or soften Cascade Prevention.** Rejected: it is load-bearing for a real
failure. The defect is an absence, not the presence of that rule.

**Add "unless told otherwise" to Cascade Prevention itself.** Rejected: it buries
the exception inside the rule it modifies, where an agent scanning for the halt
instruction reads the first clause and acts. A named section is greppable and
survives summarisation.

**Rely on the operator repeating the order.** Rejected: that is the status quo,
and it is what failed. The order was given and acknowledged, and the stack still
won.

## Not Established

Whether this wording is sufficient in practice. Prose in an instruction file has
no test that proves an agent will read it the intended way, and the honest claim
here is narrower than "fixed": the counterweight now exists in text, where before
there was nothing for a standing order to stand on. Whether agents actually hold
a standing order across a boundary is observable only in future sessions.

The second paragraph ("running low on context is not a reason to stop") has the
widest blast radius, because it applies to every session rather than only to
audit-shaped work. It was included deliberately, on operator authorization, and
is the line most worth revisiting if this change misfires.
