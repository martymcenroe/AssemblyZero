# Claude Code Task: Implement Usage Data Scraper via Terminal Automation

## Context

Claude Code's `/status` command shows usage quota data (5-hour session %, weekly %, reset times) that is NOT available via the `-p` SDK mode or any programmatic API. GitHub issues #8412 and #5621 have requested this feature since August 2025 with no response from Anthropic.

I need to scrape this data by automating the terminal UI.

## Task Overview

1. Create a GitHub issue in my AssemblyZero repo documenting this problem and solution
2. Implement a Python script that automates Claude Code's TUI to extract usage data
3. Integrate it with my existing hourly heartbeat system
4. Test it on my Windows system

## Part 1: Create GitHub Issue

Create an issue in `mcwiz/AssemblyZero` (private repo) with:

**Title:** `feat: Implement Claude Code usage quota scraper via terminal automation`

**Body:**
```markdown
## Problem

Claude Max subscription has rolling usage windows:
- 5-hour session window (resets 5 hours after first use)
- Weekly all-models window (resets weekly)
- Weekly Sonnet-only window (separate quota)

This data is visible in Claude Code via `/status` → Usage tab:
- Current session: X% used, Resets [time]
- Current week (all models): X% used, Resets [date/time]
- Current week (Sonnet only): X% used, Resets [date/time]

**The problem:** This data is NOT available programmatically.
- `claude -p` mode doesn't support `/status`
- No HTTP API endpoint exists
- No JSON output flag for usage data
- GitHub issues #8412 and #5621 open since Aug-Sep 2025, no response

## Solution

Automate the terminal UI to scrape the data:
1. Launch Claude Code in a pseudo-terminal
2. Send `/status` command
3. Navigate to Usage tab (Tab key)
4. Capture terminal buffer
5. Parse percentages and reset times with regex
6. Exit cleanly
7. Save to log file

## Implementation

Using Python with `pexpect` (or `winpty`/`pywinpty` on Windows) to:
- Spawn Claude Code process
- Interact with TUI programmatically
- Capture ANSI-formatted output
- Strip formatting and parse data

## Files

- Script: `C:\Users\mcwiz\Projects\claude-usage-scraper.py`
- Log: `C:\Users\mcwiz\Projects\claude-usage.log`
- Integration: Called by `claude-heartbeat.ps1` hourly

## Acceptance Criteria

- [ ] Script runs on Windows 11
- [ ] Extracts all three quota percentages
- [ ] Extracts all three reset times
- [ ] Logs to structured format (JSON or CSV)
- [ ] Handles errors gracefully (Claude not installed, rate limited, etc.)
- [ ] Completes in under 30 seconds
- [ ] Can be called from PowerShell scheduled task

## References

- GitHub Issue #8412: https://github.com/anthropics/claude-code/issues/8412
- GitHub Issue #5621: https://github.com/anthropics/claude-code/issues/5621
```

**Labels:** `enhancement`, `automation`

## Part 2: Implement the Scraper

### Requirements

Create `C:\Users\mcwiz\Projects\claude-usage-scraper.py` that:

1. **Spawns Claude Code** in a pseudo-terminal
2. **Waits for ready state** (detect the welcome banner or prompt)
3. **Sends `/status`** command
4. **Sends Tab twice** to navigate to Usage tab
5. **Captures terminal output** including ANSI codes
6. **Parses the data** using regex:
   - `Current session` → percentage, reset time
   - `Current week (all models)` → percentage, reset date/time
   - `Current week (Sonnet only)` → percentage, reset date/time
7. **Exits cleanly** with Escape then `/exit` or Ctrl+C
8. **Outputs JSON** to stdout and appends to log file

### Expected Output Format

```json
{
  "timestamp": "2026-01-11T15:40:00-06:00",
  "session": {
    "percent_used": 85,
    "resets_at": "5pm",
    "resets_tz": "America/Chicago"
  },
  "weekly_all": {
    "percent_used": 92,
    "resets_at": "Jan 15, 2am",
    "resets_tz": "America/Chicago"
  },
  "weekly_sonnet": {
    "percent_used": 13,
    "resets_at": "Jan 13, 4pm",
    "resets_tz": "America/Chicago"
  },
  "status": "success"
}
```

### Technical Approach for Windows

On Windows, use one of these:

