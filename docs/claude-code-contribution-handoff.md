# Claude Code Contribution Session - Handoff Document

## Who I Am

Marty - 62-year-old PE (Texas EE), MS in CS and EE, 29 years at AT&T as Director of Data Science & AI, 21 US patents, currently building AgentOS/Aletheia. Direct communication style, allergic to fluff.

## What I Want to Accomplish

### Primary: File a Feature Request

**Title:** Programmatic access to /status usage data for scheduled automation

**Related Issues:**
- #1886 - Make `/status` checkable from command line (11 upvotes, open)
- #8412 - Include usage data in status line JSON input (15 upvotes, open)

**My Use Case:**

I've built a Windows Task Scheduler system that runs Claude Code via `claude -p` for:
- Hourly heartbeat to anchor usage windows
- Daily deep audits at 4:30 AM
- Batch audit jobs during idle hours

This maximizes my $100/month Max subscription by:
1. Running heavy workloads during sleep hours
2. Anchoring reset windows to predictable times
3. Automating routine tasks (audits, tests)

**The Problem:**

I can schedule `claude -p "/audit 0817"` and it works beautifully. But I cannot:
- Query current 5-hour window usage %
- Query weekly usage %
- Get reset times programmatically
- Log which model served the request

The `/status` command shows all this but only works interactively.

**Proposed Solution:**

Either:
1. `claude --status --json` - CLI flag that outputs usage JSON
2. Add usage fields to statusLine JSON input (per #8412)
3. `claude usage --json` - Subcommand for usage data

**Sample Output Desired:**
```json
{
  "model": "claude-opus-4-5-20251101",
  "five_hour_window": {
    "percent_used": 4,
    "resets_at": "2026-01-07T14:00:00-06:00"
  },
  "weekly_window": {
    "percent_used": 82,
    "resets_at": "2026-01-08T02:00:00-06:00"
  },
  "sonnet_weekly": {
    "percent_used": 2,
    "resets_at": "2026-01-13T16:00:00-06:00"
  }
}
```

### Secondary: Explore Contributing Code

**Interest Areas:**
1. Plugin that logs model/session data for scheduled jobs
2. Any `good first issue` related to CLI, usage tracking, or scheduling
3. Improvements to `-p` (print) mode capabilities

**My Skills:**
- Python, JavaScript/TypeScript
- AWS (Lambda, Bedrock, DynamoDB)
- CLI tooling, automation
- 21 patents worth of creative problem-solving

---

## Background Context

### The Capacity Optimization System I Built

**Files created:**
- `C:\Users\mcwiz\Projects\claude-heartbeat.ps1` - Hourly heartbeat script
- `C:\Users\mcwiz\Projects\claude-heartbeat.log` - 14-day rolling log
- `C:\Users\mcwiz\Projects\claude-daily-audit.ps1` - 4:30 AM deep audit
- `C:\Users\mcwiz\Projects\claude-capacity-optimization.md` - Full documentation

**Scheduled Tasks:**
- `Claude-Heartbeat` - Every hour at :01
- `Claude-DailyAudit` - Daily at 4:30 AM

**Key Discovery:**

`claude -p "prompt"` works perfectly for automation:
```powershell
$trigger = New-ScheduledTaskTrigger -Daily -At "04:30"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\claude-daily-audit.ps1"
Register-ScheduledTask -TaskName "Claude-DailyAudit" -Trigger $trigger -Action $action
```

This runs audits, saves output to markdown, works great. The only missing piece is programmatic usage data.

### Research Done

From GitHub issues:
- No HTTP API endpoint for usage data
- `claude usage` has no JSON output flag
- No cached usage file accessible
- Usage data only available via interactive `/usage` or `/status`
- Feature requests exist but not implemented

### Why This Matters

For Max subscribers doing serious automation:
1. Know when to schedule heavy jobs (after reset)
2. Track usage patterns over time
3. Avoid hitting limits during critical work
4. Build dashboards/alerts for team usage

---

## Action Items for Claude Code

### 1. Fork anthropics/claude-code

```bash
gh repo fork anthropics/claude-code --clone
cd claude-code
```

### 2. File the Feature Request

Use the issue template. Reference:
- #1886 (CLI status access)
- #8412 (statusLine JSON)
- My specific use case above

### 3. Explore the Codebase

Look for:
- Where `/status` gets its data
- The statusLine implementation
- How `-p` mode differs from interactive
- Plugin architecture for potential workaround

### 4. Check for Good First Issues

```bash
gh issue list --label "good first issue" --state open
gh issue list --label "help wanted" --state open
```

### 5. Consider a Plugin Approach

If core changes are too complex, a plugin could:
- Hook into session start/end
- Log available metadata to file
- Provide `/usage-log` command
- Work around current limitations

---

## My Other Open Issues

I may have other issues open on claude-code - check under my activity. Cross-reference to avoid duplicates.

---

## Communication Style

- Direct, no hedging
- Short declarative sentences
- Show me code, not explanations
- I'll ask if I need more detail
- Don't ask permission, just do it

---

## End Goal

Get the feature request filed cleanly, explore whether I can contribute a fix or plugin, and establish myself as a contributor to this high-visibility project.

Let's go.
