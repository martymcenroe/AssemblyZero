---
repo: martymcenroe/AssemblyZero
issue: 304
url: https://github.com/martymcenroe/AssemblyZero/issues/304
fetched: 2026-02-16T08:50:56.541809Z
---

# Issue #304: feat: Implementation Readiness Review workflow (LLD → Implementation Spec)

## Summary

Create a new workflow that transforms an approved LLD into an **Implementation Spec** - a document with enough concrete detail that an AI implementation workflow can execute autonomously without guessing or discovering state.

## The Gap

Our current LLD review checks for *design quality*:
- Requirement coverage (95%+)
- Safety/security concerns addressed
- Test scenarios defined
- Architecture decisions documented

But it does NOT verify the LLD contains enough detail for **autonomous implementation**:
- No concrete data examples (just TypedDicts, no actual JSON)
- No "current state" snapshots (what does the code look like now?)
- No line-by-line diff guidance
- Abstract pseudocode instead of pattern-matched transformations

**Result:** LLDs pass review but implementations struggle, requiring multiple iterations or human intervention.

## Proposed Solution

Add an **Implementation Readiness Review** workflow between LLD approval and implementation:

```
Issue → LLD → [LLD Review] → Approved LLD → [Impl Readiness Review] → Implementation Spec → [Implementation]
```

### New Artifact: Implementation Spec

The Implementation Spec extends the approved LLD with:

1. **Concrete Data Examples**
   - Actual JSON/YAML samples, not just schema definitions
   - Real values, not placeholders

2. **Current State Snapshots**
   - Relevant excerpts from files being modified
   - The specific constants, functions, or patterns being changed
   - "Before" state so AI knows what to transform

3. **Diff Guidance**
   - Line-level or block-level change descriptions
   - "Replace X with Y" instead of "modify to support Z"

4. **Pattern Anchoring**
   - References to existing code patterns in the repo
   - "Follow the pattern in `similar_module.py:45-60`"

5. **Dependency Chain**
   - Exact order of file modifications
   - What must exist before each step can proceed

### Workflow Design

```
Nodes:
  N0: Load approved LLD
  N1: Analyze codebase for current state (read files mentioned in 2.1)
  N2: Generate implementation spec draft (Claude)
  N3: Validate mechanical completeness
  N4: Human gate (optional)
  N5: Review spec (Gemini - different prompt than LLD review)
  N6: Finalize spec

Routing:
  N3 BLOCKED → N2 (regenerate)
  N5 REVISE → N2 (regenerate)
  N5 APPROVED → N6 (finalize)
```

### Implementation Readiness Review Criteria (Gemini)

Different from LLD review - focused on executability:

- [ ] Every "Modify" file has current state excerpt included
- [ ] Every data structure has concrete example (not just types)
- [ ] Every function has input/output examples
- [ ] Change instructions are specific enough to generate a diff
- [ ] No "implement X" without specifying HOW
- [ ] References to existing patterns are valid (file:line exists)

## Files to Create

| File | Purpose |
|------|---------|
| `assemblyzero/workflows/implementation_spec/` | New workflow module |
| `assemblyzero/workflows/implementation_spec/graph.py` | LangGraph definition |
| `assemblyzero/workflows/implementation_spec/state.py` | State definition |
| `assemblyzero/workflows/implementation_spec/nodes/` | Node implementations |
| `docs/standards/XXXX-implementation-spec-template.md` | Template for specs |
| `prompts/implementation_spec/` | Drafter and reviewer prompts |

## Success Criteria

1. Implementation Specs contain enough detail that implementation workflow succeeds on first try (>80% of the time)
2. Reduced back-and-forth in implementation phase
3. Clear separation: LLD = design decisions, Spec = execution instructions

## Related

- #139 - When implementing, also rename workflows/testing/ to workflows/implementation/
- Depends on requirements workflow being stable (it is now after #299, #301, #303)

## Labels

`enhancement`, `workflow`, `priority:high`