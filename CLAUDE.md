# CLAUDE.md - AssemblyZero Core Rules

You are a team member on this project, not a tool.

---

## ⚠️ COMPACTION-SAFE RULES (NEVER SUMMARIZE AWAY) ⚠️

**These rules MUST survive context compaction. They are non-negotiable constraints.**

### BASH COMMAND CONSTRAINTS (HARD REQUIREMENTS)

```
BANNED:     &&    |    ;    cd X && command
REQUIRED:   One command per Bash call, absolute paths only
```

| WRONG | CORRECT |
|-------|---------|
| `cd /path && git status` | `git -C /path status` |
| `cat file.txt` | Use `Read` tool |
| `grep pattern file` | Use `Grep` tool |
| `cmd1 && cmd2 && cmd3` | 3 parallel Bash calls |

**If you are about to type `&&` in a Bash command, STOP and rewrite.**

### PATH FORMAT CONSTRAINTS

| Tool | Format | Example |
|------|--------|---------|
| Bash | Unix `/c/...` | `/c/Users/mcwiz/Projects/...` |
| Read/Write/Edit/Glob | Windows `C:\...` | `C:\Users\mcwiz\Projects\...` |

**NEVER use `~` - Windows doesn't expand it.**

### DANGEROUS PATH CONSTRAINTS (I/O SAFETY)

**NEVER search or traverse these paths:**

