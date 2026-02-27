# The Pipeline: Idea to Tested and Deployed Code

> *"Entia non sunt multiplicanda praeter necessitatem."* — but sometimes you need three workflows.

AssemblyZero automates the full journey from an idea to tested, reviewed, and merged code. Three workflows run in sequence, each producing an artifact that feeds the next.

---

## The Three Stages

```
 GitHub Issue
      │
      ▼
┌─────────────────────────┐
│  Stage 1: REQUIREMENTS  │  "What should we build?"
│  run_requirements_       │
│  workflow.py --type lld  │
│                         │
│  Claude drafts ──►      │
│  Gemini reviews         │
└────────┬────────────────┘
         │ produces: LLD (Low-Level Design)
         ▼
┌─────────────────────────┐
│  Stage 2: SPEC          │  "How exactly should we build it?"
│  run_implementation_     │
│  spec_workflow.py        │
│                         │
│  Reads codebase ──►     │
│  Claude drafts ──►      │
│  Gemini reviews         │
└────────┬────────────────┘
         │ produces: Implementation Spec
         ▼
┌─────────────────────────┐
│  Stage 3: IMPLEMENTATION│  "Build it."
│  run_implement_from_     │
│  lld.py                  │
│                         │
│  TDD: Red ──► Green ──► │
│  Refactor ──► Review    │
└────────┬────────────────┘
         │ produces: Code + Tests + PR
         ▼
    Merged to main
```

---

## Stage 1: Requirements Workflow

**CLI:** `poetry run python tools/run_requirements_workflow.py --type lld --issue <N>`

**Input:** GitHub issue number
**Output:** Approved LLD in `docs/lld/active/LLD-<N>.md`

What it does:
- Reads the issue body from GitHub
- Claude drafts a Low-Level Design document following the LLD template
- Mechanical validation checks paths, structure, completeness
- Gemini reviews for design quality
- Iterates up to 3 times until approved
- Writes approved LLD to `docs/lld/active/`

The LLD defines *what* to build: files to change, data structures, function signatures, test scenarios, and architecture decisions. It's a design document, not implementation instructions.

**Wiki:** [Requirements Workflow](Requirements-Workflow)

---

## Stage 2: Implementation Spec Workflow (NEW - #304)

**CLI:** `poetry run python tools/run_implementation_spec_workflow.py --issue <N>`

**Input:** Approved LLD
**Output:** Implementation Spec in `docs/lld/drafts/spec-<N>.md`

What it does:
- **N0: Load LLD** — Reads the approved LLD, parses files-to-modify table
- **N1: Analyze Codebase** — Reads actual source files, extracts current state excerpts, finds similar patterns in the codebase
- **N2: Generate Spec** — Claude produces a concrete implementation spec with:
  - Current state excerpts for every file being modified
  - Concrete JSON/YAML examples for every data structure
  - Input/output examples for every function
  - Line-level change instructions
  - Pattern references (file:line) to similar existing code
- **N3: Validate Completeness** — Mechanical checks that the spec is implementation-ready
- **N4: Human Gate** — Optional human review (disabled by default)
- **N5: Review Spec** — Gemini reviews for implementation readiness
- **N6: Finalize** — Writes approved spec

The spec bridges the gap between "what to build" (LLD) and "build it" (implementation). It gives the implementation workflow enough concrete detail to succeed on the first try.

---

## Stage 3: TDD Implementation Workflow

**CLI:** `poetry run python tools/run_implement_from_lld.py --issue <N>`

**Input:** LLD (or Implementation Spec, via #384)
**Output:** Working code with tests, committed to branch

What it does:
- Creates an isolated git worktree
- Follows the TDD pipeline: N0→N1→N1.5→N1b→N2→N2.5→N3→N4→N4b→N5→N6→N7→N8
- Scaffolds failing tests (RED), implements code (GREEN), validates
- Gemini reviews the implementation
- Creates PR when approved

**Wiki:** [Implementation Workflow](Implementation-Workflow)

---

## The Orchestrator (#305 - Coming Next)

**CLI:** `poetry run python tools/orchestrate.py --issue <N>`

The orchestrator chains all three stages automatically. Point it at an issue number and walk away:

1. Runs Requirements Workflow → produces LLD
2. Runs Implementation Spec Workflow → produces Spec
3. Runs TDD Implementation → produces Code + Tests

With resume support: if any stage fails, you can restart from the failed stage without re-running earlier stages.

**Status:** LLD approved, ready to build.

---

## When to Use Each Stage

| Scenario | Start From |
|----------|------------|
| New feature, issue exists | Stage 1 (or Orchestrator) |
| LLD already approved | Stage 2 |
| Simple change, LLD exists, no-lld label | Stage 3 directly |
| Implementation Spec exists | Stage 3 (via #384 adapter) |

---

## Artifacts Produced

```
docs/
├── lld/
│   ├── active/LLD-305.md          ← Stage 1 output
│   └── drafts/spec-0305.md        ← Stage 2 output
├── lineage/
│   └── active/305-testing/        ← Stage 3 audit trail
│       ├── 001-lld.md
│       ├── 002-test-plan.md
│       ├── ...prompts & responses...
│       └── 053-final.md
└── standards/
    ├── 0701-implementation-spec-template.md
    └── 0702-implementation-readiness-review.md
```

---

## Related

- [Requirements Workflow](Requirements-Workflow) — Stage 1 details
- [Implementation Workflow](Implementation-Workflow) — Stage 3 details
- [Governance Gates](Governance-Gates) — Review gates across all stages
- [Gemini Verification](Gemini-Verification) — Multi-model review architecture