**Option A: pywinpty (recommended)**
```python
import winpty
# Spawn claude.exe in PTY
# Read/write to PTY
```

**Option B: subprocess with ConPTY**
```python
import subprocess
# Use Windows ConPTY API via ctypes or pywin32
```

**Option C: pexpect with Git Bash**
```python
import pexpect
# pexpect works on Windows if using Git Bash or WSL
child = pexpect.spawn('bash -c "claude"')
```

**Option D: pyautogui + subprocess (fallback)**
```python
import subprocess
import pyautogui
import time
# Open terminal, type commands, screenshot and OCR
# Fragile but works
```

Try Option A or C first. Fall back to D if needed.

### Handling ANSI Escape Codes

The terminal output will contain ANSI codes for colors and positioning. Strip them:

```python
import re
def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)
```

### Regex Patterns for Parsing

After stripping ANSI:

```python
# "Current session" followed by "X% used"
session_pattern = r'Current session.*?(\d+)%\s*used.*?Resets\s+([^\n]+)'

# "Current week (all models)" followed by "X% used"  
weekly_all_pattern = r'Current week \(all models\).*?(\d+)%\s*used.*?Resets\s+([^\n]+)'

# "Current week (Sonnet only)" followed by "X% used"
weekly_sonnet_pattern = r'Current week \(Sonnet only\).*?(\d+)%\s*used.*?Resets\s+([^\n]+)'
```

### Error Handling

Handle these cases:
- Claude not installed → exit with error JSON
- Claude fails to start → timeout after 10 seconds
- Rate limited (can't start session) → detect and report
- Parse failure → return raw output in error field

### Log File Format

Append to `C:\Users\mcwiz\Projects\claude-usage.log`:

```
2026-01-11 15:40:00 | session:85% resets:5pm | weekly:92% resets:Jan15 | sonnet:13% resets:Jan13
```

## Part 3: Integrate with Heartbeat

After the scraper works, update `C:\Users\mcwiz\Projects\claude-heartbeat.ps1` to:

1. Run the scraper FIRST (before the heartbeat call)
2. Log the usage data
3. Then run the normal heartbeat
4. If session > 90%, log a warning

Add to heartbeat script:
```powershell
# Get usage data via scraper
$usageJson = python "C:\Users\mcwiz\Projects\claude-usage-scraper.py" 2>&1
try {
    $usage = $usageJson | ConvertFrom-Json
    $usageLine = "session:$($usage.session.percent_used)% | weekly:$($usage.weekly_all.percent_used)% | sonnet:$($usage.weekly_sonnet.percent_used)%"
} catch {
    $usageLine = "usage:ERROR"
}

# Include in log entry
$logEntry = "$timestamp | $usageLine | heartbeat:OK | ..."
```

## Part 4: Test

1. Run the scraper manually:
```powershell
python C:\Users\mcwiz\Projects\claude-usage-scraper.py
```

2. Verify JSON output matches current `/status` values

3. Run heartbeat manually:
```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\claude-heartbeat.ps1
Get-Content C:\Users\mcwiz\Projects\claude-heartbeat.log -Tail 1
```

4. Verify log entry includes usage data

## Dependencies to Install

```powershell
pip install pywinpty --break-system-packages
# or
pip install pexpect --break-system-packages
# or  
pip install pyautogui pillow pytesseract --break-system-packages
```

## Commands to Inspect Environment

```powershell
# Check Python available
python --version

# Check Claude Code available
claude --version

# Check if pywinpty installed
python -c "import winpty; print('pywinpty OK')"

# Check if pexpect installed  
python -c "import pexpect; print('pexpect OK')"
```

## Constraints

- Must work on Windows 11
- Python 3.10+ available
- Claude Code v2.1.4 installed
- Script must complete in < 30 seconds
- Must not leave orphan Claude processes

## Deliverables

1. GitHub issue created in mcwiz/AssemblyZero
2. `claude-usage-scraper.py` working and tested
3. Updated `claude-heartbeat.ps1` with integration
4. Demonstration of successful log entry with usage data

## Start Here

First, check which PTY libraries are available:
```powershell
python -c "import winpty" 2>&1
python -c "import pexpect" 2>&1
python -c "import pty" 2>&1
```

Then create the GitHub issue using `gh issue create`.

Then implement the scraper based on which library is available.
