# System Overview — Persona Map

> *"A man is not dead while his name is still spoken."*

## The Discworld Agent Architecture

AssemblyZero's autonomous agents are organized into functional layers, each named after a Discworld character whose personality defines the agent's operational philosophy.

```mermaid
graph TB
    subgraph Orchestration["ORCHESTRATION LAYER"]
        Om["The Great God Om<br/><i>Human Orchestrator</i>"]
        Moist["Moist von Lipwig<br/><i>Pipeline (Issue→PR)</i>"]
    end

    subgraph Core["CORE WORKFLOW LAYER"]
        Issue["Issue Workflow<br/>(7 nodes)"]
        Req["Requirements Workflow<br/>(10 nodes)"]
        Spec["Impl Spec Workflow<br/>(7 nodes)"]
        TDD["TDD Workflow<br/>(13 nodes)"]
    end

    subgraph Intelligence["INTELLIGENCE LAYER"]
        Librarian["The Librarian<br/><i>Document Retrieval</i><br/>#88"]
        Hex["Hex<br/><i>Codebase Intelligence</i><br/>#92"]
        Historian["The Historian<br/><i>Duplicate Detection</i><br/>#91"]
        Angua["Captain Angua<br/><i>External Scout</i><br/>#93"]
    end

    subgraph Foundation["FOUNDATION LAYER"]
        Brutha["Brutha<br/><i>RAG Vector Store</i><br/>#113"]
    end

    subgraph Maintenance["MAINTENANCE LAYER"]
        LuTze["Lu-Tze<br/><i>Janitor / Hygiene</i><br/>#94"]
        DEATH["DEATH<br/><i>Doc Reconciliation</i><br/>#114"]
    end

    subgraph Verification["VERIFICATION LAYER"]
        Gemini["Gemini 3 Pro<br/><i>Adversarial Review</i>"]
    end

    Om -->|"Intent"| Moist
    Moist -->|"Orchestrates"| Issue
    Moist -->|"Orchestrates"| Req
    Moist -->|"Orchestrates"| Spec
    Moist -->|"Orchestrates"| TDD

    Issue -->|"Queries"| Historian
    Req -->|"Queries"| Librarian
    Spec -->|"Queries"| Hex
    TDD -->|"Queries"| Hex

    Librarian -->|"Retrieves from"| Brutha
    Hex -->|"Retrieves from"| Brutha
    Historian -->|"Retrieves from"| Brutha

    Issue -->|"Review"| Gemini
    Req -->|"Review"| Gemini
    TDD -->|"Review"| Gemini

    TDD -->|"Post-merge"| DEATH
    LuTze -.->|"Monitors"| Core
```

## Persona Implementation Status

| Persona | Layer | Status | Issue | Module |
|---------|-------|--------|-------|--------|
| The Great God Om | Orchestration | Active | — | Human-in-the-loop |
| Moist von Lipwig | Orchestration | Implemented | #305 | `tools/orchestrate.py` |
| Brutha | Foundation | Implemented | #113 | `assemblyzero/rag/` |
| The Librarian | Intelligence | Implemented | #88 | `assemblyzero/rag/librarian.py` |
| Hex | Intelligence | Implemented | #92 | `assemblyzero/rag/codebase_retrieval.py` |
| The Historian | Intelligence | Implemented | #91 | `assemblyzero/workflows/issue/nodes/historian.py` |
| Captain Angua | Intelligence | Implemented | #93 | `assemblyzero/workflows/scout/` |
| Lu-Tze | Maintenance | Implemented | #94 | `assemblyzero/workflows/janitor/` |
| DEATH | Maintenance | Manual | #114 | Documentation process |
| Lord Vetinari | Visibility | Planned | — | GitHub Projects automation |
| Commander Vimes | Security | Planned | — | Regression guardian |
| Lord Downey | Deletion | Planned | — | Safe code deletion |
| Ponder Stibbons | Quality | Planned | #307 | Auto-fix compositor |

## Layer Descriptions

### Orchestration Layer
**Om + Moist** — Human intent flows through the pipeline. Om provides the "what" and "why"; Moist ensures the message reaches its destination through all five stages.

### Core Workflow Layer
Four LangGraph state machines with SQLite checkpointing. Each workflow is retryable, resumable, and gated by Gemini verification.

### Intelligence Layer
**Librarian, Hex, Historian, Angua** — These personas provide context to the core workflows. The Librarian retrieves governance docs, Hex understands the codebase, the Historian checks for duplicates, and Angua scouts external repositories.

### Foundation Layer
**Brutha** — The shared RAG infrastructure (ChromaDB + local embeddings) that all intelligence personas build upon. Brutha remembers everything; he does not hallucinate.

### Maintenance Layer
**Lu-Tze + DEATH** — Post-execution care. Lu-Tze continuously sweeps (broken links, stale worktrees, drift). DEATH arrives after implementation to reconcile documentation.

### Verification Layer
**Gemini 3 Pro** — Adversarial review at three gates: issue review, LLD review, and implementation review. Claude builds; Gemini reviews.

## References

- [Dramatis Personae (wiki)](https://github.com/martymcenroe/AssemblyZero/wiki/Dramatis-Personae)
- [ADR-0210: Discworld Persona Convention](../adrs/0210-discworld-persona-convention.md)
- [ADR-0211: RAG Architecture](../adrs/0211-rag-architecture.md)
