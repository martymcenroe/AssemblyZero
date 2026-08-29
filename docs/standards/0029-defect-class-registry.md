# 0029 — The defect-class registry

**Status:** Active
**Issue:** #2576
**Sibling standards:** 0025 (prompt revision from telemetry), 0027 (idempotent rolls), 0028 (structured or reject)

The fleet already thinks in defect classes. It just had nowhere to keep them.

"A zero needs a denominator" was born on #2546 and applied twice more within a
day. "Consult the enforcement record before attributing" was born on #2556 and
applied again on #2561 the same afternoon. The S2-regression class, the flake
class, and the fail-open regime were each named, each real, and each living in
scattered comments, closed issues, and one lessons file.

**When a new instance appears, the class match is what makes the fix fast and
its fixture shape obvious.** Before this registry, that match happened in an
agent's memory of the campaign — which does not survive the campaign.

## How to use this

**Finding a defect:** read the detection questions. They are written to be
answerable against a diff or a halt without knowing the history. A yes means you
have an instance of a known class, and the fixture shape tells you what test to
write before you touch anything.

**Filing:** name the class in the issue. An instance filed without its class is
a fact; filed with it, it is evidence about a pattern, and the pattern is what
gets fixed.

**Auditing:** a standing audit becomes "sweep the codebase for instances of a
registered class", which is mechanical in exactly the way the Six Rules demand.
Audits are programs, not inspections. §Backlog below names the three that
convert.

**Adding a class:** two independent instances, minimum. One instance is a bug;
a class is a claim that the shape recurs, and that claim needs evidence. Give
it a name someone would say out loud, the invariant it protects, the detection
question, the canonical fixture shape, and every known instance.

---

## The classes

### 1. A zero needs a denominator

**Invariant.** A count of zero is meaningless without the population it was
counted against. "No failures" and "nothing was measured" are different facts
and must never render identically.

**Detection question.** *If this number were zero because the measurement never
ran, would the output look any different?*

**Fixture shape.** Drive the code with an empty input AND with a
never-populated input; assert the two produce distinguishable output.

**Instances.** #2546 (the founding case), #2552 (zero requirements named —
declared-none vs unreadable, with the searched path), #2575 (a store that does
not exist renders `| NO |`; one that exists and is empty renders `0`).

---

### 2. Attribution requires the enforcement record

**Invariant.** A halt, a log line, or a report never attributes a change to an
actor without consulting the record of what the machinery itself did. Blaming
the drafter for what enforcement did is the specific failure.

**Detection question.** *Does this message name a cause it did not read
evidence for?*

**Fixture shape.** A state where the mechanism (not the actor) produced the
observed condition; assert the message names enforcement, not the actor.

**Instances.** #2556 (the cap halt consults `pinning_events` before any
drafter-unchanged claim), #2561 (the same consult on the `kept_failing`
branch), #2574 (the halt bundle quotes the events rather than summarising
them).

**Note.** This is the special case of the general rule *never attribute an
artifact without proof*. The general form governs operator attribution too.

---

### 3. The demanded change is never refusable

**Invariant.** A change one gate explicitly demands is never revertible by
another gate in the same round. A loop that can demand and refuse the same edit
cannot converge, and burns its cap producing byte-identical drafts.

**Detection question.** *Does this complaint name its edit target in a
vocabulary the enforcement can read — and does that name actually occur in the
draft?* Both halves are required. A token that parses but matches nothing
unlocks nothing.

**Fixture shape.** A producer-consumer test: a fixture that genuinely fails the
check, the REAL emitted message, and an assertion that the enforcement
vocabulary reaches at least one line of the draft. See
`tests/unit/test_completeness_message_addressability.py`, which is this class's
reference sweep, and `tests/unit/test_completeness_pinning_deadlock.py`, its
first entry.

**Instances.** #2555 (the fence complaint that deadlocked; dashed `lines N-M`
citations added to the vocabulary), #2560 (demanded ADDITIONS land — a demand
to add has no line to cite by construction), #2557 (the sweep that found three
more unaddressable messages and the `()`-suffix hazard), #2628 (the section
boundary that ended at injection's own subheading, so a compliant draft read as
empty), #2633 (the variant below).

**The taxonomy is three-way, not two.** A complaint is *addressed* (it cites a
line), *demands an addition* (there is no line to cite, and the #2560 exemption
carries it), or *unaddressable* (it targets existing content in a scheme the
enforcement cannot read). Only the third is a defect. Collapsing the middle case
into the third produces false alarms on correct code.

