# Test Report — A Standing Order Survives a Task Boundary (#3301)

## What This Change Is

Six lines of prose in `CLAUDE.md`. There is no code path, no function, and no
runtime behaviour to exercise. Saying so plainly is the point of this report:
inventing a test that passes without measuring anything would be worse than
recording the absence.

## What Was Verified

**1. The file still parses as intended markdown, and the section lands where it
was meant to.** `## Standing Orders` sits immediately after Cascade Prevention's
paragraph and immediately before `## Merging PRs`, at the same heading level, so
it reads as a sibling rule rather than a subsection of either.

**2. Cascade Prevention is byte-unchanged.** Confirmed by reading the diff: the
change is a pure insertion. This was the design constraint, so it is the one
property worth asserting mechanically.

**3. The instruction counts.** Halt-shaped and continue-shaped instructions in
this file, counted over an authored pattern set, before and after:

| | halt | continue |
|---|---|---|
| before | 4 | 0 |
| after | **8** | 3 |

**The halt count doubled, and that is a defect in the counting, not in the
change.** Nothing was removed and no halt was added. The new section contains the
string `what do you want to work on next` and the word `unprompted` — because it
names the task-boundary question in order to FORBID it. The counter cannot tell a
quoted prohibition from an instruction, so a counterweight written in the natural
style scores as four more halts.

This was predicted before it was measured and it still surprised me in
magnitude. It is the reason the counts below are labelled evidence rather than a
measurement.

The number that means what it says is **continue: 0 → 3**. Before this change
there was nothing in the file for a standing order to stand on; now there is.

## What Was NOT Verified, And Cannot Be Here

**That an agent actually behaves differently.** No automated test can establish
it. The change alters what a model reads at load time; the only evidence is
observed conduct in later sessions, and a single session proves nothing either
way.

**That the counting method is a good measure of pressure.** It is not, entirely.
The counter scores a sentence that QUOTES a halt in order to forbid it the same
as one that instructs a halt — this section's own text names the task-boundary
question in order to prohibit it. On the file it was developed against, adding a
counterweight of this shape RAISED the halt count. The counts above are reported
as evidence, not as a measurement of the thing the issue is about, and the
before/after comparison is only meaningful because both sides were counted the
same way.

## Regression Risk

Low and slow-acting. The failure mode of this change is not a crash but an agent
continuing past a point where it should have stopped — which surfaces as
unwanted work, not an error, and would be attributed to the model rather than to
this file. If that happens, the second paragraph is the first thing to revisit.
