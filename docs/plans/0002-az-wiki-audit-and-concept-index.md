# Plan 0002 — AssemblyZero Wiki Audit + Technical Concept Index

**Status:** Draft, awaiting operator review
**Date:** 2026-06-04 Central
**Author:** Claude / AssemblyZero session
**Scope:** `AssemblyZero.wiki` only (53 pages). The other fleet wikis (Aletheia.wiki, Hermes.wiki, etc.) are explicitly out of scope.

---

## 1. Why this document exists

The operator (Marty) asked for two things in one session:

1. **An audit plan** for the AssemblyZero wiki against the AssemblyZero code. Suspected problems: drift (wiki describes how things used to work), wrong information (wiki claims that aren't true now), missing information (code surfaces with no wiki coverage), reorganization opportunities, and gaps where diagrams would help where prose currently strains.
2. **A technical concept index** that supports interview prep — Marty has to explain technical concepts in interviews, and the wiki is currently organized by topic/persona rather than by concept. An index keyed by concept (with a short pitch + a pointer to the wiki page that proves it) would let him look up "explain X" in real time.

This document is the plan for both. It does not execute either; execution is the next session's job.

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

## 4. Part B — Technical Concept Index

### 4.1 Why an index distinct from the wiki

The wiki is organized by **topic and persona** (Architecture / Security & Governance / Cost & Platform / etc.). That's the right organization for someone *learning* the system. It's the wrong organization for someone in an interview who is asked *"explain X."*

An interview question lands as a concept ("multi-agent orchestration", "how do you prevent agents from approving their own PRs", "what's a classic-PAT pattern"). Marty needs to navigate from CONCEPT → 30-second pitch → 3-minute deep-dive → "let me show you the actual code/PR/wiki page that proves I built this." The current wiki gives him the deep-dive but not the 30-second pitch and not the search index keyed by concept.

The concept index closes that gap. It is a **lookup table from concept name to interview-ready material**, with pointers into the wiki for proof.

### 4.2 Format per entry

Each concept entry is a short, fixed-shape block:

```markdown
## {Concept Name}

**One-line definition:** {15 words or less; the simplest possible answer}

**30-second pitch:** {2-3 sentences. What it is, why it exists, what it
buys you. No jargon that requires further explanation. The version you'd
say to a CTO who is half-listening.}

**3-minute deep-dive:**
- {Foundational mechanism it relies on}
- {The actual design choice that distinguishes this from the obvious version}
- {The constraint or failure mode that made the design choice necessary}
- {How it composes with other AZ concepts}
- {What the empirical evidence is — PRs landed, issues solved, scale numbers}

**Show me in code:** [`path/to/file.py`](link), [PR #N](link), [wiki page](link)

**Likely follow-ups:**
- "How would you scale this?"
- "What's the failure mode?"
- "How does this compare to {industry alternative}?"

**Related concepts:** [[Concept A]], [[Concept B]], [[Concept C]]
```

The 30-second pitch is **the load-bearing field.** Most interview questions are answered there; deep-dive and code-show are for follow-ups. Each pitch should be road-tested by Marty saying it aloud cold — if it doesn't roll off, it's wrong.

### 4.3 Initial concept list (candidates)

Drawn from the wiki sidebar + memory + recent session work. ~30 concepts; the index can grow.

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
- Daily activity / contribution-graph operations

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

**Interview-narrative concepts (not technical concepts but explainers)**
- "What is AssemblyZero?" (the elevator pitch for the whole thing)
- "Why build it?" (the constraint that made it necessary)
- "What does success look like?" (the velocity / quality metric story)
- "What did you learn that surprised you?" (vulnerability + competence in one)

### 4.4 Where the index lives

Three options; pick before building:

| Option | Pros | Cons |
|---|---|---|
| **A.** As a wiki page (`AssemblyZero.wiki/Concept-Index.md`) | Lives with the source material; cross-links work naturally; visible to anyone reading the wiki | Public; if Marty wants interview-private notes (likely follow-ups, weak spots) they'd need to be elsewhere |
| **B.** As a separate private repo | Private; can hold interview-specific notes; can include "things to avoid saying" and "questions I struggled with" | Disconnected from the wiki; maintenance has to be ritualized; cross-linking is via URL not wikilink |
| **C.** As a structured YAML the wiki renders from | Single source of truth; could generate both wiki view + private deep-dive view; data-driven | Build cost; YAML-to-Markdown rendering is a small project of its own; overkill for ~30 entries |

**Recommendation:** Start with **Option A** for the public-safe content (definition + pitch + deep-dive + show-me); keep "likely follow-ups" and any candor-about-weaknesses in a **separate private notes file** (Option B's content, without committing to a full private repo). Migrate to C if the index outgrows 30 entries and starts feeling stale.

### 4.5 Maintenance hooks

The index will rot without a maintenance ritual. Three hooks:

1. **Audit cycle integration.** Every wiki audit pass (Part A) emits "concepts touched" as a side-finding. The concept-index author pulls those and updates the relevant entries' "show me in code" pointers.
2. **Interview retro.** After each actual interview, Marty captures: which questions arose, which answers wobbled, which concepts were missing from the index. Update the index within 24h while it's fresh.
3. **New-PR hook.** When a substantive PR merges on AZ, ask "does this PR change what 'X' means?" for any concept the PR touches. If yes, update the entry's "show me in code" + deep-dive bullets.

The first hook costs nothing (subsumed by audit work). The second is operator-driven. The third can be checklist-prompted from the existing handoff log.

## 5. Sequencing — what to do first

Three phases, ordered by interview-value-per-unit-time:

**Phase 1 — Concept index first (~3-5 days agent time, mostly drafting)**
- Pick Option A above (wiki-hosted public content)
- Draft 5 highest-value concepts as a calibration batch (likely: AssemblyZero-as-a-whole, multi-agent orchestration, Cerberus/pr-sentinel separation, banned-list enforcement, LLD-driven implementation)
- Have Marty say each pitch aloud and revise until it lands
- Then expand to the full ~30 concepts using the calibrated template

Justification: this directly serves the interview Marty is preparing for. It also creates the rubric for what "good wiki coverage of a concept" looks like, which informs the audit.

**Phase 2 — Currency audit on AssemblyZero.wiki (~3-5 days)**
- Dimension 1 only, all 53 pages
- Build `tools/audit_wiki_currency.py` early; let it do the dead-link/dead-ref detection
- File one issue per dead reference
- Apply fixes in batches (the existing #1279/#1280 pattern)

Justification: currency is the highest-yield dimension. Most reader friction with a wiki is "this command doesn't work" / "this file doesn't exist." Fixing currency makes everything else more visible.

**Phase 3 — Other dimensions, one at a time**
- Pedagogy and Visual Aids paired (they share the reader-journey lens)
- Completeness next (needs the code-surface inventory, which Phase 1's concept index work partially produces)
- Correctness last (most subjective, most expensive per page)
- Reorganization only if patterns emerge organically across the other dimensions

Justification: avoid the trap of designing a clean information architecture before knowing what's actually in the wiki. Reorganization should be a consequence of audit, not an axiom.

**Phases are sequential, not parallel.** Each phase produces enough learning that the next phase's plan should be revised before starting it. Do not pre-commit to a 3-month gantt; commit to Phase 1 and review.

## 6. Open questions for the operator

These are decisions only Marty can make. None block starting Phase 1.

1. **Is Phase 1 (concept index) the right place to start, or should the currency audit go first?** Concept index is interview-urgency; currency audit is debt-reduction. If the interview is this week, Phase 1 is obvious. If the interview is in 30 days, Phase 2 might dominate.
2. **Public or private for the "likely follow-ups" content?** The default per §4.4 is "public for the safe stuff, private file for the candid stuff." If Marty wants to keep the whole index private until interview season ends, that's a different shape.
3. **Who owns the concept-index pitch quality — operator or agent?** Agent can draft, but the pitch only works if Marty can say it. Probably a draft-by-agent → revise-by-operator loop. The plan assumes this; explicit confirmation helps.
4. **Are the Discworld chronicle pages in scope for audit?** They're stylistically distinctive, not technical reference. Default is to exclude them from currency/correctness audits (they're not making testable claims) but include in pedagogy/organization (they're part of the reader's experience). Confirm.
5. **Should the audit tool (`tools/audit_wiki_currency.py`) live in AZ or be a sibling repo?** AZ is the natural home (it's the meta-system), but the tool reads `AssemblyZero.wiki.git` — sibling-repo file access from inside AZ. Probably fine, but worth flagging.

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
