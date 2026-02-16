# Claude Capacity Optimization System

## Overview

A Windows Task Scheduler-based system for maximizing the value of Anthropic's $100/month Max subscription by strategically timing automated Claude Code tasks to align usage windows with personal schedule.

**Location:** `C:\Users\mcwiz\Projects\`  
**Created:** 2026-01-06  
**Status:** Phase 1 (Heartbeat) - Active

---

## Motivation

### The Problem

The Claude Max subscription ($100/month) includes usage limits that reset on a rolling 5-hour window. The window timer starts when you *begin* using Claude, not at fixed times. This creates a scheduling problem:

1. **Misaligned resets** - If you hit your limit at 2 PM and walk away, the reset happens at 7 PM. But if you're not at your computer until 9 PM, you've "wasted" 2 hours of capacity.

2. **Unpredictable availability** - Without tracking, you never know exactly when your next window opens.

3. **Idle overnight hours** - 8+ hours of potential compute time goes unused while sleeping.

### The Insight

By scheduling automated tasks at strategic times, you can:
- Anchor reset windows to predictable times aligned with your daily routine
- Run heavy workloads (audits, tests, batch jobs) during idle hours
- Maximize the utility extracted from the fixed subscription cost

### Example Scenario

**Before optimization:**
- Wake at 8 AM, start using Claude at 10 AM
- Hit limit at 3 PM, walk away
- Reset at 8 PM, but you're at dinner
- Resume at 9 PM, hit limit at 2 AM
- Windows drift chaotically

**After optimization:**
- Scheduled heartbeat runs at 5 AM (anchors Window 1)
- Window 1 resets at 10 AM when you wake
- Scheduled batch job runs at 3 PM (anchors Window 2)
- Window 2 resets at 8 PM for evening work
- Windows stay aligned to your life

---

## Current Implementation

### Phase 1: Heartbeat (Active)

A minimal task that touches the Claude API hourly to provide:
- Reset window anchoring
- Usage tracking via logs
- Proof of concept for larger automation

#### Files

| File | Location | Purpose |
|------|----------|---------|
| `claude-heartbeat.ps1` | `C:\Users\mcwiz\Projects\` | PowerShell script |
| `claude-heartbeat.log` | `C:\Users\mcwiz\Projects\` | Permanent log (14-day retention) |

#### Scheduled Task

| Property | Value |
|----------|-------|
| Name | `Claude-Heartbeat` |
| Trigger | Every hour at :01 |
| Action | Run `claude-heartbeat.ps1` |
| Window | Hidden (no focus steal) |
| Condition | Only when computer is on |

---

## How to Run

### Check Status

```powershell
# See if task is registered
Get-ScheduledTask -TaskName "Claude-Heartbeat"

# See last run time and result
Get-ScheduledTaskInfo -TaskName "Claude-Heartbeat"

# View the log
cat C:\Users\mcwiz\Projects\claude-heartbeat.log

# Tail the log (watch for new entries)
Get-Content C:\Users\mcwiz\Projects\claude-heartbeat.log -Tail 10 -Wait
```

### Manual Trigger

```powershell
# Run heartbeat manually
& "C:\Users\mcwiz\Projects\claude-heartbeat.ps1"

# Or trigger the scheduled task
Start-ScheduledTask -TaskName "Claude-Heartbeat"
```

### Modify Schedule

```powershell
# Unregister existing
Unregister-ScheduledTask -TaskName "Claude-Heartbeat" -Confirm:$false

# Re-register with new schedule (e.g., every 5 hours instead of hourly)
$trigger = New-ScheduledTaskTrigger -Once -At "00:01" -RepetitionInterval (New-TimeSpan -Hours 5)
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\claude-heartbeat.ps1"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "Claude-Heartbeat" -Trigger $trigger -Action $action -Settings $settings
```

### Disable/Enable

```powershell
# Pause without deleting
Disable-ScheduledTask -TaskName "Claude-Heartbeat"

