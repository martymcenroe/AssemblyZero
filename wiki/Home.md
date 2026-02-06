# AssemblyZero

## Multi-Agent Orchestration Platform for Enterprise AI Development

> Run 12+ AI agents concurrently. One identity. Full governance. Measurable ROI.

```mermaid
graph TD
    subgraph Intent["THE GREAT GOD OM"]
        O["Human Intent<br/>& Oversight"]
    end

    subgraph Agents["CLAUDE AGENTS (12+)"]
        A["Feature | Bug Fix<br/>Docs | Review"]
    end

    subgraph Verify["GEMINI VERIFICATION"]
        G["LLD Review | Code Review<br/>Security | Quality"]
    end

    subgraph Gov["GOVERNANCE GATES"]
        M["Requirements | Implementation<br/>Reports | Audit Trail"]
    end

    subgraph Future["LANGGRAPH EVOLUTION"]
        R["State Machines<br/>Checkpoints | Supervisors"]
    end

    O --> A
    A --> G
    G --> Gov
    Gov --> R
    R -.->|"Feedback Loop"| A
```

---

## Production Evidence: 207 Issues, 159 Closed

AssemblyZero isn't theoretical. It's been battle-tested through **207 issues** (159 closed, 48 open) in 27 days:

**[View Full Metrics Dashboard →](Metrics)**

```
Issues closed per day (Central Time):
2026-01-11:   2 ##
2026-01-17:   8 ########
2026-01-21:  12 ############
2026-02-01:   7 #######
2026-02-02:  23 #######################
2026-02-03:  55 #######################################################
2026-02-04:  31 ###############################
```

| Theme | Examples |
|-------|----------|
| **Workflow Automation** | LLD workflow, implementation workflow, TDD workflow |
| **Governance & Gates** | Gemini verification, mechanical validation, skipped test gates |
| **Bug Fixes** | Unicode encoding, import errors, stale state bugs |
| **Intelligence Layer** | Scout workflow, verdict analyzer, template learning |
| **Infrastructure** | GitHub Actions, Poetry dependencies, cross-platform |

**Current velocity:** 9.4 issues/day average (55 issues on peak day)

---

## The Problem We Solve

AI coding assistants like Claude Code and GitHub Copilot are transforming software development. But **enterprise adoption stalls** because:

| Challenge | Reality |
|-----------|---------|
| **No coordination** | Multiple agents conflict and duplicate work |
| **No governance** | Security teams can't approve ungoverned AI |
| **No verification** | AI-generated code goes unreviewed |
| **No metrics** | Leadership can't prove ROI |
| **Permission friction** | Constant approval prompts destroy flow state |

Organizations run pilots. Developers love the tools. Then adoption plateaus at 10-20% because **the infrastructure layer is missing**.

---

## The Solution

AssemblyZero provides that infrastructure layer:

| Capability | What It Does | Enterprise Value |
|------------|--------------|------------------|
| **Multi-Agent Orchestration** | 12+ concurrent agents, one identity | Scale without chaos |
| **Gemini Verification** | AI reviews AI before humans approve | Quality gates that work |
| **Governance Gates** | Enforced checkpoints (design, code, docs) | Security team approval |
| **Permission Management** | Eliminate friction, track patterns | Developer productivity |
| **34 Audits** | Security, privacy, AI safety, compliance | Compliance readiness |
| **Metrics & KPIs** | Adoption, friction, cost, productivity | Prove ROI to leadership |

---

## For Different Audiences

### Engineering Leaders
- [Why AssemblyZero?](For-Enterprise-Leaders-Why-AssemblyZero) - Business case, ROI, adoption strategy
- [Measuring Productivity](Measuring-Productivity) - KPIs, dashboards, metrics that matter
- [Security & Compliance](Security-Compliance) - What security teams need to approve

### Architects & Technical Leaders
- [Multi-Agent Orchestration](Multi-Agent-Orchestration) - **The headline feature**
- [Gemini Verification](Gemini-Verification) - Claude + Gemini architecture
- [LangGraph Evolution](LangGraph-Evolution) - **The roadmap** (state machines, checkpointing)
- [How the AssemblyZero Learns](How-the-AssemblyZero-Learns) - Self-improving governance feedback loop

### Developers
- [Quick Start](Quick-Start) - 5-minute setup
- [Permission Friction](Permission-Friction) - The #1 adoption blocker solved
- [Why Windows?](Why-Windows) - Cross-platform design decisions

### Security & Compliance Teams
- [Governance Gates](Governance-Gates) - LLD, implementation, report gates
- [Security Compliance](Security-Compliance) - OWASP, GDPR, AI Safety audits

---

## Core Workflows

AssemblyZero implements two primary governed workflows:

### Requirements Workflow
```mermaid
graph TD
    I["Issue Created"]
    L["Write LLD"]
    G{"Gemini<br/>Review"}
    R["Revise"]
    A["APPROVED"]
    C["Ready for<br/>Implementation"]

    I --> L
    L --> G
    G -->|"BLOCK"| R
    R --> G
    G -->|"APPROVE"| A
    A --> C
```

Design documents are reviewed by Gemini before any code is written. [Learn more](Requirements-Workflow)

### Implementation Workflow
```mermaid
graph TD
    S["Start Coding"]
    W["Create Worktree"]
    I["Implement"]
    T["Run Tests"]
    R["Generate Reports"]
    G{"Gemini<br/>Review"}
    P["Create PR"]
    M["Merge & Cleanup"]

    S --> W
    W --> I
    I --> T
    T --> R
    R --> G
    G -->|"BLOCK"| I
    G -->|"APPROVE"| P
    P --> M
```

Code is reviewed by Gemini before PR creation. [Learn more](Implementation-Workflow)

---

## Roadmap: LangGraph Evolution

AssemblyZero is **production-ready today** with prompt-based orchestration. The roadmap transforms it into an enterprise-grade state machine platform:

| Timeline | Milestone | Impact |
|----------|-----------|--------|
| **Q1 2026** | LangGraph state machines, checkpointing | Gates enforced, not suggested |
| **Q2 2026** | Supervisor pattern, LangSmith observability | Autonomous task decomposition |
| **Q3 2026** | Dynamic tool graphs, multi-tenant support | Scale to organizations |

See: [LangGraph Evolution](LangGraph-Evolution) for the full technical vision.

---

## Key Differentiators

### 1. Multi-Model Verification (Unique)
Claude builds code. Gemini reviews it. This isn't just "two models" - it's adversarial verification where one AI checks another's work before humans approve. [Learn more](Gemini-Verification)

### 2. Friction-First Approach
We obsess over permission friction because it's the #1 adoption killer. Our friction logging protocol (Zugzwang) identifies patterns, and our tools auto-remediate them. [Learn more](Permission-Friction)

### 3. Self-Improving Governance
The system learns from Gemini verdicts to improve templates automatically. 164 verdicts analyzed, 6 template sections added. [Learn more](How-the-AssemblyZero-Learns)

### 4. Discworld Personas
Every workflow has a [Discworld character](Dramatis-Personae) defining its philosophy. This isn't whimsy - it's intuitive system design. Vimes guards (regression tests), Lu-Tze sweeps (janitor), Brutha remembers (RAG).

---

## The Cast

| Persona | Function | Philosophy |
|---------|----------|------------|
| **[The Great God Om](The-Great-God-Om)** | Human Orchestrator | Pure Intent |
| **Moist von Lipwig** | Pipeline Orchestration | Keep messages moving |
| **Lord Vetinari** | Work Visibility | Information is power |
| **Commander Vimes** | Regression Tests | Deep suspicion |
| **Captain Angua** | External Intelligence | Sensory awareness |
| **Brutha** | RAG Memory | Perfect recall |
| **Lu-Tze** | Maintenance | Constant sweeping |

[Full cast →](Dramatis-Personae)

---

## Get Started

1. **Read the architecture**: [Multi-Agent Orchestration](Multi-Agent-Orchestration)
2. **Understand the roadmap**: [LangGraph Evolution](LangGraph-Evolution)
3. **See the metrics**: [Measuring Productivity](Measuring-Productivity)
4. **Try it**: [Quick Start](Quick-Start)

---

*"A man is not dead while his name is still spoken."*
**GNU Terry Pratchett**