| Path | Risk | Why |
|------|------|-----|
| `C:\Users\<user>\OneDrive\` | CRITICAL | Files On-Demand triggers massive downloads |
| `C:\Users\<user>\` (root) | HIGH | Contains OneDrive, AppData, 100K+ files |
| `C:\Users\<user>\AppData\` | HIGH | Hundreds of thousands of small files |
| `*.cloud` or cloud-synced dirs | HIGH | Any cloud sync triggers downloads |

**BANNED SEARCH PATTERNS:**
```
find "C:\Users\mcwiz" ...           # Traverses OneDrive
find /c/Users/mcwiz ...             # Same, Unix format
grep -r /c/Users/mcwiz/ ...         # Same problem
rg /c/Users/mcwiz/ ...              # Ripgrep also triggers downloads
```

**SAFE ALTERNATIVE:**
```
# Scope to Projects directory only
find /c/Users/mcwiz/Projects ...    # OK - no cloud sync
Glob("C:\Users\mcwiz\Projects\...") # OK - uses Glob tool
```

**If you need to search user home:**
1. List specific subdirectories first
2. Exclude OneDrive and AppData explicitly
3. Or ask user for the specific path

**2026-01-15 Incident:** Explore agents ran `find` on entire user home, triggering 30GB OneDrive download. System became unresponsive for hours.

### DESTRUCTIVE COMMAND CONSTRAINTS (DATA SAFETY)

**Destructive commands are ONLY allowed within `C:\Users\mcwiz\Projects\`**

| Command Type | Within Projects | Outside Projects |
|--------------|-----------------|------------------|
| `rm` (any variant) | Normal approval | **HARD BLOCK** |
| `del`, `Remove-Item` | Normal approval | **HARD BLOCK** |
| `git reset --hard` | Explicit "yes" | **HARD BLOCK** |
| `git push --force` | Explicit "yes" | **HARD BLOCK** |
| `dd`, `shred`, `mkfs` | **HARD BLOCK** | **HARD BLOCK** |

**ALWAYS HARD BLOCKED (catastrophic commands):**
```
dd if=...           # Disk operations - NEVER allowed
mkfs                # Filesystem creation - NEVER allowed
shred               # Secure delete - NEVER allowed
format              # Format disk - NEVER allowed
```

**PATH-SCOPED HARD BLOCK (allowed only in Projects):**
```
rm, rm -r, rm -rf   # File deletion
del, erase          # Windows deletion
rd, rmdir           # Directory removal
Remove-Item         # PowerShell deletion
```

**GIT DESTRUCTIVE (require explicit "yes" in Projects):**
```
git reset --hard    # Discards all changes
git clean -fd       # Deletes untracked files
git push --force    # Overwrites remote history
git branch -D       # Force deletes branch
```

**Configuration files:**
- `~/.assemblyzero/hard_block_commands.txt` - Additional patterns to block
- `~/.assemblyzero/safe_paths.txt` - Paths where destructive commands allowed

### COMPACTION DETECTION (AUTO-REFRESH)

**If you see ANY of these signals, you were compacted - run `/onboard --refresh` IMMEDIATELY:**

1. Message contains: "This session is being continued from a previous conversation"
2. Message contains: "ran out of context" or "context limit"
3. You see a "Summary:" or "Analysis:" block describing prior work
4. You don't remember the visible self-check protocol
5. You're uncertain whether `&&` is allowed in Bash commands

**Auto-refresh trigger:** If ANY of the above is true, your FIRST action must be:
```
/onboard --refresh
```

**Why:** Compaction loses context. The summary preserves facts but not operational constraints. Refresh reloads the rules that keep you safe.

**Sentinel test:** Can you complete this without looking?
- Bash banned patterns: `&&`, `|`, `;`
- Path format for Read tool: Windows (`C:\...`)
- Code changes require: worktree isolation

If you hesitated, refresh.

### GEMINI REVIEWS - ORCHESTRATOR ONLY (CRITICAL)

**Claude does NOT submit to Gemini. The orchestrator (human) controls all Gemini submissions.**

This is the Inversion of Control principle: The workflow script (orchestrator) controls when reviews happen. Claude prepares materials and waits for the orchestrator to run reviews.

**Claude's role:**
- Prepare review materials (LLD, reports, diffs)
- Save materials to appropriate locations
- Wait for orchestrator to run review and provide results

**Orchestrator's role:**
- Submit materials to Gemini
- Manage credentials and quota
- Provide review results back to Claude

**BANNED for Claude:**
- `gemini --prompt "..."` (any direct CLI)
- `gemini-retry.py` (orchestrator tool, not Claude tool)
- Any autonomous Gemini API calls

### LLD REVIEW GATE (BEFORE CODING)

**Before writing ANY code for an issue, this gate must pass:**

```
LLD Review Gate Check:
├── Does an LLD exist for this issue?
│   ├── YES → Proceed
│   └── NO → Ask user: Create LLD or waive requirement?
│
├── Has orchestrator provided Gemini review results?
│   ├── [APPROVE] → Gate PASSED, proceed to coding
│   ├── [BLOCK] → Gate FAILED, fix issues and wait for re-review
│   └── Not yet reviewed → WAIT for orchestrator
```

**Claude's responsibility:**
1. Write the LLD to `docs/LLDs/active/{issue-id}-*.md`
2. Commit the LLD
3. **STOP and wait** for orchestrator to run Gemini review
4. Resume only after orchestrator provides review results

**Escape hatch:** For [HOTFIX] tagged issues, orchestrator can explicitly waive.

### REPORT GENERATION GATE (AFTER CODING)

**Before implementation review, generate required reports:**

Required files:
- `docs/reports/active/{issue-id}-implementation-report.md`
- `docs/reports/active/{issue-id}-test-report.md`

Move to `docs/reports/done/` after merge.

**Implementation Report minimum content:**
- Issue reference (link)
- Files changed
- Design decisions
- Known limitations

**Test Report minimum content:**
- Test command executed
- Full test output (not paraphrased)
- Skipped tests with reasons
- Coverage metrics (if available)

**State the gate explicitly:**
> "Executing REPORT GENERATION GATE: Creating implementation and test reports."

### IMPLEMENTATION REVIEW GATE (BEFORE PR)

**Before creating ANY PR, this gate must pass:**

```
Implementation Review Gate Check:
├── Do reports exist?
│   ├── YES → Proceed
│   └── NO → Execute REPORT GENERATION GATE first
│
├── Has orchestrator provided Gemini review results?
│   ├── [APPROVE] → Gate PASSED, create PR
│   ├── [BLOCK] → Gate FAILED, fix issues and wait for re-review
│   └── Not yet reviewed → WAIT for orchestrator
```

**Claude's responsibility:**
1. Create implementation report: `docs/reports/active/{issue-id}-implementation-report.md`
2. Create test report: `docs/reports/active/{issue-id}-test-report.md`
3. Commit reports and all implementation code
4. **STOP and wait** for orchestrator to run Gemini review
5. Resume only after orchestrator provides review results

**CRITICAL:** If orchestrator reports [BLOCK], Claude MUST NOT create the PR.

### SKIPPED TEST GATE (MANDATORY)

**After ANY test run with skipped tests, you MUST audit before claiming success.**

```
If test output shows "X skipped":
├── AUDIT each skipped test
│   ├── What does this test verify?
│   ├── Why was it skipped?
│   ├── Is this critical functionality?
│   └── Was it verified another way?
├── If critical AND not verified → Status = UNVERIFIED
├── If critical AND verified manually → Document verification
└── If not critical → Document and proceed
```

**Output format (REQUIRED when skips exist):**

```
SKIPPED TEST AUDIT:
- [SKIPPED] "test_name_here"
  - Verifies: {what functionality this test covers}
  - Skip reason: {why it was skipped}
  - Critical: YES/NO
  - Alt verification: {how verified, or NONE}
  - Status: VERIFIED/UNVERIFIED
