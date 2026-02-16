# LLD Review: #199 - Feature: Schema-driven project structure: eliminate tool/standard drift

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD proposes a solid schema-driven approach to standardize project structure, eliminating drift between documentation and tooling. The technical approach using a recursive JSON schema is sound and follows architectural standards. However, the Testing Strategy (Section 10) falls significantly below the 95% coverage threshold for Requirements defined in Section 3, specifically missing integration tests for the tool itself and content validation for the golden schema. This requires revision before implementation.

## Open Questions Resolved
- [x] ~~Should the schema support conditional directories (e.g., `docs/lineage/` only for certain project types)?~~ **RESOLVED: No.** Keep the schema declarative and simple for v1. Use the `required: false` flag for optional directories. Conditional logic adds unnecessary complexity at this stage.
- [x] ~~Should we version the schema and support migrations between versions?~~ **RESOLVED: Yes to versioning, No to automated migrations.** Include a `version` field (as proposed) to enable future compatibility checks, but do not build automated migration logic (e.g., moving files) in this iteration.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Schema file `docs/standards/0009-structure-schema.json` exists and is valid JSON | T090 (Input: Actual schema file) | ✓ Covered |
| 2 | Schema includes all directories currently in `DOCS_STRUCTURE` list | - | **GAP** |
| 3 | Schema includes `docs/lineage/` with `active/` and `done/` subdirectories | T090 | ✓ Covered |
| 4 | `new-repo-setup.py` reads structure from schema (no hardcoded directory lists) | - | **GAP** |
| 5 | `new-repo-setup.py --audit` validates against schema | T070, T080 | ✓ Covered |
| 6 | Standard 0009 references the schema as the authoritative source | N/A (Documentation) | - |
| 7 | Existing functionality preserved (setup creates same directories as before) | - | **GAP** |

**Coverage Calculation:** 3 requirements covered / 6 testable requirements = **50%**

**Verdict:** BLOCK

**Missing Test Scenarios:**
1.  **Req 2 (Parity):** `test_schema_content_parity` - A test that asserts specific "golden" paths (e.g., `docs/standards`, `tools`) exist in the actual schema file.
2.  **Req 4 (Integration):** `test_tool_integration_load` - A test (mocking `sys.argv`) that runs `new-repo-setup.py` and verifies it actually calls `load_structure_schema`.
3.  **Req 7 (Creation):** `test_directory_creation` - A test verifying that `os.makedirs` is called for paths defined in a test schema (mocked execution).

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found. Recursive depth is naturally limited by JSON tree structure (DAG).

### Safety
- [ ] No issues found. Safe directory creation (`exist_ok=True`) specified.

### Security
- [ ] No issues found. Path traversal mitigation included.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] No issues found. Path structure `docs/standards/0009-structure-schema.json` is compliant.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** BLOCK. Coverage is 50%, well below the 95% threshold. Add the missing test scenarios listed in the Coverage Analysis above to Section 10.
- [ ] **Section 10.1 Scenarios:** Current scenarios (T010-T090) focus entirely on the *library functions* (loading/auditing). There are no scenarios testing the *application logic* (the script execution itself).

## Tier 3: SUGGESTIONS
- **Performance:** Consider caching the schema load if the tool ever evolves into a long-running process (currently ephemeral, so not critical).
- **Maintainability:** Add a comment in `new-repo-setup.py` pointing to the schema file location to aid future developers.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision