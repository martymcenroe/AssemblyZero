# ADR 0204: Janitor Probe Plugin System

## Status

Accepted

## Context

Issue #94 introduces the Janitor workflow with four built-in probes (links, worktrees, harvest, todo). We need a pattern for organizing probes that allows:

1. Easy addition of new probes without modifying core workflow code
2. Crash isolation — one probe failure doesn't affect others
3. Consistent data structures across all probes

## Decision

We adopt a **registry-based probe system** with the following characteristics:

- **Probe Interface:** Each probe is a function `(repo_root: str) -> ProbeResult`
- **Registry:** `PROBE_REGISTRY` dict maps `ProbeScope` names to probe functions
- **Isolation:** `run_probe_safe()` wraps each probe in try/except, converting crashes to error-status `ProbeResult` objects
- **Discovery:** Probes are registered in `assemblyzero/workflows/janitor/probes/__init__.py` via lazy import

### Adding a New Probe

1. Create `assemblyzero/workflows/janitor/probes/new_probe.py`
2. Implement `probe_new(repo_root: str) -> ProbeResult`
3. Add to `ProbeScope` literal type in `state.py`
4. Register in `_build_registry()` in `probes/__init__.py`
5. Add CLI scope option in `tools/run_janitor_workflow.py`

## Alternatives Considered

- **Class-based plugins with auto-discovery:** More complex, not needed at current scale
- **Entry points / setuptools plugins:** Over-engineered for internal-only probes
- **Simple function list:** No type safety on scope names

## Consequences

- New probes require changes to 3 files (probe module, state.py, probes/__init__.py)
- All probes share the same `ProbeResult` contract
- Crash isolation is guaranteed by the `run_probe_safe` wrapper
- Scope validation happens at parse time via the `ProbeScope` literal type