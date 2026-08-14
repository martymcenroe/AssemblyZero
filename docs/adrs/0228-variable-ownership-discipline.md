# ADR 0228: One variable, one owner, and only the owner asserts

**Status:** Accepted
**Date:** 2026-08-14
**Categories:** Process, Data, Reliability
**Related:** #2314 (this ADR); #2315 (the checker that enforces it); ADR 0226 (the sibling, which gives conditions a checkable form); #1899 (the requirements-consistency gate); #2221 (the standalone caller for that gate); #2227 (the ruling that put the form check in launcher preflight); standard 0028 (ask structured, get structured, or reject); boostgauge #7 (the document the corpus comes from); boostgauge #235, #240, #249, #252, #273, #274, #275, #277, #278, #279, #280, #281, #282, #283, #290, #291, #292 and #294 (the eighteen conflicts)

---

## 1. Context

ADR 0226 gave requirements a checkable form for their *conditions*. A requirement states when it applies, in an EARS sentence or in a decision table that enumerates every combination. A program verifies that the enumeration is complete.

That ADR did not settle what a requirement may say about an *outcome*. Conditions became countable. Outcomes stayed in prose, and prose lets any sentence make a claim about any piece of state.

boostgauge issue #7 is the first requirement converted to the ADR 0226 form. It kept producing contradictions after the conversion, in a class the conversion does not address.

### The measured record

The requirements-consistency gate filed eighteen conflicts against boostgauge #7 between 2026-08-09 and 2026-08-13. They arrived in twelve separate halts. Each halt cost a run, an operator ruling and a redraw.

| Filed | Conflicts |
|---|---|
| 2026-08-09 | #235 |
| 2026-08-10 | #240, #249, #252 |
| 2026-08-11 | #273, #274, #275, #277, #278, #279, #280, #281, #282, #283 |
| 2026-08-13 | #290, #291, #292, #294 |

Every one of the eighteen is the same defect. A criterion asserted the fate of a state variable it did not own.

Six recurring moves account for all eighteen.

| Move | Instances | Count |
|---|---|---|
| Two criteria assert the same variable under overlapping conditions | #235, #249, #290 | 3 |
| A blanket claim, while another rule owns an exception to it | #240, #252, #273, #274, #275, #277, #282, #283 | 8 |
| Annexation: a criterion in one domain asserts an outcome another domain owns | #279, #294 | 2 |
| An extension or a boundary term is undefined, so ownership cannot be assigned | #291, #292 | 2 |
| One claim bundles two variables that follow different rules | #278 | 1 |
| A post-condition on a variable that has an external writer | #280, #281 | 2 |

Three of them read more clearly as text than as categories.

#277 says: "Exactly three things write to or read from the config file, in this order. Nothing else touches it." A separate requirement gives thresholds a live re-read during the session. The blanket sentence owns the whole file and forbids the exception the other requirement mandates.

#294 says a non-threshold key edited on disk during a session "takes effect at the next launch." That is a reload criterion promising a persistence outcome. The exit-write criteria own what the file holds after quit, and they say the hand-made value wins.

#292 turns on the word "threshold," which the issue never defines. The config carries a `thresholds` object and a separate `telltale_windows` object that governs which samples a threshold is evaluated against. Nobody can say which criterion owns `telltale_windows.short`, so both claim it and they disagree.

### Why detection is the wrong place for this

The semantic gate finds these one at a time. It samples an issue with a single model call per run, so its coverage of a long document is partial by construction. #294 was filed on 2026-08-13 against a paragraph that had already passed the pre-roll check twice.

A sampling detector that keeps finding new instances of one class is reporting that the class is writable. Twelve halts over five days is the cost of leaving it writable.

The condition half of this problem was solved by making the bad form unwritable. Section 3.2 of ADR 0226 does not detect an incomplete enumeration; it makes an incomplete enumeration countable, and therefore refusable at authoring time. The outcome half needs the same treatment.

## 2. Decision

**We will assign every state variable a single owner, and permit only that owner to assert the variable's fate.** Five clauses bind every issue the orchestrator rolls.

