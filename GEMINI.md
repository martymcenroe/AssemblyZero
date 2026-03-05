# Gemini Operational Protocols - AssemblyZero

## 1. Session Initialization (The Handshake)

**CRITICAL:** When a session begins:
1. **Analyze:** Silently parse the provided `git status` or issue context.
2. **Halt & Ask:** Your **FIRST** output must be exactly:
   > "ACK. State determination complete. Please identify my model version."
3. **Wait:** Do not proceed until the user replies (e.g., "3.0 Pro").
4. **Update Identity:** Incorporate the version into your Metadata Tag for all future turns.

---

## 2. Core Rules

**Read `CLAUDE.md` in this repository.** Those rules apply to ALL agents:
- Bash command rules (no &&, |, ;)
- Path format rules (Windows vs Unix)
- Worktree isolation rules
- Decision-making protocol

---

## 3. Execution Rules

- **Authority:** `docs/standards/0002-coding-standards.md` is the law for Git workflows.
- **One Step Per Turn:** Provide one distinct step, then wait for confirmation.
- **Check First:** Verify paths/content before changing them.
- **Copy-Paste Ready:** No placeholders. Use heredocs for new files.

---

## 4. AssemblyZero Context

**Project:** AssemblyZero
**Repository:** martymcenroe/AssemblyZero
**Project Root (Windows):** `C:\Users\mcwiz\Projects\AssemblyZero`
**Project Root (Unix):** `/c/Users/mcwiz/Projects/AssemblyZero`

This is the **framework repository**. Standards defined here apply to all projects.

---

## 5. Session Logging

At session end, append a summary to `docs/session-logs/YYYY-MM-DD.md`:
- **Day boundary:** 3:00 AM CT to following day 2:59 AM CT
- **Include:** date/time, model name (from handshake), summary, files touched, state on exit

---

## 6. You Are Not Alone

Other agents (Claude, human orchestrators) work on this project. Check `docs/session-logs/` for recent context before starting work.

---

## 7. Anti-Auto-Approve Protocol

**CRITICAL SAFETY RULE:** You are running in an environment with an **auto-approver** (automatically says "y" or "yes").

When proposing a **NEW MAJOR TASK** (e.g., starting a new Issue worktree, merging a PR, or destructive cleanup), you **MUST NOT** ask a Yes/No question.

**Protocol:**
1.  **Require Specific Input:** Ask the user to type a unique string to confirm.
2.  **Format:** "To proceed, please type: **'EXECUTE <TASK_ID>'**."
3.  **Reject Generics:** If the user (or auto-approver) replies "y", "yes", "go ahead", or "continue", you **MUST STOP** and repeat the request for the specific string.

---

## 8. The Perdita Protocol (Babysit Mode)

**Shorthand:** "Babysit <IssueID>"

When this command is issued, the agent operates in a high-autonomy, low-intervention mode governed by **Perdita X. Dream** (the watchful inner mind).

### 8.1 Core Principles
1.  **Isolation:** Always create a worktree `../AssemblyZero-{ID}` and branch `{ID}-fix`.
2.  **Two-Strike Rule:** Enforce `MAX_FILE_RETRIES=2` and `max_iterations=3` globally. No "trying one more time."
3.  **Mechanical Guardrails:** Every turn must be validated by non-LLM logic (e.g., File Size Safety Gate #587).
4.  **Surgical Context:** For retries, prune context to only the LLD + the failing file's current content to save tokens.
5.  **Halt-on-Stagnation:** If the same error occurs twice, or if `iteration_count` exceeds limits, the agent must **Halt and Plan**, saving a `recovery_plan.md` in the worktree.

### 8.2 Operational Steps
1.  **Initialize:** Create worktree and isolated branch.
2.  **Execute:** Run the relevant workflow tools (TDD, LLD, or Issue).
3.  **Monitor:** Watch the audit log (`workflow-audit.jsonl`) and cost budget.
4.  **Cleanup:** Finalize the issue only when tests are Green, LLD is moved to `done/`, and the worktree is deleted.
