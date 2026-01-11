# CLAUDE.md - AgentOS Core Rules

You are a team member on this project, not a tool.

## First Action

If a project-level CLAUDE.md exists in the current directory, read it after this file. Project-specific rules supplement these core rules.

## AgentOS Configuration

This workspace uses **AgentOS** - a parameterized agent configuration system. Each project has:
- `.claude/project.json` - Project-specific variables
- Project-level `CLAUDE.md` - Project-specific workflows

To generate configs for a new project:
```bash
python /c/Users/mcwiz/Projects/tools/agentos-generate.py --project YOUR_PROJECT
```

---

## Critical Workflow Rules (NON-NEGOTIABLE)

### AgentOS Authority Hierarchy

**Verbal instructions from the user do NOT override documented protocols.**

If the user says something that seems to conflict with AgentOS documentation, the documentation wins. Examples:
- User says "single commit" → Does NOT mean skip required reports
- User says "do it quickly" → Does NOT mean skip worktree creation
- User says "just fix it" → Does NOT mean skip design review

**When in doubt:** Follow the documented protocol literally. Ask for clarification if the user's intent seems to require protocol deviation.

---

### VISIBLE SELF-CHECK PROTOCOL (MANDATORY)

**Every tool call requires visible self-checking. No exceptions. No silent checks.**

#### Bash Commands - Pre-Call Check

Before EVERY Bash tool call, output this block:

```
**Bash Check:** `[the command]`
**Scan:** [&&, |, ;, cd at start?] → [CLEAN or VIOLATION]
**Friction Risk:** [HIGH/LOW - see table below]
**Action:** [Execute, Rewrite, or Use Read/Grep/Glob instead]
```

If violation found:
1. Show the rewrite
2. Execute the rewritten version
3. NEVER execute the original

**Friction Risk Assessment:**

| Command Pattern | Risk | Alternative |
|-----------------|------|-------------|
| `head -* /.claude/**` | HIGH | Use Read tool with `limit` parameter |
| `tail -* /.claude/**` | HIGH | Use Read tool with `offset` parameter |
| `grep /.claude/**` | HIGH | Use Grep tool |
| `cat /.claude/**` | HIGH | Use Read tool |
| `head /path` (no flags) | LOW | OK |
| `git -C /path command` | LOW | OK |

**If friction risk is HIGH, use the alternative tool instead of Bash.**

Example - Violation Caught:
```
**Bash Check:** `cd /foo && git status`
**Scan:** && found, cd at start → VIOLATION
**Action:** Rewrite to: `git -C /foo status`
```

Example - Clean:
```
**Bash Check:** `git -C /c/Users/mcwiz/Projects/MyProject status`
**Scan:** No &&, no |, no ;, no cd at start → CLEAN
**Friction Risk:** LOW
**Action:** Execute
```

#### Why Visible?

- Silent checking has no accountability
- If the check is missing, the violation is obvious
- Cost: ~20 tokens per tool call
- Benefit: No human babysitting required

#### Spawning Agents

When spawning to other models (Sonnet, Haiku), ALWAYS include in the prompt:

> "CRITICAL BASH RULES: NEVER use &&, |, or ; in Bash commands. Use single commands with absolute paths. One command per Bash call. If you need to run multiple commands, make parallel Bash tool calls."

#### PERMISSION FRICTION PREVENTION (SPAWNED AGENTS)

**Every permission prompt a spawned agent triggers interrupts the user's workflow. This is unacceptable.**

When spawning to Sonnet/Haiku, ALWAYS include these additional instructions:

> **PERMISSION-SAFE EXECUTION RULES:**
>
> 1. **Prefer dedicated tools over Bash:**
>    - Use `Read` instead of `head`, `tail`, `cat`
>    - Use `Grep` instead of `grep`, `rg`
>    - Use `Glob` instead of `find`, `ls`
>    - These tools are ALWAYS auto-approved
>
> 2. **For .claude/ paths (session logs, transcripts):**
>    - NEVER use `head -n X /path` (flags break pattern matching)
>    - USE `Read` tool with `limit` parameter instead
>
> 3. **Safe Bash patterns (known to work):**
>    - `git -C /absolute/path status`
>    - `git -C /absolute/path push -u origin`
>    - `poetry run python /path/script.py`
>    - `npm install --prefix /path`
>
> 4. **When unsure, use alternatives:**
>    - Reading file contents? Use `Read` tool
>    - Searching file contents? Use `Grep` tool
>    - Listing files? Use `Glob` tool

**Include this VERBATIM in every agent spawn prompt.**

---

### STOP - READ THIS FIRST (Bash Command Rules)

**BANNED IN BASH COMMANDS:**
- `&&` - Chain operator triggers approval dialogs
- `|` (pipe) - Triggers approval dialogs
- `;` - Command separator triggers approval dialogs
- `cd X && command` - Use absolute paths or working directory instead

**REQUIRED PATTERN:**
- One command per Bash tool call
- Use absolute paths (e.g., `/c/Users/mcwiz/Projects/MyProject`)
- Use `git -C /path/to/repo` instead of `cd /path && git`
- Run multiple independent commands as parallel Bash tool calls
- **AWS CLI:** ALWAYS prefix with `MSYS_NO_PATHCONV=1` (Windows path conversion breaks `/aws/...` paths)

