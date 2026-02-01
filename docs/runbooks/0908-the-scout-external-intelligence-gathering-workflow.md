# 0908 - The Scout: External Intelligence Gathering Workflow

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-02-01

---

## Purpose

Operational runbook for The Scout: External Intelligence Gathering Workflow (Issue #93).

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| Require interactive confirmation (or `--yes`) before sending internal code to LLM. | `verify` |

---

## Architecture

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Sec as Security/Budget
    participant Graph as LangGraph
    participant Explorer
    participant Extractor
    participant Analyst
    participant API as GitHub/Gemini

    User->>CLI: run(--max-tokens 30k)
    CLI->>Sec: check_static_budget(internal_file)
    
    alt budget ok
        CLI->>Graph: invoke(state)
        Graph->>Explorer: search_repos()
        Explorer->>API: search_query()
        API-->>Explorer: 100+ results
        Explorer->>Explorer: Slice Top-3 (Bound Loop)
        
        Graph->>Extractor: extract_details(top_3_repos)
        
        loop For each of Top-3
            Extractor->>Sec: check_remaining_budget()
            alt has budget
                Extractor->>API: fetch_content()
                Extractor->>Sec: sanitize_content()
                Extractor->>Sec: update_usage(content)
            else budget full
                Extractor-->>Graph: Stop Extraction
            end
        end
        
        Graph->>Analyst: analyze_gaps()
        Analyst->>API: generate(prompt)
        
        opt 400 Context Error
            API-->>Analyst: Error: Context Exceeded
            Analyst->>Sec: adaptive_truncate(context)
            Analyst->>API: retry_generate(truncated_prompt)
        end
        
        API-->>Analyst: Analysis Result
        Graph->>CLI: Final Brief
        CLI->>Sec: get_safe_write_path()
        CLI->>User: Write File
    end
```

---

## Procedure

*Procedure steps to be documented.*

---

## Verification

| Check | Command | Expected |
|-------|---------|----------|
| Feature works | `run feature` | Success |

---

## Troubleshooting

### Common Issues

*Document common issues and resolutions here.*

---

## Related Documents

- [Issue #93](https://github.com/issues/93)
- [LLD-093](../lld/active/LLD-093.md)

## Implementation Files

- `agentos/workflows/testing/nodes/document.py`
- `agentos/workflows/testing/templates/__init__.py`
- `agentos/workflows/testing/templates/wiki_page.py`
- `agentos/workflows/testing/templates/runbook.py`
- `agentos/workflows/testing/templates/lessons.py`
- `agentos/workflows/testing/templates/cp_docs.py`
- `agentos/workflows/testing/graph.py`
- `agentos/workflows/testing/state.py`
- `agentos/workflows/testing/nodes/__init__.py`

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-01 | Initial version (auto-generated) |
