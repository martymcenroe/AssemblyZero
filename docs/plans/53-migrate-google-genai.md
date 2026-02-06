# Plan: Evaluate Issue #53 - Migrate from google.generativeai to google.genai

## Should We Do This Now?

### Current Situation Assessment

**Main Branch Status:** 741a921 (STABLE & WORKING)
- ✓ Workflow completing successfully
- ✓ Template fixes in place
- ✓ Gemini API calls working (6-7 minute responses)
- ⚠️ Deprecation warnings appearing but non-blocking

**Issue #53 Status:** Open since earlier
- Tracked migration from deprecated `google.generativeai` to `google.genai`
- Package support ended, no future bug/security fixes
- Deprecation deadline: August 31, 2025

### Arguments FOR Migrating Now

1. **Stable Base**: Main branch is working, good time for maintenance
2. **Dependency Ready**: langchain-google-genai v4.2.0 (Jan 13, 2026) already migrated to google-genai
3. **Timeline Pressure**: Deprecation happened August 2025, we're 5 months past deadline
4. **Clean Warnings**: Removes FutureWarning noise from logs
5. **Security**: No more security/bug fixes for deprecated package

### Arguments AGAINST Migrating Now

1. **"If it ain't broke"**: System just stabilized after debugging session
2. **Testing Burden**: Requires thorough testing of credential rotation logic
3. **Risk of Regression**: Error pattern matching might break
4. **User Focus**: May want to work on features, not maintenance
5. **Unknown Unknowns**: New SDK might have subtle behavioral changes

### Recommendation: **DEFER TO LATER** ⏸️

**Reasoning:**
- User just recovered from a difficult debugging session where multiple issues compounded
- Workflow is finally stable and delivering value
- Migration risk is **medium-high** due to complex error handling and credential rotation
- No immediate forcing function (API still works, just deprecated)
- Better to batch with other maintenance work or during planned downtime

**Suggested Trigger Points for Future Migration:**
1. **After Feature Milestone**: When user completes current feature work
2. **Planned Maintenance Window**: During scheduled refactoring time
3. **Forcing Function**: If deprecated API actually stops working
4. **Batched Work**: Combine with other dependency updates

---

## If We Decide to Proceed: Migration Plan

### Phase 1: Preparation (Read-Only Research)

**Research Tasks:**
1. Read official migration guide: https://ai.google.dev/gemini-api/docs/migrate
2. Review google-genai package docs: https://googleapis.github.io/python-genai/
3. Check langchain-google-genai 4.2.0 changelog for breaking changes
4. Document API differences in detail

**Expected Findings:**
- Client instantiation pattern changes
- Model creation pattern changes
- Response structure may differ
- Error messages/types may change

### Phase 2: Worktree Setup (MANDATORY)

```bash
# Create worktree for issue #53
git worktree add ../AssemblyZero-53-migrate-genai -b 53-migrate-google-genai

# Push branch immediately
git -C ../AssemblyZero-53-migrate-genai push -u origin HEAD

# Work ONLY in worktree, never in main
cd ../AssemblyZero-53-migrate-genai
```

### Phase 3: Code Changes

**Files to Modify:**

1. **`pyproject.toml`**
   - Change: `google-generativeai (>=0.8.6,<0.9.0)` → `google-genai (>=1.0.0,<2.0.0)`
   - Update: `langchain-google-genai` to `>=4.2.0,<5.0.0`
   - Run: `poetry lock && poetry install`

2. **`assemblyzero/core/gemini_client.py`** (Critical Changes)

   **Import (Line 21):**
   ```python
   # OLD:
   import google.generativeai as genai

   # NEW:
   from google import genai
   ```

   **Configuration (Line 229):**
   ```python
   # OLD:
   genai.configure(api_key=cred.key)
   model = genai.GenerativeModel(...)

   # NEW:
   client = genai.Client(api_key=cred.key)
   # Store client reference for reuse
   ```

   **Model Usage (Lines 232-238):**
   ```python
   # OLD:
   model = genai.GenerativeModel(
       model_name=self.model,
       system_instruction=system_instruction,
   )
   response = model.generate_content(content)

   # NEW:
   # Research needed: exact API pattern for generate_content
   # Likely: client.models.generate_content(model=..., contents=...)
   ```

   **Response Parsing (Line 241):**
   ```python
   # Verify response.text still exists in new SDK
   # If not, find equivalent accessor
   ```

3. **`tests/test_gemini_client.py`** (Update Mocks)

   **Mock Paths (Lines 197-198, 240-241, 265-266):**
   ```python
   # OLD:
   with patch("google.generativeai.configure") as mock_configure:
       with patch("google.generativeai.GenerativeModel") as mock_model_class:

   # NEW:
   with patch("google.genai.Client") as mock_client_class:
       # Update mock structure to match new API
   ```

