# 0832 - Cost Optimization Audit

**File:** `docs/audits/0832-audit-cost-optimization.md`
**Status:** Active
**Frequency:** Monthly
**Auto-Fix:** Partial (can update model hints, cannot restructure code)

---

## 1. Purpose

Evaluate all AgentOS skills, commands, and tools for token efficiency and cost optimization. Identify opportunities to reduce API costs without degrading capability.

**Cost matters because:**
- Opus is ~15x more expensive than Haiku
- Sonnet is ~3x more expensive than Haiku
- Unnecessary context loading wastes tokens
- Verbose prompts cost money with no benefit
- Wrong model selection compounds over time

---

## 2. Audit Scope

### 2.1 What Gets Audited

| Category | Location | Examples |
|----------|----------|----------|
| **Skills** | `AgentOS/.claude/commands/` | `/onboard`, `/cleanup`, `/code-review` |
| **Tools** | `AgentOS/tools/` | `agentos-permissions.py`, `gemini-retry.py` |
| **Prompts** | Embedded in skills | Agent spawn prompts, review templates |
| **Workflows** | `CLAUDE.md`, skill docs | Multi-step procedures |

### 2.2 What Gets Measured

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Model selection | Cheapest capable model | Review model hints in docs |
| Context loading | Parallel, minimal | Count sequential reads that could be parallel |
| Prompt verbosity | Concise, no redundancy | Word count of embedded prompts |
| Spawn efficiency | Spawn only when needed | Review spawn conditions |
| Caching opportunities | Cache where possible | Identify repeated expensive operations |

---

## 3. Cost Reference

### 3.1 Model Pricing (Relative)

| Model | Input | Output | Relative Cost |
|-------|-------|--------|---------------|
| Haiku | $0.25/M | $1.25/M | 1x (baseline) |
| Sonnet | $3/M | $15/M | ~12x |
| Opus | $15/M | $75/M | ~60x |

### 3.2 Operation Costs (Estimated)

| Operation | Typical Cost | Model |
|-----------|--------------|-------|
| `/onboard --refresh` | ~$0.01 | Haiku |
| `/onboard --quick` | ~$0.02 | Haiku |
| `/onboard --full` | ~$0.35 | Sonnet |
| `/cleanup --quick` | ~$0.02 | Haiku |
| `/cleanup` | ~$0.10 | Haiku |
| `/cleanup --full` | ~$0.50 | Sonnet |
| `/code-review` (3 agents) | ~$1.50 | Sonnet x3 |
| `/friction` | ~$0.80 | Sonnet |
| Single file read | ~$0.001 | - |
| Codebase exploration | ~$0.20 | Sonnet |

---

## 4. Audit Checklist

### 4.1 Model Selection

For each skill/command, verify the model hint is appropriate:

| Check | Pass Criteria |
|-------|---------------|
| Model hint exists | Skill doc specifies recommended model |
| Model matches complexity | Simple tasks → Haiku, Complex reasoning → Opus |
| Model hint is enforced | Spawn prompts include model specification |

**Model Selection Guide:**

| Task Type | Recommended Model | Examples |
|-----------|-------------------|----------|
| File parsing, checklist validation | Haiku | Permission cleanup, status checks |
| Pattern matching, simple transforms | Haiku | Terminology search, timestamp comparison |
| Web research, framework analysis | Sonnet | Horizon scanning, capability checks |
| Code generation, refactoring | Sonnet | Bug fixes, feature implementation |
| Security analysis, incident review | Opus | Security audit, post-mortem |
| Complex reasoning, nuanced judgment | Opus | Architecture decisions, design review |

### 4.2 Context Loading

| Check | Pass Criteria |
|-------|---------------|
| Parallel reads used | Independent files read in single message |
| No redundant reads | Same file not read multiple times |
| Minimal context | Only necessary files loaded |
| Lazy loading | Files read only when needed |

**Common Anti-Patterns:**

```markdown
❌ BAD: Sequential reads of independent files
Read file A
[wait for response]
Read file B
[wait for response]
Read file C

✅ GOOD: Parallel reads
Read file A, B, C simultaneously
```

```markdown
❌ BAD: Reading entire file when only header needed
Read entire 1000-line file
Extract first 10 lines

✅ GOOD: Use limit parameter
Read file with limit=10
```