1. The issue carries a variable table. Each state variable is named, its extension is defined mechanically, and exactly one criteria group owns claims about it.
2. Only the owner asserts. A non-owner criterion may reference a variable's fate by citing its owner, and may not state a value.
3. No blanket without its scope inline. Every universal quantifier carries its held-fixed conditions, or cites the exception list that limits it.
4. Boundary terms resolve mechanically. Any term that partitions variables has a membership test.
5. One variable per claim. This is the variable-side sibling of the ADR 0226 condition-split rule.

## 3. The five clauses in detail

### 3.1 The variable table

The table names the state the requirement governs, before any criterion asserts anything about it.

| Variable | Extension | Owner |
|---|---|---|
| `position` | the `position` object's `x` and `y` keys | the exit-write criteria |
| `thresholds` | every key under the `thresholds` object | the hot-reload criteria |
| `telltale_windows` | the `short`, `medium` and `long` keys under `telltale_windows` | the hot-reload criteria |
| `theme` | the `theme` key | the exit-write criteria |

Three columns, and each does a separate job.

**The name** is the literal key, in code ticks. Ownership is assigned over keys and not over concepts, because a key is a thing a reader and a checker can both point at.

**The extension** states which keys the name covers. A name without an extension is where #291 lived. Its sentence promised that the app "re-reads it during the session," and the reader cannot tell whether "it" is the whole file or the thresholds section. The two readings own different key sets and produce different programs.

**The owner** is one criteria group. Not one criterion, because a decision table projects into several. Not two groups, because two owners is the defect this ADR exists to remove.

The extension column is what makes clause 4 checkable. A term such as "threshold" partitions the config, so it owes the table a membership test. Once `telltale_windows` has a row, #292 cannot be written.

### 3.2 Only the owner asserts

A non-owner criterion that needs to mention a variable cites the owner instead of stating a value.

Wrong: "A non-threshold key edited directly in the config file takes effect at the next launch."

Right: "A non-threshold key edited directly in the config file leaves the running session unchanged. What the file holds at the next launch is governed by the exit-write criteria."

The two sentences differ in one respect. The first states a value, and it happens to be a value the exit-write criteria contradict. The second states the outcome its own domain owns, then hands the reader to the criteria that own the rest.

This clause is what makes the citation form worth writing. A reader who follows the pointer reaches one answer. A reader of two value-stating criteria reaches two.

### 3.3 No blanket without its scope inline

"Never," "always," "only," "nothing else" and "byte-identical" are the words this clause governs. Eight of the eighteen conflicts are one of them.

A universal is a claim over every case, so it collides with any rule that carves out a case. The repair is not to delete the universal. A universal is often the clearest statement available, and #277's "exactly three things write to the config file" is genuinely useful to an implementer. The repair is to write the scope in the same sentence.

"Exactly three things write to the config file: launch read, exit write, and the live threshold re-read. Nothing else touches it."

The exception is now inside the blanket rather than in a different section, so the sentence is true as written and the collision cannot occur.

### 3.4 Boundary terms resolve mechanically

A term that sorts variables into groups needs a membership test, and the variable table is where the test lives.

"Threshold" sorted keys into two groups for three separate criteria and had no definition. Under one reading `telltale_windows.short` is a threshold and hot-reloads. Under the other it is not and waits for the next launch. Both readings pass every check that existed, because the ambiguity is in a word rather than in a structure.

The test does not have to be elaborate. "The keys under the `thresholds` object" is enough. It is checkable, it is short, and it settles the case that produced #292.

### 3.5 One variable per claim

ADR 0226 splits a requirement whose behavior turns on more than three conditions. This clause splits a claim that asserts more than one variable.

#278 bundled a value's origin with its persistence. A value that arrived from a command-line flag and was never touched by hand is a claim about two variables at once: which value is live during the session, and what the file holds after quit. Those two follow different rules, and one sentence cannot carry both without picking a rule for the pair.

The split is the same authoring act as the ADR 0226 split. Each resulting claim names one variable and states its own outcome.

## 4. The kill test

The discipline is worth adopting only if it removes the corpus. Each of the eighteen conflicts was checked against the five clauses.

| Conflict | Killed by | How |
|---|---|---|
| #235, #249, #290 | 1 and 2 | Two criteria assert one variable; the table permits one owner |
| #240, #252, #273, #274, #275, #277, #282, #283 | 3 | A universal with no scope inline |
| #279, #294 | 2 | A criterion states a value another domain owns |
| #291 | 1 and 2 | The re-read's extension is undefined, and a Reads-section sentence states a value the hot-reload criteria own |
| #292 | 4 | "Threshold" has no membership test |
| #278 | 5 | One claim, two variables |
| #280, #281 | 1 and 2 | A post-condition on a variable with a writer outside the asserting group |