**Variant: the check's domain is narrower than the document's (#2633).** The
sharpest form of this class is not a badly worded message — it is a check that
sees only one of the identifier namespaces the document actually uses, and so
reports correct work as absent while blaming the author.

`check_manifest_traceability` demanded a manifest-row citation from every test.
The manifest's domain is the injected criteria table alone, so five behavioural
tests had no row to cite. The drafter traced them to LLD **test-scenario** ids
instead — `row 010`, `row 020`, `row 030`, `row 100`, `row 110`, every one a
real row of the LLD's own Test Scenarios table, and exactly the five non-visual
scenarios — plus a valid `REQ-N` on every test. The halt then read *"test(s)
citing no manifest row"* about five tests that visibly cited two identifiers
each. Three revisions, cap.

**Detection question for the variant.** *Does this check enumerate every
namespace the upstream document defines, or only its own?* When the artifact
carries identifiers the check cannot resolve, a "missing" verdict is a domain
error rather than a finding.

**Read the artifact before believing the halt.** #2633 was first diagnosed as
counterfeit compliance — a drafter manufacturing plausible-looking near-misses
under an impossible demand. That would have been a new and alarming claim about
drafter behaviour, and it was wrong: every citation resolved against the LLD.
A halt that blames the author is precisely when the author's output deserves
checking first.

---

### 4. Conservation through transformation

**Invariant.** A transformation that merges, stitches, or rewrites a document
never silently loses or multiplies a conserved quantity. When conservation
cannot be maintained, emit an unmerged whole — never the stitch.

**Detection question.** *Can this transformation emit a result holding fewer,
or more, of the conserved thing than either input justified?*

**Fixture shape.** Two inputs whose merge would violate conservation; assert
the gate fires and that the fallback is one entire input, not a repair.

**Instances.** #2559 (the merge conservation gate — revision unenforced or
previous entire, never the stitch), #2563 (literal conservation in the LLD
derivation: qualifying clauses carried verbatim into derived rows).

---

### 5. The input/litter distinction

**Invariant.** A cleanup mechanism never removes what another stage reads as
input. The distinction is by OWNERSHIP, not by appearance: the rolling issue's
inputs are protected; other issues' droppings remain litter.

**Detection question.** *Does anything this sweep can delete get read on entry
by a later stage — and is the exemption scoped to the rolling issue, or
blanket?*

**Fixture shape.** A tree holding both the rolling issue's input and another
issue's leftovers; assert the first survives and the second is cleared.

**Instances.** #2551 (issue-scoped leavings exemption at both sweep sites),
#2144 (the founding opposite — the janitor exists because litter accumulated),
#2571 (a working copy is a cache; the loader rebuilds from refs rather than
depending on an untracked file surviving).

**Why the scoping is load-bearing.** A blanket exemption solves the deletion and
re-creates #2144. Both failures are real and they pull in opposite directions,
which is why this class is stated as ownership rather than as "do not delete".

---

### 6. Fail-open must be declared

**Invariant.** Every site that continues past a failure is a decision on
record, not an accident. Declared sites remain fail-open and remain counted;
what the gate acts on is *undeclared*.

**Detection question.** *If this handler fires, is the run's output
distinguishable from a successful one?* A silent fall-through is the class.

**Fixture shape.** Not a fixture — a repo-wide gate.
`tests/unit/test_fail_open_audit.py` compares every site against a baseline and
fails on a new undeclared one. The ruling is `# fail-open: <why>` inside the
handler body (or directly above a warn-and-return).

**Instances.** #2475 (the regime), #2508 (68 sites in the standing backlog),
#2575 (six sites ruled in place; five toward inclusion, one deliberately toward
exclusion because misattribution is invisible while undercounting is not).

**Placement is part of the class.** Handler-class rulings go INSIDE the handler
body; warn-and-return rulings directly above the return. The marker is the
literal string `# fail-open:` — a comma instead of the colon does not register,
which has already cost one round trip.

---

### 7. The once-under-load flake

**Invariant.** A test that fails once under load and passes on retry is not
noise. It is a real defect whose trigger is timing, and re-running is not
triage.

**Detection question.** *Did this pass on retry with no code change — and has
anyone identified the shared resource?*

**Fixture shape.** Reproduce under contention (parallel workers, a filled
cache, a held lock) rather than in isolation.

**Instances.** #2522, #2538.

---

### 8. A resume inherits, never rediscovers

**Invariant.** A resume uses what the halt recorded. It never rediscovers state
from a world that has meanwhile changed, because the halt knew exactly what it
had and the world no longer does.

**Detection question.** *Does this resume path read anything the halt could
have recorded instead?*

**Fixture shape.** Halt with recorded state, mutate the world, assert the
resume refuses BY NAME rather than proceeding on the changed input.

**Instances.** #2551 (the LLD swept as leavings), #2552 (the
zero-requirements fallback that would have certified against nothing), #2514
(stale counters putting a resumed round over its own ceiling), #2570 (the
resume contract — the machinery that closes the class).

**Each was the same defect wearing a different artifact.** That is what earns
it a class entry rather than three bug fixes.

---

## Backlog conversion

Three standing audits become class sweeps. A sweep is a program: it re-runs,
and its findings cite registry entries.

| audit | class | status |
|---|---|---|
| #2557 — completeness message addressability | 3, the demanded change is never refusable | **Executed.** `tests/unit/test_completeness_message_addressability.py`; findings in `docs/audits/0905-message-addressability-sweep-2026-08-28.md` |
| #2508 — 68 fail-open sites | 6, fail-open must be declared | Gate exists; the backlog is the ruling pass |
| #2540 — fact-verifier vs proxy-heuristic | 3 and 1 (a proxy that vetoes is a zero without a denominator) | Not started |

## Lessons discipline

A new entry in `docs/lessons-learned.md` either cites a class here or founds
one. A lesson that fits no class and does not found one is a fact about one
day, and will be gone by the next campaign — which is the condition this
registry exists to end.
