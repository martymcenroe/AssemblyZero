# Measuring Productivity

> KPIs, metrics, and dashboards for proving AI coding assistant ROI

---

## The Measurement Challenge

"We have 5 pilots running" is where many AI adoption efforts stall. Without measurement:

- **Leadership can't justify budget** - "How much does this save us?"
- **Security can't approve expansion** - "What's the risk profile?"
- **Teams can't improve** - "Are we getting better at this?"
- **Skeptics aren't convinced** - "Prove it works"

AssemblyZero treats measurement as a first-class concern, not an afterthought.

---

## KPI Framework

### Tier 1: Adoption Metrics (Leading Indicators)

These show whether the tools are being used:

| Metric | Definition | Target | Warning |
|--------|------------|--------|---------|
| **Active Users** | Developers with 5+ agent sessions/week | 80% of team | < 50% |
| **Session Frequency** | Agent sessions per developer per day | 3+ sessions | < 1 session |
| **Feature Utilization** | % of capabilities used (chat, edit, review) | 60%+ | < 30% |
| **Permission Friction Rate** | Approval prompts per session | < 2 | > 5 |

**Why these matter:** Low adoption = low ROI, regardless of theoretical productivity gains.

### Tier 2: Productivity Metrics (Quality Indicators)

These show whether the tools improve outcomes:

| Metric | Definition | Target | Warning |
|--------|------------|--------|---------|
| **Cycle Time** | Time from issue creation to PR merge | -30% vs baseline | +10% |
| **Review Iterations** | PR revisions before approval | -40% vs baseline | +20% |
| **First-Time Quality** | PRs approved without revision | 70%+ | < 50% |
| **Gemini Approval Rate** | % of submissions passing gate | 80%+ | < 60% |

**Why these matter:** Faster cycles with fewer iterations = real productivity improvement.

### Tier 3: Efficiency Metrics (Lagging Indicators)

These show dollar impact:

| Metric | Definition | Target | Warning |
|--------|------------|--------|---------|
| **Cost per Feature** | (Agent costs + human time) / features delivered | -25% vs baseline | +10% |
| **Token Efficiency** | Useful outputs / total tokens consumed | Improving trend | Declining trend |
| **Rework Rate** | Features requiring post-merge fixes | -50% vs baseline | +20% |
| **Velocity (Story Points)** | Points delivered per sprint | +20% vs baseline | -10% |

**Why these matter:** This is what the CFO and CTO care about.

---

## Permission Friction Metrics

Friction is the #1 adoption killer. We measure it obsessively:

### Friction Rate

```
Friction Rate = Approval Prompts / Tool Calls

Target: < 0.05 (5% of tool calls require approval)
Warning: > 0.15 (15%)
Critical: > 0.30 (30% - developers will abandon the tool)
```

### Friction Types

| Type | Description | Remediation |
|------|-------------|-------------|
| **Pattern mismatch** | Allowed pattern doesn't match actual command | Broaden pattern |
| **New command** | First use of a command type | Add to allowed patterns |
| **Bash flags** | Flags like `-n 50` break pattern matching | Use dedicated tools |
| **Path variations** | Same logical path, different formats | Normalize paths |
| **Spawned agent** | Subagent inherits wrong permissions | Propagate patterns |

### Friction Tracking Protocol (Zugzwang)

Real-time friction logging:

```markdown
## FRICTION LOG - Session 2026-01-21-001

| Time | Tool | Command/Action | Friction | Resolution |
|------|------|----------------|----------|------------|
| 09:15 | Bash | `head -n 50 /path/file` | YES | Used Read tool instead |
| 09:18 | Bash | `git -C /path status` | NO | Pattern matched |
| 09:22 | Bash | `poetry run python ...` | NO | Pattern matched |
| 09:45 | Bash | `npm install --prefix ...` | YES | Added pattern |

### Session Summary
- Tool calls: 47
- Friction events: 2
- Friction rate: 4.3%
- Patterns added: 1
```

### Friction Reduction Over Time

The goal is consistent improvement:

```
Week 1: 18% friction rate (new project, many new patterns)
Week 2: 12% friction rate (patterns accumulating)
Week 4: 6% friction rate (most patterns learned)
Week 8: 3% friction rate (mature project)
Steady state: 2-3% (new edge cases only)
```

---

## Gemini Gate Metrics

Gemini verification provides natural quality checkpoints:

### Gate Approval Rates

| Gate | Target | Warning | Action if Low |
|------|--------|---------|---------------|
| **LLD Review** | 75%+ first pass | < 50% | Improve LLD templates |
| **Implementation Review** | 80%+ first pass | < 60% | Review coding patterns |
| **Security Audit** | 90%+ passing | < 80% | Training on security patterns |

### Common Rejection Reasons

Track why Gemini blocks submissions:

```
LLD Rejections (last 30 days):
├── Missing error handling spec: 35%
├── Incomplete API contract: 25%
├── Missing security considerations: 20%
├── Unclear data flow: 15%
└── Other: 5%

Implementation Rejections (last 30 days):
├── Missing test coverage: 40%
├── Security vulnerability detected: 25%
├── Pattern violation: 20%
├── Missing documentation: 10%
└── Other: 5%
```

This data drives training priorities.

---

## Cost Attribution

### Per-Feature Costing

