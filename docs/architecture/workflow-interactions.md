# Workflow Interactions — How Workflows Chain

## Pipeline Orchestration (Moist von Lipwig)

The five workflow stages are independent LangGraph state machines that chain together through shared filesystem artifacts. Moist (the orchestrator) drives the pipeline, ensuring each stage completes before the next begins.

```mermaid
graph TD
    subgraph Moist["MOIST VON LIPWIG — Pipeline Orchestrator"]
        direction LR
        Start["Start"] --> Stage1
        Stage1["Stage 1:<br/>Issue"] --> Gate1{"Human<br/>Gate"}
        Gate1 --> Stage2["Stage 2:<br/>Requirements"]
        Stage2 --> Gate2{"Gemini<br/>Gate"}
        Gate2 --> Stage3["Stage 3:<br/>Impl Spec"]
        Stage3 --> Gate3{"Human<br/>Gate"}
        Gate3 --> Stage4["Stage 4:<br/>TDD"]
        Stage4 --> Gate4{"Gemini<br/>Gate"}
        Gate4 --> Stage5["Stage 5:<br/>PR + Merge"]
    end
```

### Stage Handoff Protocol

Each stage writes its output to the lineage directory. The next stage reads from there:

| Stage | Reads | Writes | Gate |
|-------|-------|--------|------|
| Issue | `ideas/active/*.md` | `lineage/active/N/issue-brief.md` | Human approval |
| Requirements | Issue brief + RAG context | `lineage/active/N/lld.md` | Gemini APPROVE |
| Impl Spec | LLD + codebase context | `lineage/active/N/implementation-spec.md` | Human approval |
| TDD | Impl spec + codebase context | Code + tests + reports | Gemini APPROVE |
| Merge | PR approved | `lineage/done/N/` (archived) | Human merge |

## Checkpoint / Resume

Every workflow uses SQLite checkpointing via LangGraph's `SqliteSaver`. This means:

```mermaid
graph LR
    subgraph Normal["NORMAL FLOW"]
        N1["Node 1"] --> N2["Node 2"] --> N3["Node 3"]
    end

    subgraph Interrupt["AFTER INTERRUPTION"]
        R["Resume from<br/>last checkpoint"] --> N2b["Node 2<br/>(retry)"] --> N3b["Node 3"]
    end

    N2 -.->|"Session crash<br/>or timeout"| R
```

- Checkpoints are stored in `.assemblyzero/checkpoints/`
- Each workflow invocation gets a unique thread ID
- On resume, the workflow picks up from the last completed node
- State includes: all node outputs, RAG results, Gemini verdicts, iteration counts

## Workflow-to-Persona Dependencies

```mermaid
graph TB
    subgraph IssueWF["Issue Workflow"]
        I_Load["Load Brief"]
        I_Hist["Historian Node"]
        I_Draft["Draft Issue"]
        I_Review["Gemini Review"]
        I_Gate["Human Gate"]
        I_Publish["Publish to GitHub"]

        I_Load --> I_Hist
        I_Hist --> I_Draft
        I_Draft --> I_Review
        I_Review --> I_Gate
        I_Gate --> I_Publish
    end

    subgraph ReqWF["Requirements Workflow"]
        R_Load["Load Issue"]
        R_Lib["Librarian Node"]
        R_Analyze["Analyze Codebase"]
        R_Design["Designer Node"]
        R_Review["Gemini Review"]
        R_Gate["Human Gate"]

        R_Load --> R_Lib
        R_Lib --> R_Analyze
        R_Analyze --> R_Design
        R_Design --> R_Review
        R_Review -->|"BLOCK"| R_Design
        R_Review -->|"APPROVE"| R_Gate
    end

    subgraph SpecWF["Impl Spec Workflow"]
        S_Load["Load LLD"]
        S_Hex["Hex Query"]
        S_Draft["Draft Spec"]
        S_Validate["Validate"]
        S_Gate["Human Gate"]

        S_Load --> S_Hex
        S_Hex --> S_Draft
        S_Draft --> S_Validate
        S_Validate --> S_Gate
    end

    subgraph TDDWF["TDD Workflow"]
        T_Load["Load Spec"]
        T_Hex["Hex Query"]
        T_Scaffold["Scaffold Tests"]
        T_Implement["Implement"]
        T_Test["Run Tests"]
        T_Report["Generate Reports"]
        T_Review["Gemini Review"]
        T_PR["Create PR"]

        T_Load --> T_Hex
        T_Hex --> T_Scaffold
        T_Scaffold --> T_Implement
        T_Implement --> T_Test
        T_Test -->|"Fail"| T_Implement
        T_Test -->|"Pass"| T_Report
        T_Report --> T_Review
        T_Review -->|"BLOCK"| T_Implement
        T_Review -->|"APPROVE"| T_PR
    end

    IssueWF -->|"issue-brief.md"| ReqWF
    ReqWF -->|"lld.md"| SpecWF
    SpecWF -->|"implementation-spec.md"| TDDWF
```

## Supporting Workflows

### Scout Workflow (Angua)

The Scout runs independently — it is triggered on demand, not as part of the main pipeline.

```mermaid
graph LR
    Brief["Research Brief"] --> Search["GitHub Search"]
    Search --> Analyze["Pattern Analysis"]
    Analyze --> Report["Innovation Brief"]
    Report --> Budget["Token Budget Check"]
    Budget --> Output["Gap Analysis"]
```

### Janitor Workflow (Lu-Tze)

The Janitor runs on a schedule or on demand. It does not feed into the main pipeline but maintains the environment.

```mermaid
graph TD
    Trigger["Manual or Scheduled"] --> Probes
    subgraph Probes["PROBE PHASE"]
        Links["Link Probe"]
        Worktrees["Worktree Probe"]
        Harvest["Harvest Probe"]
        Todo["TODO Probe"]
    end

    Probes --> Report["Reporter"]
    Report --> Fixers["Auto-Fix<br/>(if enabled)"]
    Fixers --> Summary["Hygiene Report"]
```

## Human Gates

Every workflow has at least one human gate. These are explicit pause points where the human orchestrator (Om) reviews and approves before the system proceeds.

| Workflow | Gate Location | What Human Reviews |
|----------|--------------|-------------------|
| Issue | After Gemini review | Draft issue quality |
| Requirements | After Gemini APPROVE | LLD design decisions |
| Impl Spec | After validation | Spec completeness |
| TDD | Before PR creation | Code + test quality |
| Merge | PR approval | Final review |

Gates cannot be bypassed. The `--yes` flag exists only on the LLD workflow for batch processing scenarios.

## References

- [End-to-End Orchestration (wiki)](https://github.com/martymcenroe/AssemblyZero/wiki/End-to-End-Orchestration)
- [LangGraph Evolution (wiki)](https://github.com/martymcenroe/AssemblyZero/wiki/LangGraph-Evolution)
- [Governance Gates (wiki)](https://github.com/martymcenroe/AssemblyZero/wiki/Governance-Gates)
