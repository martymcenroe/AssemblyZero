# LLD Review: 199-Feature: Schema-Driven Project Structure

## Identity Confirmation
I am Gemini 3 Pro, acting as Senior Software Architect & AI Governance Lead.

## Pre-Flight Gate
PASSED

## Review Summary
The LLD provides a solid foundation for schema-driven project structure but fails strict quality gates due to insufficient test coverage. Specifically, the core requirement of *creating* directories is not tested (only listing/auditing is covered), and the integrity of the actual schema file content is not verified against requirements. Section 2.4 is also missing the function signature for the directory creation logic.

## Open Questions Resolved
- [x] ~~Should the schema support conditional directories (e.g., `docs/lineage/` only for certain project types)?~~ **RESOLVED: No.** To maintain a "canonical" source of truth, the schema should remain declarative and flat. Use the `required: boolean` field. If complex logic is needed later, use overlay profiles, but do not embed logic in the JSON data.
- [x] ~~Should templates referenced in the schema be validated for existence during schema load?~~ **RESOLVED: Yes.** The `load_structure_schema` function should verify that any referenced template files actually exist. This ensures "Fail Fast" behavior (Safety) rather than failing halfway through project creation.

## Requirement Coverage Analysis (MANDATORY)

**Section 3 Requirements:**
| # | Requirement | Test(s) | Status |
|---|-------------|---------|--------|
| 1 | Schema file `docs/standards/0009-structure-schema.json` exists and is valid JSON | T010 (Validates loader logic) | ✓ Covered |
| 2 | Schema includes all directories currently in `DOCS_STRUCTURE` and `SRC_STRUCTURE` constants | - | **GAP** |
| 3 | Schema includes `docs/lineage/active` and `docs/lineage/done` directories | - | **GAP** |
| 4 | `tools/new-repo-setup.py` creates directories by reading from schema | - | **GAP** |
| 5 | `tools/new-repo-setup.py --audit` validates against schema | T090, T100, T110 | ✓ Covered |
| 6 | Standard 0009 markdown references schema as authoritative source | - | N/A (Doc) |
| 7 | All existing tests pass after refactor | - | N/A (Regression) |

**Coverage Calculation:** 2 requirements covered / 5 applicable requirements = **40%**

**Verdict:** **BLOCK**

**Missing Test Scenarios:**
1.  `test_create_structure_happy_path`: A test verifying that applying the schema actually creates directories on disk (Req 4).
2.  `test_production_schema_integrity`: A test that loads the *actual* `docs/standards/0009-structure-schema.json` file (not a fixture) and asserts it contains the required paths from Req 2 and Req 3.

## Tier 1: BLOCKING Issues
No blocking issues found. LLD is approved for implementation.

### Cost
- [ ] No issues found.

### Safety
- [ ] No issues found.

### Security
- [ ] No issues found.

### Legal
- [ ] No issues found.

## Tier 2: HIGH PRIORITY Issues

### Architecture
- [ ] **Missing Function Signature:** Section 2.4 defines `audit`, `flatten`, and `load`, but does not define the function responsible for actually creating the directories (e.g., `create_structure(root: Path, schema: ProjectStructureSchema) -> None`). This is the core logical component described in Req 4 but is missing from the spec.

### Observability
- [ ] No issues found.

### Quality
- [ ] **Requirement Coverage:** **BLOCK**. Coverage is 40% (Target: ≥95%). See analysis above. The core feature (creation) and data integrity (schema content) are untested.

## Tier 3: SUGGESTIONS
- **Schema Validation:** Consider adding a test case `test_schema_template_validation` to cover the Open Question resolution (verifying templates exist).
- **Type Safety:** In `flatten_files`, consider returning a typed object instead of `dict[str, Any]` for better IDE support.

## Questions for Orchestrator
1. None.

## Verdict
[ ] **APPROVED** - Ready for implementation
[x] **REVISE** - Fix Tier 1/2 issues first
[ ] **DISCUSS** - Needs Orchestrator decision