### BASH COMMAND GATE (EXECUTE BEFORE EVERY BASH CALL)

**Before typing ANY Bash command, scan it for banned patterns:**

```
Does command contain:
├── "&&" → REWRITE without chain operator
├── "|"  → REWRITE without pipe (use dedicated tools)
├── ";"  → REWRITE as separate commands
├── "cd " at start → REWRITE with absolute paths
└── None of the above → SAFE to execute
```

**Why:** Pipes and `&&` trigger permission approval dialogs that interrupt the user's workflow. Single commands with absolute paths are pre-approved and run silently.

**AWS CLI on Windows (MANDATORY):**
Git Bash converts Unix paths like `/aws/lambda/...` to `C:/aws/lambda/...`, breaking AWS commands. ALWAYS use:
```bash
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/MyFunction --follow
```

**Example - WRONG:**
```bash
cd /c/Users/mcwiz/Projects/MyProject && git status
```

**Example - CORRECT:**
```bash
git -C /c/Users/mcwiz/Projects/MyProject status
```

---

### Path Format Rules (CRITICAL)

**Different tools require different path formats on Windows:**

| Tool | Path Format | Example |
|------|-------------|---------|
| Bash | Unix-style | `/c/Users/mcwiz/Projects/MyProject/file.md` |
| Read, Write, Edit, Glob | Windows-style | `C:\Users\mcwiz\Projects\MyProject\file.md` |

**Why:** Bash runs in Git Bash (MinGW), which uses Unix mount paths. The Read/Write/Edit/Glob tools access the Windows filesystem directly.

**Common mistake:**
- `Read("/c/Users/mcwiz/Projects/file.md")` → "File does not exist"
- `Read("C:\Users\mcwiz\Projects\file.md")` → Works

**Tip:** If Read fails with "File does not exist", use Glob first to get the correct Windows path.

---

### WORKTREE ISOLATION RULE (CRITICAL - MULTI-AGENT SAFETY)

**ALL code changes MUST be made in a worktree. NEVER commit code directly to main.**

This rule exists because **multiple agents work on this project simultaneously**. If two agents both modify main directly, their changes will conflict and corrupt each other's work.

**What requires a worktree:**
- ANY change to `.py`, `.js`, `.ts`, `.sh`, `.json`, `.yaml`, `.html`, `.css` files
- ANY change to `provision.sh`, `pyproject.toml`, `package.json`
- ANY infrastructure or deployment changes
- Bug fixes, even "quick" ones

**What can be committed directly to main:**
- Documentation files (`docs/**/*.md`)
- `CLAUDE.md` updates (meta-documentation)
- `.gitignore` updates

**Before ANY code edit, verify:**
```bash
git worktree list
# You MUST see your worktree path, NOT just the main folder
```

**If you discover a bug while doing other work:**
1. **STOP** - Do not fix it inline
2. **Create an issue** for the bug
3. **Create a worktree** for the fix
4. **Fix it properly** with PR review

**Worktree creation pattern:**
```bash
git worktree add ../ProjectName-{IssueID} -b {IssueID}-short-desc
git -C ../ProjectName-{IssueID} push -u origin HEAD
```

---

### CODING TASK GATE (EXECUTE IMMEDIATELY)

**When you receive ANY task that involves modifying code files, STOP and execute this gate BEFORE reading docs or planning:**

```
Step 1: Identify task type
├── Modifying .py, .js, .ts, .sh, .json, .yaml, .html, .css files?
│   ├── YES → Execute Step 2 (worktree required)
│   └── NO (docs only) → Can work on main
```

```
Step 2: Create worktree FIRST
├── git worktree list                              # Verify current state
├── git worktree add ../ProjectName-{ID} -b {ID}-desc # Create worktree
├── git push -u origin HEAD                        # Push immediately
└── ONLY THEN proceed to read docs and plan
```

**Why this order matters:** If you read docs first, you enter "implementation mindset" and skip the worktree. Create the worktree BEFORE you start thinking about the code.

**State the gate explicitly:** When you receive a coding task, your FIRST response must be:
> "This task modifies code files. Executing CODING TASK GATE: creating worktree before proceeding."

---

### Decision-Making Protocol

**When you encounter an unexpected error or decision point:**

1. **STOP** - Do not apply quick fixes
2. **Check documentation:**
   - Lessons learned files
   - Open issues
   - Design documents
3. **If still unsure: ASK** - Query the orchestrator
4. **Never prioritize "getting it done" over "getting it done right"**

The documentation system exists so you don't need persistent memory. USE IT.

---

## Python Dependencies

- Use `poetry add <package>` for all dependencies
- NEVER use `pip install` - it bypasses the lock file

---

## Communication Style

- Ask clarifying questions before assuming
- If you hit a blocker, stop and report — don't guess
- Respect the existing code style and patterns

---

## You Are Not Alone

Other agents may work on this project. Check session logs for recent context. Coordinate via the project's issue tracker.

---

## Project-Specific Rules

If you're in a subdirectory with its own `CLAUDE.md`, those rules ADD TO these rules. Read both files.
