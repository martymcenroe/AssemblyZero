# 0603 Unleashed - Auto-Approval PTY Wrapper

**Tools:** `tools/unleashed.py`, `tools/unleashed-danger.py` (+ test variants)
**Issue:** [#10](https://github.com/martymcenroe/AgentOS/issues/10)
**Audit:** [0820-unleashed-audit-checklist.md](../audits/0820-unleashed-audit-checklist.md)

---

## Overview

Unleashed is a PTY wrapper that eliminates permission friction by auto-approving Claude Code permission prompts after a 10-second countdown, giving users a window to cancel.

**Use case:** Unattended or low-friction Claude sessions where you trust the operations but want a safety window.

---

## File Structure

| File | Purpose | Version Format |
|------|---------|----------------|
| `unleashed.py` | Production with safety checks | `1.x.y` |
| `unleashed-test.py` | Test version with `--debug` flag | `1.x.y-t` |
| `unleashed-danger.py` | Production, NO safety checks | `1.x.y-danger` |
| `unleashed-danger-test.py` | Test danger with `--debug` flag | `1.x.y-danger-t` |

### When to Use Which

| Scenario | Recommended |
|----------|-------------|
| Normal development work | `unleashed` |
| Debugging unleashed issues | `unleashed-test --debug` |
| Uninterrupted long-running tasks | `unleashed-danger` |
| Debugging danger mode issues | `unleashed-danger-test --debug` |

---

## Quick Start

### Bash Aliases (Recommended)

These aliases are configured in `~/.bash_profile`:

```bash
# Production versions
unleashed                    # Normal with safety checks
unleashed-danger             # No safety checks, no interrupts

# Test versions (deploy changes here first)
unleashed-test               # Test with --debug available
unleashed-danger-test        # Test danger with --debug available
```

### Direct Invocation

```bash
# Production
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python tools/unleashed.py --cwd "$(pwd)"

# With options
unleashed --delay 5          # 5-second countdown
unleashed --dry-run          # Test detection without injection
unleashed-test --debug       # Verbose debug output
```

### Check Version

```bash
unleashed --version              # 1.4.0
unleashed-test --version         # 1.4.0-t
unleashed-danger --version       # 1.4.0-danger
unleashed-danger-test --version  # 1.4.0-danger-t
```

---

## Safety Checks (Normal Mode Only)

The production `unleashed.py` includes safety checks that `unleashed-danger.py` does NOT have:

### 1. Hard Block

**NEVER auto-approves** destructive commands outside of `Projects/` directory:

| Command | Within Projects | Outside Projects |
|---------|-----------------|------------------|
| `rm`, `rm -rf` | Normal countdown | **HARD BLOCK** |
| `del`, `Remove-Item` | Normal countdown | **HARD BLOCK** |
| `dd if=...` | **HARD BLOCK** | **HARD BLOCK** |
| `mkfs`, `shred` | **HARD BLOCK** | **HARD BLOCK** |

### 2. Dangerous Path Detection

Requires explicit `yes` confirmation for commands targeting:
- User home root (`/c/Users/mcwiz/`)
- OneDrive, Dropbox, Google Drive
- AppData, `.cache`

### 3. Git Destructive Commands

Requires explicit `yes` confirmation in Projects:
- `git reset --hard`
- `git clean -fd`
- `git push --force`
- `git branch -D`

### Configuration Files

| File | Purpose |
|------|---------|
| `~/.agentos/excluded_paths.txt` | Additional dangerous path patterns |
| `~/.agentos/hard_block_commands.txt` | Additional commands to hard block |
| `~/.agentos/safe_paths.txt` | Additional safe paths for destructive commands |

---

## Danger Mode

`unleashed-danger` is for when you need **uninterrupted Claude operation** and accept all risks.

### Differences from Normal Mode

| Feature | Normal | Danger |
|---------|--------|--------|
| Hard block checks | Yes | **No** |
| Dangerous path detection | Yes | **No** |
| Git destructive warnings | Yes | **No** |
| Sends Escape to Claude | Yes (on block/cancel) | **Never** |
| Input filtering | Standard | **Aggressive** |

### No-Interrupt Guarantee

Danger mode will **NEVER** send Escape or any character to Claude that would interrupt it:
- No bare `\x1b` (Escape) writes
- Terminal response garbage is aggressively filtered
- Only safe user input passes through

### Aggressive Input Filtering

Danger mode filters out terminal response characters that could interrupt Claude:
- Digits (0-9) - part of terminal responses
- Semicolons (;) - CSI parameter separator
- Brackets ([ ]) - CSI sequences
- Question mark (?) - terminal mode queries
- All escape sequences (except Shift+Tab for option selection)

---

## Debug Mode (Test Versions Only)

Test versions support `--debug` flag for verbose logging:

```bash
unleashed-test --debug
unleashed-danger-test --debug
```

Debug output includes:
- Footer detection logging
- Input character logging (what keys are received)
- Terminal response filtering logs
- Tool type detection
- Safety check results

**Production versions have NO debug output.**

---

## How It Works

### Detection

Unleashed detects permission prompts by looking for Claude Code's footer pattern:

```
Esc to cancel · Tab to add additional instructions
```

The regex handles Unicode variations in the separator (middle dot, en-dash, em-dash, hyphen).

### Countdown Sequence

1. Footer detected in PTY output
2. **Tool type detected** (Bash, Write, Edit, etc.)
3. **Safety checks applied** (normal mode only):
   - Hard block check
   - Git destructive check
   - Dangerous path check
4. Countdown overlay displayed (10 seconds default)
5. If user presses printable key → cancelled
6. If countdown completes → Enter injected, prompt approved

### 3-Option Prompt Handling

When Claude shows 3 options (including "Yes, and don't ask again..."), unleashed:
1. Sends Shift+Tab to select option 2
2. Sends Enter to confirm

This reduces future permission prompts for the same operation.

---

## Options

| Option | Description | Available In |
|--------|-------------|--------------|
| `--version`, `-v` | Show version and exit | All |
| `--dry-run` | Test detection without injecting Enter | All |
| `--delay N` | Countdown delay in seconds (default: 10) | All |
| `--cwd PATH` | Working directory for Claude | All |
| `--debug` | Enable verbose debug output | Test versions only |

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `UNLEASHED_DELAY` | Countdown delay in seconds | 10 |
| `UNLEASHED_VERSION` | Set by unleashed for `/unleashed-version` skill | - |

---

## Logging

All sessions are logged to `AgentOS/logs/`:

### Log Files

| Mode | Raw Log | Event Log |
|------|---------|-----------|
| Normal | `unleashed_TIMESTAMP.log` | `unleashed_events_TIMESTAMP.jsonl` |
| Danger | `unleashed-danger_TIMESTAMP.log` | `unleashed-danger_events_TIMESTAMP.jsonl` |

### Event Types

| Event | Description |
|-------|-------------|
| `START` | Session started |
| `FOOTER_DETECTED` | Permission prompt detected |
| `PERMISSION_PROMPT` | Tool type detected (normal mode) |
| `PATH_CHECK` | Dangerous path check result (normal mode) |
| `HARD_BLOCK_TRIGGERED` | Command blocked (normal mode) |
| `GIT_DESTRUCTIVE_DETECTED` | Git command needs confirmation (normal mode) |
| `DANGEROUS_PATH_DETECTED` | Path needs confirmation (normal mode) |
| `COUNTDOWN_START` | Countdown began |
| `AUTO_APPROVED` | Prompt auto-approved |
| `CANCELLED_BY_USER` | User pressed key to cancel |
| `CHILD_EXITED` | Claude process exited |
| `END` | Session ended |

---

## Change Workflow

**Always deploy changes to test versions first:**

1. Make changes to `*-test.py` file
2. Test with `unleashed-test` or `unleashed-danger-test`
3. Use `--debug` flag to verify behavior
4. Run audit checklist: `docs/audits/0820-unleashed-audit-checklist.md`
5. Promote changes to production version
6. Increment version appropriately
7. Run audit checklist again

### Version Incrementing

| Change Type | Version Bump |
|-------------|--------------|
| Bug fix | `1.4.0` → `1.4.1` |
| New feature | `1.4.0` → `1.5.0` |
| Breaking change | `1.4.0` → `2.0.0` |

Test versions always match their production track with `-t` suffix.

---

## Troubleshooting

### "pywinpty not installed"

```bash
poetry add pywinpty
```

### Countdown doesn't trigger

1. Run with `--debug` (test version) to see footer detection
2. Check if the footer pattern is visible in Claude's output
3. Check raw log for the footer text

### Claude gets interrupted (danger mode)

This should not happen. If it does:
1. Run `unleashed-danger-test --debug`
2. Check input filtering logs
3. Report the issue with debug output

### TUI corruption

1. Press Ctrl+L to redraw Claude's screen
2. Try a larger terminal window
3. The terminal resets on exit (`\x1bc`)

### Input not working

1. Ensure running in proper terminal (Git Bash, Windows Terminal)
2. Not running in non-interactive shell
3. Check with `--debug` flag to see what input is received

---

## Architecture

```
┌─────────────────┐
│   User Input    │
│   (keyboard)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  InputReader    │────▶│   Unleashed     │
│  (msvcrt)       │     │   (main loop)   │
│  [filters in    │     └────────┬────────┘
│   danger mode]  │              │
└─────────────────┘    ┌─────────┴─────────┐
                       │                   │
                       ▼                   ▼
              ┌─────────────────┐  ┌─────────────────┐
              │  Footer Check   │  │  Safety Checks  │
              │  (regex match)  │  │  (normal only)  │
              └────────┬────────┘  │  - Hard block   │
                       │           │  - Git destruct │
                       │           │  - Danger path  │
                       │           └─────────────────┘
                       ▼
              ┌─────────────────┐
              │ CountdownOverlay│
              │ (ANSI escape)   │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Auto-Approve   │
              │  (Enter/Shift+  │
              │   Tab+Enter)    │
              └─────────────────┘
```

---

## Security Considerations

### Normal Mode (`unleashed`)

Provides safety checks but still auto-approves most operations:
- Hard blocks catastrophic commands (`dd`, `mkfs`, `shred`)
- Requires confirmation for destructive commands outside Projects
- Requires confirmation for git destructive commands
- Full audit logging

### Danger Mode (`unleashed-danger`)

**NO safety checks whatsoever.** Use only when:
- You fully trust the operations being performed
- You need uninterrupted Claude execution
- Permission prompts are pure friction with no protective value
- You accept responsibility for any destructive actions

### When NOT to Use Either

- Working with untrusted code
- Operations affecting production systems
- When you need to review each action
- When running commands from untrusted sources

---

## Dependencies

- `pywinpty` - PTY handling for Windows
- `msvcrt` - Windows keyboard input (built-in)
- Python 3.8+
- Git Bash or Windows Terminal

---

## Related Documentation

- [0820-unleashed-audit-checklist.md](../audits/0820-unleashed-audit-checklist.md) - Verification procedures
- [unleashed-shift-tab-bug-analysis.md](../reports/unleashed-shift-tab-bug-analysis.md) - Bug analysis report