Eighteen of eighteen fall to at least one clause. None escapes.

This is a test of the discipline's coverage and not of its correctness. A document can satisfy all five clauses and still state the wrong outcome in every criterion. An ADR 0226 table can likewise enumerate every combination and be wrong in every row. Review adjudicates content. The clauses remove one class of form defect, and the class they remove is the one that produced twelve halts in five days.

## 5. Alternatives Considered

### Option A: The ownership discipline, enforced by a form checker (SELECTED)

**Description:** As stated in section 2, with deterministic enforcement in the existing form-check module.

**Pros:**
- The defect class becomes unwritable rather than findable, which is what ADR 0226 did for conditions.
- Enforcement is deterministic. Variables are literal key names, so extraction is lexical and costs no model call.
- The variable table is readable by the operator, the drafting LLM and the checker, with no translation step between them.
- The corpus is removed entirely, on the evidence of section 4.

**Cons:**
- Authoring cost rises. Every rolled issue now owes a variable table.
- Ownership is a property of form. A table can assign one owner per variable and the owner can still be wrong.
- Existing issues carry no variable table, so each needs one at conversion time.

### Option B: Strengthen the semantic gate (Rejected)

**Description:** Leave requirements as they are and improve the gate's detection of ownership conflicts.

**Pros:**
- No authoring change and no conversion work.
- The gate already reports these conflicts accurately, with a divergence scenario the operator can rule on.

**Cons:**
- The gate is a sampling detector with one model call per run. Its coverage of a long issue is partial, and #294 shows what partial coverage looks like: a conflict surfacing after the paragraph had passed twice.
- Detection is the expensive half. Twelve halts, twelve rulings and twelve redraws bought what a table would have prevented at authoring time.
- This is the argument ADR 0226 already had, and lost, as its Option C.

### Option C: A formal state model, such as TLA+ or Alloy (Rejected, not triggered)

**Description:** Model the config state machine formally and prove that no two transitions conflict.

**Pros:**
- Machine-checked ownership is stronger than a table anyone can fill in wrongly.
- Decides conflicts that no table can express.

**Cons:**
- The operator rules on these documents. A notation he does not read removes the one step nobody else can perform. ADR 0226 rejected formal specification on this ground and the ground has not moved.
- The drafters here are LLMs reading English, so a formal notation adds a translation step, and translation is where ambiguity returns.
- The defect rate does not justify the weight. One document produced all eighteen conflicts.

### Option D: Amend ADR 0226 rather than write a sibling (Rejected)

**Description:** Fold the five clauses into ADR 0226 as a fourth rule.

**Pros:**
- One document for the whole requirement form.
- No cross-reference for a reader to follow.

**Cons:**
- The operator ruled for a sibling on 2026-08-13, and the ruling has a reason behind it. Conditions and outcomes are separate obligations with separate evidence bases and separate checkers. An issue can satisfy one and violate the other.
- ADR 0226 is Accepted and its evidence base is the seven conflicts of 2026-08-11. Rewriting an accepted ADR around a later corpus obscures which decision was made when.

## 6. Rationale

The deciding argument is the one ADR 0226 made, applied to the half it did not cover.

Three parties read a requirement here. The operator rules on it. The drafting LLM derives an LLD from it. A checker verifies its form. A table of names, extensions and owners is a notation all three handle without translation. That property is what made the decision table the right answer for conditions.

The second argument is that ownership is what the eighteen conflicts were always about. Read the gate's own divergence scenarios and every one reduces to the same question: which criterion decides this key. The gate never phrases it that way, because it compares sentence pairs and reports pairs. Naming the underlying question turns eighteen findings into one rule.

The third argument is cost asymmetry, and the numbers here are measured rather than argued. Detection cost twelve halts across five days. Prevention costs a three-column table written once per issue.

We accept that a well-formed ownership table can assign the wrong owner. Correctness is not a property any check in this ADR verifies. Review does that, and the semantic gate remains the backstop for what the clauses cannot express.

## 7. Security Risk Analysis

