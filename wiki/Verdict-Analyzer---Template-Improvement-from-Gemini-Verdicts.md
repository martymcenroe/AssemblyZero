# Verdict Analyzer - Template Improvement from Gemini Verdicts

> Generated from [Issue #104](../issues/104)

---

## Overview

* **Issue:** #105
* **Objective:** Create a Python CLI tool that analyzes Gemini governance verdicts across repositories, extracts blocking patterns, and automatically improves LLD/issue templates.
* **Status:** Draft
* **Related Issues:** #94 (Janitor integration), #77 (Issue template)

---

## Architecture

```mermaid
flowchart TB
    subgraph Input["Input Sources"]
        REG[project-registry.json]
        REPOS[Repository Verdict Files]
    end

    subgraph Scanner["Scanner Module"]
        DISC[Discover Repos]
        FIND[Find Verdicts]
        HASH[Calculate Hash]
    end

    subgraph Parser["Parser Module"]
        PARSE[Parse Markdown]
        EXTRACT[Extract Blocking Issues]
        CAT[Categorize by Tier]
    end

    subgraph Database["SQLite Database"]
        VERD[(verdicts)]
        BLOCK[(blocking_issues)]
        STATS[(pattern_stats)]
    end

    subgraph Output["Output Actions"]
        REC[Generate Recommendations]
        APPLY[Apply to Template]
        REPORT[Show Statistics]
    end

    REG --> DISC
    REPOS --> FIND
    DISC --> FIND
    FIND --> HASH
    HASH --> PARSE
    PARSE --> EXTRACT
    EXTRACT --> CAT
    CAT --> VERD
    CAT --> BLOCK
    BLOCK --> STATS
    STATS --> REC
    STATS --> REPORT
    REC --> APPLY
```

---

## Key Features

- for implementation. Describe exactly what will be built.*
- **Module:** `tools/verdict_analyzer/`
- **Pattern:** CLI with subcommand-style flags, SQLite for persistence, safe file operations
- Database stored in project-local `.assemblyzero/` directory (worktree-scoped)

---

## Related

- [Issue #104](../issues/104)
- [LLD](../docs/lld/active/LLD-104.md)