### Phase 4: Critical Testing Areas

**1. Error Classification Testing**
```python
# Test that these patterns still match:
# - QUOTA_EXHAUSTED (429)
# - CAPACITY_EXHAUSTED (529, 503, 504)
# - AUTH_ERROR (401, 403)
```

**Risk**: New SDK might use different error messages/types
**Mitigation**: Capture real error responses and verify patterns

**2. Credential Rotation Testing**
```python
# Test multi-credential rotation:
# 1. First credential hits quota → rotates
# 2. Second credential succeeds
# 3. State file updates correctly
```

**Risk**: Client instantiation per-credential might behave differently
**Mitigation**: Test with real credentials in dev environment

**3. Backoff Logic Testing**
```python
# Test capacity exhaustion:
# 1. Trigger 529 error
# 2. Verify exponential backoff
# 3. Verify retry with same credential
```

**Risk**: Backoff timing might change
**Mitigation**: Add explicit timing assertions

**4. Model Verification Testing**
```python
# Verify Pro-tier model enforcement:
# - gemini-3-pro-preview works
# - gemini-2.0-flash rejected
# - Model name in response matches request
```

**Risk**: Model naming conventions might change
**Mitigation**: Test with actual API calls

### Phase 5: Integration Testing

**Test Scenarios:**
1. Run full issue workflow with real credentials
2. Trigger quota exhaustion (use up free tier)
3. Test OAuth credential (if supported)
4. Verify audit logging captures correct model name
5. Confirm error messages are actionable

**Success Criteria:**
- All 35 unit tests pass
- Full workflow completes successfully
- Credential rotation triggers correctly
- Error messages remain informative
- No regression in functionality

### Phase 6: Documentation Updates

**Files to Update:**
- Issue #53 (close with implementation details)
- Issue #50 implementation report (note migration)
- Any LLD docs referencing the old package

---

## Risk Mitigation Strategy

### High Risk: Error Pattern Matching Breaks

**Current Dependency:**
```python
QUOTA_EXHAUSTED_PATTERNS = ["TerminalQuotaError", "429", ...]
CAPACITY_PATTERNS = ["MODEL_CAPACITY_EXHAUSTED", "529", ...]
```

**Mitigation:**
1. Capture real error responses from new SDK
2. Update patterns if needed
3. Add comprehensive error logging during testing
4. Keep old patterns as fallback if possible

### Medium Risk: Response Structure Changes

**Current Dependency:**
```python
response.text  # Direct attribute access
```

**Mitigation:**
1. Check new SDK docs for response object structure
2. Add defensive access with getattr() if needed
3. Test with various response types

### Medium Risk: langchain-google-genai Breaking Changes

**Known Changes (v4.0.0):**
- Dropped gRPC transport (REST only)
- Changed `with_structured_output` default method

**Mitigation:**
1. Review v4.2.0 changelog thoroughly
2. Test langchain integration if used elsewhere
3. Pin exact version in pyproject.toml

---

## Verification Steps (Post-Implementation)

1. **Unit Tests**: All 35 tests in `test_gemini_client.py` pass
2. **Real API Test**: Run `tools/gemini-test-credentials.py` (uses CLI, not SDK)
3. **Workflow Test**: Complete one full issue creation cycle
4. **Rotation Test**: Manually exhaust one credential's quota
5. **Error Test**: Force 529 error and verify backoff
6. **Audit Test**: Verify model name appears correctly in verdicts

---

## Sources

Migration documentation:
- [Migrate to Google GenAI SDK](https://ai.google.dev/gemini-api/docs/migrate)
- [Medium: Migrating to the new Google Gen AI SDK](https://medium.com/google-cloud/migrating-to-the-new-google-gen-ai-sdk-python-074d583c2350)
- [Google Gen AI SDK Docs](https://googleapis.github.io/python-genai/)
- [langchain-google-genai 4.0.0 Release](https://github.com/langchain-ai/langchain-google/discussions/1422)

Deprecated SDK:
- [Deprecated SDK GitHub](https://github.com/google-gemini/deprecated-generative-ai-python)

---

## Timeline Estimate (If Approved)

- **Phase 1 (Research)**: 2-3 hours
- **Phase 2 (Setup)**: 15 minutes
- **Phase 3 (Code Changes)**: 3-4 hours
- **Phase 4 (Testing)**: 4-6 hours
- **Phase 5 (Integration)**: 2-3 hours
- **Phase 6 (Documentation)**: 1 hour

**Total**: 12-17 hours over 2-3 days

**Complexity**: Medium-High (requires careful testing, real API calls, credential exhaustion testing)