### 4.3 Prompt Efficiency

| Check | Pass Criteria |
|-------|---------------|
| No redundant instructions | Instructions not repeated |
| Concise language | No filler words |
| Structured output requested | JSON/markdown format specified |
| No unnecessary context | Background info only when needed |

**Prompt Size Guidelines:**

| Prompt Type | Target Length | Maximum |
|-------------|---------------|---------|
| Simple task | 50-100 words | 200 words |
| Complex task | 100-200 words | 400 words |
| Full procedure | 200-400 words | 800 words |

### 4.4 Spawn Efficiency

| Check | Pass Criteria |
|-------|---------------|
| Spawn justified | Task requires different model or parallelism |
| Spawn prompt minimal | Only necessary context passed |
| Results used efficiently | Spawn results not re-processed unnecessarily |

**When to Spawn:**

| Scenario | Spawn? | Reason |
|----------|--------|--------|
| Parallel independent tasks | Yes | Concurrent execution |
| Task needs cheaper model | Yes | Cost savings |
| Task needs more capable model | Yes | Capability requirement |
| Sequential dependent tasks | No | Main agent can handle |
| Simple one-off task | No | Overhead not justified |

### 4.5 Caching Opportunities

| Check | Pass Criteria |
|-------|---------------|
| Repeated operations identified | Same query not run multiple times |
| Static data cached | Config files, templates read once |
| Results reused | Expensive computations stored |

### 4.6 User Interaction Efficiency

| Check | Pass Criteria |
|-------|---------------|
| Questions batched | Multiple questions in single message |
| Context not repeated | Don't re-explain what agent already knows |
| Partial reads used | `limit` parameter for large files |

**Why batching matters:**
Each message carries context overhead. One message with 5 questions costs less than 5 separate messages because the full conversation history is re-sent each time.

### 4.7 Protocol Overhead (User Trade-offs)

Some AgentOS protocols add token cost for safety/auditability:

| Protocol | Cost | When to Skip |
|----------|------|--------------|
| Visible self-check | ~20 tokens/Bash call | Token-critical sessions, trusted operations |
| Full spawn instructions | ~100 tokens/spawn | Simple spawns to Haiku |
| Detailed commit messages | ~50 tokens | Quick doc updates |

**These are USER decisions.** The protocols exist for good reasons, but when you're at 58% budget with 3 days left, pragmatism wins.

---

## 5. Skill-by-Skill Audit

### 5.1 /onboard

| Aspect | Current | Optimal | Gap |
|--------|---------|---------|-----|
| Model hint | Haiku for refresh/quick, Sonnet for full | Correct | None |
| Parallel reads | Yes (Step 1) | Correct | None |
| Modes | 3 (refresh/quick/full) | Correct | None |

**Findings:** Well optimized. Refresh mode added for post-compact efficiency.

### 5.2 /cleanup

| Aspect | Current | Optimal | Gap |
|--------|---------|---------|-----|
| Model hint | ✅ Haiku for quick/normal, Sonnet for full | Correct | None |
| Git operations | Sequential | Could batch some | Minor |
| Session log | Single write | Correct | None |

**Findings:** ✅ FIXED 2026-01-14 - Model hints added.

### 5.3 /code-review

| Aspect | Current | Optimal | Gap |
|--------|---------|---------|-----|
| Model hint | ✅ Opus for security, Sonnet for others | Correct | None |
| Parallel agents | Yes | Correct | None |
| File reading | ✅ Shared context from parent | Correct | None |

**Findings:** ✅ FIXED 2026-01-14 - Model hints added. Agents now receive context in spawn prompt and are instructed NOT to re-read files.

### 5.4 /sync-permissions

| Aspect | Current | Optimal | Gap |
|--------|---------|---------|-----|
| Model hint | ✅ "Zero LLM cost" noted | Correct | None |
| JSON parsing | Python tool | Correct | None |
| Validation | Added | Correct | None |

**Findings:** ✅ FIXED 2026-01-14 - Documentation now notes this is a Python tool with zero LLM cost.

### 5.5 /friction

