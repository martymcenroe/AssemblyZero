# ADR 0226: Requirements are authored in a checkable form

**Status:** Accepted
**Date:** 2026-08-11
**Categories:** Process, Data, Reliability
**Related:** #2218 (this ADR); #2219 (the checker, and the rulings that scoped EARS and defined the row ID convention); #1899 (the requirements-consistency gate); #2221 (the standalone caller for that gate); standard 0028 (ask structured, get structured, or reject); boostgauge #7 (the first converted requirement); boostgauge #235, #240, #249, #252, #273, #274, #275 (the seven conflicts); boostgauge #270 (a pass criterion carries values, not pointers)

---

## 1. Context

The requirements-consistency gate reads an issue before any drafting begins. It halts the run when two acceptance criteria contradict each other, and files an issue naming the pair. The gate works as designed.

On boostgauge issue #7 it fired seven times across five separate operator rulings. Every firing landed on the same paragraph. The rulings were boostgauge #235, #240, #249 and #252, followed by #273, #274 and #275 from a single run on 2026-08-11.

Each ruling amended one sentence of English prose, and each amendment carried a condition. The neighboring sentences making adjacent claims never received that condition. Prose offers no mechanism to propagate a qualifier across a paragraph, so every repair produced the next contradiction.

The requirement underneath is a function of two independent conditions. The first is whether the app was launched with `--reset-config`. The second is whether the user moved or resized the window. Four combinations exist. The paragraph described three of them in overlapping sentences and left the fourth ambiguous.

The gate's output carries a second signal. One defect produced three issues, because a pairwise comparison over prose can only report pairs. A complete enumeration reports one gap instead.

### The same defect, one stage later

boostgauge ruling #270 established that a test pass criterion must carry the value it asserts, rather than cite the document holding that value. The specification stage reads the LLD and not the design docs. An LLD that pointed at a color instead of quoting it left the test writer nothing to assert, and the only test then available was one that verified nothing. Seven specification halts on boostgauge #1 came from that gap.

This ADR applies the same requirement one level higher. The LLD stage reads the issue. An issue that states combinatorial behavior as overlapping prose leaves the drafter to guess which reading was intended.

## 2. Decision

**We will author requirements in a form whose completeness a program can verify.** Three rules bind every issue the orchestrator rolls.

1. Each requirement is one sentence in an EARS pattern, carrying its own trigger or state condition.
2. Where behavior depends on two or three independent conditions, the requirement is a decision table enumerating every combination, and each row becomes one acceptance criterion.
3. A requirement whose behavior depends on more than three conditions is split into several requirements rather than tabulated.

## 3. The three rules in detail

### 3.1 EARS sentence patterns

Every requirement takes one of five forms (Mavin et al., 2009):

| Pattern | Form |
|---|---|
| Ubiquitous | The `<system>` shall `<response>` |
| Event-driven | WHEN `<trigger>` the `<system>` shall `<response>` |
| State-driven | WHILE `<state>` the `<system>` shall `<response>` |
| Unwanted behavior | IF `<condition>` THEN the `<system>` shall `<response>` |
| Optional feature | WHERE `<feature is present>` the `<system>` shall `<response>` |

The benefit is that a conditional requirement cannot be written as though it were universal. Both halves of the boostgauge #7 collision were conditional statements written in the ubiquitous form. "On exit only hand-made changes are written" is state-driven and never said so. "It rewrites the file to defaults regardless" is event-driven and never said so. Each one read as a universal law, so the two appeared to contradict.

A parser can reject a sentence matching none of the five patterns. That check is cheap and runs at authoring time.

**EARS binds the sentences of the marked requirements section, and nothing else.** The requirements of an issue are the bullets under a `## Requirements` heading, and each of those bullets must match one of the five patterns. Prose elsewhere in the issue, including the summary, a narrative paragraph, and a table's preamble, is not read as a requirement sentence and is not EARS-checked. An issue with no such section is reported as zero requirement sentences examined out of zero, which is an honest vacuous result rather than a pass. Section 3.2 states the one exemption that matters, for acceptance criteria (#2219).

