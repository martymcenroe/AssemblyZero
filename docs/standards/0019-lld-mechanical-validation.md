# LLD Mechanical Validation Criteria

<!-- Standard: 0019 -->
<!-- Version: 1.0 -->
<!-- Last Updated: 2026-05-09 -->
<!-- Issue: #1066 -->

> **Purpose:** Document the structural checks that every LLD draft must pass before the LLD workflow accepts an APPROVED verdict. These checks are implemented in `assemblyzero/workflows/requirements/nodes/validate_mechanical.py` (Issue #277). They are deterministic, run without LLM calls, and execute on every drafter iteration. Until this standard existed, the criteria lived only in code — operators and reviewers had no rubric to consult when a draft was BLOCKED.

---

## 1. Overview

The mechanical validator is a node (`N1.5`) in the LLD requirements graph. It runs after the drafter (`N1`) produces a draft and before the Gemini reviewer (`N3`) evaluates it. Its job is to catch structural failures cheaply — typos in section headers, hallucinated file paths, missing mandatory sections — without burning LLM tokens.

A draft that fails mechanical validation never reaches the reviewer. The workflow loops back to `N1` with the validation errors embedded in the revision context, up to the configured `max_iterations` (default 20). The validator returns BLOCKED on errors and PENDING on success.

### 1.1 Position in the Workflow

```
N0 load_input → N1 generate_draft → N1.5 validate_mechanical → N3 review (Gemini)
                       ^                       |
                       |                       | (BLOCKED)
                       +-----------------------+
                          (revise on errors,
                           up to max_iterations)
```

### 1.2 Severity Levels

| Severity | Effect | Status set |
|---|---|---|
| **ERROR** | Blocks the workflow; loops back to N1 with the error message in revision context | `lld_status: BLOCKED` |
| **WARNING** | Logged to console; saved to audit trail; does NOT block | `lld_status: PENDING` |

---

## 2. The Eleven Checks

The validator runs eleven structural checks. Nine are ERROR-severity (blocking); two are WARNING-severity (advisory). Each check is implemented as a focused function in `validate_mechanical.py`.

### 2.1 Check 1 — Non-Empty Draft Content (ERROR)

**Implementation:** Inline in `validate_lld_mechanical()`.

**What it checks:** The `current_draft` field of the workflow state is non-empty after `.strip()`.

**Pass:** Any non-whitespace content present in `current_draft`.

**Fail:** Empty string, whitespace-only string, or missing key.

**Failure message:** `LLD content is empty`

**Why it exists:** The drafter can fail silently (API error, malformed response) and return an empty draft. Without this check, downstream parsing logic raises confusing errors that obscure the real cause.

### 2.2 Check 2 — Mandatory Sections Present (ERROR)

**Implementation:** `validate_mandatory_sections()`.

**What it checks:** The LLD content contains all three of the following exact substrings:

| Heading | Level | Section |
|---|---|---|
| `### 2.1` | h3 | Files Changed table |
| `## 11` | h2 | Risks |
| `## 12` | h2 | Definition of Done |

**Pass:** All three substrings present anywhere in the document.

**Fail:** Any one missing.

**Failure message:** `Critical: Section {N} missing from LLD`

**Why it exists:** These three sections back the four downstream checks (table parsing, file-path validation, cross-reference, risk traceability). Missing one fails the rest with cryptic errors. Failing fast here gives the drafter a clear actionable signal.

**Important:** The check is a literal substring match. `### 2.1.` (with trailing period) does NOT match `### 2.1`. The drafter must produce the exact heading.

### 2.3 Check 3 — Title Issue Number Matches Workflow Issue (ERROR + WARNING)

**Implementation:** `validate_title_issue_number()` (Issue #306).

**What it checks:** The H1 line of the LLD contains the issue number that matches the workflow's `issue_number` state field.

**Supported title formats:**

| Title | Extracted | Notes |
|---|---|---|
| `# 306 - Feature: Title` | 306 | Standard hyphen |
| `# 099 – Title` | 99 | Leading zeros stripped, en-dash |
| `# 99 — Title` | 99 | Em-dash |

**Regex:** `^#\s+0*(\d+)\s+[-–—]` (multiline)

**Pass:** Extracted number equals `state["issue_number"]`.

**Fail (ERROR):** Extracted number ≠ expected number. Message: `Title issue number ({extracted}) doesn't match workflow issue ({expected})`.

**Fail (WARNING):** No H1 found, or H1 present but issue number unparseable. Messages: `No H1 title found in LLD`, `Could not extract issue number from title`.

**Why it exists:** A drafter cross-pollination bug (running on issue #N but writing `# 0M -` due to context bleed) had been observed in production. This check catches it deterministically before any reviewer wastes time on the wrong design.

### 2.4 Check 4 — Files Changed Table Parses (ERROR)

**Implementation:** `parse_files_changed_table()` + `normalize_change_type()` (Issue #334).

**What it checks:** Section 2.1 (`### 2.1` heading) contains a markdown table with at least one valid data row after the header.

**Valid change types** (case-insensitive, after stripping parenthetical suffix): `add`, `modify`, `create`, `update`, `delete`, `remove`.

**Parenthetical suffix handling** (Issue #334): `Add (Directory)` is normalized to base type `add` with `is_directory=True`. The same applies for `Modify (Directory)`, etc.

**Path validity for table inclusion:** The path column must contain `/`, `.`, or `\\` (a path-like character) UNLESS the row is marked as a directory.

**Pass:** ≥1 data row matches the regex AND has a valid normalized change type AND a path-like value.

**Fail:** No matches. Common causes: header-only table, malformed markdown pipes, change-type values outside the valid set, paths without separators.

**Failure messages:**
- `Section 2.1 not found or malformed`
- `Section 2.1 table malformed or empty - no file entries found`

**Why it exists:** The Files Changed table is the source of truth for downstream checks. If parsing fails, the validator cannot run checks 6, 7, 8, 9 — so it fails fast here.

### 2.5 Check 5 — Repo Root Valid (ERROR)

**Implementation:** `validate_repo_root()` + `validate_file_paths_with_repo_check()` (Issue #322).

**What it checks:** The `target_repo` field of the workflow state is a usable filesystem path.

**Pass criteria (all required):**
- Not `None`.
- Not empty string, whitespace-only, or `.`.
- Path exists on disk (`Path.exists()` returns True).

**Failure messages:**
- `Cannot validate file paths: target_repo not specified` (None)
- `Cannot validate file paths: target_repo not specified (empty value)` (empty/whitespace/`.`)
- `Cannot validate file paths: target_repo '{path}' does not exist` (non-existent path)

**Why it exists:** Earlier behavior silently skipped path validation when `target_repo` was missing — letting hallucinated paths through to implementation. Issue #322 made the missing-repo case a blocking ERROR with explicit messaging.

### 2.6 Check 6 — Directory Creation Order (ERROR)

**Implementation:** `validate_directory_creation_order()` (Issue #334).

**What it checks:** When a directory is declared with `Add (Directory)`, files inside that directory must appear AFTER the directory entry in the Files Changed table — not before, not interleaved.

**Why ordering matters:** The implementation workflow walks the table in order to apply changes. A file declared before its parent directory means the parent doesn't exist when the file is created.

**Pass:** Every `Add` file row whose parent path is in the set of `Add (Directory)` declarations appears AFTER that directory's row.

**Fail:** Any `Add` file row appears before its declared parent directory.

**Failure message:** `File '{path}' depends on directory '{parent}' which appears later in the table. Reorder entries so directories come before their contents.`

**Why it exists:** Drafters sometimes generate the table top-down by feature ("here are the new files") without thinking about creation order. The implementation workflow will fail when the parent dir doesn't exist, but the failure happens later and is harder to attribute. Catching it pre-flight is cheaper.

### 2.7 Check 7 — File Path Existence and Parents (ERROR)

**Implementation:** `validate_file_paths()` + `find_similar_files()` (Issue #300, Issue #388).

**What it checks:** Each file row in Section 2.1 has consistency between the change type and the filesystem state.

| Change type | Filesystem requirement |
|---|---|
| `Modify` | File MUST exist at `{repo_root}/{path}`. |
| `Delete` | File MUST exist at `{repo_root}/{path}`. |
| `Add` (file) | Parent directory MUST exist OR be in the set of `Add (Directory)` declarations OR be implied by another `Add` file path's parent (Issue #388). |
| `Add` (directory) | Parent directory MUST exist OR be in the set of `Add (Directory)` declarations. |

**Auto-implied parents (Issue #388):** When `Add` declares `new_package/module.py`, the validator implicitly treats `new_package/` as a directory-to-create — even without an explicit `Add (Directory)` row for the package. This handles the common pattern of declaring new module files without separately declaring the package directory.

**Pass:** Every change-type / filesystem combination above is satisfied.

**Fail messages:**
- `File marked Modify but does not exist: {path}` (with optional suggestion: `Did you mean: 'similar/path.py', ...?` — Issue #300)
- `File marked Delete but does not exist: {path}`
- `Parent directory does not exist for Add file: {path}`
- `Parent directory does not exist for Add directory: {path}`

**Suggestions (Issue #300):** When a `Modify` or `Delete` references a non-existent file, the validator searches `tools/`, `assemblyzero/`, `scripts/`, `src/`, `lib/`, `tests/` for files matching the basename — including underscore↔hyphen normalization (`new_repo_setup.py` ↔ `new-repo-setup.py`). Up to 3 suggestions surface in the error message.

**Why it exists:** Hallucinated file paths are the #1 LLD failure mode. The drafter confidently writes `tools/new_repo_setup.py` when the actual file is `tools/new-repo-setup.py`, or invents an entirely fictional file. Filesystem-level validation catches this deterministically; the suggestion engine reduces revision-cycle iterations by pointing the drafter at the real path.

### 2.8 Check 8 — Placeholder Prefixes Match Reality (ERROR)

**Implementation:** `detect_placeholder_prefixes()`.

**What it checks:** Paths starting with `src/`, `lib/`, or `app/` must have a real corresponding directory at `{repo_root}/{prefix}`.

**Pass:** Either the path doesn't start with a placeholder prefix, OR the prefix directory exists in the repo.

**Fail:** Path starts with `src/`, `lib/`, or `app/` AND the directory is missing in the repo.

**Failure message:** `Path uses '{prefix}/' but that directory doesn't exist in repo: {path}`

**Why it exists:** Drafters trained on generic Python/JS conventions reach for `src/...` even when the project doesn't follow that layout. AssemblyZero itself uses `assemblyzero/...` (the package name) as the source root, not `src/`. Catching the prefix mismatch surfaces the convention drift early.

### 2.9 Check 9 — Definition of Done References Match Files Changed (ERROR)

**Implementation:** `cross_reference_sections()` + `extract_files_from_section()`.

**What it checks:** Every file path mentioned in Section 12 (Definition of Done) appears in Section 2.1 (Files Changed). Path detection looks for backtick-wrapped paths (``\`some/path.ext\```) and bare path-like patterns (`word/word/word.ext`).

**Pass:** Every path-like string in Section 12 has a matching row in the Section 2.1 file list.

**Fail:** Section 12 mentions a path that does not appear in Section 2.1.

**Failure message:** `Section 12 references file not in Section 2.1: {path}`

**Filtering:** Only path-like strings with `/` or `\` are reported. Bare filenames without a directory component are skipped to reduce noise (e.g., `pyproject.toml` mentioned conceptually in DoD without a row in 2.1).

**Why it exists:** Drafters sometimes describe "this work is done when X.py passes lint and Y.py is migrated" in DoD without listing those files in 2.1. The result is an LLD that promises changes the implementation workflow won't make. Cross-reference catches the omission deterministically.

### 2.10 Check 10 — Risk Mitigation Traceability (WARNING)

**Implementation:** `trace_mitigations_to_functions()` + `should_warn_missing_function()` + `is_approach_mitigation()` + `contains_explicit_function_reference()` (Issue #312).

**What it checks:** Mitigations in Section 11 (Risks) reference functions defined in Section 2.4 (Function Signatures). When a mitigation explicitly names a function (via backticks, parentheses, or `in func` / `via func` patterns), that function must exist in the LLD's design.

**Smart filtering (Issue #312):** Approach-style mitigations DO NOT trigger warnings even when they don't reference functions:

| Pattern | Examples | Treated as |
|---|---|---|
| Algorithmic complexity | `O(n)`, `O(1)`, `O(log n)` | Approach |
| Encoding | `UTF-8`, `encoding`, `codec` | Approach |
| Configuration practices | `opt-in`, `default unchanged`, `explicitly` | Approach |

When mitigations contain BOTH explicit function references AND approach patterns, explicit references still trigger warnings if unmatched. The approach pattern doesn't override the explicit reference.

**Function reference patterns:**

| Pattern | Example |
|---|---|
| Backticks | `` `function_name` `` |
| Parentheses | `function_name()` |
| Preposition | `in function_name`, `via function_name` |

**Pass:** Mitigation matches a function name (substring match in either direction) OR is approach-style with no explicit function reference.

**Fail (WARNING only):** Explicit function reference present, but the named function isn't in Section 2.4.

**Warning message:** `Risk mitigation has no matching function: '{first 50 chars of mitigation}...'`

**Why it's a warning, not an error:** False positives were common before the smart filter — the validator would warn on every "use UTF-8 encoding" mitigation simply because no function was named. Issue #312 added the approach-pattern detection to suppress those. Even with smart filtering, residual false positives are tolerable, so this stays at WARNING severity.

### 2.11 Check 11 — AST Import Sentinel on Existing Modify Files (WARNING)

**Implementation:** `run_ast_sentinel_on_modify_files()` calling `assemblyzero.utils.ast_sentinel.analyze_file()` (Issue #600).

**What it checks:** For each `Modify` change targeting an existing `.py` file, run an AST analysis to detect symbol references in the file body that don't trace to an import statement.

**Scope:**
- Only `Modify` (not `Add` — file doesn't exist yet) and not `Delete`.
- Only `.py` files (other languages have no AST analyzer here).
- Only files that exist on disk (already validated by check 7).

**Pass:** AST analyzer returns `result.ok == True`.

**Fail (WARNING only):** AST analyzer finds symbols referenced without imports. Each finding produces a warning.

**Warning message:** `AST sentinel: {path} line {N} — symbol '{name}' may not be imported`

**Failure mode:** If the AST analyzer raises an exception (file unparseable, encoding issue), the warning is suppressed and the failure is logged at DEBUG. This is best-effort.

**Why it's a warning, not an error:** Sentinel findings are advisory — sometimes the symbol is defined dynamically, imported via star-import, or referenced in a comment. False positives are tolerated. The signal is a hint to the reviewer that a section may need extra scrutiny.

---

## 3. Side Effects (Audit Trail and Console Output)

The validator produces audit-trail artifacts as a byproduct of running. These are not "checks" — they are observability features.

### 3.1 Lineage Audit File (Issue #334)

**Implementation:** `save_validation_errors_to_lineage()`.

**Triggered:** When validation fails AND `state["lineage_path"]` is set.

**Output path:** `{lineage_path}/validation-errors-draft{NNN}-{TIMESTAMP}.md` (e.g., `validation-errors-draft003-20260509-201534.md`).

**Format:** Markdown with header, timestamp, draft number, error count, then numbered list of error messages. Special characters (`<`, `>`) escaped to prevent log-injection.

**Why:** Future audits and post-mortems can trace what failed at each draft iteration without re-running the workflow.

### 3.2 Console Output

**Implementation:** `print_validation_errors()`.

**Triggered:** Always, when validation fails.

**Format:** Up to 5 errors displayed verbatim; if more, `... and N more error(s)` appended. Bracketed in `=` separators for visual contrast.

**Why:** Operators watching the console see what failed without grepping log files. The 5-item truncation prevents wall-of-text on draft drafts that fail many checks at once.

---

## 4. Verdict Summary

The validator produces one of two outputs:

### 4.1 BLOCKED (any ERROR)

State updates:
```python
{
    "validation_errors": [list of ERROR messages],
    "validation_warnings": [list of WARNING messages],
    "lld_status": "BLOCKED",
    "error_message": "MECHANICAL VALIDATION FAILED:\n  - {error 1}\n  - {error 2}\n...",
}
```

The router loops back to `N1_generate_draft` with the error message in the revision context, up to `max_iterations`.

### 4.2 PENDING (all checks pass; warnings allowed)

State updates:
```python
{
    "validation_errors": [],
    "validation_warnings": [list of WARNING messages],
    "lld_status": "PENDING",  # explicitly clears any prior BLOCKED status
    "error_message": "",
}
```

The router proceeds to `N3_review` (Gemini reviewer). Note that `lld_status` is explicitly set to `"PENDING"` to clear any prior `BLOCKED` status (Issue #302) — without this, a previous Gemini-side BLOCKED from an earlier round could leak into the routing decision.

---

## 5. Failure Mode Reference

When operators see a BLOCKED verdict, this table maps the error message to the underlying check and the typical fix.

| Error message contains | Check | Typical fix |
|---|---|---|
| `LLD content is empty` | 1 | Drafter API error or malformed response. Check N1 logs. |
| `Critical: Section 2.1 missing` | 2 | Drafter omitted Files Changed table heading. Re-prompt. |
| `Critical: Section 11 missing` | 2 | Drafter omitted Risks section. Re-prompt. |
| `Critical: Section 12 missing` | 2 | Drafter omitted Definition of Done section. Re-prompt. |
| `Title issue number ({E}) doesn't match workflow issue ({W})` | 3 | Drafter context bleed; re-run with `--no-cache`. |
| `Section 2.1 not found or malformed` | 4 | Section 2.1 heading present but no parseable table follows. |
| `Section 2.1 table malformed or empty` | 4 | Table header but zero data rows; or invalid change types. |
| `Cannot validate file paths: target_repo not specified` | 5 | Workflow invocation missing `--repo`; re-run with the flag. |
| `target_repo '{path}' does not exist` | 5 | Path typo or wrong drive letter. |
| `File '{path}' depends on directory '{parent}' which appears later` | 6 | Reorder Section 2.1 rows: directory before its contents. |
| `File marked Modify but does not exist: {path}` | 7 | Hallucinated path. Use suggestion if provided; otherwise check actual file location. |
| `Parent directory does not exist for Add ...` | 7 | Add an explicit `Add (Directory)` row, OR confirm an existing parent path. |
| `Path uses '{prefix}/' but that directory doesn't exist` | 8 | Project doesn't use `src/` / `lib/` / `app/`. Use the actual top-level package name. |
| `Section 12 references file not in Section 2.1` | 9 | Either remove the file from DoD prose OR add it to Files Changed. |
| `Risk mitigation has no matching function: ...` | 10 (WARNING) | Add the mitigation's function to Section 2.4 OR rephrase to be approach-style. |
| `AST sentinel: {path} line {N} — symbol '{name}' may not be imported` | 11 (WARNING) | Reviewer should verify whether the symbol is defined or imported elsewhere. |

---

## 6. Audit-by-Grep

Per the issue acceptance: every check in `validate_mechanical.py` must have a corresponding entry here. Sanity-check command:

```bash
grep -E "^def (validate_|parse_|detect_|cross_reference|trace_|run_ast)" \
  assemblyzero/workflows/requirements/nodes/validate_mechanical.py | \
  grep -v "test_"
```

Maps each function to a check section in this document:

| Function | This document |
|---|---|
| `validate_mandatory_sections` | §2.2 (Check 2) |
| `validate_repo_root` + `validate_file_paths_with_repo_check` | §2.5 (Check 5) |
| `parse_files_changed_table` + `normalize_change_type` | §2.4 (Check 4) |
| `validate_directory_creation_order` | §2.6 (Check 6) |
| `validate_file_paths` + `find_similar_files` | §2.7 (Check 7) |
| `detect_placeholder_prefixes` | §2.8 (Check 8) |
| `cross_reference_sections` + `extract_files_from_section` | §2.9 (Check 9) |
| `validate_title_issue_number` + `extract_title_issue_number` | §2.3 (Check 3) |
| `trace_mitigations_to_functions` + `is_approach_mitigation` + `should_warn_missing_function` + `contains_explicit_function_reference` + `extract_mitigations_from_risks` + `extract_function_names` + `extract_keywords` | §2.10 (Check 10) |
| `run_ast_sentinel_on_modify_files` | §2.11 (Check 11) |
| `validate_lld_mechanical` (orchestrator + empty-draft check) | §2.1 (Check 1) + §3 (side effects) |
| `save_validation_errors_to_lineage` | §3.1 |
| `print_validation_errors` | §3.2 |
| `log_skipped_mitigation` | Internal to §2.10 |

When this standard and the code disagree, **the code is authoritative.** Update this standard to match — the standard exists to describe what the code does, not to dictate it.

---

## 7. Maintenance

### 7.1 Updating Criteria

When `validate_mechanical.py` gains a new check or modifies an existing one:

1. Update the corresponding §2 sub-section, OR add a new §2.X if it's a new check.
2. Update §5 (Failure Mode Reference) with the new error message.
3. Update §6 (Audit-by-Grep) with the new function name.
4. Update the test suite (`tests/workflows/requirements/test_validate_mechanical.py`) accordingly.
5. Bump this standard's `<!-- Version: -->` and add a row to §7.2.

### 7.2 Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-05-09 | Initial version (Issue #1066). Documents 11 checks + 2 side effects implemented as of `validate_mechanical.py` lines 1-1425, covering Issues #277 / #294 / #300 / #302 / #306 / #312 / #322 / #334 / #388 / #600. |

---

## 8. References

- **Code:** [`assemblyzero/workflows/requirements/nodes/validate_mechanical.py`](../../assemblyzero/workflows/requirements/nodes/validate_mechanical.py)
- **State definition:** `assemblyzero/workflows/requirements/state.py` — defines the `RequirementsWorkflowState` fields the validator reads/writes.
- **Tests:** `tests/workflows/requirements/test_validate_mechanical.py` (if present in repo).
- **Hardening lineage:** Issues #277 (initial), #294 (state merge), #300 (file-path suggestions), #302 (clear BLOCKED), #306 (title issue check), #312 (smart mitigation filter), #322 (repo-root explicit), #334 (directory normalization + lineage), #388 (auto-implied parents), #600 (AST sentinel).
- **Adjacent standards:**
  - [0018 — Issue Spec Quality Checklist](0018-issue-spec-quality.md) — pre-LLD-workflow gate; this standard fires after.
  - [0020 — Test Plan Quality Criteria](0020-test-plan-quality.md) — test-plan-review gate in the testing workflow.
  - [0701 — Implementation Spec Template](0701-implementation-spec-template.md) — the template that defines what sections must exist (the source of truth for §2.2's mandatory-sections list).
  - [0702 — Implementation Readiness Review](0702-implementation-readiness-review.md) — semantic implementability check, fires later in the implementation workflow.
- **Related skill:** AZ #1069 — `/pre-flight-check` skill (validates Issue Spec Quality, §0018) before this validator runs.
