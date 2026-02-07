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