**A requirement sentence carries no ID (#2368).** Section 3.2 gives every table row an ID and opens its criterion with that ID, and ADR 0228 names a criteria group by that same prefix. It is natural to read those two as a general tagging convention and prefix the requirement sentences too, and `R1 — The renderer shall place the needle at the value's angle` then fails the EARS check, because the patterns anchor at the start of the sentence and `R1` is not one of the five openings.

That looks like ADR 0226 and ADR 0228 pulling in opposite directions on tagging. They do not. They govern different objects. **An ID is a join key**, and section 3.2 says so directly: it is what makes the join between grid and test list exact rather than inferred. A criterion carries one because it joins to a table row and to a variable owner. A requirement sentence joins to neither, so an ID on one is a key to nothing — decoration that every checker downstream must then tolerate, and every tolerated prefix is somewhere a malformed sentence can hide.

So the matcher does not strip the prefix, and it is not supposed to. It does name it: a bullet that would match EARS with the prefix removed is reported as wearing a criterion ID rather than as matching no pattern, because those two failures need different repairs. The first is four characters to delete; the second is a sentence to rewrite. Reporting both the same way is what sent boostgauge #1's conversion hunting for a contradiction between two ADRs that agree.

### 3.2 Lightweight Parnas tables

David Parnas and the Naval Research Laboratory rebuilt the requirements document for the A-7E aircraft's flight software in the late 1970s, under the Software Cost Reduction project. Its central technique was the tabular expression. Where a function depends on several conditions, the document states it as a grid, and the grid is the definition rather than a summary of one.

Two properties make a grid checkable:

- **Completeness.** The row conditions must cover every case.
- **Disjointness.** No two rows may apply at once.

Both are decidable by a program. With binary conditions the check reduces to counting, since `n` conditions require `2^n` rows and no combination may repeat.

**What we take:** the grid, the completeness obligation, and the disjointness obligation.

**What we leave:** the formal type system and the mathematical semantics of Parnas tabular expressions. Our rows are plain English with plain yes and no answers. Section 4 explains why.

The worked example is boostgauge #7, converted on 2026-08-11:

| Launched with `--reset-config`? | Did the user move or resize the window? | Config file after quit |
|---|---|---|
| no | no | unchanged, byte-for-byte |
| no | yes | prior contents, with the new position and size |
| yes | no | defaults |
| yes | yes | defaults, with the new position and size |

Every one of the seven historical conflicts was a question about which row a sentence described. None of them can be stated against the table.

Two disciplines keep a table readable. The column headers must be plain questions with plain answers, because a header written as a predicate expression removes the benefit. Each row must also appear as its own acceptance criterion, so the four combinations become four independently testable claims.

**A row criterion takes the row form, and is exempt from EARS.** A row criterion is a table row's projection into the test list, not a requirement sentence, and it is written in the terse form the projection produces: the conditions in column order, then the outcome. "Position, reset, moved: `position` holds the new position" is correct and complete as written. Requiring EARS of it would demand a shall-sentence per row, which restates the grid in prose and reintroduces the ambiguity the grid removed. No acceptance criterion is EARS-checked (#2219).

**Each row carries an ID, and its criterion opens with that ID.** The table gains a leading ID column holding the subject word's first letter, capitalised, plus the row number counting from one: `P1` through `P4` for a position table, `S1` through `S8` for a size table. Where two subjects share an initial, use enough letters to distinguish them. IDs are unique across the issue. The worked example above, under the convention:

| ID | Launched with `--reset-config`? | Did the user move or resize the window? | Config file after quit |
|---|---|---|---|
| C1 | no | no | unchanged, byte-for-byte |
| C2 | no | yes | prior contents, with the new position and size |
| C3 | yes | no | defaults |
| C4 | yes | yes | defaults, with the new position and size |

The criterion for `C3` then reads `- [ ] C3. Reset, not moved: the config file holds defaults`.

The ID is what makes the join between grid and test list exact rather than inferred. With IDs a checker verifies a bijection between the two ID sets and confirms that each criterion carries its own row's outcome, so a criterion labelled `C3` stating row two's outcome fails mechanically. Without them the strongest available check is a count of criteria per table plus a match on outcome text, which cannot tell whether a criterion describes its own row's combination. That residue is left to the semantic consistency gate, where a criterion contradicting its own table surfaces as the conflict class the gate already reports. The human-readable condition phrase after the ID is decoration for the reader; the ID is the join.

The convention binds every issue converted after boostgauge #7, which was converted before it existed (#2219).

### 3.3 The split rule

Two conditions produce four rows and read well. Three produce eight and remain workable. Five produce thirty-two, and a table of thirty-two rows is not read by anyone.

Parnas answered this with hierarchical decomposition into several smaller tables. We answer it with a limit at three conditions, because the count is also a design signal. A requirement whose behavior turns on five independent conditions is doing several jobs, and the table exposes that before any code is drafted.

The split is an authoring act and not a scheduling one. Each resulting requirement carries its own conditions and its own table, and each names the requirement it was split from.

## 4. Alternatives Considered

### Option A: EARS sentences, lightweight tables, and a split rule (SELECTED)

**Description:** As stated in section 2.

**Pros:**
- Completeness becomes countable rather than argued.
- The notation is readable by the operator, by the drafting LLM, and by a checker. No translation step sits between them.
- Contradictions of the enumerated kind cannot be written.
- Each row arrives as an acceptance criterion, which feeds the existing traceability check directly.

**Cons:**
- Authoring cost rises for simple requirements.
- A table can be complete and still wrong. Completeness is not correctness.
- Existing issues are written in prose and need conversion.

### Option B: Formal specification, such as TLA+, Alloy or Z (Rejected, not triggered)

**Description:** State requirements in a formal notation and prove consistency with a model checker.

**Pros:**
- Machine-checked consistency is a stronger guarantee than counting rows.
- Decides contradictions that no table can express.

**Cons:**
- The operator must read these documents and rule on them. A notation he does not read removes his ability to rule, and that is the one step in this process nobody else can perform.
- The drafters and reviewers in this pipeline are LLMs reading English. A formal notation adds a translation step, and translation is where ambiguity returns.
- The defect rate does not justify the weight. One paragraph in one issue produced all seven conflicts.

This option is not rejected permanently. It is not triggered.

### Option C: Keep prose and strengthen the gate (Rejected)

**Description:** Leave issues in prose and improve the consistency gate's detection.

**Pros:**
- No authoring change, and no conversion of existing issues.
- The gate already detects these contradictions honestly.

**Cons:**
- Detection is the expensive half. Each catch costs a halted run, an operator ruling and a redraw. Prevention at authoring costs nothing.
- Pairwise detection over prose reports pairs, which is why one defect produced three issues.
- Five rounds of this already ran on boostgauge #7. The paragraph produced a new contradiction after every repair.

### Option D: The full Software Cost Reduction method with tool support (Rejected, not triggered)

**Description:** Adopt the published method, including the formal tabular semantics and a consistency checker built for them.

**Pros:**
- Proven on avionics software far more complex than anything in this fleet.
- Supplies completeness and disjointness proofs mechanically.

**Cons:**
- The readability we want is available from the plain grid alone.
- The tooling would have to be built or adapted, which is a larger piece of work than the defect it prevents.

## 5. Rationale

The deciding factor is who has to read the document.

Three parties read a requirement in this pipeline. The operator rules on it. The drafting LLM derives an LLD from it. A checker verifies its form. A decision table is the one notation all three handle without translation. Formal specification serves the checker well and excludes the operator. Prose serves the operator and the LLM, and gives the checker nothing to verify.

Parnas made this same argument, and it deserves stating plainly because it inverts the usual expectation. His claim for tabular expressions was not only that they were more precise than prose. It was that they were more precise *and easier to read*, which is why engineers under time pressure would keep them current. Formal notations generally buy rigor at the cost of readability. Tables do not.

The second factor is cost asymmetry. Detection is expensive here and prevention is free. Each contradiction the gate catches costs a halted run, a redraw and a ruling from the operator. Writing the requirement as a table costs a few minutes once.

We accept that a complete table can still be wrong. Completeness is a property of form and not of content, and no check proposed here verifies that a row states the correct behavior. Review does that.

## 6. Security Risk Analysis

| Risk | Impact | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| A table that is complete but wrong reads as authoritative, and its form discourages the challenge that loose prose invites | Med | Med | 4 | Review adjudicates row contents. The completeness checker reports completeness only, and states that limit in its output |
| A passing completeness check is read as a correctness result | Med | Med | 4 | The checker names what it verified and what it did not, following standard 0028's refuse-loudly posture |
| Splitting a requirement scatters a security-relevant constraint so that no single document states it whole | Med | Low | 2 | Each child requirement names the requirement it was split from, so the full set is recoverable |

**Residual Risk:** Content errors inside a well-formed table remain undetected by every mechanical check in this ADR. That risk is unchanged from prose and is not made worse by this decision.

## 7. Consequences

### Positive

- Conditional statements can no longer be written as universals, so the contradiction class that produced all seven conflicts cannot be expressed.
- Completeness is countable, so a gap is reported once rather than as a set of pairs.
- Each row arrives as an independently testable acceptance criterion, which the specification stage can assert against directly.
- The condition count surfaces an oversized requirement before any code is drafted.

### Negative

- Authoring a simple requirement costs more than writing one sentence. The EARS patterns apply everywhere, while a table applies only above one condition, which bounds the cost.
- Existing issues are prose. Converting all of them at once is a large piece of work with no immediate return.
- A table invites the belief that a requirement is settled. Correctness still requires review.

### Neutral

- The requirements-consistency gate is unchanged. It continues to work on prose issues that have not been converted.
- The LLD, specification and implementation stages are unchanged.

## 8. Implementation

- **Related Issues:** #2218 (this ADR)
- **Status:** In Progress

Conversion happens when an issue next rolls, and not as a sweep. An issue that is not rolling costs nothing by staying in prose, and a sweep would convert issues whose requirements may change before anything reads them.

The mechanical checker is built (#2219): `tools/check_requirements_form.py --repo <path> --issue N`, or `--file <draft>` while authoring. It is fully deterministic and makes no model calls, so it is free and instant and runs before anything else. It verifies three things. Each bullet under `## Requirements` must match an EARS pattern. A table of `n` binary conditions must carry `2^n` rows, with no combination repeated. Each row must appear as an acceptance criterion. The checker reports what it verified and what it did not, per standard 0028, and names its row-join mode per table so the count-and-outcome mode can never be mistaken for the exact one.

The full pre-roll sequence is this form check, then the semantic requirements-consistency gate via `tools/check_requirements.py` (#2221, one model call), then the roll.

### The form check at launcher preflight (operator ruling, 2026-08-12, #2227)

#2219 built the checker and left one question open: whether it should also run inside the launcher's preflight, where a refusal costs nothing because no branch exists and no token has been spent. The ruling:

**The form check runs at launcher preflight, report-only by default.** It joins the existing refusals — an untrustworthy tree, a sick machine, the previous run's unresolved questions, open must-resolve issues — and runs before the detach hand-off, so a batch is judged as a whole before anything is spent.

**It refuses only when the issue carries at least one decision table and that table is malformed.** An unconverted prose issue never refuses; a refusal there is a false alarm by definition. This matters because conversion happens when an issue next rolls rather than as a sweep, so nearly every issue in the fleet is still prose. A gate that fired on the ordinary case would be waved through, which is the same reasoning that scoped the ADR-0217 equivalence gate to the paths a branch actually changed.

Malformation is read as the table's own shape — the second of the three rules, completeness and disjointness — because that is what a table can be malformed about and because a refusal must be an unambiguous fact. The third rule, row-to-criterion coverage, is treated on the checker's own account of its two join modes: with row IDs the join is exact and a missing criterion refuses; without them it rests on count and outcome text, which this ADR already delegates to the semantic gate, so it reports and does not refuse. EARS findings never refuse, since prose sentences are exactly where unconverted issues live. The two knobs are `REFUSING_KINDS` and `EXACT_JOIN_REFUSES` in `assemblyzero/workflows/requirements/form_gate.py`; widening the refusal is a one-line change.

**The vacuous-EARS state is surfaced out loud.** An issue with no `## Requirements` section passes every EARS check while verifying nothing about its sentences. The preflight says so explicitly rather than letting a silent pass read as a clean bill — the failure mode the checker's report format exists to prevent.

**Form-check findings are labelled as the form check's own**, distinct from the semantic gate's refusal, so one defect never reaches the operator as two complaints in two formats.

boostgauge #7 is the first converted requirement and was rolling as of 2026-08-11. Its result is the first evidence about whether this form prevents what it was adopted to prevent.

## 9. References

Bibliographic details below are recorded from recall. Confirm them against the primary sources before citing them in published work.

- Mavin, A., Wilkinson, P., Harwood, A., and Novak, M. "Easy Approach to Requirements Syntax (EARS)." IEEE International Requirements Engineering Conference, 2009.
- Heninger, K. L. "Specifying Software Requirements for Complex Systems: New Techniques and Their Application." IEEE Transactions on Software Engineering, 1980. This is the A-7E requirements document work.
- Parnas, D. L., and Madey, J. "Functional Documents for Computer Systems." Science of Computer Programming, 1995.
- Standard 0028, ask structured, get structured, or reject.
- boostgauge #7, the first requirement converted to this form.

---

## Revision History

| Date | Author | Change |
|---|---|---|
| 2026-08-11 | Claude Opus 5 | Initial draft |
| 2026-08-12 | Claude Opus 5 | Operator ruling on #2227 recorded in section 8: the form check runs at launcher preflight, report-only, refusing only on a malformed decision table so unconverted prose issues never trip it; the vacuous-EARS state is surfaced explicitly; findings are labelled distinctly from the semantic gate's. |
| 2026-08-14 | Claude Opus 5 | Section 3.1 records the #2368 ruling: a requirement sentence carries no ID. Converting boostgauge #1 read the section 3.2 row-ID convention and ADR 0228's group prefix as a general tagging rule, prefixed the requirement sentences, and read the resulting EARS rejections as the two ADRs contradicting each other. Measurement showed they do not: every `_LEADING_ID` site in the ownership checker parses acceptance criteria, never requirement sentences, and ADR 0228 section 89 states the prefix exists to make a join mechanical. An ID is a join key; a requirement sentence joins to nothing. The matcher does not strip the prefix, and now names it rather than reporting a well-formed sentence as matching no pattern. |
| 2026-08-11 | Claude Fable 5 | Building the checker (#2219) surfaced a contradiction between rule 1 and this ADR's own worked example: boostgauge #7's row criteria are mandated by section 3.2 and match no EARS pattern, so an EARS check over acceptance criteria would fail the fixture the ADR cites as its first success. Operator rulings on #2219 scoped EARS to the bullets of a marked `## Requirements` section, exempted row criteria explicitly, and adopted a row ID convention that makes the grid-to-criteria join exact. Sections 3.1, 3.2 and 8 carry those rulings. |
