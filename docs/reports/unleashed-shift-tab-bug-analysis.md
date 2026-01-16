# Unleashed Shift+Tab Input Bug - Technical Analysis

**Date:** 2026-01-15
**Author:** Claude Opus 4.5
**Status:** Open - Needs Resolution
**Severity:** Medium (Feature broken, workaround exists: run Claude directly)
**Component:** `tools/unleashed.py` InputReader class

---

## 1. Executive Summary

The `unleashed` PTY wrapper tool cannot pass Shift+Tab keystrokes through to Claude Code when running in Git Bash (mintty) on Windows. This prevents users from toggling plan mode, accept-edits mode, and other Claude Code features that use Shift+Tab for cycling.

**Root Cause:** The `msvcrt` library used for keyboard input on Windows cannot distinguish Tab from Shift+Tab when running in a mintty terminal. The modifier key state is lost.

**Workaround:** Run `claude` directly without unleashed when plan mode toggling is needed.

---

## 2. Problem Description

### 2.1 Symptoms

1. User presses Shift+Tab in unleashed session
2. Claude Code shows "Use meta+t to toggle thinking" (wrong response)
3. Plan mode does not toggle
4. Status bar continues showing "shift+tab to cycle" but the shortcut doesn't work

### 2.2 Environment

- **OS:** Windows 10/11
- **Terminal:** Git Bash (mintty)
- **Python:** 3.11+
- **Unleashed Version:** 1.3.0+ (issue introduced with hard block features)
- **Claude Code Version:** 2.1.7

### 2.3 Reproduction Steps

1. Open Git Bash terminal
2. Run `unleashed` to start Claude Code wrapper
3. Wait for Claude prompt
4. Press Shift+Tab
5. **Expected:** Status bar cycles through modes (plan mode on/off, accept edits on/off)
6. **Actual:** Nothing happens or wrong message appears

### 2.4 Verification

Running `claude` directly (without unleashed) confirms Shift+Tab works:
- Status bar correctly shows mode cycling
- User can toggle between: (none) → "accept edits on" → "plan mode on" → (none)

---

## 3. Technical Investigation

### 3.1 Input Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Git Bash (mintty)                            │
│  User types → mintty captures → sends to child process stdin    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      unleashed.py                                │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ InputReader  │    │   Main Loop  │    │  winpty PTY  │       │
│  │ (msvcrt)     │───▶│              │───▶│  (Claude)    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                                                        │
│         │ msvcrt.kbhit() / msvcrt.getwch()                      │
│         │ Cannot see Shift modifier!                             │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Debug Log Analysis

Debug logging was added to capture actual keyboard input received:

```
# Regular Tab (ord=9):
char='\t' ord=9

# Escape sequence (terminal response, NOT user input):
char='\x1b' ord=27
  escape_seq='\x1b[?61;4;6;7;14;21;22;23;24;28;32;42;52c'
```

**Key Finding:** When Shift+Tab is pressed:
- msvcrt receives `\t` (regular Tab, ord=9)
- NOT `\x00\x0f` (Windows scan code for Shift+Tab)
- NOT `\x1b[Z` (ANSI escape sequence for Shift+Tab)

### 3.3 Root Cause

**msvcrt limitations in mintty:**

1. `msvcrt.getwch()` reads Windows console input
2. It returns only the character, NOT modifier key state
3. In native Windows console, Shift+Tab sends `\x00\x0f` (null + scan code 15)
4. In mintty (Git Bash), Shift+Tab sends `\x1b[Z` to stdin
5. msvcrt doesn't see stdin escape sequences from mintty
6. Result: Shift+Tab is received as plain Tab (`\t`)

**Why Claude works directly:**

When running `claude` directly:
- Claude Code uses a library that reads raw stdin
- mintty sends `\x1b[Z` to stdin for Shift+Tab
- Claude receives and processes it correctly

---

## 4. Attempted Solutions

### 4.1 Version History

| Version | Approach | Result |
|---------|----------|--------|
| 1.3.6 | Detect Git Bash, use Unix stdin instead of msvcrt | **BROKEN** - select() doesn't work on stdin on Windows |
| 1.3.7 | Add debug logging to capture actual input | Diagnostic only |
| 1.3.8 | Add separate stdin reader thread for escape sequences | **BROKEN** - Terminal responses leaked through, garbled output |
| 1.3.9 | Filter terminal responses (DA1, CPR) | Fixed garbage, but Shift+Tab still broken |

### 4.2 Detailed Attempt Analysis

#### 4.2.1 Unix-style stdin reading (v1.3.6)

```python
# Attempted fix:
if os.environ.get('MSYSTEM'):  # Detect Git Bash
    HAS_MSVCRT = False  # Use Unix-style input

# In reader thread:
if select.select([sys.stdin], [], [], 0.01)[0]:
    char = sys.stdin.read(1)
```

**Failure reason:** `select()` on Windows only works with sockets, not file handles or stdin. This caused complete input failure.

#### 4.2.2 Dual-thread stdin reader (v1.3.8)

```python
# Two threads:
# 1. msvcrt_thread - reads via msvcrt for regular keys
# 2. stdin_thread - reads via sys.stdin.buffer for escape sequences

def _stdin_reader(self):
    stdin = sys.stdin.buffer
    while self.running:
        char = stdin.read(1)  # Blocking read
        if char == b'\x1b':
            # Read escape sequence...
```

**Failure reason:**
- stdin.read() is blocking and captured terminal responses (DA1: `\x1b[?61;...c`)
- These responses were passed through to Claude, appearing as garbage
- Input got mixed up between the two readers

#### 4.2.3 Terminal response filtering (v1.3.9)

```python
# Filter known terminal responses:
if seq.startswith('\x1b[?') and seq.endswith('c'):
    # DA1 response - discard
    pass
elif len(seq) > 3 and seq[-1] == 'R' and seq[2].isdigit():
    # CPR response - discard
    pass
else:
    self.queue.put(seq)  # User input - pass through
```

**Result:** Fixed garbage characters, but doesn't solve Shift+Tab (msvcrt still can't see it).

---

## 5. Alternative Approaches (Not Yet Tried)

### 5.1 Use `pynput` or `keyboard` library

**Approach:** Use a cross-platform keyboard library that can detect modifier keys.

```python
from pynput import keyboard

def on_press(key):
    # Can detect key + modifiers
    pass
```

**Pros:**
- Cross-platform
- Can detect modifier keys
- Well-maintained libraries

**Cons:**
- Adds dependency
- May require elevated permissions
- May not work in all terminal contexts

**Estimated Effort:** Medium

### 5.2 Use `pywinpty` input handling

**Approach:** Check if pywinpty has built-in input handling that could be used instead of separate msvcrt reading.

```python
# Investigate winpty.PtyProcess API for input handling
# May have methods to read from the controlling terminal
```

**Pros:**
- Already a dependency
- Designed for PTY handling

**Cons:**
- May not have this functionality
- Limited documentation

**Estimated Effort:** Low (investigation) to High (if needs modification)

### 5.3 Pipe stdin directly to PTY

**Approach:** Instead of reading stdin separately, pipe it directly to the PTY.

```python
# Use os.dup2() or similar to connect stdin to PTY
# Or use threading.Thread to copy stdin to PTY
```

**Pros:**
- Would preserve all escape sequences
- Simplifies input handling

**Cons:**
- May interfere with unleashed's ability to intercept input during countdown
- Could break the permission prompt detection

**Estimated Effort:** High

### 5.4 Use ConPTY instead of winpty

**Approach:** Windows 10+ has native ConPTY (Console Pseudoterminal) support. Use Windows.Terminal APIs directly.

```python
# Use Windows ConPTY APIs via ctypes or a wrapper library
```

**Pros:**
- Native Windows support
- May handle input better

**Cons:**
- Windows 10+ only
- More complex implementation
- May not solve mintty-specific issues

**Estimated Effort:** Very High

### 5.5 Fork input handling during non-countdown periods

**Approach:** Only use custom input reading during countdown; otherwise pass stdin directly through.

```python
def run(self):
    while self.running:
        if self.in_countdown:
            # Use custom input reader (can intercept)
            self._handle_countdown_input()
        else:
            # Direct passthrough - preserve escape sequences
            self._passthrough_input()
```

**Pros:**
- Shift+Tab would work when not in countdown
- Maintains countdown cancellation ability

**Cons:**
- Increased complexity
- May have race conditions at boundaries

**Estimated Effort:** Medium

### 5.6 Read from /dev/tty on Git Bash

**Approach:** Git Bash provides Unix-like device files. Try reading from `/dev/tty`.

```python
if os.path.exists('/dev/tty'):
    tty = open('/dev/tty', 'rb', buffering=0)
    # Read directly from terminal
```

**Pros:**
- More direct access to terminal input
- May receive escape sequences correctly

**Cons:**
- Git Bash specific
- May not work in all configurations

**Estimated Effort:** Medium

### 5.7 Use Windows Console Virtual Terminal Sequences

**Approach:** Enable VT sequence processing and read raw input.

