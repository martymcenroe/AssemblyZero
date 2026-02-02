# 0847 - Implementation Completeness Audit

Audit for detecting stub implementations, fake tests, broken features, and documented-but-not-implemented code.

## 1. Purpose

This audit exists because Claude consistently:
- Claims to scan but only does superficial grep
- Claims "zero problems" when problems exist
- Ignores evidence in its own context
- Requires multiple corrections to do thorough work

The explicit structure removes wiggle room.

---

## 2. Rules (NON-NEGOTIABLE)

1. **NO SHORTCUTS** - Run EVERY search listed below. Do not skip any.
2. **NO WEASEL WORDS** - Do not say "appears to be fine" or "likely complete". Say "FOUND" or "NOT FOUND".
3. **EVIDENCE REQUIRED** - Every finding must include exact `FILE:LINE` references.
4. **NO FALSE NEGATIVES** - When in doubt, FLAG IT. Let the human decide if it's a real problem.
5. **CREATE ISSUES** - After the scan, create a GitHub issue for EACH finding.
6. **NO EXCUSES** - Do not claim you "can't" do something. Figure it out.

---

## 3. Category 1: Stub Implementations

### 3.1 Required Searches

Run ALL of these:

```bash
# Empty function bodies
Grep: ^\s*pass\s*$
Grep: ^\s*\.\.\.\s*$
Grep: raise NotImplementedError

# Documented but not implemented
Grep: # TODO
Grep: # FIXME
Grep: # XXX
Grep: # HACK
Grep: not implemented
Grep: not yet implemented
```

### 3.2 Classification

For EACH `pass` or `...` found, READ the surrounding context and classify:

| Classification | Criteria |
|----------------|----------|
| **STUB** | Function does nothing but should do something |
| **LEGITIMATE** | Exception handler, abstract method, or intentional no-op |

### 3.3 Report Format

```
FILE:LINE - [STUB|LEGITIMATE] - reason
```

**Example:**
```
agentos/core/coordinator.py:76 - STUB - Comment says "For testing purposes"
agentos/core/provider.py:63 - LEGITIMATE - Abstract method in ABC
```

---

## 4. Category 2: Argparse Flags Never Used

### 4.1 Procedure

For EVERY Python file with argparse:

1. List ALL arguments defined with `add_argument`
2. Search the file for `args.ARGNAME` usage
3. If argument is defined but never used → **FLAG IT**

### 4.2 Report Format

```
FILE: --flag-name DEFINED line X, USED: [YES at line Y | NO - NEVER USED]
```

**Example:**
```
tools/run_requirements_workflow.py: --select DEFINED line 90, USED: NO - NEVER USED
tools/run_scout_workflow.py: --offline DEFINED line 45, USED: YES at line 112
```

---

## 5. Category 3: Fake Tests

### 5.1 Required Searches (tests/ directory)

```bash
# Tautological assertions
Grep: assert True
Grep: assert.*is not None\s*$

# Skip abuse
Grep: pytest\.skip\(
Grep: @pytest.mark.skip

# Mock everything
Grep: with patch.*:
```

### 5.2 Classification

| Pattern | Check | Flag If |
|---------|-------|---------|
| `assert X is not None` | Other assertions after it? | NO → WEAK TEST |
| `pytest.skip()` | Has reason string? | NO → SKIP ABUSE |
| `with patch` | Count per test file | >5 patches → MOCK HEAVY |

### 5.3 Report Format

```
FILE:LINE - [WEAK|SKIP_ABUSE|MOCK_HEAVY] - description
```

---

## 6. Category 4: Documented But Broken

### 6.1 Required Searches

```bash
# Docstrings promising behavior
Grep: """.*will.*"""
Grep: """.*should.*"""
Grep: """.*must.*"""

# Comments claiming implementation
Grep: # In a real implementation
Grep: # For testing purposes
Grep: # TODO: implement
```

### 6.2 Verification

For EACH match, verify the code ACTUALLY DOES what the docstring/comment claims.

### 6.3 Report Format

```
FILE:LINE - DOCSTRING SAYS: "X" - CODE DOES: "Y" - [MATCH|MISMATCH]
```

---

## 7. Category 5: Mock Mode / Offline Mode Failures

### 7.1 Required Searches

```bash
Grep: if.*mock
Grep: if.*offline
Grep: if.*test.*mode
Grep: load_fixture
```

### 7.2 Verification

For EACH match, verify:

| Check | Requirement |
|-------|-------------|
| Fixture file exists | Path resolves to actual file |
| Missing fixture handling | Does NOT silently return `[]` or `{}` |
| Error handling exists | Clear error message if fixture missing |

### 7.3 Report Format

```
FILE:LINE - mock/offline branch - fixture: NAME - [EXISTS|MISSING|SILENT_FAIL]
```

---

## 8. Category 6: Feature Flags Without Implementation

### 8.1 Required Searches

```bash
Grep: if.*feature
Grep: if.*enabled
Grep: if.*flag
Grep: config\.get\(
```

### 8.2 Verification

Trace each flag to verify it actually changes behavior.

---

## 9. Output Format

After completing ALL searches, produce this summary:

```markdown
## SCAN RESULTS FOR [REPO NAME]

### CRITICAL (must fix immediately)
- [ ] FILE:LINE - description

### HIGH (broken functionality)
- [ ] FILE:LINE - description

### MEDIUM (incomplete features)
- [ ] FILE:LINE - description

### LOW (code quality)
- [ ] FILE:LINE - description

### FALSE POSITIVES INVESTIGATED
- FILE:LINE - why it's actually fine

### SEARCHES COMPLETED
- [ ] Category 1: Stub implementations
- [ ] Category 2: Argparse flags
- [ ] Category 3: Fake tests
- [ ] Category 4: Documented but broken
- [ ] Category 5: Mock mode failures
- [ ] Category 6: Feature flags

### ISSUES TO CREATE
1. Title - severity - FILE:LINE
2. Title - severity - FILE:LINE
...
```

---

## 10. Post-Scan Actions (MANDATORY)

1. **CREATE GITHUB ISSUES** for each finding
2. **DO NOT** combine findings into one meta-issue
3. **DO NOT** skip creating issues because "there are too many"
4. **DO NOT** ask if issues should be created - just create them

---

## 11. Verification

If you claim "no problems found" without showing actual grep results, you are lying.

The scan results are verifiable. The human can run the same greps and check your work.

**Do the work. Show the evidence. Create the issues.**

---

## 12. Quick Version (Subsequent Scans)

If this repo has been scanned before, run at minimum:

```bash
# New code since last scan
git diff --name-only HEAD~10 -- "*.py" | xargs grep -n "pass$\|TODO\|FIXME\|NotImplemented"

# Verify previous issues are fixed
gh issue list --state open --label bug
```

---

## 13. Audit Record

| Date | Auditor | Findings Summary | Issues Created |
|------|---------|------------------|----------------|
| 2026-02-02 | Claude Opus 4.5 | FAIL: 8 findings | #149, #150, #151, #152, #153, #154, #155, #156 |

---

## 14. References

- Issue #147 (Completeness Gate design)
- Issues #149-156 (Findings from first scan)

---

*Source: AgentOS/docs/audits/0847-audit-implementation-completeness.md*
*This audit exists because Claude needs explicit constraints to do thorough work.*