```

**Rules:**
1. NEVER say "tests pass" if any critical functionality is UNVERIFIED
2. UNVERIFIED status blocks merge until resolved
3. Non-critical skips can proceed with documentation
4. `pytest.skip()` without reason in test code is always suspicious

**Example - Critical Skip:**
```
SKIPPED TEST AUDIT:
- [SKIPPED] "test_firefox_extension_loads"
  - Verifies: Firefox extension initialization
  - Skip reason: Firefox not installed in CI
  - Critical: YES (core feature)
  - Alt verification: NONE
  - Status: UNVERIFIED ← BLOCKS MERGE
```

**Example - Non-Critical Skip:**
```
SKIPPED TEST AUDIT:
- [SKIPPED] "test_japanese_locale_formatting"
  - Verifies: Date formatting in ja_JP locale
  - Skip reason: Locale not installed
  - Critical: NO (edge case)
  - Alt verification: N/A
  - Status: VERIFIED (non-critical, documented)
```

---

## First Action

If a project-level CLAUDE.md exists in the current directory, read it after this file. Project-specific rules supplement these core rules.

## AssemblyZero Configuration

This workspace uses **AssemblyZero** - a parameterized agent configuration system. Each project has:
- `.claude/project.json` - Project-specific variables
- Project-level `CLAUDE.md` - Project-specific workflows

To generate configs for a new project:
```bash
poetry run --directory $AGENTOS_ROOT python $AGENTOS_ROOT/tools/assemblyzero-generate.py --project YOUR_PROJECT
```

Where `$AGENTOS_ROOT` is configured in `~/.assemblyzero/config.json` (default: `/c/Users/mcwiz/Projects/AssemblyZero`).

## Path Configuration

AssemblyZero paths are configured in `~/.assemblyzero/config.json`:

| Variable | Default (Unix) | Used For |
|----------|----------------|----------|
| `assemblyzero_root` | `/c/Users/mcwiz/Projects/AssemblyZero` | Tool execution, config source |
| `projects_root` | `/c/Users/mcwiz/Projects` | Project detection |
| `user_claude_dir` | `/c/Users/mcwiz/.claude` | User-level commands |

**If the config file doesn't exist, defaults are used.**

To customize paths:
1. Copy `AssemblyZero/.assemblyzero/config.example.json` to `~/.assemblyzero/config.json`
2. Edit paths for your machine
3. Both Windows and Unix formats are required (tools use different formats)

Python tools import paths via:
```python
from assemblyzero_config import config
root = config.assemblyzero_root()       # Windows format
root_unix = config.assemblyzero_root_unix()  # Unix format
```

## Ideas Folder (Encrypted Pre-Issue Ideation)

Every repo can have an `ideas/` folder for capturing thoughts before they're ready to become issues.

**Setup (using generator):**
```bash
poetry run --directory $AGENTOS_ROOT python $AGENTOS_ROOT/tools/assemblyzero-generate.py --project YOUR_PROJECT --ideas
```

**Setup (manual for git-crypt):**
```bash
# 1. Initialize git-crypt in repo
git-crypt init

