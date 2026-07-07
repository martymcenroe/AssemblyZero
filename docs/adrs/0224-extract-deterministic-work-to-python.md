# ADR 0224: A skill is guidance; extract the deterministic work to Python

**Status:** Accepted
**Date:** 2026-07-07
**Categories:** Process, Skills, Determinism, Reliability
**Related:** #1695 (this ADR); unleashed#575 (`/onboard` → `pickup_decide.py`, the reference implementation); #1192; unleashed#724 (`tracked_pr_land.py`); unleashed#725 (`blog_draft.py`); LLD-444 (the `/test-gaps` skill-vs-Python decision — the counter-example)

---

## 1. Context

A skill (a `.claude/skills/*.md` prompt) is re-interpreted by the model **every
time it runs**. That is the right substrate for work that is genuinely about
*instructing the model how to think* — semantic judgment, natural-language
understanding, open-ended analysis. It is the wrong substrate for work whose
output is a **pure function of its inputs**: classification, parsing, a
side-effectful sequence that must be byte-identical on every run.

When deterministic logic lives in markdown, three things go wrong:

1. **Drift.** Each session re-derives the logic from prose. Two runs of the same
   "algorithm" diverge because the prose underdetermines it.
2. **Silent defect re-introduction.** A bug fixed in one skill's copy stays
   present in every other copy of the same pattern. The banned `git branch -D`
   incidents (#1381 / #1559 / #1647 / #1655) and the unbounded
   `until [ …="clean" ]` merge poll each recurred precisely because the
   deterministic "land a PR" sequence was hand-rolled markdown in five skills
   instead of one tested function.
3. **Untestability.** You cannot write a regression test against a paragraph.
   The only "test" is running the skill and reading the output — which is
   exactly the LLM-judgment loop the deterministic core should not need.

The principle *"a skill is just guidance; the deterministic work belongs in a
Python program"* is **real and proven** — `/onboard` has been a thin shim over
`pickup_decide.py` since unleashed#575, and that removed a whole class of
"the agent second-guessed the pickup verdict" failures. But the principle was
**uncodified**: it lived implicitly in that one skill and in LLD-444's
architecture-decision table, with no ADR to point new skills at. This ADR
codifies it as doctrine.

## 2. Decision

**When a skill contains work whose output is a deterministic function of its
inputs, extract that work into a tested Python program under `tools/` (or the
owning repo's `src/`). The skill shrinks to a thin shim: it invokes the program,
then dispatches on / renders the program's result. It does NOT re-implement,
second-guess, or re-derive the extracted logic.**

The unit of extraction is the **deterministic core**, not the whole skill. A
skill may keep an LLM shell (judgment, phrasing, "surface this to the user and
wait") around a Python core (the classification, the parse, the side-effect
sequence). Extract the core; keep the shell.

## 3. The Skill-vs-Python decision matrix

Decide **per unit of work inside a skill**, not per skill:

| The work… | Substrate | Why |
|---|---|---|
| Output is a pure function of inputs (parse, classify, compute a verdict) | **Python** | Deterministic, testable, identical every run |
| A side-effecting sequence that must be identical every run (git/gh cycles, file mutations, API writes) | **Python** | One tested path; no per-render drift; bans (e.g. `-D`) become unrepresentable in code |
| Enforces a safety invariant (a gate, a guard, a bounded loop) | **Python** | An invariant enforced by prose is enforced by nothing; code makes the unsafe state unreachable |
| Reused across ≥2 skills | **Python** | One fix fixes all callers; markdown copies drift independently |
| Requires semantic judgment / natural-language understanding | **Skill** | This is what the model is *for*; code cannot do it |
| One-off explanation, phrasing, or open-ended analysis | **Skill** | No stable function to extract; zero-deployment prose is correct |
| "Surface evidence and wait for the human" | **Skill (shell) over Python (core)** | The *decision* is deterministic; the *conversation* is the model's |

Rules of thumb:

- **If you can write a pytest for it, it belongs in Python.** If the only test
  is "run the skill and read the output," it is genuine LLM work.
- **A safety rule stated only in prose is not enforced.** Move it into code where
  the unsafe path cannot be expressed (see `tracked_pr_land._assert_no_force`,
  which makes `git branch -D` raise before it can run).
- **Do not split judgment.** Once the Python core returns a verdict, the skill
  dispatches on the verdict name — it must not re-open the decision with its own
  reasoning (the exact regression unleashed#575 removed; re-affirmed in #1586).

## 4. Reference implementation — `/onboard` over `pickup_decide.py`

`pickup_decide.py` walks the handoff log and session transcripts, classifies
each session, and emits a JSON verdict (`auto_pickup`, `surface_to_user`, …).
The `/onboard` skill's own words:

> **This skill is a thin shim.** All classification and decision logic lives in
> `pickup_decide.py` per #575. Do not interpret session categories yourself, do
> not second-guess the script's verdict, do not add LLM-judgment branches.

That is the target shape for every extraction: the deterministic core (classify,
decide) is Python with its own test suite; the skill invokes it and dispatches.
The skill retains exactly one genuinely-LLM responsibility — the
`surface_to_user` conversation — and even there it only *adds evidence*; it never
overturns the verdict.

## 5. Fresh exemplars (2026-07-07)

Two more cores were extracted the same day this ADR was written, both with tests
and both leaving their skills as thin wrappers to be wired up (skill-file edits
are classifier-gated, tracked as unleashed#727 / unleashed#729):

- **`tracked_pr_land.py`** (unleashed#724) — the issue→branch→PR→poll→merge→
  ADR-0217-graft cycle that `handoff` / `cleanup` / `quote` / `rista` each
  hand-rolled. Five safety invariants that prose could not enforce are now code:
  a bounded poll, a merge→cleanup verify-gate, a hardcoded graft where
  `git branch -D` is unrepresentable, squash-SHA-by-PR-number, and a fail-safe
  protection probe. 59 tests.
- **`blog_draft.py`** (unleashed#725) — the `/blog-draft` scaffolding (project
  anchor, slug, model-from-config, collision guard). 36 tests. The skill did
  zero LLM drafting; it was 100% deterministic and belonged in Python outright.

## 6. Extraction backlog

| Skill / pattern | Deterministic core | Status |
|---|---|---|
| `/onboard` | pickup classification + verdict | **Extracted** — `pickup_decide.py` (unleashed#575); reference impl |
| PR-landing (handoff/cleanup/quote/rista) | issue→PR→merge→graft cycle | **Extracted** — `tracked_pr_land.py` (unleashed#724); skills to adopt (unleashed#727) |
| `/blog-draft` | project/slug/date/frontmatter scaffold | **Extracted** — `blog_draft.py` (unleashed#725); skill to wrap (unleashed#729) |
| `/cleanup` Phase 2 | hygiene scan (branches / stashes / worktrees) | **Pending** — deterministic; extract next |
| `/cleanup` Phase 4 | tracked-write PR landing | **Pending** — should call `tracked_pr_land.py` |

New skills are expected to apply the matrix at authoring time: if a step is
deterministic, write the Python first and make the skill call it.

## 7. The boundary — when a skill stays a skill (LLD-444)

This doctrine is **not** "always rewrite skills as Python." LLD-444 evaluated
exactly this choice for `/test-gaps` and deliberately **kept it a skill**: its
work is *instructing the model how to analyze* a codebase for test gaps — Grep/
Read/Glob orchestration driven by semantic judgment about what a "gap" is. There
is no stable function to extract; a Python port would only re-implement the
model's own tools while losing the judgment. LLD-444 is the load-bearing
counter-example that keeps the matrix honest: **extract the deterministic core,
and leave the judgment where judgment belongs.**

## 8. Consequences

### Positive
- Deterministic behaviour becomes testable and identical across runs and repos.
- Safety invariants move from prose (unenforced) to code (unrepresentable-if-violated).
- One fix fixes all callers; copy-paste drift across skills ends.
- Skills get shorter and clearer — they read as "call X, dispatch on the result."

### Negative
- A Python core has deployment friction a skill does not: it must be invoked with
  `poetry run`, kept importable, and tested. (Mitigated: the cores live in the
  repo already used by the skills.)
- Over-application risks porting genuine judgment into brittle heuristics — §7 is
  the guard against that.

### Neutral
- The skill still exists; it becomes a shim. The division of labour (LLM shell,
  deterministic core) mirrors ADR-0219's CLAUDE.md responsibility split.

## 9. References

- unleashed#575 — `pickup_decide.py` / `/onboard` thin-shim (reference impl)
- unleashed#724 — `tracked_pr_land.py` (shared PR-cycle core)
- unleashed#725 — `blog_draft.py` (scaffolder core)
- unleashed#727 / unleashed#729 — wire the skills to the new cores (gated skill edits)
- LLD-444 §2.7 — the `/test-gaps` skill-vs-Python decision (the counter-example)
- ADR-0217 — the squash-merge graft recipe that `tracked_pr_land.py` hardcodes
- ADR-0219 — CLAUDE.md division of responsibility (adjacent LLM-vs-mechanism split)
- #1381 / #1559 / #1647 / #1655 — the `git branch -D` incidents that hand-rolled markdown produced

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-07-07 | Claude Opus 4.8 | Initial draft codifying the extract-to-Python principle (#1695) |
