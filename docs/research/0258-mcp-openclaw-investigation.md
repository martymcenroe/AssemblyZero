# 0258 - Research: MCP/OpenClaw for Multi-Team Project Coordination

## 1. Executive Summary
This report investigates the **Model Context Protocol (MCP)** and **OpenClaw** (formerly **Moltbot**) as a solution for coordinating complex, multi-team workflows across GitHub repositories. These technologies provide a standardized way for AI agents to interact with developer tools and each other, potentially serving as the "coordination layer" for the AssemblyZero ecosystem.

---

## 2. Model Context Protocol (MCP)

### 2.1 Overview
The **Model Context Protocol (MCP)** is an open standard introduced to unify how AI models (LLMs) interact with external data sources and tools. It replaces fragmented, proprietary tool-calling implementations with a common interface.

### 2.2 Key Benefits for AssemblyZero
- **Tool Portability:** An MCP-compliant server (e.g., for GitHub API access) can be used by any MCP-compliant client (Claude, Gemini, custom LangGraph nodes).
- **Security:** MCP servers run as local processes or secure remote endpoints, allowing fine-grained control over what data is exposed to the model.
- **Rich Context:** It enables "Context-as-a-Service," where agents can pull real-time repository state, issues, and PR history without bloating the prompt with static copies.

---

## 3. OpenClaw (formerly Moltbot)

### 3.1 Overview
**OpenClaw** is a self-hosted, local-first "control plane" for AI agents. It acts as an orchestrator that manages multiple specialist agents and provides them with the tools they need to perform work across different platforms.

### 3.2 Coordination Mechanisms
- **Agent-to-Agent (A2A) Protocols:** OpenClaw implements a "session" protocol that allows agents to communicate, hand off subtasks, and share state. This is critical for multi-team coordination where a "Project Manager" agent might delegate a specific fix to a "Developer" agent.
- **Adaptive Compaction:** A safety feature that allows long-running autonomous tasks to resume from the last known good state if interrupted, preventing "amnesia" in complex GitHub workflows.
- **GitHub Project Integration:** Automated management of GitHub Project Boards, including decomposing features into issues, triaging incoming bugs, and updating status based on code commits.

---

## 4. Multi-Team Coordination Use Cases

| Capability | Implementation via MCP/OpenClaw |
| :--- | :--- |
| **Feature Decomposition** | A Manager agent uses the GitHub MCP tool to create a parent issue and linked sub-tasks for different teams. |
| **Automated Triage** | An OpenClaw specialist monitors all repositories in an organization and applies standard labels based on content analysis. |
| **Cross-Project Sync** | Synchronization of dependencies and shared standards across child projects (e.g., Aletheia, Talos, Clio). |
| **Human-in-the-Loop** | Coordination agents can "pause" a workflow and request approval via Slack/Discord before committing major changes. |

---

## 5. Potential Integration with AssemblyZero

AssemblyZero currently uses a LangGraph-based workflow for requirements and implementation. Integrating OpenClaw/MCP would offer several upgrades:

1.  **Standardized Tools:** Replace custom GitHub wrappers with standard MCP GitHub servers.
2.  **Scale:** Move from single-issue workflows to organization-level orchestration.
3.  **Persistence:** Leverage OpenClaw's session management for multi-day, multi-step agent operations.

---

## 6. Recommendations & Next Steps

1.  **Pilot Setup:** Install the `openclaw` gateway and the GitHub MCP server in a sandbox environment.
2.  **Skill Development:** Create an AssemblyZero-specific MCP skill that exposes our local toolset (`run_requirements_workflow.py`, etc.) as standard MCP tools.
3.  **LLD Creation:** If the pilot is successful, create a formal LLD for a "Multi-Team Coordination Node" in the AssemblyZero orchestrator.

---
**Status:** Investigation Complete
**Research Date:** 2026-03-05
**Reference Issue:** #258