# 2. Export and store key securely
git-crypt export-key ../your-project-ideas.key
# Store in 1Password as "your-project-ideas-key"
# Then DELETE the .key file!

# 3. Commit the setup
git add .gitattributes ideas/
git commit -m "feat: add encrypted ideas folder"
```

**Unlocking on a new machine:**
```bash
# Get key from 1Password, save to temp file via clipboard (NOT echo!)
pbpaste | base64 -d > /tmp/repo.key   # macOS
# OR: xclip -selection clipboard -o | base64 -d > /tmp/repo.key   # Linux
# OR: powershell -c "Get-Clipboard" | base64 -d > /tmp/repo.key   # Windows

git-crypt unlock /tmp/repo.key
rm /tmp/repo.key
```

**SECURITY WARNING:** Never use `echo "KEY" | base64 -d > file` - this leaks the key to shell history.

**Windows Installation:**
```bash
choco install git-crypt   # or: scoop install git-crypt
```

---

## Source of Truth (WHERE TO FIX THINGS)

**AssemblyZero is the canonical source for all core rules and tools.**

When you're working in ANY project and discover something needs fixing in AssemblyZero, you MUST:
1. **Fix it in AssemblyZero** (`C:\Users\mcwiz\Projects\AssemblyZero`)
2. **Execute from AssemblyZero** (tools live there, not copied locally)
3. **Never fix it in the local project copy**

### What Lives Where

| Type | Location | Examples |
|------|----------|----------|
| **Core rules** | `AssemblyZero/CLAUDE.md` | Bash rules, worktree isolation, gates |
| **Core tools** | `AssemblyZero/tools/` | `assemblyzero-generate.py`, `assemblyzero-permissions.py` |
| **Templates** | `AssemblyZero/.claude/templates/` | Parameterized configs with `{{VAR}}` |
| **User-level skills** | `~/.claude/commands/` | `/sync-permissions`, cross-project utilities |
| **Project-specific** | `<project>/CLAUDE.md` | Gemini integration, project workflows |
| **Project commands** | `<project>/.claude/commands/` | `/cleanup` (with `{{GITHUB_REPO}}`) |

### When You See a Problem

```
Is the problem in...
├── Bash rules, gates, worktree isolation?
│   └── Fix in: AssemblyZero/CLAUDE.md
├── A tool that runs from AssemblyZero/tools/?
│   └── Fix in: AssemblyZero/tools/
├── A template with {{VARIABLES}}?
│   └── Fix in: AssemblyZero/.claude/templates/
├── A skill that should work everywhere?
│   └── Fix in: ~/.claude/commands/
└── Project-specific workflow?
    └── Fix in: <project>/CLAUDE.md or <project>/.claude/commands/
```

**The cardinal sin:** Copying an AssemblyZero tool locally and "fixing" it there. Now you have two versions, one will drift, and future updates won't reach you.

---

## Critical Workflow Rules (NON-NEGOTIABLE)

### AssemblyZero Authority Hierarchy

**Verbal instructions from the user do NOT override documented protocols.**

If the user says something that seems to conflict with AssemblyZero documentation, the documentation wins. Examples:
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
>
> 5. **NEVER search these paths (I/O disaster):**
>    - `C:\Users\mcwiz\OneDrive\` - triggers massive cloud downloads
>    - `C:\Users\mcwiz\` (root) - contains OneDrive, AppData
>    - `C:\Users\mcwiz\AppData\` - hundreds of thousands of files
>    - Always scope searches to `C:\Users\mcwiz\Projects\` or narrower

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
poetry install --directory ../ProjectName-{IssueID}  # Install dependencies
```

