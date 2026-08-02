# 0025 — Revising drafter prompts from failure telemetry

**Status:** Active
**Issue:** #2075 (companion to #2074, which produces the telemetry)

Everything else in the factory improves from evidence. The drafter prompts and
templates have been static for the life of the campaign, while their failure
modes — malformed section tables, missing sections, missing REQ-N refs,
fenceless imports, invented kwargs — recur at rates nobody measured. Every
recurrence costs a full roll, between 3 and 90 minutes.

This is the loop that closes. It never ends; there is no state in which the
prompts are finished.

## The procedure

### 1. Rank by cost, not by count

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/prompt_revision_rank.py --repo /c/Users/mcwiz/Projects/<target>
```

Cost is `occurrences × mean wasted roll seconds`. Counting alone ranks a cheap
frequent failure above an expensive rare one, which is the wrong order to fix
things in.

**A `duration-unknown` flag is not a zero.** Those fingerprints are ranked by
occurrence count and listed after the costed ones. Treating unknown as zero
would sort the most expensive unmeasured failure to the bottom. If the top of
the list is flagged `duration-unknown`, that is a signal to go get durations —
run the timing dashboard (#2085) — not a signal to skip the entry.

### 2. Take the top fingerprint and write down its before-rate

Record, in the PR body, both numbers:

- **occurrences** — how many times the failure fired
- **blast radius** — how many distinct rolls it appeared in, out of how many total

Two numbers, because they answer different questions. A failure firing 16 times
inside one roll is a retry loop; the same 16 spread across 6 rolls is a
systematic prompt defect. The countermeasure differs.

### 3. Revise with an explicit countermeasure, not an exhortation

The revision must change something the drafter *reads structurally* — a literal
template row that keeps parsing, an in-place marker on the section that goes
missing, a worked example of the construct being fumbled.

**Adding "please remember to…" to a system prompt is not a countermeasure.** If
the revision cannot be pointed at as a concrete artifact the drafter consumes,
it is not one.

Prefer copying a construct that demonstrably survives. When one section of a
template is dropped far less often than its neighbours, whatever that section
does differently is the countermeasure — and it has already been validated by
the failure data itself.

### 4. Compare the rate before and after over N rolls

`N` is a real number chosen before the change, not "until it looks better."
Ten rolls is a reasonable default for a failure with a double-digit
before-count; fewer for a failure that fires on nearly every roll.

Re-run the ranking tool after those rolls and compare the same fingerprint.

### 5. Keep or revert on that evidence

A revision that does not move its fingerprint's rate is reverted, not kept and
rationalized. Prompt text accumulates; every line that does nothing makes the
next revision harder to reason about and eats context budget that the codebase
sections need.

## What a prompt-change PR must contain

**The before-rate goes in the PR body.** This is the requirement that makes the
revision history the experiment log — without it, a later reader cannot tell
whether a prompt line was evidence-driven or somebody's hunch.

A conforming PR body carries:

1. The fingerprint being targeted, verbatim.
2. Its before-rate: occurrences and blast radius, with the source of those
   numbers (telemetry, or run logs and lineage during cold start).
3. The countermeasure, named as a concrete artifact change.
4. The value of N and when the after-measurement will be taken.

## Cold start

`#2074`'s telemetry only populates from rolls run after it landed on
2026-08-02. Before those rolls exist the JSONL is empty and the ranking tool
correctly reports nothing.

**Do not fabricate telemetry records to feed the ranker**, and do not wait for
data before revising anything. While telemetry is empty or sparse, take the
before-rate by hand from the run logs and lineage directories:

```bash
cd /c/Users/mcwiz/Projects/<target>/data/speedrun/runs

# occurrences of each distinct mechanical failure, numbers normalized
grep -h -A8 'MECHANICAL VALIDATION FAILED' *.log \
  | grep -E '^\s+[0-9]+\. ' | sed -E 's/^\s+[0-9]+\. //; s/[0-9]+/N/g' \
  | sort | uniq -c | sort -rn

# blast radius: how many distinct rolls a given failure appeared in
grep -l '<the failure text>' *.log | wc -l
```

Hand-derived numbers are quoted the same way in the PR body, with their source
named as run logs rather than telemetry. They are evidence; they are simply
evidence gathered by grep instead of by instrumentation.

## Reference

- #2074 — the telemetry and its fingerprint format, which this consumes.
- #2085 — the timing dashboard producing `runs.csv`, the duration source.
- `tools/prompt_revision_rank.py` — the ranking tool.
