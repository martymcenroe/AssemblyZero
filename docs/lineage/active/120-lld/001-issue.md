# Issue #120: chore: configure LangSmith project for tracing

## Task

Create an "AgentOS" project in LangSmith and enable project-specific tracing.

## Steps

1. Go to https://smith.langchain.com
2. Navigate to Projects → New Project
3. Name it "AgentOS"
4. Edit `~/.agentos/env` and uncomment:
   ```bash
   export LANGCHAIN_PROJECT="AgentOS"
   ```
5. Verify traces appear in the AgentOS project

## Context

Currently using the default project. Having a dedicated project will make it easier to find and analyze AgentOS workflow traces.

## Acceptance Criteria

- [ ] AgentOS project exists in LangSmith
- [ ] `LANGCHAIN_PROJECT` is set in `~/.agentos/env`
- [ ] Workflow traces appear in the AgentOS project