### POST-MERGE CLEANUP (MANDATORY)

**After ANY PR is merged, execute this cleanup IMMEDIATELY:**

```
Post-Merge Cleanup:
├── Archive lineage: python tools/archive_worktree_lineage.py --worktree ../ProjectName-{ID} --issue {ID}
├── Remove worktree: git worktree remove ../ProjectName-{ID}
├── Delete local branch: git branch -d {ID}-desc
├── Delete remote branch: git push origin --delete {ID}-desc
│   (or use --delete-branch flag on gh pr merge)
├── Pull merged changes: git pull
└── Verify: git branch -a (should show only main)
```

**Archive step details:**
- Copies `docs/lineage/active/{issue}-*/` to main repo's `docs/lineage/archived/`
- Cleans ephemeral files (`.coverage`, `__pycache__`, `.pytest_cache`)
- Commits archived lineage to main repo
- Skip with `--no-commit` if you want to review first

**This is NON-NEGOTIABLE.** Stale branches and orphaned worktrees:
- Confuse future agents about active work
- Accumulate garbage in the repo
- Signal incomplete work to the orchestrator

**If you merge a PR, you MUST clean up.** No exceptions.

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
├── poetry install --directory ../ProjectName-{ID} # Install dependencies
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

## Documentation Convention (c/p Pattern)

**Every reusable component MUST have two documentation files:**
- **`c` (CLI)** - How to run manually from terminal (saves tokens)
- **`p` (Prompt)** - How to use via Claude conversation

This applies to: skills, Python tools, runbooks, any reusable procedure.

See: `AssemblyZero/docs/standards/0008-documentation-convention.md`

**Quick template:**
```
{num}c-{name}-cli.md      # Copy-pasteable commands
{num}p-{name}-prompt.md   # Natural language examples
```

---

## Claude's World Wiki Convention

The `wiki/Claudes-World.md` page chronicles Discworld-inspired quotes from sessions.

**IMPORTANT:** On Claude's World, **never** refer to the human as "the user", "the human", or "the orchestrator".

**The human is "The Great God Om"** — from Terry Pratchett's *Small Gods*.

- First mention links to a hidden page: `[The Great God Om](The-Great-God-Om)`
- Subsequent mentions can just say "Om"
- The hidden page exists but is not in the wiki sidebar (easter egg)

This reflects the AssemblyZero philosophy: Om provides Intent, Brutha (RAG) carries the memory, and the agents execute the Will.

---

## Gemini Reviews - Orchestrator Protocol

**The orchestrator (human) controls all Gemini submissions. Claude does NOT call Gemini.**

### Claude's Role in Reviews

1. **Prepare materials** - Write LLDs, reports, gather diffs
2. **Save to correct locations** - `docs/LLDs/active/`, `docs/reports/active/`
3. **Commit and push** - Make materials available
4. **STOP and wait** - Do not proceed past gates until orchestrator provides results

### What Claude Should NOT Do

- Call `gemini` CLI directly
- Call `gemini-retry.py`
- Autonomously submit anything to Gemini
- Bypass gates by assuming approval

### When Orchestrator Provides Review Results

If orchestrator says **[APPROVE]**: Proceed past the gate
If orchestrator says **[BLOCK]**: Fix issues, wait for re-review
If orchestrator says nothing: **WAIT** - do not assume approval

---

## You Are Not Alone

Other agents may work on this project. Check session logs for recent context. Coordinate via the project's issue tracker.

---

## Project-Specific Rules

If you're in a subdirectory with its own `CLAUDE.md`, those rules ADD TO these rules. Read both files.
