# Plan 0002 — AssemblyZero Wiki Audit + Concept Field Guide

**Status:** Phase 1 in flight (5 calibration entries shipped 2026-06-04)
**Date:** 2026-06-04 Central
**Last updated:** 2026-06-04 Central (operator answers folded in)
**Author:** Claude / AssemblyZero session
**Scope:** `AssemblyZero.wiki` only (53 pages). The other fleet wikis (Aletheia.wiki, Hermes.wiki, etc.) are explicitly out of scope.

---

## 1. Why this document exists

Two things in one session:

1. **An audit plan** for the AssemblyZero wiki against the AssemblyZero code. Suspected problems: drift (wiki describes how things used to work), wrong information (wiki claims that aren't true now), missing information (code surfaces with no wiki coverage), reorganization opportunities, and gaps where diagrams would help where prose currently strains.
2. **A concept field guide** that gives a reader landing on the wiki a concept-keyed lookup — concept name → concise definition → short read → deeper read → pointer to the wiki page or code that proves the concept is real. The wiki is currently organized by topic and reader role; the field guide complements that with a single page organized by *concept*, useful for readers who arrive via search or who want a clean definition before going deep.

This document is the plan for both. Part A (audit) is methodology only; Part B (field guide) is in active drafting — the first five entries are live.

## 2. Existing context this plan must respect

- The wiki already has a per-page audit pattern in flight. Recent examples: #1279 (`Closing-the-Agent-Self-Authorization-Loop` audit fixes), #1280 (`Dependabot-Pipeline` audit fixes), #1261 (Cerberus ↔ Dependabot reconciliation), #1242 (profanity sanitization sweep across artifacts including wikis). This plan **slots into** that pattern as a systematizing layer, not a replacement.
- The wiki's `_Sidebar.md` already groups pages into nine audience-oriented sections (Start Here, Leaders, Architecture, Core Workflows, Security & Governance, Cost & Platform, Reliability, Intelligence Layer, Reflections, Chronicles). The audit should respect that structure; reorganization proposals must be load-bearing, not aesthetic.
- The wiki has dual register — technical pages alongside Discworld-themed chronicle pages (`DEATH`, `Binky`, `History-Monks`, `The-Great-God-Om`, `The-Turtle-Moves`, `Hogswatch`, `L-Space`, `Ponder-Stibbons`). These chronicle pages are deliberate; they are NOT drift to be cleaned up. The audit must distinguish "this is a metaphor page" from "this is a technical page that's wrong."
- The audit framework lives under `docs/audits/` (e.g., `0900-banned-commands-fleet-audit-2026-05-29.md`). New audits should follow that numbering and format.
- Wiki commits are made directly to `AssemblyZero.wiki.git` (a sibling repo). No PR workflow; no Cerberus on the wiki. **Wiki edits land instantly on push.** This is the central operational difference vs code edits — audit findings translate to commits, not PRs, so triage discipline matters more.

## 3. Part A — The Audit

### 3.1 Six dimensions of audit

Each dimension is independent; an audit pass against the whole wiki along ONE dimension is the unit of work. Doing all six dimensions × 53 pages in one sweep is too much for one session — pick a dimension or a cluster of pages.

| # | Dimension | What it asks |
|---|---|---|
| 1 | **Currency** | Does the wiki match the current code state? (Files exist; commands work; APIs are real; numbers are still true.) |
| 2 | **Completeness** | Is anything in the code that should be in the wiki, missing from the wiki? (New tools, new patterns, new ADRs not surfaced.) |
| 3 | **Correctness** | Where the wiki does document, is it factually right? (Distinct from currency — currency is "X used to be true," correctness is "X was never true.") |
| 4 | **Organization** | Is information findable? Are concepts grouped sensibly? Do cross-links resolve? Does the sidebar match the actual page set? |
| 5 | **Pedagogy** | Does the page teach a cold-start reader? Or does it assume context that only the author has? Is the concept order right (foundations → applications)? |
| 6 | **Visual aids** | Where would a diagram (Mermaid, ASCII, table) carry meaning that the current prose strains to deliver? |

### 3.2 Methodology per dimension

**Dimension 1 — Currency** (highest-value, most-automatable)

For each wiki page:
- Extract every file path mentioned (`tools/X.py`, `docs/Y.md`, `.github/workflows/Z.yml`). Verify each exists. List the dead refs.
- Extract every PR/issue/commit reference (#N, SHA). Verify each is in the expected state (open/closed/merged).
- Extract every command-line invocation (`poetry run python tools/X.py --flag`). Verify the script accepts those flags today.
- Extract every numeric claim ("206 issues in 21 days", "62 repos", "12 of 17 bypasses"). Verify against `gh search`, `tools/repo_count.py`-equivalent, or memory.
- Extract every named-thing claim ("the foo_bar function", "the FooBar class", "the X.Y attribute"). Grep the code; verify presence.

This dimension is **scriptable**. A `tools/audit_wiki_currency.py` (parallel to the link auditor used for code) is the natural deliverable. Output: a per-page report of dead references.

**Dimension 2 — Completeness**

Top-down: enumerate the major code surfaces and check the wiki has an entry.
- Every `tools/*.py` script with a non-trivial public CLI → at least one wiki page describing what it does
- Every `docs/standards/00*.md` → wiki page or sidebar reference
- Every `docs/adrs/02*.md` → wiki page or sidebar reference
- Every `assemblyzero/workflows/*` subpackage → wiki coverage
- Every long-lived `.github/workflows/*.yml` → wiki coverage

Bottom-up: enumerate the wiki pages and check the code surface they claim to document exists.

The deliverable: a two-column table of (code surface) ↔ (wiki page) with rows for both unmatched halves (code without wiki page, wiki page without code surface).

**Dimension 3 — Correctness**

Reader-journey audit: pretend to be a new contributor who has read no AZ code. Try to use the page to do what the page claims to enable. Note every place the page is wrong (not just outdated — wrong).

Question-driven audit: maintain a list of questions the wiki should answer ("How does Cerberus authenticate?", "Why is `--admin` banned?", "What does pr-sentinel check?"). For each question, attempt to find the answer using only the wiki. Note every miss.

The first method catches procedural wrongness; the second catches conceptual wrongness. Use both.

**Dimension 4 — Organization**

- Verify `_Sidebar.md` matches the actual page set (no orphans, no dead links).
- For each page in the sidebar, verify it lives in the most useful section.
- For each page NOT in the sidebar, decide whether to add or whether the omission is deliberate (e.g., chronicle pages).
- Map inter-page links (Mermaid-render the link graph). Identify orphan pages (zero inbound links) and pages with broken outbound links.
- Look for split-concept gaps (the same concept explained twice in different places, drifting) and merged-concept lumps (multiple concepts crammed into one page).

The deliverable: a reorganization proposal — but only if patterns emerge. Avoid reorganizing for its own sake.

**Dimension 5 — Pedagogy**

- For each page, identify its assumed reader. Match against the sidebar section it lives in. Mismatches go on the list (e.g., a "Quick Start" page that requires familiarity with the orchestrator graph).
- For each page, identify the concept order. Foundations-first or assumed-knowledge-first? Note any page that assumes the reader has read OTHER pages without saying so explicitly.
- Identify pages that lack a "why this exists" opener and jump straight into "here's how it works."

The deliverable: per-page pedagogy notes; some will resolve to "needs intro paragraph," others to "split into beginner page + reference page."

**Dimension 6 — Visual aids**

For each page, identify sections where:
- A sequence of >3 numbered steps interacting with named systems is described in prose → flowchart candidate
- A type hierarchy or contains-relationship is described in prose → class/component diagram candidate
- A state machine is described in prose → state diagram candidate
- A timeline of events is described in prose → sequence diagram candidate
- A comparison of >2 options is described as paragraphs → table candidate

GitHub Wiki supports Mermaid in fenced code blocks (` ```mermaid `). The Aletheia wiki uses this already (per its commit `312a03f fix: convert Architecture diagram from LR to TD with dashed response arrows`). AZ wiki should adopt the same pattern.

The deliverable: a backlog of "page X section Y needs diagram Z." Then ship one diagram per session as a separate concern.

### 3.3 Execution model — multi-agent fan-out

Doing one dimension across 53 pages is ~10 hours of focused reading without help. With parallel subagents:
- One agent per dimension OR one agent per sidebar section (9 sections, ~6 pages each), reading + producing structured findings
- Each agent returns JSON: `[{page, dimension, finding_type, severity, evidence, recommended_fix}, ...]`
- Main loop dedupes, prioritizes, files issues — **one issue per finding, never bundled** (per `Projects/CLAUDE.md` rule)

Verification discipline (per `feedback_triage_subagent_evidence.md` memory): subagents must paste the exact `grep` / `Read` / `gh api` output that supports each finding. Narrative claims of "verified that X" without pasted evidence are downgraded by the main loop before any wiki commit. Triage subagents fabricate confidently; the audit is no different.

### 3.4 Audit deliverables (per pass)

For each audit pass, produce:
- A dated audit doc under `docs/audits/0950-az-wiki-{dimension}-audit-{YYYY-MM-DD}.md` (numbering picks up after the most recent audit; check current head before assigning)
- One GitHub issue per finding on `martymcenroe/AssemblyZero`, labeled `wiki-audit` (label may need creating)
- A summary in the audit doc cross-referencing each filed issue
- A short-form "what this audit caught" entry in the wiki's `Audits-Catalog.md`

Wiki commits then happen one finding at a time, each with a commit message `docs(wiki): {fix} (refs AssemblyZero#{issue})` — matching the existing #1279/#1280 pattern.

## 4. Part B — Concept Field Guide

### 4.1 Why a concept-keyed guide exists alongside the wiki

The wiki is organized by **topic and reader role** (Architecture / Security & Governance / Cost & Platform / etc.). That's the right organization for a reader *learning* the system end-to-end. It is the wrong organization for a reader who has heard one term and wants a clean explanation before deciding whether to read deeper.

The field guide closes that gap. It is a single page organized by **concept** — concept name → one-line definition → short read → deeper read → pointer to the wiki page or code that proves the concept is real. A reader can land on the field guide via search, find the concept, get oriented in 30 seconds, and click through to depth.

### 4.2 Format per entry

Each entry is a short, fixed-shape block (live in `AssemblyZero.wiki/Concept-Field-Guide.md`):

```markdown
## {Concept Name}

**One-line definition:** {15 words or less; the simplest possible answer}

**30-second read:** {2-3 sentences. What it is, why it exists, what it
buys you. No jargon that requires further explanation. The version a
reader who half-understands the term can follow.}

**3-minute deep-dive:**
- {Foundational mechanism it relies on}
- {The actual design choice that distinguishes this from the obvious version}
- {The constraint or failure mode that made the design choice necessary}
- {How it composes with other AssemblyZero concepts}
- {What the empirical evidence is — PRs landed, issues solved, scale numbers}

**Show me:** [`path/to/file.py`](link), [PR #N](link), [[wiki-page]]

**Related concepts:** [[Concept A]] · [[Concept B]] · [[Concept C]]
```

The 30-second read is **the load-bearing field.** Most readers get what they need there; deep-dive and show-me are for those who want to verify or go deeper. Each entry's pointers must be live — broken pointers make the entry *wrong* (not stale), and the guide rests on its pointers being accurate.

### 4.3 Initial concept list (candidates)

Drawn from the wiki sidebar + memory + recent session work. ~30 concepts; the guide grows by addition.

**Orchestration & workflow (foundational)**
- Multi-agent orchestration (LangGraph-based)
- LLD-driven implementation pipeline
- The Pipeline (idea → tested code)
- Requirements workflow vs implementation workflow split
- Worktree isolation (parallel work without conflict)
- Test-Driven Development as the implementation contract

**Governance & safety (the differentiator)**
- Cerberus / pr-sentinel separation (agent identity vs owner identity)
- Banned-list enforcement (no `--force`, `branch -D`, `--admin`, `--no-verify`)
- Classic-PAT in-process decryption pattern (ADR-0216)
- ADR-0217 graft cleanup (no-force squash-merge orphan deletion)
- Secret guard hooks (file-level + bash-level pre-tool guards)
- Two-strike rule (loop detection)
- The "destroying uncommitted state" principle (broader than `--force`)

**Scale & operations**
- 60+ repo fleet governance
- Dependabot pipeline (per-repo + fleet)
- Branch protection at scale
- Auto-reviewer caller workflow (reusable across the fleet)
- Fleet-wide audits (banned commands, security posture)

**Cost & reliability**
- Prompt economics (Haiku routing, context pruning)
- The WinError 206 hack (Windows command-line length wall)
- Permission friction analysis
- Workflow reliability (retry, checkpoint, recovery)
- Cache-warm vs cache-cold cost discipline

**Intelligence & memory**
- Memory system (markdown files, file-based persistence)
- Codebase intelligence (Hex)
- Session handoff + pickup (continuity across sessions)
- Lessons-learned discipline (every cleanup files issues)

**Narrative explainers (not technical concepts; orient the reader)**
- "What is AssemblyZero?" (the load-bearing summary)
- "Why does it exist?" (the constraint that made it necessary)
- "What does success look like?" (the velocity / quality story)

A separate **private companion** (location TBD: `career` repo, or a password-protected dashboard) holds material that is useful to the operator but not appropriate for public reference. The companion is not in scope for this plan; it gets its own plan when the location is decided.

### 4.4 Where the guide lives

Three options were considered:

| Option | Pros | Cons |
|---|---|---|
| **A.** As a wiki page (`AssemblyZero.wiki/Concept-Field-Guide.md`) | Lives with the source material; cross-links work naturally; visible to anyone reading the wiki | Public; operator-only material would need to live elsewhere |
| **B.** As a separate private repo | Private; can hold operator-only notes | Disconnected from the wiki; maintenance has to be ritualized; cross-linking is via URL not wikilink |
| **C.** As a structured YAML the wiki renders from | Single source of truth; could generate both public and private views | Build cost; YAML-to-Markdown rendering is a small project of its own; overkill for ~30 entries |

**Decision (2026-06-04):** Option A is in use — the field guide lives on the public wiki at `AssemblyZero.wiki/Concept-Field-Guide.md`. A separate private companion will hold operator-only material; companion location is TBD (existing `career` repo wiki if one exists, otherwise a new password-protected dashboard). The companion is **out of scope for this plan**; it gets its own plan when the location is decided. The public guide must not reveal anything about the companion's existence or purpose.

### 4.5 Maintenance hooks

The guide will rot without a maintenance ritual. Three hooks:

1. **Audit cycle integration.** Every wiki audit pass (Part A) emits "concepts touched" as a side-finding. The field-guide maintainer pulls those and updates the relevant entries' "show me" pointers.
2. **Operator-driven refresh.** When the operator uses the field guide and finds an entry that wobbles (definition wrong, pitch unclear, pointer broken), capture and revise within 24h while it's fresh.
3. **New-PR hook.** When a substantive PR merges on AssemblyZero, ask "does this PR change what concept X means?" for any concept the PR touches. If yes, update the entry's "show me" pointers and deep-dive bullets.

The first hook costs nothing (subsumed by audit work). The second is operator-driven. The third can be checklist-prompted from the existing handoff log.

## 5. Sequencing — what to do first

Three phases, ordered by reader-value-per-unit-time and operator timeline:

**Phase 1 — Concept Field Guide (in flight)**
- 5 calibration entries live as of 2026-06-04 in `AssemblyZero.wiki/Concept-Field-Guide.md`: *AssemblyZero (the whole)*, *Multi-Agent Orchestration*, *Cerberus and pr-sentinel Separation*, *Banned-List Enforcement*, *LLD-Driven Implementation Pipeline*. Sidebar updated.
- Next: operator reviews calibration entries; revises pitches that don't land; agent applies revisions
- Then: expand to the full ~30 concepts from §4.3 using the calibrated template
- Estimated wall time: ~1-2 days per operator estimate

**Phase 2 — Currency audit on AssemblyZero.wiki**
- Dimension 1 only, all 53 pages
- Build `tools/audit_wiki_currency.py` early; let it do the dead-link/dead-ref detection mechanically
- File one issue per dead reference
- Apply fixes in batches (the existing #1279/#1280 pattern)
- Audit-tool output, commits, and issues must not leak any private-use framing — sterile descriptions only

Justification: currency is the highest-yield dimension. Most reader friction with a wiki is "this command doesn't work" / "this file doesn't exist." Fixing currency makes everything else more visible.

**Phase 3 — Other dimensions, one at a time**
- For Discworld chronicle pages: in scope for currency/correctness audits. If a character has a job that was never implemented, the page must be corrected — either move that capability to a "Future work" section (if a tracking issue is open), or move it to a new "Ideas previously considered" section (if no plan exists / tracking issue closed without action). Stylistic / metaphor content stays.
- Pedagogy and Visual Aids paired (they share the reader-journey lens)
- Completeness next (needs the code-surface inventory, which Phase 1 partially produces)
- Reorganization only if patterns emerge organically across the other dimensions

Justification: avoid the trap of designing a clean information architecture before knowing what's actually in the wiki. Reorganization should be a consequence of audit, not an axiom.

**Phases are sequential, not parallel.** Each phase produces enough learning that the next phase's plan should be revised before starting it. Do not pre-commit to a months-long gantt; commit to Phase 1 and review.

## 6. Decisions made (2026-06-04)

The five open questions in the original draft have been resolved:

1. **Phase 1 first.** Total estimated wall time ~1-2 days for the whole multi-phase effort, so sequencing matters less than originally framed; Phase 1 is the reader-immediate value.
2. **Public field guide; separate private companion.** The Concept Field Guide on the public wiki holds reader-safe content. A private companion (location TBD: `career` repo wiki, or a new password-protected dashboard) holds material that should not be public. The public guide must not reveal anything about who reads the private companion or why.
3. **Agent drafts; operator debates and revises.** Calibration entries land first; operator reviews and revises pitches that don't roll off the tongue. Pitch quality ownership is shared — agent generates, operator validates.
4. **Discworld chronicle pages: IN scope for currency / correctness.** If a chronicle page claims a character does X and X is not implemented, the page must be corrected. Two destinations for unimplemented claims: "Future work" (open tracking issue) or "Ideas previously considered" (no plan / issue closed without action). Stylistic content unchanged.
5. **Audit tool stays in AssemblyZero.** Sibling-repo access to `AssemblyZero.wiki.git` is fine. Tool output, commits, and filed issues must not leak any private-use framing — descriptions are sterile and reference-driven only.

---

## Appendix: References

- Existing wiki audit work: AssemblyZero#1279, #1280, #1261, #1242, #1282
- Wiki source repo: `https://github.com/martymcenroe/AssemblyZero.wiki.git` (cloned at `C:\Users\mcwiz\Projects\AssemblyZero.wiki`)
- Audit framework: `docs/audits/` (numbering picks up after the latest, currently 09xx)
- Memory feedback that constrains methodology:
  - `feedback_triage_subagent_evidence.md` — subagents fabricate; require pasted evidence
  - `feedback_no_jargon_in_operator_questions.md` — plain English in all reports
  - `feedback_file_issues_per_learning.md` — every actionable finding gets an issue
  - `feedback_no_bundling_issues.md` — one concern per issue, default to split