| Aspect | Current | Optimal | Gap |
|--------|---------|---------|-----|
| Model hint | ✅ Sonnet specified | Correct | None |
| Transcript parsing | ✅ Pre-filter with Grep | Correct | None |
| Analysis depth | Comprehensive | Correct for purpose | None |

**Findings:** ✅ FIXED 2026-01-14 - Model hint added. Pre-filtering step added to use Grep before reading full transcripts.

### 5.6 /commit-push-pr

| Aspect | Current | Optimal | Gap |
|--------|---------|---------|-----|
| Model hint | ✅ Haiku specified | Correct | None |
| Git operations | Sequential (necessary) | Correct | None |
| PR body generation | Inline | Correct | None |

**Findings:** ✅ FIXED 2026-01-14 - Model hint added.

### 5.7 /test-gaps

| Aspect | Current | Optimal | Gap |
|--------|---------|---------|-----|
| Model hint | ✅ Sonnet specified | Correct | None |
| Report mining | ✅ Pre-filter with Grep | Correct | None |

**Findings:** ✅ FIXED 2026-01-14 - Model hint added. Pre-filtering step added to use Grep before reading full reports.

---

## 6. Common Optimizations

### 6.1 Add Model Hints to All Skills

Every skill document should specify:
```markdown
**Model hint:** This skill can use **Haiku** for [reason].
```

### 6.2 Pre-Filter Before Analysis

For skills that analyze large files:
```markdown
1. Grep for relevant patterns first
2. Only read matching sections
3. Analyze filtered content
```

### 6.3 Batch Git Operations

Instead of:
```bash
git status
git diff
git log
```

Use parallel Bash calls (all three at once).

### 6.4 Share Context Between Spawned Agents

For multi-agent skills like /code-review:
- Read files once in parent
- Pass relevant excerpts to children
- Avoid duplicate reads

---

## 7. Audit Procedure

### 7.1 Preparation

1. List all skills: `ls AgentOS/.claude/commands/`
2. List all tools: `ls AgentOS/tools/`
3. Read current cost estimates from this document

### 7.2 Per-Skill Audit

For each skill:

1. **Read the skill definition** (`AgentOS/.claude/commands/{skill}.md`)
2. **Check model hint** - Is it specified? Is it appropriate?
3. **Check context loading** - Parallel? Minimal?
4. **Check spawn efficiency** - Justified? Minimal prompts?
5. **Estimate cost** - Update Section 3.2 if changed
6. **Document findings** - Update Section 5

### 7.3 Remediation

| Finding Type | Action |
|--------------|--------|
| Missing model hint | Add to skill doc |
| Wrong model | Update hint and rationale |
| Sequential reads | Refactor to parallel |
| Verbose prompts | Trim and test |
| Unnecessary spawns | Refactor workflow |

### 7.4 Auto-Fix Capabilities

This audit can auto-fix:
- [ ] Add missing model hints to skill docs
- [ ] Update cost estimates in this document

This audit requires human decision:
- [ ] Restructure skill workflows
- [ ] Change spawn strategies
- [ ] Refactor prompts

---

## 8. Audit Record

| Date | Auditor | Skills Audited | Findings | Issues |
|------|---------|----------------|----------|--------|
| 2026-01-14 | Claude Opus 4.5 | All 8 skills | 5 missing model hints, 2 pre-filter opportunities | - |
| 2026-01-14 | Claude Opus 4.5 | All 8 skills | ✅ ALL FIXED: model hints added, pre-filtering added, shared context for /code-review | - |
| 2026-01-14 | Claude Opus 4.5 | Checklist | Added 4.6 User Interaction Efficiency, 4.7 Protocol Overhead trade-offs | - |

---

## 9. Cost Tracking (Future)

### 9.1 Proposed Metrics

| Metric | Collection Method | Target |
|--------|-------------------|--------|
| Cost per session | Sum of operation costs | Track trend |
| Cost per skill | Instrument skill execution | Compare to estimates |
| Model usage distribution | Log model selections | Haiku > Sonnet > Opus |

### 9.2 Dashboard (Not Implemented)

Future: A cost dashboard showing:
- Daily/weekly/monthly spend
- Cost by skill
- Cost by project
- Trend lines

---

## 10. History

| Date | Change |
|------|--------|
| 2026-01-14 | Created. Initial audit of all 8 skills. |
