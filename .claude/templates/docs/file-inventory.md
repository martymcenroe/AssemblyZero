# {{PROJECT_NAME}} - File Inventory & Status Map

## 1. Status Taxonomy

* **Stable:** Verified, documented, production-ready.
* **Beta:** Functional but lacks full test coverage or documentation.
* **In-Progress:** Active development; expect instability.
* **Placeholder:** Skeleton or empty file; do not run.
* **Legacy:** Deprecated/archived (reference only).
* **Unknown:** Needs audit/verification.
* **Gitignored:** Not tracked; listed for completeness.

## 2. Inventory

### Root Configuration

| File | Role | Status | Linked Issue | Description |
| :--- | :--- | :--- | :--- | :--- |
| `.claude/settings.local.json` | **Config** | Stable | - | Claude Code permissions |
| `CLAUDE.md` | **Config** | Stable | - | Agent onboarding |
| `README.md` | **Doc** | Stable | - | Project overview |
| `pyproject.toml` / `package.json` | **Config** | Stable | - | Dependencies |

### Core Application

| File | Role | Status | Linked Issue | Description |
| :--- | :--- | :--- | :--- | :--- |
| `src/main.py` | **Entry** | Stable | - | Main entry point |

### Documentation

| File | Role | Status | Linked Issue | Description |
| :--- | :--- | :--- | :--- | :--- |
| `docs/0001-architecture.md` | **Spec** | Stable | - | Architecture overview |
| `docs/session-logs/*.md` | **Log** | In-Progress | - | Session logs |

### Tools & Utilities

| File | Role | Status | Linked Issue | Description |
| :--- | :--- | :--- | :--- | :--- |
| `tools/example.py` | **Utility** | Stable | - | Example tool |

### Testing

| File | Role | Status | Linked Issue | Description |
| :--- | :--- | :--- | :--- | :--- |
| `tests/test_main.py` | **Test** | Stable | - | Main tests |

## 3. Maintenance Notes

- Review this inventory during `/cleanup --full`
- Update when adding new files
- Mark deprecated files as Legacy

---

*Generated from template: AssemblyZero/.claude/templates/docs/file-inventory.md*
