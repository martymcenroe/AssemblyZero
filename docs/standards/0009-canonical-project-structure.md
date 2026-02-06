# 0009 - Canonical Project Structure

**Status:** Active
**Created:** 2026-01-20
**Applies to:** All projects under AssemblyZero governance

---

## Purpose

This standard defines the required directory structure, file naming conventions, and documentation numbering scheme for all projects. Adherence ensures:
- Instant navigation familiarity across repos
- Professional appearance to external reviewers
- Consistent agent onboarding

---

## Documentation Numbering Scheme (5-Digit)

All documentation uses a 5-digit numbering scheme:

| Range | Category | Location |
|-------|----------|----------|
| `0xxxx` | Foundational (ADRs, standards, templates) | `docs/adrs/`, `docs/standards/`, `docs/templates/` |
| `1xxxx` | Issue-specific work (LLDs, reports) | `docs/lld/`, `docs/reports/` |
| `2xxxx` | Non-issue reports | `docs/reports/` |
| `3xxxx` | Runbooks, demos, human procedures | `docs/runbooks/` |
| `4xxxx` | Artwork, videos, tutorials | `docs/media/` |
| `90001` | Session logs directory | `docs/session-logs/` |
| `90002` | Audit results directory | `docs/audit-results/` |

### Sub-ranges for Foundational Docs (0xxxx)

| Range | Contents |
|-------|----------|
| `00001-00099` | Core standards |
| `00100-00199` | Templates |
| `00200-00299` | Architecture Decision Records (ADRs) |
| `00600-00699` | Skills |
| `00800-00899` | Audits |
| `00900-00999` | Runbooks |

### Issue-Specific Docs (1xxxx)

Files in `docs/lld/` and `docs/reports/` use the issue number directly:
- `10045-lld.md` - LLD for issue #45
- `10045-implementation-report.md` - Implementation report for issue #45
- `10045-test-report.md` - Test report for issue #45

---

## Required Directory Structure

### Root Level

```
project/
├── .claude/                    # Claude Code configuration
├── .git/                       # Git repository
├── data/                       # App data: examples, templates, seeds
├── docs/                       # All documentation
├── src/                        # Application source (if applicable)
├── tests/                      # All tests
├── tools/                      # Development utilities (project-specific)
├── CLAUDE.md                   # Claude agent instructions (REQUIRED)
├── GEMINI.md                   # Gemini agent instructions (REQUIRED)
├── README.md                   # Project overview (REQUIRED)
├── pyproject.toml              # Python config (if applicable)
├── package.json                # Node.js config (if applicable)
└── .gitignore                  # Git ignore rules (REQUIRED)
```

### Source Code Location

| Project Type | Source Location |
|--------------|-----------------|
| Application (deploys/ships) | `src/` |
| Full-stack (backend + extension) | `src/` (backend), `extensions/` (browser) |
| Tools/utilities only | `tools/` |
| Browser extension only | `extensions/` |

**Notes:**
- Always use plural `extensions/` not singular
- Chrome-only projects still use `extensions/` (no Firefox subdirectory needed)

---

### Documentation Structure (`docs/`)

```
docs/
├── adrs/                       # Architecture Decision Records
│   └── (0xxxx-*.md files)
├── standards/                  # Project-specific standards
│   └── (0xxxx-*.md files)
├── templates/                  # Document templates
│   └── (0xxxx-*.md files)
├── lld/                        # Low-Level Designs
│   ├── active/                 # In-progress LLDs
│   │   └── (1xxxx-lld.md files)
│   └── done/                   # Completed LLDs
│       └── (1xxxx-lld.md files)
├── reports/                    # Implementation & test reports
│   ├── active/                 # In-progress reports
│   │   └── (1xxxx-*-report.md files)
│   └── done/                   # Completed reports
│       └── (1xxxx-*-report.md files)
├── runbooks/                   # Operational procedures
│   └── (3xxxx-*.md files)
├── session-logs/               # Agent session context (90001)
│   └── (YYYY-MM-DD.md files)
├── audit-results/              # Historical audit outputs (90002)
│   └── (YYYY-MM-DD.md files)
├── lineage/                    # Workflow artifacts (design review trail)
│   ├── active/                 # Issues currently in design review
│   │   └── {issue-id}/         # Per-issue folder with numbered artifacts
│   └── done/                   # Completed (filed to GitHub)
│       └── {issue-id}/
├── media/                      # Artwork, videos, tutorials (4xxxx)
├── legal/                      # ToS, privacy policy, regulatory compliance
├── design/                     # UI mockups, icon prompts, style guides
└── 00003-file-inventory.md     # Project file inventory (REQUIRED)
```

