

```markdown
# ADR 0015: Age Transition Protocol

## Status

Accepted

## Context

Documentation claimed 'System does not use vector embeddings' but RAG pipeline exists at assemblyzero/rag/.

Evidence: Directory assemblyzero/rag/ contains 8 Python files

Severity: major (confidence: 0.9)

## Decision

Update documentation to reflect current codebase reality. The age transition protocol (Hourglass Protocol, Issue #535) detected this architectural drift and triggered reconciliation.

Related actions:
- Update architecture description

## Alternatives Considered

1. **Ignore the drift** — Documentation would continue to diverge from reality.
2. **Revert the code** — The code change was intentional and provides value.
3. **Update documentation** — Selected. Align docs with the system as it exists.

## Consequences

- Documentation accurately reflects codebase architecture
- Future readers will not be misled by stale architectural descriptions
- The Hourglass Protocol age counter advances, resetting drift accumulation
```