```
Feature: Add Export Functionality (#47)
├── LLD Phase
│   ├── Claude tokens: 45,000 @ $0.003/1K = $0.135
│   ├── Gemini tokens: 12,000 @ $0.001/1K = $0.012
│   └── Subtotal: $0.147
├── Implementation Phase
│   ├── Claude tokens: 180,000 @ $0.003/1K = $0.540
│   ├── Human review time: 0.5 hours
│   └── Subtotal: $0.540 + human time
├── Review Phase
│   ├── Claude tokens: 30,000 @ $0.003/1K = $0.090
│   ├── Gemini tokens: 25,000 @ $0.001/1K = $0.025
│   └── Subtotal: $0.115
└── Total AI Cost: $0.802
    Human time saved (estimated): 4 hours
    Net productivity gain: 3.5 hours at $75/hr = $262.50
    ROI: $262.50 / $0.80 = 328x
```

### Monthly Cost Dashboard

```
AssemblyZero Costs - January 2026
├── Claude API: $847.00
├── Gemini API: $123.00
├── Total API: $970.00
├── Features delivered: 47
├── Cost per feature: $20.64
├── Human hours saved (est): 188 hours
├── Human cost avoided: $14,100
└── ROI: 14.5x
```

---

## Adoption Dashboard

### Team-Level View

```
┌─────────────────────────────────────────────────────────────┐
│           AGENTOS ADOPTION - TEAM ALPHA                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ADOPTION RATE          FRICTION RATE          CYCLE TIME  │
│  ████████████░░  82%    ███░░░░░░░░░░  4.2%    -32%        │
│  Target: 80%            Target: <5%             vs baseline │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  DEVELOPERS              SESSIONS/WEEK          FEATURES   │
│                                                             │
│  Alice    █████████ 23   ████████████ 47        12 PRs     │
│  Bob      ███████   18   ████████     32        8 PRs      │
│  Carol    ██████    15   ███████      28        7 PRs      │
│  Dave     ████      11   ██████       22        5 PRs      │
│  Eve      ██         6   ████         14        3 PRs      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  GEMINI GATE PERFORMANCE                                   │
│                                                             │
│  LLD Review:            ████████░░░░  78% first-pass       │
│  Implementation Review: █████████░░░  85% first-pass       │
│  Security Audit:        ██████████░░  92% passing          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Organization-Level View

```
┌─────────────────────────────────────────────────────────────┐
│           AGENTOS ADOPTION - ORGANIZATION                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  TEAM            ADOPTION    FRICTION    CYCLE TIME        │
│                                                             │
│  Alpha           ████████ 82%  █░░  4%   -32%              │
│  Beta            ██████░  65%  ██░  8%   -18%              │
│  Gamma           █████░░  52%  ███ 12%   -8%               │
│  Delta           ███░░░░  38%  ████ 18%  +5%               │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MONTHLY TRENDS                                            │
│                                                             │
│  Adoption:  42% → 52% → 61% → 68% → 73%  ↑ Improving      │
│  Friction:  18% → 14% → 10% → 7%  → 5%   ↓ Improving      │
│  ROI:       8x  → 10x → 12x → 14x → 15x  ↑ Improving      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  INVESTMENT SUMMARY (Q1 2026)                              │
│                                                             │
│  API Costs:           $4,230                               │
│  Training/Onboarding: $2,100                               │
│  Total Investment:    $6,330                               │
│  Developer Hours Saved: 892 hours                          │
│  Value at $75/hr:     $66,900                              │
│  Net ROI:             10.6x                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Audit Metrics

AssemblyZero includes 34 governance audits:

### Audit Coverage

| Category | Audits | Passing | Coverage |
|----------|--------|---------|----------|
| Security (OWASP) | 10 | 9 | 90% |
| Privacy (GDPR) | 6 | 6 | 100% |
| AI Safety (NIST) | 5 | 4 | 80% |
| Code Quality | 8 | 7 | 88% |
| Documentation | 5 | 5 | 100% |
| **Total** | **34** | **31** | **91%** |

### Audit Trend

```
Audit Pass Rate Over Time:
├── Week 1:  68% (initial issues found)
├── Week 2:  75% (high-priority fixes)
├── Week 4:  85% (most issues addressed)
├── Week 8:  91% (approaching target)
└── Target:  95% (enterprise-ready)
```

---

## Implementation: Current vs. LangSmith

### Current (Log-Based)

```python
# Manual log parsing
def calculate_friction_rate(session_log: Path) -> float:
    """Parse session transcript for friction events"""
    with open(session_log) as f:
        content = f.read()

    tool_calls = content.count("Tool call:")
    friction_events = content.count("permission") + content.count("approval")

    return friction_events / tool_calls if tool_calls > 0 else 0

# Aggregation requires custom scripts
```

### Future (LangSmith)

```python
# Automatic tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "assemblyzero-production"

# Every metric is automatic:
# - Token counts
# - Latency
# - Error rates
# - Cost attribution
# - Full traces

# Query via LangSmith API
from langsmith import Client
client = Client()

# Get friction rate for last week
runs = client.list_runs(
    project_name="assemblyzero-production",
    start_time=last_week,
    filter="tags.type = 'permission_prompt'"
)
```

---

## Related Pages

- [Permission Friction](Permission-Friction) - Deep dive on friction reduction
- [Governance Gates](Governance-Gates) - Gate implementation details
- [LangGraph Evolution](LangGraph-Evolution) - LangSmith integration roadmap
- [Multi-Agent Orchestration](Multi-Agent-Orchestration) - Architecture overview
