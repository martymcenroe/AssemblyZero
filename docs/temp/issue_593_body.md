## Objective
Perform a controlled pilot of **OpenClaw** and the **Model Context Protocol (MCP)** to evaluate their potential as a coordination layer for the AssemblyZero ecosystem.

## Pilot Steps
1. **Sandbox Setup:** Install the `openclaw` gateway in an isolated environment.
2. **MCP Skill Mapping:** Wrap an existing AssemblyZero tool (e.g., `run_requirements_workflow.py`) as an MCP Skill.
3. **Cross-Repo Test:** Attempt to have an OpenClaw-managed agent trigger a workflow in one repo (e.g., AssemblyZero) from another (e.g., Aletheia).
4. **Handoff Comparison:** Compare OpenClaw's "Adaptive Compaction" against our manual `/handoff` and `/pickup` system for state retention and human intent.

## Success Criteria
- [ ] OpenClaw successfully invokes an AssemblyZero tool via MCP.
- [ ] State is maintained across agent hand-offs.
- [ ] We have identified the specific security and token-waste risks of the platform.

## Related
- #258 (Research)
- #589 (Perdita Protocol)