**Key rules:**
- `lld/active/` and `lld/done/` - LLDs move from active to done when implemented
- `reports/active/` and `reports/done/` - Reports move when merged
- `lineage/active/` and `lineage/done/` - Design review artifacts move when issue is filed
- Files in lld/ and reports/ are **FLAT** (no subdirectories per issue)
- Files in lineage/ are **NESTED** by issue (each issue gets its own folder)
- Session logs and audit results use date-based names, not numbered

### Lineage Structure (`docs/lineage/`)

The lineage folder captures the design review workflow - the "paper trail" showing how each issue evolved from idea through Gemini review to filing.

```
docs/lineage/
├── active/                     # Issues currently in design review
│   └── {issue-id}/             # e.g., 4-footnote-handling/
│       ├── 001-brief.md        # Initial idea/problem statement
│       ├── 002-draft.md        # First LLD draft (Claude)
│       ├── 003-verdict.md      # Gemini review verdict
│       ├── 004-draft.md        # Revised draft after feedback
│       ├── 005-verdict.md      # Second review verdict
│       └── 006-filed.json      # Filing metadata
└── done/                       # Completed (filed to GitHub)
    └── {issue-id}/
```

**Naming convention:**
- Folder: `{issue-number}-{short-description}/` (e.g., `4-footnote-handling/`)
- Files: `{NNN}-{type}.{ext}` where NNN is sequence number (001, 002, ...)
- Types: `brief`, `draft`, `verdict`, `filed`

---

### Test Structure (`tests/`)

```
tests/
├── unit/                       # Fast, isolated tests
├── integration/                # Multiple components together
├── e2e/                        # End-to-end browser/system tests
├── smoke/                      # Quick sanity/environment tests
├── contract/                   # Extension<->backend API agreements
├── visual/                     # Visual regression testing
├── benchmark/                  # Performance, load, latency
├── security/                   # Red-team, adversarial, penetration
├── accessibility/              # ARIA, WCAG, screen readers
├── compliance/                 # Privacy, GDPR, regulatory
├── fixtures/                   # Test data (JSON, HTML, seeds)
└── harness/                    # Test utilities, helpers, mocks
```

**All directories are required**, even if empty (use `.gitkeep`).

**Definitions:**
- **smoke/** - Quick sanity tests: verify environment works before full test suite
- **fixtures/** - Test *data*: sample JSON, mock HTML, database seeds
- **harness/** - Test *infrastructure*: helper functions, mock servers, setup/teardown

---

### Claude Configuration (`.claude/`)

```
.claude/
├── project.json                # Project variables (REQUIRED)
├── settings.json               # Hook configuration (REQUIRED)
├── settings.local.json         # Local overrides (gitignored)
├── hooks/                      # Pre/post tool execution scripts
├── commands/                   # Custom slash commands
└── gemini-prompts/             # Gemini review templates
```

---

## File Naming Conventions

### Documentation Files

| Type | Pattern | Example |
|------|---------|---------|
| Standard | `0xxxx-name.md` | `00009-canonical-project-structure.md` |
| ADR | `0xxxx-ADR-name.md` | `00201-ADR-worktree-isolation.md` |
| Template | `0xxxx-TEMPLATE-name.md` | `00101-TEMPLATE-lld.md` |
| LLD | `1xxxx-lld.md` | `10045-lld.md` |
| Implementation report | `1xxxx-implementation-report.md` | `10045-implementation-report.md` |
| Test report | `1xxxx-test-report.md` | `10045-test-report.md` |
| Runbook | `3xxxx-name.md` | `30001-deployment-runbook.md` |
| Session log | `YYYY-MM-DD.md` | `2026-01-20.md` |
| Audit result | `YYYY-MM-DD.md` | `2026-01-20.md` |

### Directory Naming

- Always use **plural** for collections: `tests/`, `extensions/`, `tools/`
- Always use **lowercase** with hyphens: `session-logs/`, `audit-results/`
- Never use underscores in directory names

---

## Project-Specific vs AssemblyZero

| AssemblyZero (0xxxx) | Project (1xxxx+) |
|-----------------|------------------|
| Generic standards | Project-specific implementations |
| Reusable templates | Filled-in templates |
| Framework audits | Project audit results |
| Shared tools | Project-specific utilities |

Projects **inherit** from AssemblyZero but can override with project-specific docs.

---

## Compliance Verification

Run the following audits to verify structure compliance:
- `00835-audit-structure-compliance.md` - Directory structure
- `00836-audit-gitignore-consistency.md` - .gitignore patterns
- `00837-audit-readme-compliance.md` - README template adherence

---

## Migration Notes

When migrating existing repos:
1. Create all required directories (use `.gitkeep` for empty ones)
2. Rename directories to match conventions (e.g., `test/` -> `tests/`)
3. Move files to correct locations (e.g., root `RUNBOOK.md` -> `docs/runbooks/`)
4. Renumber docs to match scheme
5. Update imports/paths in code
