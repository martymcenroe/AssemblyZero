<!-- Last Updated: 2026-02-17 -->
<!-- Updated By: Issue #534 -->

# Standard 0015: Spelunking Audit Protocol

## Purpose

Define the protocol for spelunking audits — deep verification that documentation claims match codebase reality.

## Scope

All documentation files in the repository, including README.md, standards, ADRs, wiki pages, and persona files.

## Definitions

- **Claim**: A verifiable factual assertion in a document (e.g., "11 tools in tools/")
- **Drift**: When a claim no longer matches reality
- **Drift Score**: Percentage of verifiable claims that match reality (target: >90%)
- **Probe**: An automated check that verifies a specific category of claims
- **Spelunking Checkpoint**: A YAML-declared verification point for manual audit integration

## Protocol

### Automated Probes

Six probes run automatically:

1. **Inventory Drift** — file counts vs. inventory document
2. **Dead References** — file path references to nonexistent files
3. **ADR Collision** — duplicate numeric prefixes in ADR files
4. **Stale Timestamps** — documents with outdated "Last Updated" dates
5. **README Claims** — technical assertions contradicted by code
6. **Persona Status** — persona markers without status declarations

### Drift Score Calculation

```
drift_score = (matching_claims / verifiable_claims) * 100
```

- UNVERIFIABLE claims are excluded from the denominator
- Score >= 90%: PASS
- Score < 90%: FAIL

### Checkpoint Format

Existing audits can declare spelunking checkpoints in YAML:

```yaml
checkpoints:
  - claim: "11 tools exist in tools/"
    verify_command: "glob tools/*.py | count"
    source_file: "docs/standards/0003-file-inventory.md"
```

## Compliance

All documentation files SHOULD have a "Last Updated" timestamp. All file path references in documentation MUST point to existing files. ADR numeric prefixes MUST be unique.