```python
import ctypes
kernel32 = ctypes.windll.kernel32

# Enable virtual terminal processing
ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200
kernel32.SetConsoleMode(handle, ENABLE_VIRTUAL_TERMINAL_INPUT)
```

**Pros:**
- Native Windows API
- May enable escape sequence reading

**Cons:**
- May not work with mintty (not Windows console)
- Complex implementation

**Estimated Effort:** High

---

## 6. Recommended Investigation Order

1. **5.6 - /dev/tty reading** (Low risk, medium effort)
   - Quick to test if it works in Git Bash

2. **5.5 - Fork input handling** (Medium risk, medium effort)
   - Preserves existing functionality while fixing Shift+Tab

3. **5.2 - pywinpty investigation** (Low risk, low effort)
   - May already have a solution we're not using

4. **5.1 - pynput/keyboard library** (Low risk, medium effort)
   - Known working solutions for keyboard input

---

## 7. Impact Assessment

### 7.1 Affected Features

- Plan mode toggle (Shift+Tab)
- Accept edits mode toggle (Shift+Tab)
- Any other Claude Code shortcuts using Shift+Tab

### 7.2 User Impact

- **Severity:** Medium
- **Frequency:** Every unleashed session
- **Workaround:** Run `claude` directly when mode toggling needed

### 7.3 Scope

- Only affects Windows + Git Bash (mintty)
- Does not affect native Windows Terminal (probably)
- Does not affect macOS/Linux (untested, but likely uses different input)

---

## 8. Related Issues

- **INC-001:** OneDrive Mass Download (2026-01-15) - Same debugging session
- Hard block feature additions (v1.3.0) - Trigger for investigation

---

## 9. Files Involved

| File | Role |
|------|------|
| `tools/unleashed.py` | Main PTY wrapper, InputReader class |
| `~/.agentos/input_debug.log` | Debug output for keyboard analysis |

---

## 10. References

- [pywinpty documentation](https://github.com/spyder-ide/pywinpty)
- [mintty documentation](https://mintty.github.io/)
- [Windows Console Virtual Terminal Sequences](https://docs.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences)
- [msvcrt module documentation](https://docs.python.org/3/library/msvcrt.html)

---

## 11. Appendix: Debug Log Sample

```
# From ~/.agentos/input_debug.log during Shift+Tab testing:

char='\x1b' ord=27
  escape_seq='\x1b[?61;4;6;7;14;21;22;23;24;28;32;42;52c'
  FILTERED (DA1 response)
char='\t' ord=9          # <-- Shift+Tab received as plain Tab!
char='\t' ord=9
char='\t' ord=9
char='e' ord=101
char='x' ord=120
char='i' ord=105
char='t' ord=116
char='\r' ord=13
```

Note: Multiple Tab characters (ord=9) when Shift+Tab was pressed confirms msvcrt cannot distinguish the two.

---

## 12. Gemini 3 Pro Review (2026-01-15)

**Reviewer:** Gemini 3 Pro Preview via gemini-rotate.py
**Verdict:** Root cause analysis accurate, documentation comprehensive

### Key Finding

> "msvcrt is the wrong tool for mintty. The analysis is accurate."

### Recommended Approach: Conditional Threaded Stdin Reader

**Why v1.3.8 failed:** The dual-thread approach mixed msvcrt AND stdin readers, causing conflicts. The fix is to use **only** stdin reader when in mintty.

**Implementation:**
1. Detect mintty via `MSYSTEM` environment variable
2. If mintty: Use `sys.stdin.buffer.read(1)` in a background thread (blocking read, non-blocking via queue)
3. If Windows console (CMD/PowerShell): Continue using msvcrt

**Why it works:**
- Addresses v1.3.6 failure (no `select` needed with threads)
- Addresses v1.3.8 failure (no mixing of readers)
- No new dependencies
- Preserves msvcrt for standard Windows users

### Alternative Rankings (Gemini Assessment)

| Priority | Approach | Assessment |
|----------|----------|------------|
| 1st | Conditional Threaded Stdin Reader | No new deps, solves specific issue |
| 2nd | pynput library | Robust fallback, but adds dependency |
| Not recommended | Fork input handling (5.5) | Too complex, race condition prone |

### Reviewer Notes

> "The bug report is comprehensive and technically sound. It correctly identifies that msvcrt on Windows interacts with the higher-level Console Input Buffer, where mintty's injection of Shift+Tab appears indistinguishable from Tab."

---

## 13. Version History of This Document

| Date | Change |
|------|--------|
| 2026-01-15 | Initial creation during debugging session |
| 2026-01-15 | Added Gemini 3 Pro review findings |
