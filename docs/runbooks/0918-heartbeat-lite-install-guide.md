# 0918 - Claude Code Heartbeat Lite Install Guide

**Category:** Runbook / Installation Guide
**Version:** 1.0
**Last Updated:** 2026-02-06
**Platform:** Windows (PowerShell only)

---

## What This Does

Runs `claude -p "HEARTBEAT"` on a schedule to **reset your 5-hour session timer** so it doesn't expire while you're away from the keyboard. That's it. One command, on a loop.

**Cost:** ~20 tokens per ping. At hourly intervals, roughly half a cent per day.

---

## Prerequisites

| Requirement | Check Command |
|-------------|---------------|
| **Claude Code** | `claude --version` |
| **PowerShell** | Already on your machine |

That's the whole list.

---

## Install (3 Steps)

### Step 1: Create the Script

Create a file called `claude-heartbeat.ps1` somewhere convenient — your Projects folder, Documents, Desktop, wherever. It contains one line:

```powershell
claude -p "HEARTBEAT" --model haiku
```

That's the entire script.

**Optional — add logging** if you want a record of each ping:

```powershell
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logFile = Join-Path $scriptDir "claude-heartbeat.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

try {
    $result = claude -p "HEARTBEAT" --model haiku --output-format json 2>&1
    $json = ($result | Where-Object { $_ -match '^\{' } | Select-Object -First 1) | ConvertFrom-Json
    "$timestamp | heartbeat:OK | $($json.usage.input_tokens)/$($json.usage.output_tokens) tokens | `$$($json.total_cost_usd)" | Add-Content $logFile
} catch {
    "$timestamp | heartbeat:ERROR | $_" | Add-Content $logFile
}
```

The log file will appear next to the script automatically.

### Step 2: Test It

Open PowerShell and run:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\full\path\to\claude-heartbeat.ps1"
```

If using the logging version, check that the log file was created next to the script.

### Step 3: Register the Scheduled Task

Run this in an **elevated PowerShell** (right-click PowerShell, "Run as Administrator"):

```powershell
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument '-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File "C:\full\path\to\claude-heartbeat.ps1"'

$trigger = New-ScheduledTaskTrigger `
    -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 1)

Register-ScheduledTask `
    -TaskName 'Claude-Heartbeat' `
    -Action $action `
    -Trigger $trigger `
    -Description 'Hourly Claude Code heartbeat to keep session alive'
```

Verify it registered:

```powershell
Get-ScheduledTask -TaskName 'Claude-Heartbeat' | Format-Table TaskName, State
```

You should see `Ready`. Done.

---

## Managing It

```powershell
# Check status
Get-ScheduledTask -TaskName 'Claude-Heartbeat' | Get-ScheduledTaskInfo

# Disable temporarily
Disable-ScheduledTask -TaskName 'Claude-Heartbeat'

# Re-enable
Enable-ScheduledTask -TaskName 'Claude-Heartbeat'

# Remove completely
Unregister-ScheduledTask -TaskName 'Claude-Heartbeat' -Confirm:$false
```

---

## Troubleshooting

**"claude is not recognized"** — Claude Code isn't in PATH for the scheduled task context. Find the full path (`Get-Command claude | Select-Object Source`) and use that in the script instead of just `claude`.

**Task runs but no effect** — Make sure you're logged into Claude Code. Run `claude` interactively once to authenticate.

**Computer was asleep** — Windows won't fire the task while sleeping. The heartbeat will resume when you wake the machine.

---

## Agent Instructions

If you are a Claude Code agent setting this up for a user:

1. Ask the user where they want the script saved, or default to their Projects folder
2. Get the full path to `claude` via `Get-Command claude` in case it's not in the scheduled task's PATH
3. Use the full path in the script if `claude` alone doesn't resolve
4. Test the script (Step 2) before registering the scheduled task
5. The scheduled task registration requires admin elevation — tell the user they may see a UAC prompt
