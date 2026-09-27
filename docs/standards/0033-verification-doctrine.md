# 0033: What makes a check trustworthy (verification doctrine)

**Status:** Active
**Date:** 2026-09-27
**Issue:** #3658
**Seed:** rule six of the six engineering rules in the universal instruction file (`Projects/CLAUDE.md`), "audits are programs, not inspections"
**Sibling standards:** 0007 (testing strategy), 0015 (spelunking audit protocol), 0024 (mock discipline)

## Why this is not a writing rule

The fleet keeps two kinds of rule about quality. The writing rules say what good prose is. This standard says what a trustworthy check is: how a check is built, how it is calibrated, and how its result is reported to a person.

They are kept apart because they fail differently. A writing rule fails loudly, in the prose, where a reader sees it. A verification rule fails silently: the check returns a clean result that means nothing, and the clean result is believed. Nobody notices a check that examined nothing, because there is nothing to notice. The damage shows up later, in the artifact the check was supposed to guard, and by then the check has been trusted for weeks.

Rule six in the universal instruction file is the seed: audits are programs, not inspections. A check that cannot be re-run is not a check. That one line is the doctrine compressed, and the rest of it is larger than one line and had no home. It was earned over one long document project in 2026, where a suite of audits guarded a document through many rounds of repair, and each rule below was paid for by a check that passed while the defect it was built to catch stayed in the document. The incidents are told without that project's detail.

The rules are numbered 1 to 23 and grouped by the question they answer. Cite one as standard 0033, rule N.

## 1. Non-vacuity

A check is vacuous when it can pass without having examined anything. Each rule here makes that either impossible or visible.

1. **State the denominator.** Zero findings is also what a broken audit returns when it examines nothing. A pass is reported with its denominator, "0 findings across 170 citations", never as a bare pass. A count with no denominator cannot be told from a check that ran on an empty set.
2. **Keep a negative test.** Every check keeps a test that feeds it known-bad input and asserts that the check fires. Without one, a check can stop working and nobody will know, because a check that has stopped working reports the same thing as a clean artifact.
3. **After changing a tool, ask what depended on the old behaviour.** A round-trip verifier that compares a file to itself passes forever while testing nothing. Any check that consumes a mutation needs a guard that fails when the mutation is absent; otherwise the check keeps passing after the step it verifies has been removed.
4. **Never print a finding the run did not compute.** A hardcoded conclusion is indistinguishable from a real one at a glance and is believed on the same evidence. Every line of a report is derived from the run that produced it.

## 2. Order of repair

5. **Repair the checker before the artifact.** Fixing the document first, while the audits that missed the defects still miss them, makes more mess: the repair is unverified, the next round reintroduces what was fixed, and the checker's blind spot is still there for the following defect.
6. **Calibrate the repaired checker against the known-bad version.** Keep the known-bad copy and run the repaired check against it until it reports exactly the known defects and no false alarms. Calibrating on known-bad input also proves the check fires rather than passing because it examined nothing (rule 2).

## 3. Scope is policy, not implementation detail

7. **Declare scope once, in a shared module.** Three scope bugs landed in one day from one root cause: region detection implemented four ways across four audits, each drawing the boundary a little differently. Scope belongs in a declared matrix with a shared module that every audit imports, never re-derived per audit.
8. **Translate every count.** When reporting a count, say what it means and whether it is noise. A count of 412 says nothing on its own; 412 matches, all inside a section the style manual exempts, is a finding of zero.

## 4. Choosing the instrument

9. **Regex is the wrong instrument for a question of grammar.** A dependency parse is the baseline for grammatical analysis. A pattern over characters cannot see the sentence.
10. **Parse and walk the tree for structure; patterns are for text.** Regex over raw OOXML for structural removal gutted 70 percent of a document: `.*?` with DOTALL matched across paragraph boundaries and removed everything between the first opening tag and a closing tag far away. A structural edit goes through a parser that knows where an element ends.
11. **A similarity guard that authorizes a destructive edit must use a real comparison.** `quick_ratio()` ignores word order and let an unrelated paragraph overwrite another on the same subject. A guard that gates destruction is held to the same standard as the destruction.
12. **Compare at sentence level and require a counterpart.** Min-normalized token overlap makes a long paragraph match any short one, because the short one's few tokens are all found in the long one. Compare sentence by sentence, and require that each sentence has a counterpart before calling two passages the same.

## 5. Reading a disagreement

13. **When a visual report and a structural probe disagree, suspect the probe first.** The probe has matched the wrong element far more often than the render has lied. Check what the probe selected before doubting what the eye saw.
14. **A probe artifact is not a document defect.** Check the stored bytes before raising an alarm. What the probe printed may be an artifact of how it read the file, not a fact about the file.
15. **Absence of evidence in one artifact is not evidence of absence.** A published style manual governs by name even when the template you read says nothing about it. Not finding a rule in the file in front of you does not mean there is no rule.
16. **Before treating an observed regularity as a limit, name what enforces it.** A pattern with no enforcer is a description, not a rule. If nothing would fail when the pattern is broken, the pattern is a habit, and a check built on it reports habit as law.

## 6. Comparison hygiene

17. **Normalize line endings before comparing.** Comparing git content to a working-tree file on Windows reports every line as changed unless line endings are normalized first. A comparison that authorizes a destructive operation and returns confident wrong answers is worse than none.
18. **A one-sided block in a diff is a defect until proven positional.** Content that appears on only one side has been lost or invented until someone shows that it merely moved.
19. **Generate derived reports; never hand-maintain them.** Derived reports drift silently when hand-maintained. Generate them from the source-of-truth artifact and regenerate after every build, so a report can never describe a version that no longer exists.
20. **Do not re-audit from scratch.** Diff against the existing verification record first. The record says what was checked and what was found; a fresh audit that ignores it repeats the work and loses the exceptions already decided.

## 7. Reporting to a human

21. **Triage every finding, and state purpose first.** Sort each finding into mechanical-just-fix and genuine-decision, and open the report with what it is for, so the reader knows which findings need a decision and which do not.
22. **Never surface a finding that has not been verified.** Fix the noisy check rather than forwarding its output. A check that cries wolf trains the reader to ignore it, and the next real finding goes unread.
23. **Honour existing exception lists.** An exception already decided is not re-litigated by the next audit. A check that re-raises an accepted exception is noise (rule 22).

## Where this binds

This standard governs any program that is run to say whether an artifact is acceptable: a lint, an audit, a probe, a similarity guard, a diff that gates an edit, and any report that carries one of these to a person. It binds the agent who builds the check, the agent who runs it, and the report that delivers the result. The six engineering rules in the universal instruction file are the short form; this is the long one.
