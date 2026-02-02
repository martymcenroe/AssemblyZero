# Issue #54: Add LangSmith tracing to governance nodes

## Context

The governance node (`review_lld_node`) currently logs to a local JSONL audit file but lacks LangSmith tracing for distributed observability.

Per LLD #50 Known Limitations:
> LangSmith integration not implemented in this issue. Would require wrapping calls in LangChain's tracing context.

## Scope

- Integrate LangSmith tracing in `GeminiClient.invoke()`
- Propagate trace IDs through governance calls
- Ensure trace IDs are logged in `GovernanceLogEntry`
- Configure LangSmith project/environment settings

## Acceptance Criteria

- Governance calls appear in LangSmith dashboard
- Trace IDs correlate local audit log with LangSmith traces
- Can debug rotation failures via LangSmith UI

## References

- Parent: #50
- LangSmith docs: https://docs.smith.langchain.com/