| Risk | Impact | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| A variable table assigns one owner per variable, is well formed, and names the wrong owner. Its form discourages the challenge that loose prose invites | Med | Med | 4 | Review adjudicates ownership assignments. The checker reports form only and states that limit in its output |
| An issue with no variable table passes the checker, and the silent pass reads as an ownership result | Med | High | 6 | The checker discloses the vacuous state explicitly per the #2227 ruling: no variable table produces "ownership was not checked," never a bare pass |
| A security-relevant constraint is split across two claims by clause 5, so no single claim states it whole | Med | Low | 2 | Each split claim names the claim it was split from, matching the ADR 0226 split rule |
| The clauses remove the conflicts the semantic gate was catching, and the gate is then assumed unnecessary | Low | Med | 3 | The gate stays. This ADR removes one class from its workload and makes no claim about the rest |

**Residual Risk:** A correctly formed variable table that names the wrong owner passes every mechanical check in this ADR. That risk is unchanged from prose, where nothing named the owner at all.

## 8. Consequences

### Positive

- The defect class that produced eighteen conflicts and twelve halts cannot be written once a variable table exists.
- A conflict is reported once, against a named variable, rather than as a set of sentence pairs.
- The semantic gate's per-run model call stops being spent on a class that structure can prevent, so its sampling covers the classes only sampling can reach.
- The variable table documents the config surface, which the specification stage reads directly.

### Negative

- Every rolled issue owes a variable table. For a requirement governing one key the table is overhead.
- Existing issues carry no table. Conversion happens when an issue next rolls, matching the ADR 0226 conversion rule, so the work arrives spread out rather than as a sweep.
- Ownership assignments invite the belief that a requirement is settled. Correctness still requires review.

### Neutral

- ADR 0226 is unchanged. Its three rules bind conditions, these five bind outcomes, and an issue owes both.
- The requirements-consistency gate is unchanged and continues to work on unconverted prose issues.
- The LLD, specification and implementation stages are unchanged.

## 9. Implementation

- **Related Issues:** #2314 (this ADR), #2315 (the checker)
- **Status:** In Progress

**Enforcement is a form-checker extension, tracked as #2315.** It adds five deterministic checks to `assemblyzero/workflows/requirements/form_check.py`, the module `tools/check_requirements_form.py` and the launcher preflight both read. Variables are literal key names, so per-criterion extraction is lexical and needs no model call. Every violation is reported in one pass, so one revision addresses the set.

**The vacuous state is disclosed, per the #2227 ruling.** An issue with no variable table receives "ownership was not checked: no variable table exists," never a pass that reads as assurance. This matches the treatment of the vacuous EARS state, and it exists for the same reason. A silent pass over an unchecked document is the failure the report format prevents.

**Unconverted prose issues never refuse.** Conversion happens when an issue next rolls rather than as a sweep, so most issues in the fleet carry no variable table. A gate that fired on the ordinary case would be waved through. That reasoning scoped the #2227 decision-table refusal, and the ADR 0217 equivalence gate before it.

boostgauge #7 is the corpus document and is the first real-document validation for the checker.

## 10. References

- ADR 0226, requirements are authored in a checkable form. The sibling that binds conditions.
- Standard 0028, ask structured, get structured, or reject.
- boostgauge #7, the document all eighteen conflicts were filed against.
- boostgauge #235, #240, #249, #252, #273, #274, #275, #277, #278, #279, #280, #281, #282, #283, #290, #291, #292, #294. The corpus, each carrying the gate's verbatim conflict and its divergence scenario.
- Parnas, D. L., and Madey, J. "Functional Documents for Computer Systems." Science of Computer Programming, 1995. The variable table is the mode column of a Parnas table, reduced to the ownership question.

---

## Revision History

| Date | Author | Change |
|---|---|---|
| 2026-08-14 | Claude Opus 5 | Initial draft. The corpus was measured rather than inherited: #2314 filed it as sixteen conflicts, and a count of every `must-resolve: #7 requirements conflict` issue in boostgauge returns eighteen. #277 and #291 appear in no row of the issue's move table. #277 is a blanket claim and joins clause 3's group; #291 is an undefined extension and joins #292 under a merged extension-or-boundary move. Both fall to the kill test, so the coverage claim holds at eighteen of eighteen. |
