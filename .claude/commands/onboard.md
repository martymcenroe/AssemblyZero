---
description: Agent onboarding (quick/full mode)
argument-hint: "[--help] [--refresh | --quick | --full]"
---

# Agent Onboarding

**If `$ARGUMENTS` contains `--help`:** Display the Help section below and STOP. Do not execute onboarding.

Onboard yourself to the current project by reading and understanding the documentation.

## Help

```
/onboard - Agent onboarding for current project

Usage: `/onboard [--help] [--refresh | --quick | --full]`

Options:
| Flag | Effect |
|------|--------|
| `--help` | Show this help message and exit |
| `--refresh` | Reload rules only (~$0.01, 15s) - for post-compact/resumed sessions |
| `--quick` | Read digest only, report age (~$0.02, 30s) - for simple tasks |
| `--full` | Full onboarding (~$0.35, 2min) - for complex work (default) |

Examples:
- `/onboard --help` - show this help
- `/onboard --refresh` - reload rules after context compaction
- `/onboard --quick` - quick onboard for status check
- `/onboard --full` - full onboard for feature work
- `/onboard` - same as --full
```

## Step 0: Project Detection (ALWAYS FIRST)

Detect the current project from working directory:
1. Get working directory (e.g., `/c/Users/mcwiz/Projects/AssemblyZero`)
2. Extract project name from path → `AssemblyZero`
3. Project root (Windows): `C:\Users\mcwiz\Projects\{PROJECT}`
4. Project root (Unix): `/c/Users/mcwiz/Projects/{PROJECT}`

**Known Projects and Their Structure:**

| Project | GitHub Repo | Main Guide | Immediate Plan |
|---------|-------------|------------|----------------|
| AssemblyZero | martymcenroe/AssemblyZero | `docs/index.md` | `docs/10000a-IMMEDIATE-PLAN.md` |
| Aletheia | martymcenroe/Aletheia | `docs/10000-GUIDE.md` | `docs/10000a-IMMEDIATE-PLAN.md` |
| Talos | martymcenroe/Talos | `docs/10000-GUIDE.md` | `docs/10000a-IMMEDIATE-PLAN.md` |
| maintenance | martymcenroe/maintenance | `docs/10000-GUIDE.md` | `docs/10000a-IMMEDIATE-PLAN.md` |
| claude-code | anthropics/claude-code | `README.md` | None |

**CRITICAL:** Use the correct file paths for the detected project. Do NOT use Aletheia paths when in AssemblyZero.

## Modes

| Mode | Cost | Time | Use Case |
|------|------|------|----------|
| `--refresh` | ~$0.01 | ~15s | Post-compact, resumed sessions, rule reload |
| `--quick` | ~$0.02 | ~30s | Simple tasks, status checks |
| `--full` (default) | ~$0.35 | ~2min | Complex features, audits |

## Refresh Mode (`--refresh`)

**Purpose:** Reload core rules after context compaction or when resuming a session. Does NOT re-read project state or session logs.

**Model hint:** Refresh mode can use **Haiku** since it only reads rule files.

**Use when:**
- Session was compacted and you need to reload rules
- Resuming a session with `/resume` and need rules refreshed
- You've been working for a while and want to re-anchor on constraints
- Quick sanity check that bash rules, worktree rules, etc. are loaded

**Steps (parallel reads):**

1. Read AssemblyZero core rules:
   `C:\Users\mcwiz\Projects\AssemblyZero\CLAUDE.md`

2. Read Projects root rules (if exists):
   `C:\Users\mcwiz\Projects\CLAUDE.md`

3. Read current project CLAUDE.md (detected from working directory)

4. Read Gemini rotation instructions (CRITICAL for reviews):
   `C:\Users\mcwiz\Projects\AssemblyZero\docs\prompts\gemini-rotation-instructions.md`

5. Optionally scan current permissions:
   `C:\Users\mcwiz\Projects\.claude\settings.local.json` (just the `allow` array)

**Report format:**
```
✓ Rules refreshed for {PROJECT}
• AssemblyZero core: Bash constraints, worktree isolation, visible self-check
• Gemini: Rotation tool, encoding rules, model verification
• Project rules: {one-line summary}
• Session permissions: {count} active allows
Ready to continue.
```

## Quick Mode (`--quick`)

**Model hint:** Quick mode can use **Haiku** (~66% cost savings) since it only reads existing docs.

Read only the essential files for the detected project:
1. Read `CLAUDE.md` in the project root
2. Read the project's main guide (see table above)
3. Glob `docs/session-logs/*.md` and read the most recent entry
4. Report readiness

**Use when:** Task is simple, context is clear, or you're resuming recent work.

## Full Mode (`--full` or no argument)

Complete onboarding for the **detected project**:

### Step 1: Core Documentation (parallel reads)

Read these files simultaneously based on project:

**For AssemblyZero:**
- `CLAUDE.md` - Core rules
- `docs/index.md` - Documentation index
- `docs/10000a-IMMEDIATE-PLAN.md` - Current focus (AssemblyZero-specific work only)

**For Aletheia:**
- `CLAUDE.md` - Project rules
- `docs/10000-GUIDE.md` - Filing system and prime directives
- `docs/10000a-IMMEDIATE-PLAN.md` - Current sprint focus

**For Talos:**
- `CLAUDE.md` - Project rules
- `docs/10000-GUIDE.md` - Project guide
- `docs/10000a-IMMEDIATE-PLAN.md` - Current focus (if exists)

**For maintenance:**
- `CLAUDE.md` - Project rules
- `docs/10000-GUIDE.md` - Project guide
- `docs/10000a-IMMEDIATE-PLAN.md` - Current focus (may be empty for ad-hoc project)

**For claude-code:**
- `README.md` - Project overview
- `CONTRIBUTING.md` - Contribution guidelines (if exists)

### Step 2: Current State

1. Read recent session log: Glob `docs/session-logs/*.md`, read most recent (last 3 entries)
2. Check open issues: `gh issue list --state open --limit 10 --repo {GITHUB_REPO}`
   - Use the correct repo from the table above
   - If repo unknown, get it from: `git remote -v`

### Step 3: Project-Specific Setup

**Aletheia only:**
- Check for `docs/10000b-ONBOARD-DIGEST.md` and read it
- Check for `tools/generate_onboard_digest.py` and run it if exists

### Step 4: Acknowledge

Report:
1. **Project name** - Which project you onboarded to
2. **Project type** - What kind of project it is
3. **Current focus** - From sprint doc or recent session
4. **Top 3 priority issues** - If any open issues exist
5. **Ready for command**

## Rules

- Use absolute paths and `git -C` patterns (no cd && chaining)
- Use `--repo {owner}/{repo}` for all gh commands (see table above)
- Never use forbidden commands (git reset, git push --force, pip install, etc.)
- **Code changes** require worktrees - never commit code directly to main
- **Documentation changes** can be committed directly to main (no worktree needed)

## Efficiency Notes

To minimize cost:
1. **Parallel reads** - Read independent files simultaneously
2. **Scan, don't deep-read** - For issue lists, scan titles/labels, skip bodies unless relevant
3. **Recent entries only** - For session logs, read last 3 entries, not the entire file

## Fallback for Unknown Projects

If the project is not in the known projects table:
1. Read `CLAUDE.md` (if exists)
2. Read `README.md`
3. Try `docs/10000-GUIDE.md` or `docs/index.md`
4. List top-level directories to understand structure
5. Get GitHub repo from: `git remote -v`
6. Report: "Project {NAME} - onboarding complete. Structure: {description}"