# Resume
Enable-ScheduledTask -TaskName "Claude-Heartbeat"
```

### Remove Completely

```powershell
Unregister-ScheduledTask -TaskName "Claude-Heartbeat" -Confirm:$false
Remove-Item C:\Users\mcwiz\Projects\claude-heartbeat.ps1
Remove-Item C:\Users\mcwiz\Projects\claude-heartbeat.log
```

---

## Future Work

### Phase 2: Scheduled Audits

Extend the `/audit` command with scheduling options:

```
/audit 0817                    # Run now (existing)
/audit 0817 --deep             # Run with ultrathink
/audit 0817 --delay 3          # Schedule 3 hours from now
/audit 0817 --at 13:00         # Schedule at specific time
/audit 0817 --resolve          # Run audit AND auto-fix findings
/audit --status                # Show scheduled/running audits
/audit --clean                 # Unregister completed tasks
/audit --batch 0809,0821,0819  # Queue multiple sequentially
```

#### Implementation

- `scripts/schedule-audit.ps1` - Generic audit scheduler
- `scripts/audit-status.ps1` - Show task status
- `scripts/audit-clean.ps1` - Cleanup completed tasks

### Phase 3: Daily Automation

| Task | Schedule | Purpose |
|------|----------|---------|
| `Claude-Regression` | Daily 5:00 AM | Run test suite, anchor morning window |
| `Claude-Housekeeping` | Daily 11:00 PM | Archive logs, cleanup, prep |

### Phase 4: Meta-Optimization

A housekeeping meta-task that:
- Archives audit results older than 7 days
- Unregisters completed one-time scheduled tasks
- Generates daily capacity usage report
- Identifies optimal window alignment based on usage patterns
- Preps next day's work based on audit findings

### Phase 5: /audit Command Integration

Add scheduling directly to Claude Code workflow via CLAUDE.md hooks or custom commands.

---

## Open Questions

### Capacity Impact

1. **Hourly heartbeat cost** - Running `claude -p "heartbeat"` 24x/day consumes some quota. Is this negligible or should we reduce to every 5 hours?

2. **Measurement** - How do we actually measure quota consumption? Can we query remaining capacity?

### Scheduling Strategy

3. **Optimal anchor times** - What's the ideal schedule for Marty's routine? Current thinking:
   - 5 AM: Regression (wake window at 10 AM)
   - 3 PM: Batch audits (evening window at 8 PM)
   - 11 PM: Housekeeping

4. **Weekend variance** - Should schedule differ on weekends?

### Technical

5. **Failure handling** - What if Claude API is down? Task will fail silently. Should we add retry logic or alerting?

6. **Laptop sleep** - If laptop sleeps through scheduled time, `StartWhenAvailable` runs it on wake. Is this desired behavior?

7. **VPN/Network** - Does Claude Code require network? Will tasks fail if network is down?

### Auto-Resolution

8. **Trust level** - How comfortable are we with `--resolve` auto-fixing audit findings without review?

9. **Guardrails** - What changes should require human review even in auto mode?

---

## Log Format

Each heartbeat appends a line:

```
2026-01-06 10:01:23 | heartbeat
2026-01-06 11:01:19 | heartbeat
2026-01-06 12:01:22 | heartbeat
```

Log is automatically trimmed to retain only the last 14 days of entries.

---

## Troubleshooting

### Task not running

```powershell
# Check task state
Get-ScheduledTask -TaskName "Claude-Heartbeat" | Select-Object State

# Check last result (0 = success)
(Get-ScheduledTaskInfo -TaskName "Claude-Heartbeat").LastTaskResult

# Check if claude is in PATH
where.exe claude
```

### Script won't execute manually

```powershell
# Check execution policy
Get-ExecutionPolicy -List

# Fix if needed
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Log not updating

1. Check task is enabled: `Get-ScheduledTask -TaskName "Claude-Heartbeat"`
2. Check computer was on at :01
3. Manually trigger: `Start-ScheduledTask -TaskName "Claude-Heartbeat"`
4. Check for errors: `(Get-ScheduledTaskInfo -TaskName "Claude-Heartbeat").LastTaskResult`

### Focus stealing

The task is configured with `-WindowStyle Hidden` but if you see windows popping up:

```powershell
# Verify the action arguments
(Get-ScheduledTask -TaskName "Claude-Heartbeat").Actions
```

Should show `-WindowStyle Hidden` in the Arguments.

---

## References

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)
- [PowerShell Scheduled Tasks](https://docs.microsoft.com/en-us/powershell/module/scheduledtasks/)
- [Task Scheduler Settings](https://docs.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page)

---

## History

| Date | Change |
|------|--------|
| 2026-01-06 | Created. Phase 1 heartbeat implemented and tested. |
