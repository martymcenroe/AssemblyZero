# LLD-to-Code Alignment Audit

## Purpose

Verify that implemented code matches the LLD specification, or that deviations are properly documented in the Implementation Report. Catches:
- Implementations that diverged without documentation
- LLDs that weren't updated after changes
- Missing function signatures or interfaces

## Trigger

- Before closing any implementation issue
- After major refactoring of existing features
- When updating an LLD for a new phase

**Note:** This audit applies to **Feature LLDs** that produce code. **Implementation Plans** for process/config changes are self-contained and do not require code alignment audits.

## Procedure

### Step 1: Identify LLD and Implementation

```bash
# For issue #121, find:
# LLDs live in docs/lld/active/ (in-progress) or docs/lld/done/ (complete)
LLD="docs/lld/done/1121-feature-name.md"
IMPL="src/feature.py"
TESTS="tests/test_feature.py"
REPORT="docs/reports/done/121-implementation-report.md"
```

### Step 2: Extract LLD Promises

From the LLD, extract:
1. **Function signatures** - Names, parameters, return types
2. **Data structures** - JSON schemas, class definitions
3. **Behaviors** - What each function should do
4. **Test scenarios** - IDs and descriptions from test section

### Step 3: Compare Against Implementation

| LLD Section | Check | How to Verify |
|-------------|-------|---------------|
| Function signatures | Exact match | `grep "def function_name" impl.py` |
| Parameters | Type hints match | Read function definitions |
| Return types | Match spec | Check return statements |
| Error handling | Documented cases covered | Check except blocks |
| Test scenarios | All have tests | Match test IDs to LLD IDs |

### Step 4: Document Findings

| Finding Type | Action |
|--------------|--------|
| Implementation matches LLD | Note "No deviations" in report |
| Implementation deviates | Document in Implementation Report |
| LLD outdated | Update LLD on main |
| Missing test coverage | Add tests or document gap |

### Step 5: Update Implementation Report

If deviations found, add to implementation report:

```markdown
## Deviations from LLD

| Deviation | Reason | Impact |
|-----------|--------|--------|
| Added parameter | Better API ergonomics | None |
| Changed rate limit | More conservative | Slower but safer |
```

## Checklist

- [ ] All function signatures in LLD exist in code
- [ ] Parameter types match
- [ ] Return types match
- [ ] Error handling cases covered
- [ ] Each LLD test scenario has a test function
- [ ] Deviations documented in Implementation Report
- [ ] LLD updated if interface changed
- [ ] **LLD moved from `active/` to `done/`** (when issue closes)

## LLD Lifecycle Management

**MANDATORY:** When closing an issue, move its LLD from `active/` to `done/`.

```bash
git mv docs/lld/active/1121-feature-name.md docs/lld/done/
```

## Output Format

```markdown
## LLD-to-Code Alignment Audit - Issue #{ID}

### Files Compared
- **LLD:** `docs/lld/{active|done}/1{ID}-feature.md`
- **Implementation:** `path/to/impl.py`
- **Tests:** `tests/test_feature.py`

### Alignment Status
- Function signatures: ✅ Match
- Parameters: ✅ Match
- Return types: ⚠️ Deviation (documented)
- Test coverage: ✅ All scenarios covered

### Deviations Found
| LLD Says | Code Does | Documented? |
|----------|-----------|-------------|
| 0.5s rate limit | 1.0s rate limit | ✅ Yes |

### Remediation
- [x] Updated Implementation Report
- [ ] N/A - LLD update not needed
```

---

*Template from: AssemblyZero/.claude/templates/docs/lld-code-audit.md*
