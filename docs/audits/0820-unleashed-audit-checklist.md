# Unleashed Audit Checklist

**Document ID:** 0820-unleashed-audit-checklist
**Last Updated:** 2026-01-16
**Purpose:** Verification procedures for unleashed tool suite

---

## Quick Version Check

```bash
# Run from any directory
unleashed --version          # Expected: 1.4.0
unleashed-test --version     # Expected: 1.4.0-t
unleashed-danger --version   # Expected: 1.4.0-danger
unleashed-danger-test --version  # Expected: 1.4.0-danger-t
```

---

## Version Verification

| Command | Expected Version | Actual | Pass? |
|---------|------------------|--------|-------|
| `unleashed --version` | `1.4.0` | | [ ] |
| `unleashed-test --version` | `1.4.0-t` | | [ ] |
| `unleashed-danger --version` | `1.4.0-danger` | | [ ] |
| `unleashed-danger-test --version` | `1.4.0-danger-t` | | [ ] |

**Version Format Rules:**
- Non-danger track: `1.x.y` (production), `1.x.y-t` (test)
- Danger track: `1.x.y-danger` (production), `1.x.y-danger-t` (test)

---

## unleashed-danger: No Interruption Guarantee

**CRITICAL:** unleashed-danger must NEVER send Escape or any character to Claude that would interrupt it.

### Automated Code Audit

Run these grep commands from `AgentOS/tools/` directory:

```bash
# Check 1: No bare escape writes (must return 0 lines, excluding comments)
grep -n "\.write('\\\x1b')" unleashed-danger.py | grep -v "^#"
# Expected: (no output)

# Check 2: No escape writes via variable (excluding Shift+Tab which is OK)
grep -n "write.*\\\\x1b" unleashed-danger.py | grep -v "\[Z" | grep -v "^#"
# Expected: Only lines with \x1b[Z (Shift+Tab) are OK

# Check 3: No safety handler calls in _handle_countdown
grep -n "_handle_hard_block\|_handle_dangerous\|_handle_git" unleashed-danger.py
# Expected: (no output - methods should not exist in danger version)
```

### Manual Code Review Checklist

- [ ] `_handle_countdown` does NOT call `_handle_hard_block`
- [ ] `_handle_countdown` does NOT call `_handle_dangerous_confirmation`
- [ ] `_handle_countdown` does NOT call `_handle_git_confirmation`
- [ ] No `self.pty_process.write('\x1b')` calls exist (except Shift+Tab `\x1b[Z`)
- [ ] InputReader filters Escape sequences (drops them, never passes through)

---

## Debug Output Verification

### Production Versions (NO debug output)

```bash
# Check unleashed.py has no DEBUG variable
grep -n "^DEBUG" unleashed.py
# Expected: (no output)

# Check unleashed-danger.py has no DEBUG variable
grep -n "^DEBUG" unleashed-danger.py
# Expected: (no output)

# Check no sys.stderr.write DEBUG lines in production
grep -n "sys.stderr.write.*DEBUG" unleashed.py unleashed-danger.py
# Expected: (no output)

# Check no debug_log function in production
grep -n "def debug_log" unleashed.py unleashed-danger.py
# Expected: (no output)
```

### Test Versions (debug output gated by --debug flag)

```bash
# Check unleashed-test.py has DEBUG variable
grep -n "^DEBUG = False" unleashed-test.py
# Expected: Line showing DEBUG = False

# Check unleashed-danger-test.py has DEBUG variable
grep -n "^DEBUG = False" unleashed-danger-test.py
# Expected: Line showing DEBUG = False

# Check test versions have debug_log function
grep -n "def debug_log" unleashed-test.py unleashed-danger-test.py
# Expected: Both files have debug_log function
```

---

## Input Filtering (Danger Mode)

### Aggressive Filter Verification

The danger mode InputReader must filter terminal response characters:

```bash
# Check InputReader filters terminal response chars
grep -n "0123456789;\[\]?c" unleashed-danger.py unleashed-danger-test.py
# Expected: Shows the filter string in _reader_thread
```

**Filtered Characters (must NOT pass through):**
- Digits (0-9) - part of terminal responses
- Semicolons (;) - CSI parameter separator
- Brackets ([ ]) - CSI sequences
- Question mark (?) - terminal mode queries
- Letter 'c' - device attributes response terminator

**Safe Characters (should pass through):**
- Printable ASCII (32-126)
- Tab (9)
- Enter (13)
- Backspace (8)

---

## Alias Verification

```bash
# Verify aliases are properly configured
type unleashed
# Expected: unleashed is aliased to `poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/unleashed.py --cwd "$(pwd)"`

type unleashed-test
# Expected: unleashed-test is aliased to `poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/unleashed-test.py --cwd "$(pwd)"`

type unleashed-danger
# Expected: unleashed-danger is aliased to `poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/unleashed-danger.py --cwd "$(pwd)"`

type unleashed-danger-test
# Expected: unleashed-danger-test is aliased to `poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/unleashed-danger-test.py --cwd "$(pwd)"`
```

---

## Safety Check Verification (Non-Danger Versions Only)

### Production unleashed.py

```bash
# Verify safety checks exist in production
grep -n "check_hard_block\|check_dangerous_path\|check_git_destructive" unleashed.py
# Expected: Multiple function definitions AND calls in _handle_countdown

# Verify _handle_hard_block exists and sends Escape
grep -n "_handle_hard_block" unleashed.py
grep -n "write.*\\\\x1b" unleashed.py | grep -v "\[Z"
# Expected: _handle_hard_block sends Escape to cancel dangerous commands
```

---

## Functional Test Checklist

### Test 1: Basic Auto-Approval

1. [ ] Run `unleashed` and start a Claude session
2. [ ] Trigger a permission prompt (e.g., Bash command)
3. [ ] Wait for 10s countdown
4. [ ] Verify auto-approval occurs
5. [ ] Press a key during countdown to verify cancellation

### Test 2: Debug Mode (Test Versions)

1. [ ] Run `unleashed-test --debug`
2. [ ] Verify `[DEBUG]` messages appear on stderr
3. [ ] Test footer detection, input filtering, countdown
4. [ ] Verify debug output provides useful diagnostics

### Test 3: Danger Mode No-Interrupt

1. [ ] Run `unleashed-danger`
2. [ ] Trigger multiple permission prompts
3. [ ] Verify Claude is NEVER interrupted by terminal garbage
4. [ ] Verify countdown and auto-approval work reliably

---

## Change Workflow Verification

When making changes to unleashed:

1. [ ] Deploy changes to `*-test.py` file first
2. [ ] Test with `unleashed-test` or `unleashed-danger-test`
3. [ ] Verify functionality works as expected
4. [ ] Run this audit checklist
5. [ ] Promote to production version
6. [ ] Increment version appropriately
7. [ ] Run audit checklist again

---

## File Summary

| File | Purpose | Version Format |
|------|---------|----------------|
| `unleashed.py` | Production with safety checks | `1.x.y` |
| `unleashed-test.py` | Test version with --debug | `1.x.y-t` |
| `unleashed-danger.py` | Production no safety checks | `1.x.y-danger` |
| `unleashed-danger-test.py` | Test danger with --debug | `1.x.y-danger-t` |

---

## Audit Sign-Off

| Audit Item | Status | Auditor | Date |
|------------|--------|---------|------|
| Version verification | | | |
| No-interrupt guarantee | | | |
| Debug output verification | | | |
| Input filtering | | | |
| Alias verification | | | |
| Safety checks (non-danger) | | | |
| Functional tests | | | |

**Notes:**

---

*Run this checklist after any changes to the unleashed tool suite.*
