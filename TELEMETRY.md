# Telemetry

AssemblyZero includes optional telemetry that records structured events about tool and workflow usage. This document explains what is collected, where it is stored, and how to control it.

## What Is Collected

| Category | Event Types | Trigger |
|----------|------------|---------|
| Session | `session.start`, `session.end` | Unleashed PTY lifecycle |
| Workflow | `workflow.start`, `workflow.complete`, `workflow.error` | LangGraph workflows |
| Tool | `tool.start`, `tool.complete`, `tool.error` | CLI tool invocations |
| Error | `error.import`, `error.network`, `error.unhandled` | Exceptions |
| Approval | `approval.permission`, `approval.sentinel` | Auto-approvals |

Every event includes:

- **actor**: `human` or `claude` (detected from environment variables)
- **repo**: repository name
- **github_user**: GitHub username (from `gh auth status`)
- **timestamp**: ISO 8601 UTC
- **machine_id**: hashed hostname (not reversible)

No source code, file contents, prompts, or API keys are ever collected.

## Where It Is Stored

- **Primary**: DynamoDB table `assemblyzero-telemetry` in `us-east-1`
- **Fallback**: Local JSONL files at `~/.assemblyzero/telemetry-buffer/`

Access is restricted to a scoped IAM user with PutItem and Query permissions only.

## Retention

Events expire automatically after **90 days** via DynamoDB TTL.

Local buffer files are cleaned up when successfully synced to DynamoDB via `poetry run python -m assemblyzero.telemetry.sync`.

## How to Disable

Set the environment variable:

```bash
export ASSEMBLYZERO_TELEMETRY=0
```

When disabled, no events are emitted and no network calls are made. The telemetry module becomes a complete no-op.

## Debug Mode

To inspect what events would be emitted without sending them to DynamoDB, check the local buffer files:

```bash
ls ~/.assemblyzero/telemetry-buffer/
cat ~/.assemblyzero/telemetry-buffer/2026-02-24.jsonl
```

## Dashboard

A web dashboard is available at the Worker URL for querying and visualizing telemetry data. Access requires an API key.
